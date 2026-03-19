from PIL import Image
import imagehash, cv2, numpy as np, pytesseract, re, os, time, base64
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
except Exception:
    webdriver = None
    Options = None
from rapidfuzz import process
from urllib.parse import urlparse
import socket
import requests
import shutil
import tempfile
import hashlib

# ---------- Config ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # current file location
BRANDS_FOLDER = os.path.join(BASE_DIR, "Brands")


def _resolve_user_folder():
    env_folder = os.getenv("USER_FOLDER")
    if env_folder:
        return env_folder
    # Vercel and similar serverless runtimes provide writable temp storage only.
    return os.path.join(tempfile.gettempdir(), "spot-the-fake-user")


USER_FOLDER = _resolve_user_folder()


os.makedirs(BRANDS_FOLDER, exist_ok=True)
os.makedirs(USER_FOLDER,   exist_ok=True)


def _configure_tesseract_if_available():
    """Best-effort Tesseract discovery so OCR works even when PATH is not configured."""
    configured_cmd = os.getenv("TESSERACT_CMD")
    candidates = [
        configured_cmd,
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for cmd in candidates:
        if cmd and os.path.exists(cmd):
            pytesseract.pytesseract.tesseract_cmd = cmd
            return True
    return False


OCR_AVAILABLE = _configure_tesseract_if_available()
_CLOUDINARY_REF_URL_CACHE = {}


def _cloudinary_config():
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not cloud_name or not api_key or not api_secret:
        return None
    return {
        "cloud_name": cloud_name,
        "api_key": api_key,
        "api_secret": api_secret,
    }


def _upload_to_cloudinary(local_path, folder, public_id=None, overwrite=True):
    cfg = _cloudinary_config()
    if not cfg or not local_path or not os.path.exists(local_path):
        return None

    timestamp = str(int(time.time()))
    params_to_sign = {
        "folder": folder,
        "timestamp": timestamp,
        "overwrite": str(bool(overwrite)).lower(),
    }
    if public_id:
        params_to_sign["public_id"] = public_id

    sign_base = "&".join(f"{k}={params_to_sign[k]}" for k in sorted(params_to_sign))
    signature = hashlib.sha1((sign_base + cfg["api_secret"]).encode("utf-8")).hexdigest()

    upload_url = f"https://api.cloudinary.com/v1_1/{cfg['cloud_name']}/image/upload"
    try:
        with open(local_path, "rb") as f:
            files = {"file": f}
            data = {
                "api_key": cfg["api_key"],
                "timestamp": timestamp,
                "folder": folder,
                "overwrite": str(bool(overwrite)).lower(),
                "signature": signature,
            }
            if public_id:
                data["public_id"] = public_id

            resp = requests.post(upload_url, files=files, data=data, timeout=20)
        if not resp.ok:
            print(f"[WARN] Cloudinary upload failed ({resp.status_code}): {resp.text[:160]}")
            return None

        payload = resp.json()
        return payload.get("secure_url") or payload.get("url")
    except Exception as e:
        print(f"[WARN] Cloudinary upload exception: {e}")
        return None


def _get_reference_image_url(ref_img_path):
    if not ref_img_path:
        return None
    if ref_img_path in _CLOUDINARY_REF_URL_CACHE:
        return _CLOUDINARY_REF_URL_CACHE[ref_img_path]

    ref_name = os.path.splitext(os.path.basename(ref_img_path))[0]
    secure_url = _upload_to_cloudinary(
        ref_img_path,
        folder="spot-the-fake/reference",
        public_id=f"ref_{ref_name}",
        overwrite=False,
    )
    if secure_url:
        _CLOUDINARY_REF_URL_CACHE[ref_img_path] = secure_url
    return secure_url

# ---------- URL Utilities ----------
def normalize_url(url: str) -> str:
    """Ensure scheme; return normalized URL string."""
    if not re.match(r'^[a-zA-Z]+://', url or ''):
        url = "https://" + url.strip()
    return url

def is_file_input(url_or_path: str) -> bool:
    """True if input is a local image (path) or file:// URL."""
    if str(url_or_path).lower().startswith("file://"):
        return True
    # If it looks like a path and exists, treat as image
    return os.path.exists(url_or_path)


def extract_domain(url: str):
    """Robust domain extraction (ignores file://)"""
    if is_file_input(url):
        return None
    try:
        p = urlparse(url)
        host = p.hostname or ""
        if not host:
            return None

        host = host.lower()

        # Remove www prefix if present
        if host.startswith('www.'):
            host = host[4:]

        # Split into parts and get the main domain name
        parts = host.split('.')
        if len(parts) >= 2:
            # Take the first part (brand name) for most domains
            # e.g., "example" from "example.com" or "paypal" from "paypal.com"
            return parts[0] if parts[0] else None
        elif len(parts) == 1:
            # Single part domain (edge case)
            return parts[0] if parts[0] else None
        else:
            return None

    except Exception:
        return None

def check_dns(url: str, timeout=3) -> bool:
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(host)
        return True
    except Exception:
        return False

def check_http(url: str, timeout=6) -> bool:
    """Lightweight HTTP reachability check; ignores TLS errors."""
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True, verify=False)
        return 200 <= r.status_code < 400
    except Exception:
        return False

