# translator.py

import re
import requests
import json
import time
import os

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None

from config import *

# ---------- Safe defaults in case config.py is missing some keys ----------
if 'GROQ_API_KEY' not in globals():
    GROQ_API_KEY = ''
if 'TRANSLATION_MODEL' not in globals():
    TRANSLATION_MODEL = 'llama-3.3-70b-versatile'
if 'FALLBACK_MODELS' not in globals():
    FALLBACK_MODELS = ['llama-3.1-8b-instant', 'gemma2-9b-it']
if 'LLM_ARTIFACT_PATTERNS' not in globals():
    LLM_ARTIFACT_PATTERNS = []
if 'GRAMMAR_FIXES' not in globals():
    GRAMMAR_FIXES = {}
if 'IRAN_RESPECT' not in globals():
    IRAN_RESPECT = {}
if 'GEO_NAMES' not in globals():
    GEO_NAMES = {}
if 'REPEATED_WORD_PATTERN' not in globals():
    REPEATED_WORD_PATTERN = r'\b(\w+)(\s+\1\b)+'
if 'PERSIAN_SOURCE_DOMAINS' not in globals():
    PERSIAN_SOURCE_DOMAINS = []
if 'PROHIBITED_SOURCES' not in globals():
    PROHIBITED_SOURCES = []
if 'REQUIRED_ECONOMIC_TERMS' not in globals():
    REQUIRED_ECONOMIC_TERMS = ['economy', 'inflation', 'oil', 'gold', 'dollar',
                               'market', 'price', 'rate', 'fed', 'bank']
if 'BLOCKED_TERMS' not in globals():
    BLOCKED_TERMS = []
if 'PERSIAN_ECONOMIC_KEYWORDS' not in globals():
    PERSIAN_ECONOMIC_KEYWORDS = ['اقتصاد', 'دلار', 'طلا', 'نفت', 'بازار', 'تورم',
                                 'نرخ بهره', 'بورس', 'ارز', 'یورو', 'شاخص', 'بشکه']


# ================= PERSIAN TEXT PROCESSING =================
def to_persian_digits(text):
    if not text:
        return text
    translation = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    return text.translate(translation)


def fa(text):
    """Prepare Persian text for matplotlib rendering (reshape + bidi)."""
    if not text:
        return text
    try:
        text = to_persian_digits(text)
        if arabic_reshaper is not None:
            text = arabic_reshaper.reshape(text)
        if get_display is not None:
            text = get_display(text)
        return text
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
    """Remove HTML, markdown, LLM artifacts, and clean up whitespace."""
    if not text:
        return ""

    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)          # tags -> space (no glued words)
    text = re.sub(r'&nbsp;?', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&[a-zA-Z#0-9]+;', ' ', text)

    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|.*?\|', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    for pattern in LLM_ARTIFACT_PATTERNS:
        try:
            text = re.sub(pattern, '', text)
        except re.error:
            pass

    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def remove_repeated_words(text):
    if not text:
        return text
    try:
        text = re.sub(REPEATED_WORD_PATTERN, r'\1', text, flags=re.IGNORECASE)
    except re.error:
        pass
    text = re.sub(r'نیروهای\s+نیروهای\s+', 'نیروهای ', text)
    text = re.sub(r'شورای\s+شورای\s+', 'شورای ', text)
    text = re.sub(r'رهبر\s+رهبر\s+', 'رهبر ', text)
    text = re.sub(r'معظم\s+معظم\s+', 'معظم ', text)
    return text


def apply_persian_fixes(text):
    """Apply all Persian post-processing fixes."""
    if not text:
        return text

    text = clean_text(text)

    for wrong, correct in GRAMMAR_FIXES.items():
        text = text.replace(wrong, correct)

    for eng, fa_text in IRAN_RESPECT.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)

    for eng, fa_text in GEO_NAMES.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)

    text = remove_repeated_words(text)
    text = to_persian_digits(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ================= ECONOMIC FILTERS =================
def is_economic_news(title, summary, content=''):
    """Filter: blocked terms checked on title/summary only; economic terms on full text."""
    title_text = f"{title} {summary}".lower()
    for term in BLOCKED_TERMS:
        if term in title_text:
            return False, f"blocked: {term}"

    text = f"{title} {summary} {content}".lower()
    economic_count = 0
    for term in REQUIRED_ECONOMIC_TERMS:
        if term in text:
            economic_count += 1

    if economic_count >= 1:
        return True, "passed"
    return False, "no economic terms"


def is_persian_economic(title, summary, content=''):
    """Check if Persian text contains economic keywords."""
    title_text = f"{title} {summary}"
    for term in BLOCKED_TERMS:
        if term in title_text:
            return False, f"blocked: {term}"

    text = f"{title} {summary} {content}"
    for term in PERSIAN_ECONOMIC_KEYWORDS:
        if term in text:
            return True, "passed"
    for term in REQUIRED_ECONOMIC_TERMS:
        if term in text.lower():
            return True, "passed"
    return False, "no economic keywords"


def is_prohibited_source(url):
    for source in PROHIBITED_SOURCES:
        if source in (url or ''):
            return True
    return False


def is_persian_source(url):
    for domain in PERSIAN_SOURCE_DOMAINS:
        if domain in (url or ''):
            return True
    return False


# ================= GROQ API =================
_model_cache = {'list': None, 'expires': 0.0}

def get_available_models():
    """Fetch (and cache for 1 hour) available chat models from Groq."""
    if _model_cache['list'] and time.time() < _model_cache['expires']:
        return _model_cache['list']
    try:
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            available = [m.get('id') for m in resp.json().get('data', []) if m.get('id')]
            available = [m for m in available if not any(x in m for x in
                          ('whisper', 'tts', 'guard', 'embed'))]
            preferred = ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile',
                         'qwen/qwen3-32b', 'llama-3.1-8b-instant', 'gemma2-9b-it']
            result = [p for p in preferred if p in available]
            result += [m for m in available if m not in result]
            if result:
                _model_cache['list'] = result[:6]
                _model_cache['expires'] = time.time() + 3600
                return _model_cache['list']
    except Exception as e:
        print(f"  ⚠ Model discovery failed: {e}")
    return []


