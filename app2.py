import requests
from bs4 import BeautifulSoup
import json
import re
import pickle
import pandas as pd
import os
try:
    import shap
except Exception:
    shap = None
import socket
import ssl
import ipaddress
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from groq import Groq
except Exception:
    Groq = None

if load_dotenv is not None:
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ---------- Load LGBM Model Package ----------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "phishing_lgbm.pkl")
with open(MODEL_PATH, "rb") as f:
    package = pickle.load(f)

ml_model = package["model"]
scaler = package["scaler"]
features_list = package["features"]
lgbm_model = ml_model.named_estimators_["lgbm"]

LLM_PROVIDER = "groq"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _extract_json_payload(response_text):
    if not response_text:
        return None
    json_match = re.search(r'{.*}', response_text, re.DOTALL)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        return None


def get_llm_status():
    return {
        "provider": LLM_PROVIDER,
        "model": GROQ_MODEL,
        "groq_sdk_available": Groq is not None,
        "api_key_configured": bool(os.getenv("GROQ_API_KEY")),
    }


def _extract_domain(url):
    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").lower() or None
    except Exception:
        return None


def _first_non_null(values):
    for value in values:
        if value:
            return value
    return None


def _parse_rdap_date(value):
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _score_registrar(registrar_name):
    if not registrar_name:
        return "unknown"

    normalized = registrar_name.lower()
    trusted_keywords = [
        "markmonitor",
        "godaddy",
        "namecheap",
        "cloudflare",
        "google",
        "amazon",
        "tucows",
        "enom",
    ]
    risky_keywords = ["unknown", "privacy", "hidden", "offshore", "cheap"]

    if any(k in normalized for k in trusted_keywords):
        return "trusted"
    if any(k in normalized for k in risky_keywords):
        return "risky"
    return "neutral"


def _fetch_domain_profile(domain):
    profile = {
        "domain": domain,
        "created_at": None,
        "age_days": None,
        "registrar": None,
        "registrar_reputation": "unknown",
        "source": "rdap",
    }
    if not domain:
        return profile

    rdap_endpoints = [
        f"https://rdap.org/domain/{domain}",
        f"https://rdap.verisign.com/com/v1/domain/{domain}",
    ]
    rdap_payload = None
    for endpoint in rdap_endpoints:
        try:
            resp = requests.get(endpoint, timeout=8)
            if resp.ok:
                rdap_payload = resp.json()
                break
        except Exception:
            continue

    if not rdap_payload:
        return profile

    events = rdap_payload.get("events") or []
    creation_candidates = [
        e.get("eventDate")
        for e in events
        if str(e.get("eventAction", "")).lower() in ("registration", "registered")
    ]
    created_at = _parse_rdap_date(_first_non_null(creation_candidates))
    if created_at is None:
        created_at = _parse_rdap_date(
            _first_non_null([
                rdap_payload.get("registrationDate"),
                rdap_payload.get("created"),
            ])
        )

    registrar = None
    entities = rdap_payload.get("entities") or []
    for entity in entities:
        roles = [str(r).lower() for r in (entity.get("roles") or [])]
        if "registrar" not in roles:
            continue
        vcard = entity.get("vcardArray")
        if isinstance(vcard, list) and len(vcard) > 1:
            for item in vcard[1]:
                if len(item) >= 4 and item[0] == "fn":
                    registrar = item[3]
                    break
        if registrar:
            break

    if created_at:
        age_days = max(0, (datetime.now(timezone.utc) - created_at).days)
        profile["created_at"] = created_at.isoformat()
        profile["age_days"] = int(age_days)

    if registrar:
        profile["registrar"] = registrar
        profile["registrar_reputation"] = _score_registrar(registrar)

    return profile