# ---------- Selenium Screenshot ----------
def capture_viewport_screenshot(url, save_path, width=1280, height=720, retries=1):
    """Viewport screenshot with timeouts + retries. Returns save_path or None."""
    if webdriver is None or Options is None:
        print("[WARN] Selenium not available in this runtime; screenshot capture skipped.")
        return None

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-insecure-localhost")
    options.add_argument(f"--window-size={width},{height}")
    driver = None

    for attempt in range(retries + 1):
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(12)
            driver.get(url)
            # wait a bit for layout
            time.sleep(2.5)
            screenshot = driver.get_screenshot_as_base64()
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(screenshot))
            return save_path
        except Exception as e:
            if attempt >= retries:
                print(f"❌ Error capturing screenshot (attempt {attempt+1}): {e}")
                return None
            time.sleep(1.5)  # brief backoff then retry
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            driver = None

# ---------- Image Normalization ----------
def normalize_image(img_path, target_size=(1280, 720), bg_color=(255,255,255)):
    try:
        img = Image.open(img_path).convert("RGB")
    except Exception:
        # If PIL fails, return a blank canvas to avoid crashes
        return Image.new("RGB", target_size, bg_color)

    img.thumbnail(target_size, Image.Resampling.LANCZOS)
    background = Image.new("RGB", target_size, bg_color)
    offset = ((target_size[0] - img.width) // 2,
              (target_size[1] - img.height) // 2)
    background.paste(img, offset)
    return background

# ---------- OCR Preprocessing ----------
def preprocess_for_ocr(img_path):
    try:
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        # gentle denoise and binarization
        img = cv2.medianBlur(img, 3)
        img = cv2.threshold(img, 0, 255, cv2.THRESH_OTSU | cv2.THRESH_BINARY)[1]
        return img
    except Exception:
        return None

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9 ]', ' ', text).lower().strip()


def _clamp01(value):
    try:
        return float(max(0.0, min(1.0, value)))
    except Exception:
        return 0.0


def _normalize_color_score(score):
    # Histogram correlation is usually in [-1, 1]. Normalize safely to [0, 1].
    try:
        s = float(score)
    except Exception:
        return 0.0
    if -1.0 <= s <= 1.0:
        return _clamp01((s + 1.0) / 2.0)
    return _clamp01(s)


def extract_text_from_image(img_path):
    """Run OCR with multiple preprocessing variants for better text capture."""
    if not OCR_AVAILABLE:
        return ""

    try:
        base = np.array(normalize_image(img_path).convert("RGB"))
        gray = cv2.cvtColor(base, cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        variants = [
            gray,
            cv2.GaussianBlur(gray, (3, 3), 0),
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1],
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1],
            cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                7,
            ),
        ]

        ocr_config = "--oem 3 --psm 6"
        extracted_chunks = []
        for variant in variants:
            try:
                text = pytesseract.image_to_string(variant, config=ocr_config)
            except Exception:
                continue

            cleaned = clean_text(text)
            if len(cleaned) >= 3:
                extracted_chunks.append(cleaned)

        if not extracted_chunks:
            return ""

        # Prefer the richest extraction to preserve most useful tokens.
        return max(extracted_chunks, key=len)
    except Exception:
        return ""


def structure_similarity(img1_path, img2_path):
    """Compare coarse page layout/structure using normalized template correlation."""
    try:
        img1 = np.array(normalize_image(img1_path).convert("RGB"))
        img2 = np.array(normalize_image(img2_path).convert("RGB"))

        g1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
        g2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
        g1 = cv2.resize(g1, (640, 360), interpolation=cv2.INTER_AREA)
        g2 = cv2.resize(g2, (640, 360), interpolation=cv2.INTER_AREA)

        e1 = cv2.Canny(g1, 60, 160)
        e2 = cv2.Canny(g2, 60, 160)
        corr = cv2.matchTemplate(e1, e2, cv2.TM_CCOEFF_NORMED)[0][0]
        return _clamp01((float(corr) + 1.0) / 2.0)
    except Exception:
        return 0.0