def call_groq(system_prompt, user_text, max_tokens=600, temperature=0.2):
    """Call Groq API with model fallback and retries."""
    if not GROQ_API_KEY:
        return ""

    models_to_try = get_available_models()
    if not models_to_try:
        base = []
        if TRANSLATION_MODEL:
            base.append(TRANSLATION_MODEL)
        if FALLBACK_MODELS:
            base.extend([m for m in FALLBACK_MODELS if m])
        models_to_try = base or ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant']

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    for model in models_to_try[:4]:
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
                resp = requests.post(url, headers=headers, json=data, timeout=60)

                if resp.status_code == 200:
                    try:
                        result = resp.json()['choices'][0]['message']['content'] or ''
                    except (KeyError, IndexError, ValueError) as e:
                        print(f"  ⚠ Unexpected API response format on {model}: {e}")
                        break
                    if not result:
                        break
                    # strip reasoning-model thinking blocks
                    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
                    result = re.sub(r'</?think>', '', result)
                    result = clean_text(result)
                    if len(result) > 10:
                        return result
                    print(f"  ⚠ Model {model} returned empty/short result")
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
                    try:
                        msg = resp.json().get('error', {}).get('message', '')
                        if msg:
                            print(f"     {msg[:120]}")
                    except Exception:
                        pass
                    break  # try the next model

            except requests.exceptions.Timeout:
                print(f"  ⏱ Timeout on {model} (attempt {attempt + 1})")
                time.sleep(1)
                continue
            except Exception as e:
                print(f"  ❌ {type(e).__name__} on {model}: {str(e)[:80]}")
                break

    print("  ❌ All Groq models failed.")
    return ""


