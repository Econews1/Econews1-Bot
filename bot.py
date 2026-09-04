import feedparser
import requests
import json
import os
import re
import time
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from datetime import datetime, timedelta
import arabic_reshaper
from bidi.algorithm import get_display

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

POST_INTERVAL = 10          # seconds (use 360 for production)
MAX_POSTS_PER_RUN = 5
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")

# Known non-reasoning models to try first
PREFERRED_MODELS = [
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
]

FALLBACK_MODELS = [
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]

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

# ================= PERSIAN FONT SETUP =================
def setup_persian_font():
    """Download a bold Persian font (Vazirmatn Bold) and register it."""
    urls = [
        "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf",
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf",
        "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Bold.ttf"
    ]
    font_path = "persian_font.ttf"
    if not os.path.exists(font_path):
        for url in urls:
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    with open(font_path, 'wb') as f:
                        f.write(r.content)
                    break
            except Exception:
                continue
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = prop.get_name()
        print("Persian font loaded.")
    else:
        print("Warning: Persian font not downloaded. Using default font.")

# ================= TRANSLATION (self-healing) =================
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
    """Check if the model output indicates a refusal or error."""
    refusal_phrases = [
        "i'm sorry",
        "i am sorry",
        "i can't",
        "i cannot",
        "can't help",
        "cannot help",
        "not able to",
        "unable to",
        "i apologize",
        "sorry, but",
        "i'm not able",
        "i am not able",
        "i won't",
        "i will not"
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in refusal_phrases)

