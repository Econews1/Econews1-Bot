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

# Candidate models to try first (in order)
CANDIDATE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama3-8b-8192",          # likely decommissioned, but kept as fallback
    "mixtral-8x7b-32768"
]

# Cache for dynamically discovered model
_discovered_model = None

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
    """Fetch list of available models from Groq API."""
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = []
            for m in data.get('data', []):
                if m.get('active', False):
                    models.append(m['id'])
            return models
        else:
            print(f"Failed to fetch models: {resp.status_code} {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

def get_translation_model():
    """Return a working model ID, trying candidates first then falling back to dynamic discovery."""
    global _discovered_model
    # First check if we already found a model earlier in this run
    if _discovered_model:
        return _discovered_model

    # Try candidate models one by one in a quick test (can reuse translation function later)
    # But we need to test them in actual translation; we'll handle that in translate_to_persian.
    # For now, we just return the first candidate; the translation loop will try others if it fails.
    for model in CANDIDATE_MODELS:
        # We'll do a minimal test: just attempt a trivial translation and check status.
        # To avoid extra API calls, we could directly attempt the real translation and see if it fails.
        # Here we'll just return the first candidate; the translate function will iterate through candidates on failure.
        return model
    # If all candidates are bad (shouldn't happen since we return first), we do dynamic discovery.
    models = get_groq_models()
    if models:
        # Prefer models containing "llama" or "mixtral"
        preferred = [m for m in models if 'llama' in m or 'mixtral' in m]
        if preferred:
            _discovered_model = preferred[0]
        else:
            _discovered_model = models[0]
        return _discovered_model
    return None

def translate_to_persian(text):
    """Translate English text to Persian, trying multiple models automatically."""
    if not GROQ_API_KEY:
        return "[NO TRANSLATION - ADD GROQ KEY] " + text

    global _discovered_model

    # List of models to try, in order
    models_to_try = CANDIDATE_MODELS.copy()
    if _discovered_model and _discovered_model not in models_to_try:
        models_to_try.insert(0, _discovered_model)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    for model in models_to_try:
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Translate this financial news text to Persian. Output only translation."},
                {"role": "user", "content": text}
            ],
            "max_tokens": 300,
            "temperature": 0.3
        }
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"Trying model {model} -> status {resp.status_code}")
            if resp.status_code == 200:
                # Success, cache this model
                _discovered_model = model
                return resp.json()['choices'][0]['message']['content'].strip()
            else:
                print(f"Model {model} failed: {resp.text[:200]}")
                continue  # try next model
        except Exception as e:
            print(f"Model {model} exception: {e}")
            continue

    # If all candidates fail, try dynamic discovery
    print("All candidate models failed. Fetching available models...")
    available = get_groq_models()
    for model in available:
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Translate this financial news text to Persian. Output only translation."},
                {"role": "user", "content": text}
            ],
            "max_tokens": 300,
            "temperature": 0.3
        }
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            print(f"Trying dynamically discovered model {model} -> status {resp.status_code}")
            if resp.status_code == 200:
                _discovered_model = model
                return resp.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Dynamic model {model} exception: {e}")
            continue

    # If nothing works, return original text with error
    return "[TRANSLATION FAILED] " + text

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
    summary_en = article['summary'][:300]
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