# ================= TRANSLATION PROMPTS =================
TRANSLATE_PROMPT_TEMPLATE = """Translate the following English news into Persian (Farsi).

Return ONLY a valid JSON object, exactly this format:
{"title": "عنوان فارسی", "summary": "خلاصه فارسی"}

"title" rules:
- Exactly ONE complete Persian sentence that states the main news: who did what, and the key number if there is one.
- 10 to 18 words. A grammatically complete sentence, NOT a fragment and NOT a colon-style headline.

"summary" rules:
- 3 to 5 fluent Persian sentences (about 200 to 450 characters total).
- Cover the whole story: what happened, the important numbers, the cause, and the expected market impact.
- Plain flowing text: no lists, no bullets, no headings, no quotation marks.

Language rules:
- Natural, formal Persian as used in Iranian economic media.
- All digits in Persian numerals (۰۱۲۳۴۵۶۷۸۹).
- Terminology: Federal Reserve→فدرال رزرو، interest rate→نرخ بهره، inflation→تورم، GDP→تولید ناخالص داخلی، unemployment→بیکاری، oil→نفت، gold→طلا، dollar→دلار، central bank→بانک مرکزی، sanctions→تحریم، OPEC→اوپک، treasury/bond→اوراق قرضه، stock→سهام، barrel→بشکه، ounce→اونس.
- Countries: United States→ایالات متحده، Russia→روسیه، China→چین، Germany→آلمان، France→فرانسه، UK→بریتانیا، Japan→ژاپن، India→هند، Saudi Arabia→عربستان سعودی، Ukraine→اوکراین، Iran→ایران، European Union→اتحادیه اروپا.
- People: Powell→پاول، Trump→ترامپ، Biden→بایدن، Lagarde→لاگارد، Yellen→یلن، Putin→پوتین، Zelensky→زلنسکی.
- The JSON values must contain ONLY Persian text: no English words, no Latin letters, no HTML, no markdown.

English news:
{NEWS}

JSON output:"""


PERSIAN_SUMMARY_TEMPLATE = """خبر زیر را برای یک کانال تلگرامی اقتصادی به فارسی روان خلاصه کن.

قوانین:
- خروجی فقط یک پاراگراف فارسی روان با ۳ تا ۵ جمله باشد (حدود ۲۰۰ تا ۴۵۰ کاراکتر).
- کل ماجرا پوشش داده شود: رویداد اصلی، اعداد و ارقام کلیدی، دلایل و پیامدهای احتمالی.
- متن پیوسته؛ بدون فهرست، بدون گلوله، بدون عنوان و بدون علامت‌گذاری اضافه.
- اعداد به صورت فارسی نوشته شوند (۱۲۳).
- فقط خودِ خلاصه را بنویس؛ هیچ توضیح، برچسب یا کلمه اضافه‌ای اضافه نکن.

عنوان خبر: {TITLE}

متن خبر:
{CONTENT}

خلاصه:"""


TITLE_PROMPT_TEMPLATE = """Translate this English news headline into ONE natural, complete Persian sentence.

Rules:
- Output ONLY the Persian sentence. No English, no quotes, no explanation.
- A full grammatical sentence stating who did what.
- Use Persian digits for numbers and standard Iranian economic terminology.

Headline: {TITLE}"""


# ================= OUTPUT PARSING / VALIDATION =================
def _parse_json_result(text):
    if not text:
        return None
    cleaned = re.sub(r'```[a-zA-Z]*', '', text).replace('```', '')
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not m:
        return None
    raw_json = m.group(0)
    try:
        obj = json.loads(raw_json)
        if isinstance(obj, dict):
            return {str(k).strip().lower(): v for k, v in obj.items()}
    except json.JSONDecodeError:
        pass
    fixed = raw_json.replace('،', ',').replace("'", '"')
    fixed = re.sub(r',\s*}', '}', fixed)
    try:
        obj = json.loads(fixed)
        if isinstance(obj, dict):
            return {str(k).strip().lower(): v for k, v in obj.items()}
    except Exception:
        pass
    return None


def validate_title(persian_title, min_len=20):
    if not persian_title:
        return False
    t = persian_title.strip()
    if not (min_len <= len(t) <= 250):
        return False
    persian_chars = len(re.findall(r'[\u0600-\u06FF]', t))
    if persian_chars / max(len(t), 1) < 0.6:
        return False
    bad = ['ترجمه', 'عنوان:', 'خلاصه:', 'JSON', 'json', '{', '}',
           'Title', 'title', 'Summary', 'summary', '```', 'Note']
    for b in bad:
        if b in t:
            return False
    return True


def validate_summary(persian_summary):
    """A summary is only shown if it is substantial (a few real lines)."""
    if not persian_summary:
        return False
    s = persian_summary.strip()
    if len(s) < 100:
        return False
    persian_chars = len(re.findall(r'[\u0600-\u06FF]', s))
    if persian_chars / max(len(s), 1) < 0.6:
        return False
    bad = ['ترجمه', 'JSON', 'json', '```', '{', '}', 'خلاصه:', 'Summary', 'summary']
    for b in bad:
        if b in s:
            return False
    return True