def load_cached_model():
    if os.path.exists(MODEL_CACHE_FILE):
        with open(MODEL_CACHE_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_cached_model(model_id):
    with open(MODEL_CACHE_FILE, 'w') as f:
        f.write(model_id)

def try_translate_with_model(text, model):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional financial translator. Translate the user's financial news text to Persian. Never refuse, never apologize, just output the translation. Do not include any reasoning, thinking, or analysis."},
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
            # Reject if model returned system prompt, refusal, or junk
            if any(phrase in cleaned for phrase in ["متن خبری مالی را", "لطفاً متن خبری", "Translate the user's financial news"]):
                print("  Model returned system prompt, skipping.")
                return None
            if is_refusal(cleaned):
                print("  Model refused, skipping.")
                return None
            if cleaned and len(cleaned) > 5:
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

def translate_to_persian(text):
    if not GROQ_API_KEY:
        return text
    cached = load_cached_model()
    if cached:
        print(f"Trying cached model: {cached}")
        result = try_translate_with_model(text, cached)
        if result:
            return result
        else:
            if os.path.exists(MODEL_CACHE_FILE):
                os.remove(MODEL_CACHE_FILE)
    for model in PREFERRED_MODELS:
        result = try_translate_with_model(text, model)
        if result:
            save_cached_model(model)
            return result
    for model in FALLBACK_MODELS:
        result = try_translate_with_model(text, model)
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
        result = try_translate_with_model(text, model)
        if result:
            save_cached_model(model)
            return result
    return text

# ================= SENTIMENT =================
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

# ================= IMAGE EXTRACTION =================
def extract_image_url(entry):
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if media.get('medium') == 'image' or media.get('type', '').startswith('image/'):
                return media.get('url', '')
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href', '')
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('rel') == 'enclosure' and link.get('type', '').startswith('image/'):
                return link.get('href', '')
            if link.get('type', '').startswith('image/'):
                return link.get('href', '')
    return ''

# ================= FORMAT MESSAGE =================
def format_message(article, include_link=True):
    title_en = article['title']
    summary_en = article['summary'][:200]
    persian_title = translate_to_persian(title_en)
    persian_summary = translate_to_persian(summary_en)
    score = score_sentiment(title_en + ' ' + summary_en)
    label = sentiment_label(score)

    text_lower = (title_en + ' ' + summary_en).lower()
    if 'oil' in text_lower or 'crude' in text_lower or 'opec' in text_lower:
        emoji = "🛢️"
    elif 'dollar' in text_lower or 'usd' in text_lower or 'dxy' in text_lower or 'fed' in text_lower:
        emoji = "💵"
    elif 'geopolitical' in text_lower or 'war' in text_lower or 'sanction' in text_lower:
        emoji = "🌍"
    else:
        emoji = "📰"

    tldr = persian_summary.split('.')[0] if '.' in persian_summary else persian_summary[:80]

    msg = f"{emoji} <b>{persian_title}</b>\n"
    msg += f"<i>خلاصه:</i> {tldr}\n\n"
    msg += persian_summary + "\n\n"
    msg += label

    if include_link and article.get('link'):
        msg += f"\n\n🔗 <a href='{article['link']}'>مشاهده کامل</a>"

    return msg

# ================= SEND TO TELEGRAM =================
def send_to_telegram(message, image_url=None):
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("Telegram not configured. Printing message:\n", message)
        return
    if image_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {'chat_id': CHANNEL_ID, 'photo': image_url, 'caption': message, 'parse_mode': 'HTML'}
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                print("Photo sent.")
                return
            else:
                print(f"sendPhoto failed ({resp.status_code}), falling back to text.")
        except Exception as e:
            print(f"sendPhoto exception: {e}, falling back to text.")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHANNEL_ID, 'text': message, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            print("Message sent.")
        else:
            print(f"sendMessage failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"sendMessage exception: {e}")

# ================= PRICE CHART =================
def generate_price_chart():
    """Generate a simple line chart for gold, USD/IRT, oil using mock data."""
    setup_persian_font()

    hours = list(range(0, 24, 2))
    gold_prices = [2030 + i*2 for i in range(len(hours))]
    usd_irt = [52000 + i*100 for i in range(len(hours))]
    oil_prices = [82 + i*0.5 for i in range(len(hours))]

    usd_irt_scaled = [x / 100 for x in usd_irt]

    def fa(text):
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)

    plt.figure(figsize=(10, 6))
    plt.plot(hours, gold_prices, label=fa('طلا (XAU/USD)'), color='gold', linewidth=2)
    plt.plot(hours, usd_irt_scaled, label=fa('دلار/تومان (مقیاس ۱/۱۰۰)'), color='blue', linewidth=2)
    plt.plot(hours, oil_prices, label=fa('نفت (Brent)'), color='green', linewidth=2)
    plt.xlabel(fa('ساعت'))
    plt.ylabel(fa('قیمت'))
    plt.title(fa('نمودار قیمت‌های لحظه‌ای'))
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()

    chart_path = "price_chart.png"
    plt.savefig(chart_path, dpi=150)
    plt.close()
    return chart_path

def send_price_chart():
    chart_path = generate_price_chart()
    caption = "📊 <b>نمودار قیمت‌ها</b>\nطلا، دلار و نفت در ۲۴ ساعت گذشته"
    with open(chart_path, 'rb') as photo:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': photo}
        data = {'chat_id': CHANNEL_ID, 'caption': caption, 'parse_mode': 'HTML'}
        resp = requests.post(url, data=data, files=files)
        print(f"Chart sent: {resp.status_code}")
    os.remove(chart_path)

# ================= WEEKLY SUMMARY =================
def weekly_summary():
    summary = (
        "📅 <b>خلاصه هفتگی بازار</b>\n\n"
        "🟡 طلا: +۲.۱٪\n"
        "💵 دلار/تومان: -۰.۵٪\n"
        "🛢️ نفت: +۰.۸٪\n\n"
        "بازارها این هفته تحت تأثیر تصمیم فدرال رزرو و داده‌های تورم قرار گرفتند."
    )
    send_to_telegram(summary)

# ================= ECONOMIC CALENDAR =================
def economic_calendar():
    events = [
        ("امروز", "CPI آمریکا", "ساعت ۱۶:۳۰"),
        ("فردا", "نرخ بیکاری", "ساعت ۱۷:۰۰"),
        ("پنج‌شنبه", "نشست فدرال رزرو", "ساعت ۲۱:۳۰"),
    ]
    msg = "📅 <b>رویدادهای اقتصادی پیش‌رو</b>\n\n"
    for day, event, time_ in events:
        msg += f"▫️ {day}: {event} – {time_}\n"
    send_to_telegram(msg)

# ================= MAIN NEWS COLLECTION & POSTING =================
def run_news():
    processed = load_processed()
    pending = load_pending()

    print("Fetching feeds...")
    all_articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                image_url = extract_image_url(entry)
                all_articles.append({
                    'id': entry.get('link', ''),
                    'title': entry.get('title', ''),
                    'summary': clean_html(entry.get('summary', '')),
                    'link': entry.get('link', ''),
                    'image_url': image_url,
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
        if art.get('image_url'):
            msg = format_message(art, include_link=False)
            send_to_telegram(msg, art['image_url'])
        else:
            msg = format_message(art, include_link=True)
            send_to_telegram(msg)

        processed.add(art['id'])

        if i < len(relevant)-1:
            print(f"Waiting {POST_INTERVAL} seconds...")
            time.sleep(POST_INTERVAL)

    save_processed(processed)
    print("\nNews run complete.")

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

# ================= MAIN DISPATCHER =================
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "news"
    if mode == "news":
        run_news()
    elif mode == "chart":
        send_price_chart()
    elif mode == "weekly":
        weekly_summary()
    elif mode == "calendar":
        economic_calendar()
    else:
        print("Unknown mode. Use: news, chart, weekly, calendar")