def _compute_similarity_confidence(details):
    ocr = details.get("ocr") or {}
    txt_len_ref = int(ocr.get("ref_text_len") or 0)
    txt_len_target = int(ocr.get("target_text_len") or 0)
    ocr_available = bool(ocr.get("ocr_available"))

    conf = 0.75
    if not ocr_available:
        conf -= 0.2
    elif txt_len_ref < 20 or txt_len_target < 20:
        conf -= 0.1

    spread = np.std([
        details.get("image", 0.0),
        details.get("color", 0.0),
        details.get("text", 0.0),
        details.get("structure", 0.0),
    ])
    if spread > 0.35:
        conf -= 0.1

    return _clamp01(conf)


def _build_similarity_assessment(score, details, brand_name=None, domain=None, domain_alignment=None):
    risk_level = "low"
    status = "low_resemblance"
    headline = "Low resemblance to brand references"
    summary = "Visual profile does not closely match known brand assets."
    recommendations = [
        "Cross-check the URL and certificate details before sharing sensitive data.",
    ]
    reasons = []

    if score >= 0.88:
        reasons.append("Very high overall visual similarity")
        if domain_alignment is False:
            risk_level = "critical"
            status = "likely_impersonation"
            headline = "Very high similarity with brand-domain mismatch"
            summary = "The page strongly resembles a known brand, but the domain context does not align."
            recommendations = [
                "Treat as likely phishing impersonation.",
                "Do not enter credentials or payment details.",
                "Open the official site directly from your bookmarks or search.",
            ]
            reasons.append("Brand mismatch against current domain")
        else:
            risk_level = "medium"
            status = "high_resemblance"
            headline = "Very high brand resemblance"
            summary = "The screenshot is highly similar to a known brand reference."
            recommendations = [
                "Verify the exact hostname to rule out lookalike domains.",
                "Use multi-factor authentication for sensitive accounts.",
            ]
    elif score >= 0.70:
        risk_level = "high" if domain_alignment is False else "medium"
        status = "possible_impersonation" if domain_alignment is False else "moderate_resemblance"
        headline = "High resemblance detected"
        summary = "The page shares strong visual elements with a known brand."
        recommendations = [
            "Validate domain spelling and security indicators before proceeding.",
            "Avoid entering credentials if the page was reached through an unexpected link.",
        ]
        reasons.append("High visual and structural overlap")
        if domain_alignment is False:
            reasons.append("Brand-domain alignment check failed")
    elif score >= 0.45:
        risk_level = "medium"
        status = "partial_resemblance"
        headline = "Partial resemblance found"
        summary = "Some branding cues are similar, but the match is not strong."
        recommendations = [
            "Use additional phishing signals (content, domain age, urgency cues) for final judgement.",
        ]
        reasons.append("Moderate component-level match")

    ocr = details.get("ocr") or {}
    if bool(ocr.get("ocr_available")) and (ocr.get("target_text_len", 0) < 20):
        reasons.append("Limited text extracted from screenshot; text signal may be weak")

    return {
        "risk_level": risk_level,
        "status": status,
        "headline": headline,
        "summary": summary,
        "reasons": reasons,
        "recommendations": recommendations,
        "domain": domain,
        "brand": brand_name,
        "domain_alignment": domain_alignment,
    }

# ---------- Similarity Functions ----------
def image_similarity(img1_path, img2_path):
    img1 = normalize_image(img1_path)
    img2 = normalize_image(img2_path)
    try:
        ph = imagehash.phash(img1)
        dh = imagehash.dhash(img1)
        ph2 = imagehash.phash(img2)
        dh2 = imagehash.dhash(img2)
        phash_sim = 1 - (ph - ph2) / (len(ph.hash) ** 2)
        dhash_sim = 1 - (dh - dh2) / (len(dh.hash) ** 2)
        return (phash_sim + dhash_sim) / 2
    except Exception:
        return 0.0

def color_similarity(img1_path, img2_path, bins=32):
    try:
        img1 = np.array(normalize_image(img1_path))
        img2 = np.array(normalize_image(img2_path))
        hist1 = cv2.calcHist([img1],[0,1,2],None,[bins,bins,bins],[0,256,0,256,0,256])
        hist2 = cv2.calcHist([img2],[0,1,2],None,[bins,bins,bins],[0,256,0,256,0,256])
        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()
        return float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL))
    except Exception:
        return 0.0

