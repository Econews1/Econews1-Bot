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

def translate_to_persian(text):
    """Translate via Groq API; fallback to a simple placeholder if no key."""
    if not GROQ_API_KEY:
        return "[NO TRANSLATION - ADD GROQ KEY] " + text
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}",
               "Content-Type": "application/json"}
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Translate this financial news text to Persian. Output only translation."},
            {"role": "user", "content": text}
        ],
        "max_tokens": 300,
        "temperature": 0.3
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'].strip()
        else:
            return f"[TRANSLATION ERROR {resp.status_code}] " + text
    except Exception as e:
        return f"[TRANSLATION FAILED] " + text

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
    summary_en = article['summary'][:300]  # truncate
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

    # Fetch new articles
    print("Fetching feeds...")
    all_articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:  # limit per feed for testing
                all_articles.append({
                    'id': entry.get('link', ''),
                    'title': entry.get('title', ''),
                    'summary': clean_html(entry.get('summary', '')),
                    'link': entry.get('link', ''),
                })
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # Combine pending + new, filter
    candidates = pending + all_articles
    relevant = []
    for art in candidates:
        if art['id'] in processed:
            continue
        text = (art['title'] + ' ' + art['summary']).lower()
        if any(kw in text for kw in KEYWORDS):
            relevant.append(art)

    # Sort by nothing (RSS order) then limit
    relevant = relevant[:MAX_POSTS_PER_RUN]

    if not relevant:
        print("No new relevant articles.")
        save_processed(processed)
        return

    # Post each with delay
    for i, art in enumerate(relevant):
        print(f"\n--- Article {i+1}/{len(relevant)} ---")
        msg = format_message(art)
        print(msg)   # Dry-run: print instead of Telegram post

        processed.add(art['id'])

        if i < len(relevant)-1:
            print(f"Waiting {POST_INTERVAL} seconds...")
            time.sleep(POST_INTERVAL)

    save_processed(processed)
    print("\nRun complete.")

if __name__ == "__main__":
    run()