def _fetch_ssl_profile(domain):
    profile = {
        "valid": None,
        "issuer": None,
        "expires_at": None,
        "days_to_expiry": None,
    }
    if not domain:
        return profile

    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=6) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
        if not cert:
            return profile

        profile["valid"] = True
        issuer = cert.get("issuer") or []
        issuer_flat = []
        for row in issuer:
            for key, value in row:
                issuer_flat.append(f"{key}={value}")
        profile["issuer"] = ", ".join(issuer_flat) if issuer_flat else None

        not_after = cert.get("notAfter")
        if not_after:
            expiry_ts = ssl.cert_time_to_seconds(not_after)
            expiry_dt = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
            profile["expires_at"] = expiry_dt.isoformat()
            profile["days_to_expiry"] = int((expiry_dt - datetime.now(timezone.utc)).days)
    except Exception:
        profile["valid"] = False

    return profile


def _fetch_network_profile(domain):
    profile = {
        "ip": None,
        "ip_reputation": "unknown",
        "asn": None,
        "asn_reputation": "unknown",
    }
    if not domain:
        return profile

    try:
        ip = socket.gethostbyname(domain)
        profile["ip"] = ip
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
            profile["ip_reputation"] = "risky"
        else:
            profile["ip_reputation"] = "neutral"
    except Exception:
        return profile

    try:
        resp = requests.get(
            f"http://ip-api.com/json/{profile['ip']}?fields=status,as,hosting,proxy,mobile",
            timeout=4,
        )
        if resp.ok:
            payload = resp.json()
            if payload.get("status") == "success":
                profile["asn"] = payload.get("as")
                if payload.get("proxy") or payload.get("hosting"):
                    profile["asn_reputation"] = "risky"
                else:
                    profile["asn_reputation"] = "neutral"
    except Exception:
        pass

    return profile


def _detect_sensitive_fields(soup):
    inputs = soup.find_all("input") if soup else []
    text_blob = (soup.get_text(" ", strip=True).lower() if soup else "")

    password_fields = 0
    payment_indicators = 0
    payment_tokens = [
        "card", "cvv", "expiry", "exp", "iban", "upi", "paypal",
        "routing", "swift", "ifsc", "account number", "debit", "credit",
    ]

    for field in inputs:
        field_type = str(field.get("type", "")).lower()
        if field_type == "password":
            password_fields += 1

        hay = " ".join([
            str(field.get("name", "")),
            str(field.get("id", "")),
            str(field.get("placeholder", "")),
            str(field.get("autocomplete", "")),
        ]).lower()
        if any(token in hay for token in payment_tokens):
            payment_indicators += 1

    if any(token in text_blob for token in payment_tokens):
        payment_indicators += 1

    return {
        "has_password_field": password_fields > 0,
        "password_field_count": password_fields,
        "has_payment_indicator": payment_indicators > 0,
        "payment_indicator_count": payment_indicators,
    }


def _build_urgency(phishing_prob, llm_risk, sensitive_fields, risk_signals):
    reasons = []
    level_rank = 0  # 0=low, 1=medium, 2=high, 3=critical

    if phishing_prob >= 0.8:
        level_rank = max(level_rank, 2)
        reasons.append("ML score is strongly phishing-leaning")
    elif phishing_prob >= 0.5:
        level_rank = max(level_rank, 1)
        reasons.append("ML score indicates suspicious risk")

    llm_risk_norm = str(llm_risk or "").lower()
    if "high" in llm_risk_norm or llm_risk_norm == "phishing":
        level_rank = max(level_rank, 2)
        reasons.append("LLM flagged high-risk language")
    elif "medium" in llm_risk_norm or llm_risk_norm == "suspicious":
        level_rank = max(level_rank, 1)
        reasons.append("LLM flagged suspicious language")

    redirects = int((risk_signals.get("redirect") or {}).get("depth") or 0)
    if redirects >= 4:
        level_rank = max(level_rank, 2)
        reasons.append(f"High redirect chain depth detected ({redirects})")

    if (risk_signals.get("ssl") or {}).get("valid") is False:
        level_rank = max(level_rank, 2)
        reasons.append("SSL certificate validation failed")

    domain_age = (risk_signals.get("domain") or {}).get("age_days")
    if isinstance(domain_age, int) and domain_age < 30:
        level_rank = max(level_rank, 2)
        reasons.append("Domain appears recently registered")

    network_profile = risk_signals.get("network") or {}
    if network_profile.get("ip_reputation") == "risky" or network_profile.get("asn_reputation") == "risky":
        level_rank = max(level_rank, 2)
        reasons.append("Network reputation appears risky")

    if sensitive_fields.get("has_password_field") or sensitive_fields.get("has_payment_indicator"):
        reasons.append("Sensitive credential or payment fields detected")
        if level_rank >= 2:
            level_rank = 3
        else:
            level_rank = max(level_rank, 1)

    levels = ["low", "medium", "high", "critical"]
    unique_reasons = []
    for reason in reasons:
        if reason not in unique_reasons:
            unique_reasons.append(reason)

    return {
        "level": levels[level_rank],
        "reasons": unique_reasons,
    }

