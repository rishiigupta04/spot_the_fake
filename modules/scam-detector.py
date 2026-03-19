import requests
from bs4 import BeautifulSoup
import json
import re
import os

try:
    from groq import Groq
except Exception:
    Groq = None

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

def extract_main_content(html):
    """
    Extracts clean, main body text from HTML.
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    for element in soup(["script", "style", "meta", "link", "header", "footer", "nav", "aside"]):
        element.decompose()
        
    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    return text

def find_heuristic_explanations(text):
    """
    Scans text for specific, concrete patterns common in scams and phishing.
    Returns a list of explanatory sentences. This is our rule-based evidence.
    """
    explanations = []
    text_lower = text.lower()

    urgency_keywords = ['immediately', 'urgent', 'action required', 'within 24 hours', 'account suspended', 'verify now', 'failure to comply', 'account closure', 'limited time']
    found_urgency = [word for word in urgency_keywords if word in text_lower]
    if found_urgency:
        explanations.append(f"Uses urgency/fear language: '{found_urgency[0]}'.")

    prize_keywords = ['winner', 'prize', 'reward', 'selected', 'free gift', 'you have won', 'congratulations', 'claim your', 'lottery']
    found_prizes = [word for word in prize_keywords if word in text_lower]
    if found_prizes:
        explanations.append(f"Mentions prizes/rewards: '{found_prizes[0]}'.")

    authority_keywords = ['social security', 'administration', 'microsoft', 'apple', 'paypal', 'support', 'security department', 'amazon', 'netflix', 'bank', 'government']
    found_authority = [word for word in authority_keywords if word in text_lower]
    if found_authority:
        explanations.append(f"Impersonates/mentions authority: '{found_authority[0]}'.")

    sensitive_info_keywords = ['password', 'social security number', 'ssn', 'credit card', 'debit card', 'bank account', 'login credentials', 'verify your identity', 'date of birth', 'mother\'s maiden name']
    found_sensitive = [word for word in sensitive_info_keywords if word in text_lower]
    if found_sensitive:
        explanations.append(f"Requests sensitive info: '{found_sensitive[0]}'.")

    if text_lower.count('!') > 3:
        explanations.append("Uses excessive exclamation marks (!), common in scam content.")

    return explanations

def analyze_with_groq(content, model_name=None):
    """
    Sends the extracted content to Groq LLM API.
    Returns a verdict and the LLM's own reasoning.
    """
    system_prompt = """You are an expert cybersecurity analyst. Your task is to analyze the content of a website and determine if it is a scam, phishing attempt, or otherwise malicious.
    Analyze the provided text and respond STRICTLY in the following JSON format and nothing else:

    {
      "verdict": "yes" or "no",
      "confidence": "high", "medium", or "low",
      "reasons": ["list", "of", "brief", "reasons", "for", "the", "verdict"]
    }

    Considerations for a "yes" (malicious) verdict:
    - Creates a sense of urgency (e.g., "Your account will be suspended!").
    - Impersonates a well-known company (e.g., Microsoft, PayPal, a bank).
    - Requests sensitive information (passwords, credit card numbers, SSN).
    - Promises unrealistic rewards or prizes.
    - Contains threats or warnings.
    - Poor grammar and spelling inconsistencies.
    - Pressures the user to click a link or download a file.
    - Anything you deem suspicious
    """
    
    model_name = model_name or GROQ_MODEL

    try:
        if Groq is None:
            raise RuntimeError("groq SDK is not installed. Install with: pip install groq")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")

        user_message = f"Analyze this website content for scams:\n\n{content}"
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
        json_match = re.search(r'{.*}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        else:
            print("Model did not return valid JSON. Raw response:")
            print(response_text)
            return None
        
    except Exception as e:
        print(f"Error with Groq: {e}")
        return None


def analyze_with_ollama(content, model_name="mistral"):
    """Backward-compatible wrapper for older call sites."""
    resolved_model = GROQ_MODEL if model_name == "mistral" else model_name
    return analyze_with_groq(content, model_name=resolved_model)

def main():
    """
    Main function to run the hybrid analysis.
    """
    print("🌐 Website Scam & Phishing Analyzer")
    print("----------------------------------------")
    website_url = input("Please enter the full URL to analyze: ").strip()
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        print(f"\n📡 Fetching URL: {website_url}")
        response = requests.get(website_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Failed to fetch URL: {e}")
        return

    html_content = response.text
    main_text = extract_main_content(html_content)
    text_for_llm = website_url + main_text[:2000]
    full_text_for_heuristics = main_text

    print(f"✓ Extracted {len(text_for_llm)} characters for analysis.")
    print("🧠 Running hybrid analysis (LLM + Heuristics)...")
    print("This may take 10-20 seconds on first run...\n")
    print("-"*60)
    print(main_text)
    print("-"*60)
    llm_result = analyze_with_groq(text_for_llm)
    heuristic_reasons = find_heuristic_explanations(full_text_for_heuristics)
    print("-"*60)
    print(llm_result)
    print("-"*60)
    if llm_result:
        final_verdict = {
            "url": website_url,
            "verdict": llm_result['verdict'],
            "confidence": llm_result['confidence'],
            "llm_reasons": llm_result.get('reasons', []),
            "heuristic_reasons": heuristic_reasons,
            "all_reasons": llm_result.get('llm_reasons', []) + heuristic_reasons
        }
        
        print("="*60)
        print(f"📋 URL: {website_url}")
        verdict_text = '🔴 MALICIOUS' if final_verdict['verdict'] == 'yes' else '🟢 LIKELY SAFE'
        print(f"⚖️ Final Verdict: {verdict_text}")
        print(f"🎯 Confidence: {final_verdict['confidence'].upper()}")
        
        print("\n🤖 AI's Contextual Analysis:")
        if final_verdict['llm_reasons']:
            for reason in final_verdict['llm_reasons']:
                print(f" • {reason}")
        else:
            print(" • No specific reasons provided by AI.")
            
        print("\n🔍 Concrete Evidence Found in Text:")
        if final_verdict['heuristic_reasons']:
            for reason in final_verdict['heuristic_reasons']:
                print(f" • {reason}")
        else:
            print(" • No strong heuristic patterns detected.")
        print("="*60)
    else:
        print("❌ LLM analysis failed. Falling back to heuristics only.")
        print("Heuristic reasons found:", heuristic_reasons)

if __name__ == "__main__":
    main()