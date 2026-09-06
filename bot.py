import feedparser
import requests
import json
import os
import re
import time
import sys
import difflib

from config import *
from translator import *
from charts import send_price_charts

# ================= PERSIAN FONT SETUP (moved to translator, but re-export here if needed) =================
# For backward compatibility, if any code in bot.py uses setup_persian_font, import it:
from translator import setup_persian_font, to_persian_digits, fa

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
        return "اثر بر طلا: افزایش قیمت 📈"
    elif score <= -1:
        return "اثر بر طلا: کاهش قیمت 📉"
    else:
        return ""

def score_oil_sentiment(text):
    text_lower = text.lower()
    score = 0
    for w in OIL_BULLISH:
        if w in text_lower:
            score += 1
    for w in OIL_BEARISH:
        if w in text_lower:
            score -= 1
    return score

def oil_sentiment_label(score):
    if score >= 1:
        return "اثر بر نفت: افزایش قیمت 📈"
    elif score <= -1:
        return "اثر بر نفت: کاهش قیمت 📉"
    else:
        return ""

# ================= MEDIA EXTRACTION =================
def extract_media_urls(entry):
    image_url = ""
    video_url = ""
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            mtype = media.get('type', '')
            medium = media.get('medium', '')
            url = media.get('url', '')
            if medium == 'image' or mtype.startswith('image/'):
                if not image_url:
                    image_url = url
            elif medium == 'video' or mtype.startswith('video/'):
                if not video_url:
                    video_url = url
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        for thumb in entry.media_thumbnail:
            if not image_url:
                image_url = thumb.get('url', '')
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            etype = enc.get('type', '')
            if etype.startswith('image/') and not image_url:
                image_url = enc.get('href', '')
            elif etype.startswith('video/') and not video_url:
                video_url = enc.get('href', '')
    if hasattr(entry, 'links'):
        for link in entry.links:
            ltype = link.get('type', '')
            if link.get('rel') == 'enclosure' and ltype.startswith('image/') and not image_url:
                image_url = link.get('href', '')
            elif link.get('rel') == 'enclosure' and ltype.startswith('video/') and not video_url:
                video_url = link.get('href', '')
            elif ltype.startswith('image/') and not image_url:
                image_url = link.get('href', '')
            elif ltype.startswith('video/') and not video_url:
                video_url = link.get('href', '')
    return image_url, video_url

# ================= PRIORITY SCORING =================
def priority_score(article):
    score = 0
    text = (article.get('title', '') + ' ' + article.get('summary', '')).lower()
    if article.get('video_url'):
        score += 20
    elif article.get('image_url'):
        score += 15
    if re.search(r'[۰-۹0-9]', text):
        score += 5
    if len(article.get('summary', '')) > 100:
        score += 3
    if any(country in text for country in IMPORTANT_COUNTRIES):
        score += 10
    if any(term in text for term in CORE_PRICE_TERMS):
        score += 12
    gold_score = score_sentiment(text)
    oil_score = score_oil_sentiment(text) if any(kw in text for kw in ['oil', 'crude', 'brent', 'wti', 'opec', 'petroleum', 'energy']) else 0
    if abs(gold_score) >= 1 or abs(oil_score) >= 1:
        score += 8
    return score

# ================= FORMAT MESSAGE =================
def format_message(article):
    title_en = article.get('title', '')
    summary_en = article.get('summary', '')[:200]

    lang = detect_language(title_en + ' ' + summary_en)

    if lang == 'fa':
        persian_title = title_en
        persian_summary = summarize_persian(summary_en) if summary_en else ""
    else:
        simple_title_en = simplify_to_english(title_en)
        simple_summary_en = simplify_to_english(summary_en) if summary_en else ""
        persian_title = translate_english_to_persian(simple_title_en)
        persian_summary = translate_english_to_persian(simple_summary_en) if simple_summary_en else ""

    persian_title = apply_all_glossaries(persian_title)
    persian_summary = apply_all_glossaries(persian_summary)

    if persian_summary and title_en:
        t1 = re.sub(r'[^\w\s]', '', persian_title)
        t2 = re.sub(r'[^\w\s]', '', persian_summary)
        if len(t1) > 0 and len(t2) > 0:
            words1 = set(t1.split()[:8])
            words2 = set(t2.split()[:8])
            common = len(words1.intersection(words2))
            similarity = common / max(len(words1), len(words2))
            if similarity > 0.7:
                persian_summary = ""

    main_summary = ""
    extra_details = ""
    if persian_summary:
        parts = [p.strip() for p in re.split(r'[.!?]', persian_summary) if p.strip()]
        if parts:
            main_summary = parts[0] + '.'
            if len(parts) > 1:
                extra_details = '. '.join(parts[1:]) + '.'

    text_lower = (title_en + ' ' + summary_en).lower()
    gold_label = sentiment_label(score_sentiment(text_lower))
    is_oil = any(kw in text_lower for kw in ['oil', 'crude', 'brent', 'wti', 'opec', 'petroleum', 'energy'])
    oil_label = oil_sentiment_label(score_oil_sentiment(text_lower)) if is_oil else ""

    emoji = "📰"
    if is_oil:
        emoji = "🛢️"
    elif 'dollar' in text_lower or 'usd' in text_lower or 'dxy' in text_lower or 'fed' in text_lower:
        emoji = "💵"
    elif 'geopolitical' in text_lower or 'war' in text_lower or 'sanction' in text_lower:
        emoji = "🌍"

    msg = f"{emoji} <b>{persian_title}</b>\n"
    if main_summary:
        msg += "\n" + main_summary
    if extra_details:
        msg += "\n" + extra_details
    if gold_label or oil_label:
        sentiment_lines = []
        if gold_label:
            sentiment_lines.append(gold_label)
        if oil_label:
            sentiment_lines.append(oil_label)
        msg += "\n\n" + "\n".join(sentiment_lines)

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