def text_similarity_with_debug(img1_path, img2_path):
    debug = {
        "ocr_available": bool(OCR_AVAILABLE),
        "ref_text_len": 0,
        "target_text_len": 0,
        "common_tokens": 0,
        "token_overlap_ratio": 0.0,
    }

    try:
        text1 = extract_text_from_image(img1_path)
        text2 = extract_text_from_image(img2_path)
        debug["ref_text_len"] = len(text1)
        debug["target_text_len"] = len(text2)

        if not text1 or not text2:
            return 0.0, debug

        # TF-IDF cosine similarity
        vectorizer = TfidfVectorizer().fit([text1, text2])
        vectors = vectorizer.transform([text1, text2])
        tfidf_sim = float(cosine_similarity(vectors[0], vectors[1])[0][0])

        # Jaccard similarity
        set1, set2 = set(text1.split()), set(text2.split())
        common_tokens = len(set1 & set2)
        union_count = len(set1 | set2)
        debug["common_tokens"] = common_tokens
        debug["token_overlap_ratio"] = (common_tokens / union_count) if union_count else 0.0
        jaccard_sim = (len(set1 & set2) / len(set1 | set2)) if set1 and set2 else 0.0

        return (tfidf_sim + jaccard_sim) / 2, debug
    except Exception:
        return 0.0, debug


def text_similarity(img1_path, img2_path):
    score, _ = text_similarity_with_debug(img1_path, img2_path)
    return score

def website_similarity(ref_img, target_img, weights=(0.42, 0.2, 0.23, 0.15), brand_name=None, domain=None, domain_alignment=None):
    try:
        img_sim = _clamp01(image_similarity(ref_img, target_img))
        col_sim = _normalize_color_score(color_similarity(ref_img, target_img))
        txt_sim, txt_debug = text_similarity_with_debug(ref_img, target_img)
        txt_sim = _clamp01(txt_sim)
        struct_sim = _clamp01(structure_similarity(ref_img, target_img))

        # Dynamic reweighting: when OCR signal is weak, reduce text impact and rely more on visual/layout.
        w_img, w_col, w_txt, w_struct = weights
        if (txt_debug.get("ref_text_len", 0) < 20) or (txt_debug.get("target_text_len", 0) < 20):
            w_img, w_col, w_txt, w_struct = 0.48, 0.22, 0.08, 0.22

        total_w = w_img + w_col + w_txt + w_struct
        w_img, w_col, w_txt, w_struct = [w / total_w for w in (w_img, w_col, w_txt, w_struct)]

        base_score = (w_img * img_sim) + (w_col * col_sim) + (w_txt * txt_sim) + (w_struct * struct_sim)
        consistency = 1.0 - np.std([img_sim, col_sim, txt_sim, struct_sim])
        final_score = _clamp01((0.9 * base_score) + (0.1 * _clamp01(consistency)))

        details = {
            "image": img_sim,
            "color": col_sim,
            "text": txt_sim,
            "structure": struct_sim,
            "ocr": txt_debug,
            "weights_applied": {
                "image": w_img,
                "color": w_col,
                "text": w_txt,
                "structure": w_struct,
            },
            "consistency": _clamp01(consistency),
        }
        details["confidence"] = _compute_similarity_confidence(details)
        details["assessment"] = _build_similarity_assessment(
            final_score,
            details,
            brand_name=brand_name,
            domain=domain,
            domain_alignment=domain_alignment,
        )
        return final_score, details, [w_img, w_col, w_txt, w_struct]
    except Exception as e:
        print(f"[ERROR] Website similarity failed: {e}")
        return None, None, None


# ---------- Fuzzy Brand Detection ----------
def fuzzy_match_brand(domain):
    brands = [os.path.splitext(f)[0].replace("_ref","") for f in os.listdir(BRANDS_FOLDER) if f.lower().endswith(".png")]
    if not brands:
        print("❌ No brand reference images found in dataset.")
        return None
    best = process.extractOne(domain, brands)
    if not best:
        return None
    best_match, score, _ = best
    if score >= 75:
        print(f"🔍 Fuzzy matched '{domain}' → '{best_match}' (score={round(score,1)})")
        return best_match
    return None

# ---------- Explainability ----------
def _notify(notifier, level, message):
    if notifier is None:
        return

    fn = getattr(notifier, level, None)
    if callable(fn):
        fn(message)


def _notify_json(notifier, payload):
    if notifier is None:
        return

    fn = getattr(notifier, "json", None)
    if callable(fn):
        fn(payload)


