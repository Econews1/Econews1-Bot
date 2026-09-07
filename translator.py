# translator.py

import re
import requests
import json
import time
import os
import difflib
import arabic_reshaper
from bidi.algorithm import get_display

from config import *


# ================= PERSIAN TEXT PROCESSING =================
def to_persian_digits(text):
    if not text:
        return text
    translation = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    return text.translate(translation)


def fa(text):
    """Prepare Persian text for matplotlib rendering."""
    if not text:
        return text
    try:
        text = to_persian_digits(text)
        reshaped = arabic_reshaper.reshape(text)
        return reshaped
    except Exception as e:
        print(f"Error in fa(): {e}")
        return text


# ================= PERSIAN FONT SETUP =================
_persian_font_prop = None

def setup_persian_font():
    global _persian_font_prop
    if _persian_font_prop is not None:
        return _persian_font_prop

    font_path = "persian_font.ttf"
    urls = [
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf",
        "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Regular.ttf",
    ]
    if not os.path.exists(font_path):
        for url in urls:
            try:
                r = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(font_path, 'wb') as f:
                        f.write(r.content)
                    break
            except Exception as e:
                print(f"Font download failed: {e}")
                continue

    if os.path.exists(font_path):
        try:
            import matplotlib.font_manager as fm
            import matplotlib.pyplot as plt
            fm.fontManager.addfont(font_path)
            prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [prop.get_name(), 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            _persian_font_prop = prop
            print(f"Persian font loaded: {prop.get_name()}")
            return prop
        except Exception as e:
            print(f"Font registration failed: {e}")

    print("Warning: Persian font not loaded.")
    _persian_font_prop = None
    return None


# ================= TEXT CLEANING =================
def clean_text(text):
    """Remove HTML, markdown, LLM artifacts, and clean up."""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove markdown
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|.*?\|', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove LLM artifacts
    for pattern in LLM_ARTIFACT_PATTERNS:
        text = re.sub(pattern, '', text)
    
    # Remove tables
    text = re.sub(r'\|.*?\|.*?\|', '', text)
    
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def remove_repeated_words(text):
    """Remove any repeated word patterns."""
    if not text:
        return text
    
    # Use the pattern from config
    text = re.sub(REPEATED_WORD_PATTERN, r'\1', text, flags=re.IGNORECASE)
    
    # Additional specific fixes
    text = re.sub(r'نیروهای\s+نیروهای\s+', 'نیروهای ', text)
    text = re.sub(r'شورای\s+شورای\s+', 'شورای ', text)
    text = re.sub(r'رهبر\s+رهبر\s+', 'رهبر ', text)
    text = re.sub(r'معظم\s+معظم\s+', 'معظم ', text)
    
    return text


def apply_persian_fixes(text):
    """Apply all Persian post-processing fixes."""
    if not text:
        return text
    
    # Clean LLM artifacts
    text = clean_text(text)
    
    # Apply grammar fixes
    for wrong, correct in GRAMMAR_FIXES.items():
        text = text.replace(wrong, correct)
    
    # Apply Iran respect terms
    for eng, fa_text in IRAN_RESPECT.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    
    # Apply geographic names (English -> Persian)
    for eng, fa_text in GEO_NAMES.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    
    # Remove repeated words
    text = remove_repeated_words(text)
    
    # Convert to Persian digits
    text = to_persian_digits(text)
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


# ================= ECONOMIC FILTER =================
def is_economic_news(title, summary):
    """
    STRICT filter: Only pass news that directly mentions economic factors
    that affect gold, oil, USD, or major markets.
    """
    text = f"{title} {summary}".lower()
    
    # First check if any blocked term is present
    for term in BLOCKED_TERMS:
        if term in text:
            return False, f"blocked: {term}"
    
    # Check if at least one economic term is present
    economic_count = 0
    for term in REQUIRED_ECONOMIC_TERMS:
        if term in text:
            economic_count += 1
    
    if economic_count >= 1:
        return True, "passed"
    
    return False, "no economic terms"


def is_persian_economic(title, summary):
    """Check if Persian text contains economic keywords."""
    text = f"{title} {summary}"
    
    # Check for blocked Persian terms
    for term in BLOCKED_TERMS:
        if term in text:
            return False, f"blocked: {term}"
    
    # Check for economic keywords
    for term in PERSIAN_ECONOMIC_KEYWORDS:
        if term in text:
            return True, "passed"
    
    return False, "no economic keywords"


def is_prohibited_source(url):
    """Check if URL is from a prohibited source."""
    for source in PROHIBITED_SOURCES:
        if source in url:
            return True
    return False


def is_persian_source(url):
    """Check if URL is from a Persian source (skip translation)."""
    for domain in PERSIAN_SOURCE_DOMAINS:
        if domain in url:
            return True
    return False


# ================= GROQ API =================

def get_available_models():
    """Fetch available models from Groq API dynamically."""
    try:
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            models = resp.json().get('data', [])
            available = [m['id'] for m in models]
            # Prioritize best models
            preferred = ['llama-3.1-70b-versatile', 'mixtral-8x7b-32768', 
                        'gemma2-9b-it', 'llama-3.1-8b-instant']
            result = []
            for p in preferred:
                if p in available:
                    result.append(p)
            # Add remaining available models
            for m in available:
                if m not in result:
                    result.append(m)
            return result
    except Exception as e:
        print(f"  ⚠ Model discovery failed: {e}")
    return []


def call_groq(system_prompt, user_text, max_tokens=400, temperature=0.1):
    """Call Groq API with dynamic model discovery."""
    if not GROQ_API_KEY:
        return ""
    
    # Try discovered models first, fallback to config
    models_to_try = get_available_models()
    if not models_to_try:
        models_to_try = [TRANSLATION_MODEL] + FALLBACK_MODELS
    
    for model in models_to_try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9
        }
        
        for attempt in range(3):
            try:
                resp = requests.post(url, headers=headers, json=data, timeout=45)
                
                if resp.status_code == 200:
                    try:
                        result = resp.json()['choices'][0]['message']['content'].strip()
                    except (KeyError, IndexError, json.JSONDecodeError) as e:
                        print(f"  ⚠ Unexpected API response format: {e}")
                        break
                    
                    result = re.sub(r'<\/?think>', '', result)
                    result = clean_text(result)
                    
                    if result and len(result) > 10:
                        return result
                    else:
                        print(f"  ⚠ Model {model} returned empty or too short result")
                        break
                
                elif resp.status_code == 429:
                    wait = 5 * (attempt + 1)
                    print(f"  ⚠ Rate limited on {model}, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                
                elif resp.status_code >= 500:
                    print(f"  ⚠ Server error {resp.status_code} on {model}, retrying...")
                    time.sleep(2)
                    continue
                
                else:
                    print(f"  ❌ Groq API error {resp.status_code} on {model}")
                    if resp.text:
                        try:
                            error_json = json.loads(resp.text)
                            print(f"     {error_json.get('error', {}).get('message', resp.text[:100])}")
                        except:
                            print(f"     {resp.text[:100]}")
                    break
                    
            except requests.exceptions.Timeout:
                print(f"  ⏱️ Timeout on {model} (attempt {attempt+1})")
                time.sleep(2)
                continue
            except Exception as e:
                print(f"  ❌ Exception on {model}: {e}")
                break
        
        else:
            continue
    
    print(f"  ❌ All models failed.")
    return ""


def simplify_english(text):
    """Step 1: Simplify English into complete, grammatically correct sentences."""
    if not text:
        return ""
    
    prompt = """Rewrite this news text as 2-3 simple, complete English sentences.

RULES:
- Each sentence MUST have a subject and verb
- Merge related short sentences into one complete sentence
- Remove any tables, lists, or markdown
- Keep only the main economic facts
- Output ONLY the rewritten sentences, nothing else

Example input: "Gold prices rose. This happened after the Fed meeting. Strong dollar."
Example output: "Gold prices rose after the Federal Reserve meeting, despite a strong dollar."

Text to rewrite: """
    
    result = call_groq(prompt, text, max_tokens=200)
    
    # If API fails, do basic cleanup
    if not result:
        # Simple sentence merging as fallback
        sentences = re.split(r'(?<=[.!?])\s+', text)
        merged = ' '.join(sentences[:3])
        result = clean_text(merged)
    
    return result


def translate_to_persian(english_text):
    """Step 2: Translate simplified English to natural Persian."""
    if not english_text:
        return ""
    
    prompt = """Translate this English news to Persian (Farsi).

STRICT RULES:
1. Output ONLY the Persian translation
2. NO English words in output
3. NO explanations, notes, or commentary
4. NO markdown, tables, or formatting
5. Use natural Persian sentence structure
6. Use these Persian terms exactly:
   - Federal Reserve → فدرال رزرو
   - Interest rate → نرخ بهره
   - Inflation → تورم
   - GDP → تولید ناخالص داخلی
   - Unemployment → بیکاری
   - Oil → نفت
   - Gold → طلا
   - Dollar → دلار
   - Central Bank → بانک مرکزی
   - Sanctions → تحریم
   - OPEC → اوپک

7. Geographic names:
   - United States → ایالات متحده
   - Russia → روسیه
   - China → چین
   - Germany → آلمان
   - France → فرانسه
   - UK → بریتانیا
   - Japan → ژاپن
   - Ukraine → اوکراین
   - Iran → ایران
   - Saudi Arabia → عربستان سعودی
   - Saxony-Anhalt → زاکسن-آنهالت

8. Names:
   - Zelensky → زلنسکی
   - Putin → پوتین
   - Trump → ترامپ
   - Khamenei → خامنه‌ای
   - Pezeshkian → پزشکیان

9. If "Supreme Leader" → رهبر معظم
10. If "Iranian government" → دولت ایران
11. Numbers use Persian digits (۱۲۳)

Input: """
    
    result = call_groq(prompt, english_text, max_tokens=300)
    
    if not result:
        return ""
    
    # Post-processing
    result = apply_persian_fixes(result)
    
    return result


def validate_translation(persian_text, english_text):
    """Step 3: Validate translation quality."""
    if not persian_text:
        return False, "empty"
    
    # Check length
    if len(persian_text) < 15:
        return False, "too short"
    
    if len(persian_text) > 600:
        return False, "too long"
    
    # Check for LLM artifacts
    artifact_indicators = [
        'ترجمه', 'خلاصه', 'نکات', 'دلیل', 'تحلیل', 'ساختار',
        'Here', 'Translation', 'Note', 'explain', 'output'
    ]
    for indicator in artifact_indicators:
        if indicator in persian_text[:80]:
            return False, f"contains '{indicator}'"
    
    # Check Persian character ratio
    persian_chars = len(re.findall(r'[\u0600-\u06FF]', persian_text))
    total_chars = len(persian_text.strip())
    
    if total_chars > 0 and persian_chars / total_chars < 0.6:
        return False, "not Persian enough"
    
    # Check for broken phrases
    broken_phrases = [
        'معظم معظم', 'شورای شورای', 'نیروهای نیروهای',
        'ارزش از ارزش', 'پاسخ ایجاد', 'خوشحال می‌کند',
        'معظمی', 'دوردست', 'ساکسونی آنها'
    ]
    for phrase in broken_phrases:
        if phrase in persian_text:
            return False, f"broken phrase: {phrase}"
    
    return True, "valid"


def translate_news_article(article):
    """
    Full translation pipeline:
    1. Check source type (Persian vs English)
    2. Apply economic filter
    3. For English: Simplify → Translate → Validate → Fix
    4. For Persian: Apply fixes directly
    """
    title = article.get('title', '')
    summary = article.get('summary', '')[:200]  # Limit summary length
    source_url = article.get('link', '')
    
    # Check for prohibited sources
    if is_prohibited_source(source_url):
        return None, None
    
    # Check if from Persian source (skip translation)
    if is_persian_source(source_url):
        # Apply economic filter
        is_econ, reason = is_persian_economic(title, summary)
        if is_econ:
            # Apply fixes to Persian text
            fixed_title = apply_persian_fixes(title)
            fixed_summary = apply_persian_fixes(summary) if summary else ""
            return fixed_title, fixed_summary
        else:
            print(f"  ✗ Persian filter: {reason}")
            return None, None
    
    # For English sources: strict economic filter
    is_econ, reason = is_economic_news(title, summary)
    if not is_econ:
        print(f"  ✗ Filter: {reason}")
        return None, None
    
    # Step 1: Simplify English
    print("  Step 1: Simplifying English...")
    simplified = simplify_english(f"{title}. {summary}")
    if not simplified:
        simplified = f"{title}. {summary}"
    
    # Step 2: Translate to Persian
    print("  Step 2: Translating to Persian...")
    persian = translate_to_persian(simplified)
    
    if not persian:
        print("  ✗ Translation failed")
        return None, None
    
    # Step 3: Validate
    print("  Step 3: Validating...")
    is_valid, validation_reason = validate_translation(persian, simplified)
    if not is_valid:
        print(f"  ✗ Validation failed: {validation_reason}")
        # Try once more with shorter input
        shorter_input = simplified[:150]
        persian = translate_to_persian(shorter_input)
        if persian:
            is_valid, _ = validate_translation(persian, shorter_input)
            if not is_valid:
                return None, None
        else:
            return None, None
    
    # Step 4: Apply final fixes
    print("  Step 4: Applying fixes...")
    persian = apply_persian_fixes(persian)
    
    # Split into title and summary
    lines = persian.split('\n')
    if len(lines) > 1:
        persian_title = lines[0].strip()
        persian_summary = ' '.join(lines[1:]).strip()
    else:
        # Try splitting by period
        parts = re.split(r'(?<=[.!?؟])\s+', persian, maxsplit=1)
        persian_title = parts[0].strip()
        persian_summary = parts[1].strip() if len(parts) > 1 else ""
    
    return persian_title, persian_summary


# ================= UTILITY =================
def detect_language(text):
    """Detect if text is Persian, Russian, or English."""
    if not text:
        return "en"
    if re.search(r'[\u0600-\u06FF]', text):
        return "fa"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    else:
        return "en"