def _extract_title_summary(raw):
    parsed = _parse_json_result(raw)
    if parsed:
        t = str(parsed.get('title') or '').strip()
        s = str(parsed.get('summary') or '').strip()
    else:
        lines = [l.strip() for l in raw.split('\n') if l.strip()]
        t = lines[0] if lines else ''
        s = ' '.join(lines[1:]) if len(lines) > 1 else ''
    return apply_persian_fixes(t), apply_persian_fixes(s)


# ================= TRANSLATION FUNCTIONS =================
def translate_and_summarize(title, content):
    """English -> Persian title + multi-sentence summary (single JSON call)."""
    combined = (title.strip() + '. ' + (content or '').strip()).strip()
    combined = combined[:3500]
    if not combined:
        return "", ""

    system_prompt = ("You are a professional Persian financial news editor for an "
                     "Iranian economics Telegram channel.")
    user_prompt = TRANSLATE_PROMPT_TEMPLATE.replace('{NEWS}', combined)

    for temperature in (0.2, 0.1):
        raw = call_groq(system_prompt, user_prompt, max_tokens=900, temperature=temperature)
        if not raw:
            continue
        persian_title, persian_summary = _extract_title_summary(raw)
        if validate_title(persian_title):
            if not validate_summary(persian_summary):
                persian_summary = ""   # no good summary -> omit it
            return persian_title, persian_summary

    return "", ""


def translate_title_fallback(title):
    """Fallback: translate only the headline into a full Persian sentence."""
    prompt = TITLE_PROMPT_TEMPLATE.replace('{TITLE}', (title or '').strip()[:300])
    raw = call_groq("You are a professional Persian financial translator.",
                    prompt, max_tokens=200, temperature=0.1)
    if not raw:
        return ""
    persian = apply_persian_fixes(raw)
    if validate_title(persian, min_len=15):
        return persian
    return ""


def summarize_persian_content(title, content):
    """Summarize an already-Persian article into a few fluent Persian sentences."""
    content = (content or '').strip()[:3000]
    if not content:
        return ""
    prompt = (PERSIAN_SUMMARY_TEMPLATE
              .replace('{TITLE}', (title or '')[:200])
              .replace('{CONTENT}', content))
    raw = call_groq("ویراستار حرفه‌ای خبر اقتصادی فارسی هستی.",
                    prompt, max_tokens=600, temperature=0.3)
    if not raw:
        return ""
    candidate = apply_persian_fixes(raw)
    if validate_summary(candidate):
        return candidate
    return ""


# ================= MAIN PIPELINE =================
def translate_news_article(article):
    """
    Full translation pipeline. Returns (persian_title, persian_summary).
    - persian_summary is "" when no good summary could be produced.
    - Returns (None, None) when the article should be skipped.
    """
    title = article.get('title', '') or ''
    summary = article.get('summary', '') or ''
    content = article.get('content', '') or ''
    link = article.get('link', '') or ''

    if is_prohibited_source(link):
        print("  ✗ Prohibited source")
        return None, None

    full_text = content if len(content) > len(summary) else summary

    # ---------- Persian sources (e.g. Farsnews, Donya) ----------
    if is_persian_source(link) or detect_language(title) == 'fa':
        ok, reason = is_persian_economic(title, summary, content)
        if not ok:
            print(f"  ✗ Persian filter: {reason}")
            return None, None

        fixed_title = apply_persian_fixes(title)
        if not validate_title(fixed_title, min_len=12):
            print("  ✗ Persian title failed validation")
            return None, None

        persian_summary = ""
        if len(full_text) >= 300:
            print("  Summarizing Persian article...")
            persian_summary = summarize_persian_content(title, full_text)
        if not persian_summary and len(summary) >= 100:
            candidate = apply_persian_fixes(summary)
            if validate_summary(candidate):
                persian_summary = candidate
        return fixed_title, persian_summary

    # ---------- English sources ----------
    ok, reason = is_economic_news(title, summary, content)
    if not ok:
        print(f"  ✗ Filter: {reason}")
        return None, None

    print("  Translating to Persian (title + summary)...")
    persian_title, persian_summary = translate_and_summarize(title, full_text)

    if not persian_title:
        print("  JSON translation failed - trying title-only translation...")
        persian_title = translate_title_fallback(title)
        persian_summary = ""

    if not persian_title:
        print("  ✗ Translation failed")
        return None, None

    return persian_title, persian_summary


# ================= UTILITY =================
def detect_language(text):
    if not text:
        return "en"
    if re.search(r'[\u0600-\u06FF]', text):
        return "fa"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    return "en"