# ---------- Feature Extractor ----------
def extract_features(url):
    feats = {}
    feats['length_url'] = len(url)
    feats['length_hostname'] = len(re.findall(r'://([^/]+)/?', url)[0]) if "://" in url else len(url)
    feats['ip'] = 1 if re.match(r'^\d+\.\d+\.\d+\.\d+$', url) else 0
    feats['nb_dots'] = url.count('.')
    feats['nb_hyphens'] = url.count('-')
    feats['nb_at'] = url.count('@')
    feats['nb_qm'] = url.count('?')
    feats['nb_and'] = url.count('&')
    feats['nb_or'] = url.count('|')
    feats['nb_eq'] = url.count('=')
    feats['nb_underscore'] = url.count('_')
    feats['nb_tilde'] = url.count('~')
    feats['nb_percent'] = url.count('%')
    feats['nb_slash'] = url.count('/')
    feats['nb_star'] = url.count('*')
    feats['nb_colon'] = url.count(':')
    feats['nb_comma'] = url.count(',')
    feats['nb_semicolumn'] = url.count(';')
    feats['nb_dollar'] = url.count('$')
    feats['nb_space'] = url.count(' ')
    feats['nb_www'] = url.count('www')
    feats['nb_com'] = url.count('.com')
    feats['nb_dslash'] = url.count('//')
    feats['http_in_path'] = 1 if "http" in url[url.find("://")+3:] else 0
    feats['https_token'] = 1 if "https" in url else 0
    feats['ratio_digits_url'] = sum(c.isdigit() for c in url) / len(url)
    feats['ratio_digits_host'] = 0.0
    feats['punycode'] = 1 if "xn--" in url else 0
    feats['shortening_service'] = 1 if re.search(r'bit\.ly|goo\.gl|tinyurl|ow\.ly', url) else 0
    feats['path_extension'] = 1 if re.search(r'\.[a-zA-Z0-9]{2,4}(/|$)', url) else 0
    feats['phish_hints'] = 1 if re.search(r'login|verify|bank|account|update|secure', url.lower()) else 0
    feats['domain_in_brand'] = 0
    feats['brand_in_subdomain'] = 0
    feats['brand_in_path'] = 0
    feats['suspecious_tld'] = 1 if re.search(r'\.(zip|review|country|kim|cricket|science|work|party|info)$', url) else 0
    return feats

# ---------- SHAP Explainability Formatter ----------
def format_shap_explanations(features_list, shap_array, prediction_type):
    explanations = []
    for feat, val in zip(features_list, shap_array[0]):
        if abs(val) < 0.2:  # ignore weak contributions
            continue
        direction = "phishing" if val > 0 else "legitimate"
        if prediction_type == "legitimate" and val < 0:
            text = f"{feat.replace('_',' ')} pushes towards legitimate."
            explanations.append(text)
        elif prediction_type == "phishing" and val > 0:
            text = f"{feat.replace('_',' ')} pushes towards phishing."
            explanations.append(text)
    return explanations