def explain_score(details, weights, final_score, notifier=None):
    keys = ["image", "color", "text"]
    contributions = {k: details[k] * weights[i] for i, k in enumerate(keys)}

    explanation = "\n--- Explainability ---\n"
    for i, k in enumerate(keys):
        explanation += f"{k.capitalize()} contribution: {contributions[k]:.3f} (raw={details[k]:.3f}, weight={weights[i]})\n"
    explanation += f"Total Score: {final_score:.3f}\n"

    _notify(notifier, "markdown", f"```\n{explanation}\n```")

    return explanation


def check_website(user_input, lgbm_score=None, llm_score=None, ui_weight=0.4, lgbm_weight=0.3, llm_weight=0.3, notifier=None):
    """
    user_input: URL or local image
    lgbm_score, llm_score: optional external scores from your ML/LLM modules
    """
    ui_score, ui_details, ui_weights = None, None, None
    brand_name, ref_img, user_img = None, None, None
    domain = None
    domain_alignment = None

    # --------- Case 1: Local image input ---------
    if is_file_input(user_input):
        fname = os.path.basename(user_input)
        guess = re.split(r'[^a-z0-9]+', os.path.splitext(fname.lower())[0])
        guess = next((g for g in guess if g), None)
        brand_name = guess if guess else None
        if not brand_name:
            _notify(notifier, "error", "❌ Local image provided but cannot guess brand name from filename. Rename like 'paypal_user.png'.")
            return None

        matched = fuzzy_match_brand(brand_name) or brand_name
        ref_img = os.path.join(BRANDS_FOLDER, f"{matched}_ref.png")
        if os.path.exists(ref_img):
            user_img = user_input.replace("file://", "") if user_input.lower().startswith("file://") else user_input
            ui_score, ui_details, ui_weights = website_similarity(ref_img, user_img, brand_name=matched)
        else:
            _notify(notifier, "warning", f"⚠ No reference found for '{matched}' in dataset.")

    # --------- Case 2: URL input ---------
    else:
        url = normalize_url(user_input)
        domain = extract_domain(url)
        if not domain:
            _notify(notifier, "error", "❌ Invalid URL (cannot extract domain).")
            return None

        if not check_dns(url):
            _notify(notifier, "error", f"❌ DNS resolution failed for '{url}'.")
            return None
        if not check_http(url):
            _notify(notifier, "error", f"❌ '{url}' not reachable (HTTP check failed).")
            return None

        brand_name = domain
        ref_img = os.path.join(BRANDS_FOLDER, f"{brand_name}_ref.png")
        if not os.path.exists(ref_img):
            brand_name = fuzzy_match_brand(domain)
            if brand_name:
                ref_img = os.path.join(BRANDS_FOLDER, f"{brand_name}_ref.png")

        if os.path.exists(ref_img):
            user_img = os.path.join(USER_FOLDER, f"{brand_name}_user.png")
            saved = capture_viewport_screenshot(url, user_img, retries=1)
            if saved:
                domain_alignment = bool(brand_name and domain and (brand_name in domain or domain in brand_name))
                ui_score, ui_details, ui_weights = website_similarity(
                    ref_img,
                    user_img,
                    brand_name=brand_name,
                    domain=domain,
                    domain_alignment=domain_alignment,
                )
            else:
                _notify(notifier, "warning", "⚠ Screenshot failed -> skipping similarity analysis.")
        else:
            _notify(notifier, "warning", f"⚠ No reference found for '{domain}'.")

    # --------- Show Website Similarity if available ---------
    if ui_score is not None:
        _notify(notifier, "markdown", f"*Final Similarity Score:* {ui_score:.3f}")
        _notify_json(notifier, ui_details)
        explain_score(ui_details, ui_weights, ui_score, notifier=notifier)
    else:
        _notify(notifier, "info", "ℹ Website similarity analysis not available.")

    # --------- Return structured result ---------
    if ui_score is not None:
        reference_image_url = _get_reference_image_url(ref_img)
        user_screenshot_url = _upload_to_cloudinary(
            user_img,
            folder="spot-the-fake/user",
            public_id=f"user_{brand_name}_{int(time.time())}" if brand_name else None,
            overwrite=True,
        )

        return {
            "brand": brand_name,
            "domain": domain,
            "domain_alignment": domain_alignment,
            "reference_image": ref_img,
            "user_screenshot": user_img,
            "reference_image_url": reference_image_url,
            "user_screenshot_url": user_screenshot_url,
            "score": ui_score,
            "details": ui_details,
            "weights": ui_weights,
            "assessment": (ui_details or {}).get("assessment") if isinstance(ui_details, dict) else None,
            "confidence": (ui_details or {}).get("confidence") if isinstance(ui_details, dict) else None,
        }
    else:
        return None