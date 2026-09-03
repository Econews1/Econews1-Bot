import feedparser
import requests
import json
import os
import re
import time
from datetime import datetime

# ================= CONFIGURATION =================
RSS_FEEDS = [
    "https://www.forexlive.com/feed/news",
    "https://www.fxstreet.com/rss/news",
    "https://www.kitco.com/news/rss",
    "https://oilprice.com/rss/main",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.bls.gov/feed/bls_latest.rss",
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.eia.gov/rss/todayinenergy.xml",
]

POST_INTERVAL = 10      # seconds (use 360 for production)
MAX_POSTS_PER_RUN = 5
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Known non-reasoning models to try first
PREFERRED_MODELS = [
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
]

# Fallback if preferred models fail (reasoning or others)
FALLBACK_MODELS = [
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]

# File to cache the last working model
MODEL_CACHE_FILE = "last_working_model.txt"

# ================= KEYWORD FILTER =================
KEYWORDS = [
    'gold', 'xau', 'dollar', 'dxy', 'fed', 'rate', 'inflation',
    'cpi', 'oil', 'crude', 'brent', 'wti', 'opec', 'gdp', 'nfp',
    'treasury', 'yield', 'sanction', 'geopolitical', 'recession'
]

BULLISH = ['rate cut', 'weak dollar', 'geopolitical tension', 'recession',
           'inflation', 'safe haven', 'central bank buying', 'stimulus',
           'dovish', 'crisis', 'war']
BEARISH = ['rate hike', 'strong dollar', 'risk appetite', 'higher yields',
           'hawkish', 'economic growth', 'optimism', 'risk-on', 'tightening']

# ================= HELPER FUNCTIONS =================
def clean_html(text):
    return re.sub('<.*?>', '', text)