# ---------- Extract Main Content ----------
def extract_main_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    for element in soup(["script", "style", "meta", "link", "header", "footer", "nav", "aside", "noscript"]):
        element.decompose()
    text = soup.get_text(" ", strip=True)
    return text

# ---------- LLM Analysis (Groq) ----------
def analyze_with_groq(content, model_name=None, return_error=False):
    system_prompt = """You are an expert cybersecurity analyst. 
Your task is to analyze the content of a website and determine if it is a scam, phishing attempt, or otherwise malicious.
Respond STRICTLY in this JSON format:

{
  "verdict": "phishing" or "legitimate",
  "risk_level": "High Risk" or "Medium Risk" or "Low Risk",
  "reasons": ["list of brief reasons"],
  "evidence_snippets": ["list of concrete snippets found in the text"]
}
"""
    model_name = model_name or GROQ_MODEL
    try:
        if Groq is None:
            raise RuntimeError("groq SDK is not installed. Install with: pip install groq")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")

        user_message = f"Analyze this website content:\n\n{content}"
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message}
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        response_text = (response.choices[0].message.content or "").strip()
        parsed = _extract_json_payload(response_text)
        if return_error:
            if parsed is None:
                return None, "Groq response did not contain valid JSON"
            return parsed, None
        return parsed
    except Exception as e:
        print(f"❌ Error with Groq: {e}")
        if return_error:
            return None, str(e)
        return None


# Backward-compatible wrapper for any existing callers.
def analyze_with_ollama(content, model_name="mistral"):
    resolved_model = GROQ_MODEL if model_name == "mistral" else model_name
    return analyze_with_groq(content, model_name=resolved_model)