# ================= STATE =================
def load_processed():
    if os.path.exists('processed_ids.json'):
        with open('processed_ids.json') as f:
            return set(json.load(f))
    return set()

def save_processed(ids):
    with open('processed_ids.json', 'w') as f:
        json.dump(list(ids)[-1000:], f)

def load_queue():
    if os.path.exists('queue.json'):
        with open('queue.json') as f:
            return json.load(f)
    return []

def save_queue(items):
    with open('queue.json', 'w') as f:
        json.dump(items, f)

def load_posted_titles():
    if os.path.exists('posted_titles.json'):
        with open('posted_titles.json') as f:
            return json.load(f)
    return []

def save_posted_titles(titles):
    with open('posted_titles.json', 'w') as f:
        json.dump(titles, f)

# ================= DUPLICATE DETECTION =================
STOPWORDS_EN = set([
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'until',
    'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to',
    'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
    'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
    'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
    'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now'
])

def normalize_title(title):
    text = title.lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = text.split()
    tokens = [t for t in tokens if t not in STOPWORDS_EN]
    return set(tokens)

def titles_are_similar(title1, title2, threshold=0.55):
    set1 = normalize_title(title1)
    set2 = normalize_title(title2)
    if not set1 or not set2:
        return False
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    score = intersection / union
    return score >= threshold

# ================= COLLECT NEWS =================
def collect_news():
    processed = load_processed()
    queue = load_queue()
    posted_titles = load_posted_titles()

    print("Fetching feeds...")
    all_articles = []
    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:5]:
                    image_url, video_url = extract_media_urls(entry)
                    all_articles.append({
                        'id': entry.get('link', ''),
                        'title': entry.get('title', ''),
                        'summary': clean_html(entry.get('summary', '')),
                        'link': entry.get('link', ''),
                        'image_url': image_url,
                        'video_url': video_url,
                    })
            else:
                print(f"Failed to fetch {url} (status {resp.status_code})")
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    relevant = []
    for art in all_articles:
        if art['id'] in processed:
            continue
        text = (art['title'] + ' ' + art['summary']).lower()
        lang = detect_language(art['title'] + ' ' + art['summary'])

        if lang == 'fa':
            if not any(kw in text for kw in PERSIAN_KEYWORDS):
                continue
        else:
            has_core = any(term in text for term in CORE_PRICE_TERMS)
            gold_score = score_sentiment(text)
            oil_score = score_oil_sentiment(text) if any(kw in text for kw in ['oil', 'crude', 'brent', 'wti', 'opec', 'petroleum', 'energy']) else 0
            if not (has_core or abs(gold_score) >= 1 or abs(oil_score) >= 1):
                continue

        if any(titles_are_similar(art['title'], t) for t in posted_titles):
            print(f"Skipping duplicate: {art['title']}")
            continue

        relevant.append(art)

    relevant_sorted = sorted(relevant, key=priority_score, reverse=True)
    new_articles = relevant_sorted[:MAX_POSTS_PER_RUN]

    for art in new_articles:
        if art not in queue:
            queue.append(art)
            processed.add(art['id'])
            posted_titles.append(art['title'])

    posted_titles = posted_titles[-200:]

    save_queue(queue)
    save_processed(processed)
    save_posted_titles(posted_titles)
    print(f"Collected {len(new_articles)} new articles. Queue size: {len(queue)}")

# ================= POST ONE ARTICLE =================
def post_one():
    queue = load_queue()
    if not queue:
        print("Queue is empty. Nothing to post.")
        return

    article = queue.pop(0)
    msg = format_message(article)
    if article.get('image_url'):
        send_to_telegram(msg, article['image_url'])
    elif article.get('video_url'):
        send_to_telegram(msg, article['video_url'])
    else:
        send_to_telegram(msg)

    save_queue(queue)

# ================= MAIN DISPATCHER =================
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "news"
    if mode == "collect":
        collect_news()
    elif mode == "post":
        post_one()
    elif mode == "chart":
        send_price_charts()
    elif mode == "weekly":
        weekly_summary()
    elif mode == "calendar":
        economic_calendar()
    else:
        print("Unknown mode. Use: collect, post, chart, weekly, calendar")
