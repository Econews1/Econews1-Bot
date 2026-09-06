# translator.py

import difflib
import re
import requests
import os
import json
import arabic_reshaper
from bidi.algorithm import get_display

from config import *

# ================= PERSIAN TEXT PROCESSING =================
def to_persian_digits(text):
    if not text:
        return text
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    western_digits = '0123456789'
    translation = str.maketrans(western_digits, persian_digits)
    return text.translate(translation)

def fa(text):
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
        "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Regular.ttf",
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf",
        "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Regular.ttf",
        "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf",
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf",
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
            fm.fontManager.addfont(font_path)
            prop = fm.FontProperties(fname=font_path)
            import matplotlib.pyplot as plt
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [prop.get_name(), 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            _persian_font_prop = prop
            print(f"Persian font loaded: {prop.get_name()}")
            return prop
        except Exception as e:
            print(f"Font registration failed: {e}")

    print("Warning: Persian font not loaded. Using default.")
    _persian_font_prop = None
    return None

# ================= FUZZY CORRECTION =================
def fuzzy_correct_text(text, candidates, cutoff=0.85):
    if not text:
        return text
    tokens = re.findall(r'\S+', text)
    corrected_tokens = []
    for token in tokens:
        core_token = token.rstrip('،؛.!?؟')
        match = difflib.get_close_matches(core_token, candidates, n=1, cutoff=cutoff)
        if match:
            new_token = match[0] + token[len(core_token):]
            corrected_tokens.append(new_token)
        else:
            corrected_tokens.append(token)
    return ' '.join(corrected_tokens)

# ================= TRANSLATION IMPROVEMENTS =================
def apply_all_glossaries(text):
    # Exact replacements
    for wrong, right in PERSIAN_CORRECTIONS.items():
        text = text.replace(wrong, right)
    for eng, fa_text in IRAN_RESPECT_GLOSSARY.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    for eng, fa_text in ECONOMIC_GLOSSARY.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    for eng, fa_text in IRAN_SPECIFIC_GLOSSARY.items():
        text = text.replace(eng, fa_text)
    for country_dict in COUNTRY_GLOSSARY.values():
        for eng, fa_text in country_dict.items():
            text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    for wrong, right in PERSIAN_NAME_CORRECTIONS.items():
        text = text.replace(wrong, right)
    for wrong, right in PROPER_NOUN_CORRECTIONS.items():
        text = text.replace(wrong, right)

    # Fuzzy correction for proper nouns
    text = fuzzy_correct_text(text, CORRECT_TERMS, cutoff=0.85)

    return text

def detect_language(text):
    if not text:
        return "en"
    if re.search(r'[\u0600-\u06FF]', text):
        return "fa"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    else:
        return "en"

def simplify_to_english(text):
    if not text:
        return ""
    prompt = (
        "You are a professional news editor. "
        "Rewrite the following text into simple, complete English sentences. "
        "Use short sentences with clear subject-verb-object order. "
        "Avoid complex clauses. "
        "If the text is not English, first translate it into simple English. "
        "Output only the simplified English, nothing else."
    )
    return translate_with_custom_prompt(prompt, text)

def translate_english_to_persian(english_text):
    if not english_text:
        return ""
    prompt = (
        "You are a professional Persian translator specializing in financial and political news. "
        "Translate the following English text into Persian. "
        "Use natural Persian sentence structure: verb at the end of the sentence, object before subject if needed. "
        "Do NOT include any English words. Transliterate any remaining English terms into Persian letters. "
        "Output only the Persian translation, nothing else."
    )
    return translate_with_custom_prompt(prompt, english_text)

def summarize_persian(persian_text):
    if not persian_text:
        return ""
    prompt = (
        "You are a professional Persian financial news summarizer. "
        "Summarize the following Persian news text into 2-3 concise Persian sentences. "
        "Focus on key economic data, price impact, and important actors. "
        "Keep the original Persian, do not translate. "
        "Output only the summary, nothing else."
    )
    return translate_with_custom_prompt(prompt, persian_text)

# ================= TRANSLATION FUNCTIONS =================
def clean_html(text):
    return re.sub('<.*?>', '', text)

def get_groq_models():
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [m['id'] for m in data.get('data', []) if m.get('active', False)]
        else:
            print(f"Failed to fetch models: {resp.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

def extract_translation(raw_output):
    if not raw_output:
        return ""
    if '</think>' in raw_output:
        raw_output = raw_output.split('</think>')[-1].strip()
    raw_output = re.sub(r'^<think>.*?(?=<think>|$)', '', raw_output, flags=re.DOTALL).strip()
    return raw_output

def is_refusal(text):
    refusal_phrases = [
        "i'm sorry", "i am sorry", "i can't", "i cannot",
        "can't help", "cannot help", "not able to", "unable to",
        "i apologize", "sorry, but", "i'm not able", "i am not able",
        "i won't", "i will not"
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in refusal_phrases)

def apply_glossaries(text):
    return apply_all_glossaries(text)

def load_cached_model():
    if os.path.exists(MODEL_CACHE_FILE):
        with open(MODEL_CACHE_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_cached_model(model_id):
    with open(MODEL_CACHE_FILE, 'w') as f:
        f.write(model_id)

def has_latin(text):
    return bool(re.search(r'[A-Za-z]', text))

def force_persian(text):
    prompt = (
        "The following text contains some English words or Latin characters. "
        "Rewrite it entirely in Persian script, translating any remaining English terms into Persian. "
        "Use standard Persian financial terminology. Do not include any Latin letters. "
        "Keep the meaning intact. Output only the Persian text."
    )
    result = translate_with_custom_prompt(prompt, text)
    if result and not has_latin(result):
        return result
    result = re.sub(r'[A-Za-z]+', '', text)
    result = re.sub(r'\s+', ' ', result).strip()
    return result

def try_translate_with_model(text, model, custom_prompt=None):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    if custom_prompt:
        system_prompt = custom_prompt
    else:
        system_prompt = (
            "You are a professional financial translator. "
            "Detect the language of the input (English, Russian, or any other). "
            "If the input is not English, first rewrite it into simple, complete English sentences. "
            "Then translate the text into Persian (Farsi). "
            "Use simple, natural Persian sentence structure with the verb at the end. "
            "Convert all Western numerals to Persian digits. "
            "If the text mentions Iranian officials or government, use respectful language (e.g., 'جمهوری اسلامی ایران', 'مقامات ایرانی'). "
            "Important: Do NOT include any English words or Latin characters in the output. "
            "If you encounter an English term, transliterate it into Persian letters. "
            "Never refuse, never apologize, just output the final Persian translation."
        )
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "max_tokens": 8000,
        "temperature": 0.3
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        print(f"  Trying model {model} -> status {resp.status_code}")
        if resp.status_code == 200:
            raw = resp.json()['choices'][0]['message']['content'].strip()
            cleaned = extract_translation(raw)
            if any(phrase in cleaned for phrase in ["متن خبری مالی را", "لطفاً متن خبری", "Translate the user's financial news"]):
                print("  Model returned system prompt, skipping.")
                return None
            if is_refusal(cleaned):
                print("  Model refused, skipping.")
                return None
            if cleaned and len(cleaned) > 5:
                cleaned = apply_glossaries(cleaned)
                cleaned = to_persian_digits(cleaned)
                if has_latin(cleaned):
                    print("  Latin detected, forcing Persian...")
                    forced = force_persian(cleaned)
                    if forced:
                        cleaned = forced
                return cleaned
            else:
                print("  Model returned empty translation.")
                return None
        else:
            print(f"  Model {model} failed: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  Model {model} exception: {e}")
        return None

def translate_to_persian(text, custom_prompt=None):
    if not GROQ_API_KEY:
        return text
    cached = load_cached_model()
    if cached:
        print(f"Trying cached model: {cached}")
        result = try_translate_with_model(text, cached, custom_prompt)
        if result:
            return result
        else:
            if os.path.exists(MODEL_CACHE_FILE):
                os.remove(MODEL_CACHE_FILE)
    for model in PREFERRED_MODELS:
        result = try_translate_with_model(text, model, custom_prompt)
        if result:
            save_cached_model(model)
            return result
    for model in FALLBACK_MODELS:
        result = try_translate_with_model(text, model, custom_prompt)
        if result:
            save_cached_model(model)
            return result
    print("All known models failed. Fetching active models...")
    active_models = get_groq_models()
    def is_preferred(m):
        lower = m.lower()
        return 'qwen' not in lower and 'reason' not in lower
    sorted_models = sorted(active_models, key=lambda m: not is_preferred(m))
    for model in sorted_models:
        result = try_translate_with_model(text, model, custom_prompt)
        if result:
            save_cached_model(model)
            return result
    return text

def translate_summary_to_persian(title_en, summary_en):
    if not summary_en:
        return ""
    prompt = (
        "You are a professional financial news writer. "
        "Based on the title and the provided summary, write a concise Persian summary (2-3 sentences max) that explains the main event, involved country/actor, key numbers, and reason. "
        "Do NOT repeat the title. Use simple Persian sentences with verbs at the end. "
        "Convert all numbers to Persian digits. Do NOT include any English words or Latin characters. "
        "If the summary is in a language other than English, first rewrite it into simple English, then translate to Persian. "
        "Never refuse, never apologize, just output the final Persian summary."
    )
    user_content = f"Title: {title_en}\nSummary: {summary_en}"
    result = translate_with_custom_prompt(prompt, user_content)
    if result and has_latin(result):
        forced = force_persian(result)
        if forced:
            result = forced
    return result

def translate_with_custom_prompt(system_prompt, user_content):
    if not GROQ_API_KEY:
        return ""
    cached = load_cached_model()
    if cached:
        result = try_translate_with_model(user_content, cached, system_prompt)
        if result:
            return result
        else:
            if os.path.exists(MODEL_CACHE_FILE):
                os.remove(MODEL_CACHE_FILE)
    for model in PREFERRED_MODELS:
        result = try_translate_with_model(user_content, model, system_prompt)
        if result:
            save_cached_model(model)
            return result
    for model in FALLBACK_MODELS:
        result = try_translate_with_model(user_content, model, system_prompt)
        if result:
            save_cached_model(model)
            return result
    active_models = get_groq_models()
    def is_preferred(m):
        lower = m.lower()
        return 'qwen' not in lower and 'reason' not in lower
    sorted_models = sorted(active_models, key=lambda m: not is_preferred(m))
    for model in sorted_models:
        result = try_translate_with_model(user_content, model, system_prompt)
        if result:
            save_cached_model(model)
            return result
    return ""