# ---------- Hybrid Classification ----------
def classify_content(url):
    # Step 1: Fetch page
    headers = {'User-Agent': 'Mozilla/5.0'}
    domain = _extract_domain(url)
    risk_signals = {
        "domain": _fetch_domain_profile(domain),
        "ssl": _fetch_ssl_profile(domain),
        "network": _fetch_network_profile(domain),
        "redirect": {"depth": 0},
        "sensitive_fields": {
            "has_password_field": False,
            "password_field_count": 0,
            "has_payment_indicator": False,
            "payment_indicator_count": 0,
        },
    }

    try:
        print(f"[DEBUG] classify_content: fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text
        risk_signals["redirect"] = {"depth": len(response.history or [])}
        print(f"[DEBUG] fetch OK — {len(html_content)} chars")
    except requests.exceptions.SSLError:
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            html_content = response.text
            risk_signals["redirect"] = {"depth": len(response.history or [])}
            print(f"[DEBUG] fetch OK (insecure TLS fallback) — {len(html_content)} chars")
        except Exception as e:
            print(f"[ERROR] Failed to fetch URL: {e}")
            return {"error": f"Failed to fetch URL: {e}"}
    except Exception as e:
        print(f"[ERROR] Failed to fetch URL: {e}")
        return {"error": f"Failed to fetch URL: {e}"}

    # Step 2: Extract content
    soup = BeautifulSoup(html_content, 'html.parser')
    main_text = extract_main_content(html_content)
    risk_signals["sensitive_fields"] = _detect_sensitive_fields(soup)
    max_chars = 4000
    text_for_llm = (url + " " + main_text)[:max_chars]

    print(f"📡 Feeding {len(text_for_llm)} characters to LLM (max={max_chars})\n")

    # Step 3: ML prediction
    feats = extract_features(url)
    X_input = pd.DataFrame([feats]).reindex(columns=features_list, fill_value=0)
    X_scaled = scaler.transform(X_input)

    # Raw probability from model = phishing probability
    try:
        probs = ml_model.predict_proba(X_scaled)[0]
        # Determine which column corresponds to a phishing label.
        phishing_index = None
        classes = getattr(ml_model, 'classes_', None)
        if classes is not None:
            # look for common label encodings
            for candidate in ('phishing', '1', 1, True):
                try:
                    phishing_index = list(classes).index(candidate)
                    break
                except ValueError:
                    continue
        # fallback to index 1 if available
        if phishing_index is None:
            phishing_index = 1 if len(probs) > 1 else 0
        phishing_prob = float(probs[phishing_index])
    except Exception as e:
        print(f"[ERROR] ML model prediction failed: {e}")
        return {"error": f"ML model prediction failed: {e}"}

    # Convert to legitimacy confidence
    legitimacy_conf = 1 - phishing_prob

    ml_pred = "phishing" if phishing_prob > 0.5 else "legitimate"

    print(f"[DEBUG] ML phishing_prob={phishing_prob:.4f}, legitimacy_conf={legitimacy_conf:.4f}, ml_pred={ml_pred}")

    # SHAP explanations
    if shap is None:
        ml_explanations = []
    else:
        try:
            explainer = shap.TreeExplainer(lgbm_model)
            shap_values = explainer.shap_values(X_scaled)
            shap_array = shap_values[1] if isinstance(shap_values, list) else shap_values
            ml_explanations = format_shap_explanations(features_list, shap_array, ml_pred)
        except Exception as e:
            print(f"[WARN] SHAP explanation failed: {e}")
            ml_explanations = []

    # Step 4: LLM prediction (with fallback)
    llm_result = None
    llm_error = None
    llm_status = "fallback"
    try:
        llm_result, llm_error = analyze_with_groq(text_for_llm, return_error=True)
        print(f"[DEBUG] groq result: {llm_result}")
    except Exception as e:
        print(f"[WARN] Groq analysis failed or not available: {e}")
        llm_result = None
        llm_error = str(e)

    # Fallback heuristic if LLM unavailable or returns None
    if not llm_result:
        if not llm_error:
            llm_error = "Groq response unavailable; heuristic fallback used"
        heur = re.search(r'login|verify|account|password|bank|secure|update|confirm|sign in|credit card|ssn', main_text, re.IGNORECASE)
        if heur:
            llm_label = "phishing"
            llm_risk = "suspicious"
            llm_reasons = ["suspicious phishing keywords found in page text"]
            evidence_snippets = [heur.group(0)]
            print(f"[DEBUG] LLM fallback => phishing due to keyword: {heur.group(0)}")
        else:
            llm_label = "legitimate"
            llm_risk = "safe"
            llm_reasons = ["no obvious phishing language detected"]
            evidence_snippets = []
            print(f"[DEBUG] LLM fallback => legitimate (no phishing keywords)")
    else:
        llm_status = "live"
        llm_label = llm_result.get("verdict", "unknown")
        llm_risk = llm_result.get("risk_level", "suspicious")
        llm_reasons = llm_result.get("reasons", [])
        evidence_snippets = llm_result.get("evidence_snippets", [])

    # Step 5: Ensemble decision (optional — only used inside this function)
    # Ensure llm_label and ml_explanations exist and are consistent types
    if not isinstance(ml_explanations, list):
        ml_explanations = []
    if not isinstance(llm_label, str):
        llm_label = str(llm_label) if llm_label is not None else "unknown"
    if not isinstance(llm_risk, str):
        llm_risk = str(llm_risk) if llm_risk is not None else "suspicious"

    llm_score = 1.0 if llm_label == "phishing" else 0.0 if llm_label == "legitimate" else 0.5
    if llm_risk == "suspicious" and 0.15 < phishing_prob < 0.5:
        final = "phishing"
    elif phishing_prob >= 0.85:
        final = "phishing"
    elif phishing_prob <= 0.15:
        final = "legitimate"
    else:
        combined_score = (0.6 * phishing_prob) + (0.4 * llm_score)
        final = "phishing" if combined_score >= 0.5 else "legitimate"

    print(f"[DEBUG] Ensemble: final={final}, combined_score approx={(0.6*phishing_prob)+(0.4*llm_score):.4f}")

    urgency = _build_urgency(phishing_prob, llm_risk, risk_signals["sensitive_fields"], risk_signals)
    if urgency["level"] in ("high", "critical") and final == "legitimate":
        final = "phishing"

    # Return all keys with safe defaults for frontend
    return {
        "url": url,
        "final_verdict": final,
        "ml_confidence": float(round(max(0.0, min(1.0, legitimacy_conf)), 3)),
        "ml_prediction": ml_pred or "unknown",
        "ml_explanations": ml_explanations or [],
        "llm_prediction": llm_label or "unknown",
        "llm_risk_level": llm_risk or "suspicious",
        "llm_status": llm_status,
        "llm_error": llm_error,
        "llm_reasons": llm_reasons or [],
        "evidence_snippets": evidence_snippets or [],
        "risk_signals": risk_signals,
        "urgency": urgency,
        "watch_profile": {
            "domain": domain,
            "brand_hint": domain.split('.')[0] if domain else None,
        },
    }


def classify_url_fast(url):
    """Fast ML-only URL scoring for real-time clients (e.g., browser badge)."""
    try:
        feats = extract_features(url)
        X_input = pd.DataFrame([feats]).reindex(columns=features_list, fill_value=0)
        X_scaled = scaler.transform(X_input)

        probs = ml_model.predict_proba(X_scaled)[0]
        phishing_index = None
        classes = getattr(ml_model, 'classes_', None)
        if classes is not None:
            for candidate in ('phishing', '1', 1, True):
                try:
                    phishing_index = list(classes).index(candidate)
                    break
                except ValueError:
                    continue
        if phishing_index is None:
            phishing_index = 1 if len(probs) > 1 else 0

        phishing_prob = float(probs[phishing_index])
        legitimacy_score = float(max(0.0, min(1.0, 1.0 - phishing_prob)))

        if phishing_prob >= 0.7:
            risk_level = "high"
        elif phishing_prob >= 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "url": url,
            "mode": "ml_fast",
            "phishing_probability": round(phishing_prob, 4),
            "legitimacy_score": round(legitimacy_score, 4),
            "risk_level": risk_level,
            "verdict": "phishing" if phishing_prob >= 0.5 else "legitimate",
        }
    except Exception as e:
        return {"error": f"Fast URL classification failed: {e}"}