def get_groq_models():
    """Fetch list of active models from Groq API."""
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = [m['id'] for m in data.get('data', []) if m.get('active', False)]
            return models
        else:
            print(f"Failed to fetch models: {resp.status_code} {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

def extract_translation(raw_output):
    """Remove any thinking block and return only the final translation."""
    if not raw_output:
        return ""
    # If there is a closing think tag, take text after it
    if '</think>' in raw_output:
        raw_output = raw_output.split('</think>')[-1].strip()
    # Also remove any leading <think> block (in case of malformed output)
    raw_output = re.sub(r'^<think>.*?(?=<think>|$)', '', raw_output, flags=re.DOTALL).strip()
    return raw_output

def load_cached_model():
    """Load the last successful model ID from file."""
    if os.path.exists(MODEL_CACHE_FILE):
        with open(MODEL_CACHE_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_cached_model(model_id):
    """Save the successful model ID to file."""
    with open(MODEL_CACHE_FILE, 'w') as f:
        f.write(model_id)

def try_translate_with_model(text, model):
    """Attempt translation with a specific model. Return cleaned translation or None."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional financial translator. Translate the following financial news text to Persian. Output only the translation."},
            {"role": "user", "content": text}
        ],
        "max_tokens": 8000,   # High enough for reasoning models
        "temperature": 0.3
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        print(f"  Trying model {model} -> status {resp.status_code}")
        if resp.status_code == 200:
            raw = resp.json()['choices'][0]['message']['content'].strip()
            cleaned = extract_translation(raw)
            if cleaned and len(cleaned) > 5:
                return cleaned
            else:
                print(f"  Model {model} returned empty translation.")
                return None
        else:
            print(f"  Model {model} failed: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  Model {model} exception: {e}")
        return None

def translate_to_persian(text):
    """Translate text to Persian, automatically selecting the best available model."""
    if not GROQ_API_KEY:
        return text  # fallback to original English

    # 1. Try cached model first
    cached_model = load_cached_model()
    if cached_model:
        print(f"Trying cached model: {cached_model}")
        result = try_translate_with_model(text, cached_model)
        if result:
            return result
        else:
            print("Cached model failed, removing cache.")
            if os.path.exists(MODEL_CACHE_FILE):
                os.remove(MODEL_CACHE_FILE)

    # 2. Try preferred non-reasoning models
    for model in PREFERRED_MODELS:
        result = try_translate_with_model(text, model)
        if result:
            save_cached_model(model)
            return result

    # 3. Try fallback models (may include reasoning)
    for model in FALLBACK_MODELS:
        result = try_translate_with_model(text, model)
        if result:
            save_cached_model(model)
            return result

    # 4. Dynamic discovery: fetch all active models and try them
    print("All known models failed. Fetching active models...")
    active_models = get_groq_models()
    # Sort models: prefer those without "qwen" or "reasoning" in name
    def is_preferred(m):
        lower = m.lower()
        return 'qwen' not in lower and 'reason' not in lower
    sorted_models = sorted(active_models, key=lambda m: not is_preferred(m))

    for model in sorted_models:
        result = try_translate_with_model(text, model)
        if result:
            save_cached_model(model)
            return result

    # If everything fails, return original English
    return text

def score_sentiment(text):
    text_lower = text.lower()
    score = 0
    for w in BULLISH:
        if w in text_lower:
            score += 1
    for w in BEARISH:
        if w in text_lower:
            score -= 1
    return score

def sentiment_label(score):
    if score >= 1:
        return "اثر بر طلا: احتمالاً مثبت 📈"
    elif score <= -1:
        return "اثر بر طلا: احتمالاً منفی 📉"
    else:
        return "اثر بر طلا: خنثی ➖"

def format_message(article):
    title_en = article['title']
    summary_en = article['summary'][:200]
    persian_title = translate_to_persian(title_en)
    persian_summary = translate_to_persian(summary_en)
    score = score_sentiment(title_en + ' ' + summary_en)
    label = sentiment_label(score)

    msg = f"📰 <b>{persian_title}</b>\n\n"
    msg += f"{persian_summary}\n\n"
    msg += f"{label}\n\n"
    msg += f"🔗 <a href='{article['link']}'>مشاهده کامل</a>"
    return msg

# ================= STATE =================
def load_processed():
    if os.path.exists('processed_ids.json'):
        with open('processed_ids.json') as f:
            return set(json.load(f))
    return set()

def save_processed(ids):
    with open('processed_ids.json', 'w') as f:
        json.dump(list(ids)[-1000:], f)

def load_pending():
    if os.path.exists('pending_queue.json'):
        with open('pending_queue.json') as f:
            data = json.load(f)
        os.remove('pending_queue.json')
        return data
    return []

def save_pending(items):
    with open('pending_queue.json', 'w') as f:
        json.dump(items, f)

# ================= MAIN =================
def run():
    processed = load_processed()
    pending = load_pending()

    print("Fetching feeds...")
    all_articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                all_articles.append({
                    'id': entry.get('link', ''),
                    'title': entry.get('title', ''),
                    'summary': clean_html(entry.get('summary', '')),
                    'link': entry.get('link', ''),
                })
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    candidates = pending + all_articles
    relevant = []
    for art in candidates:
        if art['id'] in processed:
            continue
        text = (art['title'] + ' ' + art['summary']).lower()
        if any(kw in text for kw in KEYWORDS):
            relevant.append(art)

    relevant = relevant[:MAX_POSTS_PER_RUN]

    if not relevant:
        print("No new relevant articles.")
        save_processed(processed)
        return

    for i, art in enumerate(relevant):
        print(f"\n--- Article {i+1}/{len(relevant)} ---")
        msg = format_message(art)
        print(msg)

        processed.add(art['id'])

        if i < len(relevant)-1:
            print(f"Waiting {POST_INTERVAL} seconds...")
            time.sleep(POST_INTERVAL)

    save_processed(processed)
    print("\nRun complete.")

if __name__ == "__main__":
    run()