# ---------- Main ----------
def main():
    print("🌐 Website Scam & Phishing Analyzer")
    print("----------------------------------------")
    website_url = input("Please enter the full URL to analyze: ").strip()
    result = classify_content(website_url)

    if "error" in result:
        print(f"❌ {result['error']}")
        return

    print("="*60)
    print(f"📋 URL: {result['url']}")

    # 🔹 Module 1: Just show raw predictions, no "final verdict"
    print("\n🔍 Module 1: Phishing Detection Analysis")
    print(f"✅ ML Prediction: {result['ml_prediction']} (phishing-prob={result['ml_confidence']})")
    print(f"🤖 LLM Prediction: {result['llm_prediction']} (risk={result['llm_risk_level']})")

    print("\n🤖 AI's Contextual Analysis:")

    if result['ml_prediction'] == "phishing":
        print("\nPhishing Indicators (from ML):")
        for explanation in result['ml_explanations']:
            print(f" • {explanation}")
    else:
        print("\nLegitimate Indicators (from ML):")
        for explanation in result['ml_explanations']:
            print(f" • {explanation}")

    if result['llm_prediction'] == "phishing":
        print("\nLLM Evidence Snippets:")
        for snippet in result['evidence_snippets']:
            print(f" • {snippet}")
    else:
        print("\nLLM Reasons for Legitimacy:")
        for reason in result['llm_reasons']:
            print(f" • {reason}")

    print("="*60)
    print("ℹ️ Final Combined Verdict will be shown in the last section.")