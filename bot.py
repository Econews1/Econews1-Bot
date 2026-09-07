# bot.py

import feedparser
import requests
import json
import os
import re
import time
import sys
from datetime import datetime
from bs4 import BeautifulSoup

from config import *
from translator import *
from charts import send_price_charts, fetch_current_gold_oil, fetch_usd_toman_current


# ================= PRICE HISTORY =================
PRICE_HISTORY_FILE = "price_history.json"

def update_price_history():
    """Fetch current prices and append to history file, keeping last 48 entries."""
    try:
        gold, oil = fetch_current_gold_oil()
        usd = fetch_usd_toman_current()
        tether = usd  # USDT ≈ USD
        now = datetime.now().isoformat()
        entry = {
            'timestamp': now,
            'gold_usd': gold,
            'oil_usd': oil,
            'usd_toman': usd,
            'tether_toman': tether
        }
        
        # Load existing history
        history = []
        if os.path.exists(PRICE_HISTORY_FILE):
            with open(PRICE_HISTORY_FILE, 'r') as f:
                try:
                    history = json.load(f)
                except:
                    history = []
        
        # Append and limit to last 48 entries (24h if collected every 30min)
        history.append(entry)
        if len(history) > 48:
            history = history[-48:]
        
        with open(PRICE_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        
        print(f"  ✓ Price history updated: Gold ${gold:.2f}, Oil ${oil:.2f}, USD {usd:,.0f}")
    except Exception as e:
        print(f"  ⚠ Failed to update price history: {e}")


# ================= SENTIMENT =================
def score_gold_sentiment(text):
    """Score sentiment for gold impact."""
    text_lower = text.lower()
    score = 0
    for term in BULLISH_GOLD:
        if term in text_lower:
            score += 1
    for term in BEARISH_GOLD:
        if term in text_lower:
            score -= 1
    return score


def score_oil_sentiment(text):
    """Score sentiment for oil impact."""
    text_lower = text.lower()
    score = 0
    for term in BULLISH_OIL:
        if term in text_lower:
            score += 1
    for term in BEARISH_OIL:
        if term in text_lower:
            score -= 1
    return score


def get_sentiment_labels(text):
    """Get sentiment labels for gold and oil."""
    gold_score = score_gold_sentiment(text)
    oil_score = score_oil_sentiment(text)
    
    gold_label = ""
    if gold_score >= 2:
        gold_label = "📊 اثر بر طلا: صعودی 📈"
    elif gold_score == 1:
        gold_label = "📊 اثر بر طلا: کمی صعودی ↗"
    elif gold_score == 0:
        gold_label = "📊 اثر بر طلا: خنثی →"
    elif gold_score == -1:
        gold_label = "📊 اثر بر طلا: کمی نزولی ↘"
    else:
        gold_label = "📊 اثر بر طلا: نزولی 📉"
    
    oil_label = ""
    if any(kw in text.lower() for kw in ['oil', 'crude', 'brent', 'wti', 'opec', 'petroleum', 'energy']):
        if oil_score >= 2:
            oil_label = "🛢️ اثر بر نفت: صعودی 📈"
        elif oil_score == 1:
            oil_label = "🛢️ اثر بر نفت: کمی صعودی ↗"
        elif oil_score == 0:
            oil_label = "🛢️ اثر بر نفت: خنثی →"
        elif oil_score == -1:
            oil_label = "🛢️ اثر بر نفت: کمی نزولی ↘"
        else:
            oil_label = "🛢️ اثر بر نفت: نزولی 📉"
    
    return gold_label, oil_label


# ================= MEDIA EXTRACTION =================
def extract_image_url(entry):
    """Extract image URL from RSS entry."""
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if media.get('medium') == 'image' or media.get('type', '').startswith('image/'):
                url = media.get('url', '')
                if url and url.startswith('http'):
                    return url
    
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        for thumb in entry.media_thumbnail:
            url = thumb.get('url', '')
            if url and url.startswith('http'):
                return url
    
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                url = enc.get('href', '')
                if url and url.startswith('http'):
                    return url
    
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('type', '').startswith('image/'):
                url = link.get('href', '')
                if url and url.startswith('http'):
                    return url
    
    return ""


# ================= STATE MANAGEMENT =================
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
        json.dump(items, f, ensure_ascii=False)


def load_posted_titles():
    if os.path.exists('posted_titles.json'):
        with open('posted_titles.json') as f:
            return json.load(f)
    return []


def save_posted_titles(titles):
    with open('posted_titles.json', 'w') as f:
        json.dump(titles[-200:], f)


# ================= DUPLICATE DETECTION =================
def normalize_title(title):
    """Normalize title for duplicate detection."""
    text = title.lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = text.split()
    # Remove common stopwords
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'}
    tokens = [t for t in tokens if t not in stopwords]
    return set(tokens)


def titles_are_similar(title1, title2, threshold=0.6):
    """Check if two titles are similar enough to be duplicates."""
    set1 = normalize_title(title1)
    set2 = normalize_title(title2)
    if not set1 or not set2:
        return False
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    score = intersection / union
    return score >= threshold


# ================= SCRAPING FOR NON-RSS SOURCES =================
def scrape_farsnews():
    """Scrape economy news from Farsnews (category page)."""
    articles = []
    url = "https://farsnews.ir/Economy/posts"
    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            return articles
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Farsnews article links usually in <a> with href containing '/news/'
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            if href and '/news/' in href:
                # Construct full URL if relative
                if href.startswith('/'):
                    href = 'https://farsnews.ir' + href
                title = a.get_text(strip=True)
                if title and len(title) > 10:
                    articles.append({
                        'title': title,
                        'link': href,
                        'summary': '',
                        'image_url': ''
                    })
        # Limit to 5 most recent (first 5 found)
        return articles[:5]
    except Exception as e:
        print(f"  ⚠ Farsnews scraping error: {e}")
        return []


def scrape_donya():
    """Scrape economy news from Donya-e-Eqtesad (main page)."""
    articles = []
    url = "https://donya-e-eqtesad.com"
    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            return articles
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Look for article links – often in <h2> or <h3> with class
        for h in soup.find_all(['h2', 'h3']):
            a = h.find('a')
            if a and a.get('href'):
                href = a.get('href')
                if href.startswith('/'):
                    href = 'https://donya-e-eqtesad.com' + href
                title = a.get_text(strip=True)
                if title and len(title) > 10:
                    articles.append({
                        'title': title,
                        'link': href,
                        'summary': '',
                        'image_url': ''
                    })
        return articles[:5]
    except Exception as e:
        print(f"  ⚠ Donya scraping error: {e}")
        return []


def scrape_all_sources():
    """Collect articles from all non-RSS sources defined in SCRAPE_SOURCES."""
    all_articles = []
    for source in SCRAPE_SOURCES:
        if source['type'] == 'farsnews':
            articles = scrape_farsnews()
        elif source['type'] == 'donya':
            articles = scrape_donya()
        else:
            continue
        if articles:
            print(f"  Scraped {len(articles)} from {source['name']}")
            all_articles.extend(articles)
    return all_articles


# ================= NEWS COLLECTION =================
def collect_news():
    """Collect news from RSS feeds and scraped sources with strict filtering."""
    processed = load_processed()
    queue = load_queue()
    posted_titles = load_posted_titles()
    
    print("🔄 Fetching feeds...")
    all_articles = []
    
    # ---- RSS FEEDS ----
    for feed_url in RSS_FEEDS:
        # Skip prohibited sources
        if is_prohibited_source(feed_url):
            print(f"  ⚠ Skipping prohibited: {feed_url}")
            continue
        
        try:
            print(f"  Fetching: {feed_url}")
            resp = requests.get(
                feed_url,
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                entries = feed.entries[:3]  # Only 3 most recent
                
                for entry in entries:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    
                    if not title or not link:
                        continue
                    
                    # Check for prohibited sources in link
                    if is_prohibited_source(link):
                        continue
                    
                    # Check for duplicates
                    if link in processed:
                        continue
                    
                    if any(titles_are_similar(title, t) for t in posted_titles):
                        continue
                    
                    summary = clean_text(entry.get('summary', ''))[:200]
                    image_url = extract_image_url(entry)
                    
                    all_articles.append({
                        'title': title,
                        'summary': summary,
                        'link': link,
                        'image_url': image_url,
                    })
            else:
                print(f"  ✗ Status {resp.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"  ✗ Timeout")
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:50]}")
    
    # ---- SCRAPED SOURCES ----
    scraped = scrape_all_sources()
    for art in scraped:
        # Avoid duplicates by checking link
        if art['link'] not in processed and not any(titles_are_similar(art['title'], t) for t in posted_titles):
            all_articles.append(art)
    
    print(f"  Total articles: {len(all_articles)}")
    
    # Add to queue
    new_count = 0
    for article in all_articles:
        if article['link'] not in processed:
            queue.append(article)
            processed.add(article['link'])
            posted_titles.append(article['title'])
            new_count += 1
            
            if new_count >= MAX_POSTS_PER_RUN:
                break
    
    # --- UPDATE PRICE HISTORY ---
    update_price_history()
    
    # Save state
    save_queue(queue)
    save_processed(processed)
    save_posted_titles(posted_titles)
    
    print(f"✅ Collected {new_count} new articles. Queue: {len(queue)}")


# ================= POST NEWS =================
def post_one():
    """Post one article from the queue."""
    queue = load_queue()
    if not queue:
        print("ℹ Queue is empty.")
        return
    
    article = queue.pop(0)
    
    print(f"\n📢 Processing: {article['title'][:60]}...")
    
    # Translate through quality pipeline
    persian_title, persian_summary = translate_news_article(article)
    
    if not persian_title:
        print("  ✗ Translation failed - skipping")
        save_queue(queue)
        return
    
    print(f"  ✓ Persian: {persian_title[:50]}...")
    
    # Get sentiment
    gold_label, oil_label = get_sentiment_labels(
        article['title'] + ' ' + article['summary']
    )
    
    # Format message
    message = format_message(persian_title, persian_summary, gold_label, oil_label)
    
    # Send to Telegram
    send_to_telegram(message, article.get('image_url'))
    
    save_queue(queue)


def format_message(persian_title, persian_summary, gold_label, oil_label):
    """Format the final Telegram message."""
    
    # Determine emoji
    text_lower = persian_summary.lower() if persian_summary else ""
    if any(w in text_lower for w in ['طلا', 'سکه', 'نقره']):
        emoji = "🥇"
    elif any(w in text_lower for w in ['نفت', 'برنت', 'اوپک']):
        emoji = "🛢️"
    elif any(w in text_lower for w in ['دلار', 'ارز', 'یورو']):
        emoji = "💵"
    else:
        emoji = "📊"
    
    # Build message
    msg = f"{emoji} <b>{persian_title}</b>\n\n"
    
    if persian_summary:
        msg += f"{persian_summary}\n\n"
    
    # Add sentiment labels
    sentiment_parts = []
    if gold_label:
        sentiment_parts.append(gold_label)
    if oil_label:
        sentiment_parts.append(oil_label)
    
    if sentiment_parts:
        msg += '\n'.join(sentiment_parts) + "\n"
    
    return msg


def send_to_telegram(message, image_url=None):
    """Send message to Telegram channel."""
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("  ⚠ Telegram not configured. Preview:")
        print(f"  {message[:150]}...")
        return False
    
    # If image available, try to send as photo
    if image_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            'chat_id': CHANNEL_ID,
            'photo': image_url,
            'caption': message[:1024],
            'parse_mode': 'HTML'
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                print("  ✓ Posted with image")
                return True
        except Exception as e:
            print(f"  ⚠ Photo error: {e}")
    
    # Send as text message
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHANNEL_ID,
        'text': message[:4096],
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            print("  ✓ Posted successfully")
            return True
        else:
            print(f"  ✗ Failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


# ================= WEEKLY SUMMARY =================
def weekly_summary():
    """Send weekly market summary."""
    summary = (
        "📅 <b>خلاصه هفتگی بازار</b>\n\n"
        "🥇 <b>طلا:</b>\n"
        "   تغییر هفته: +۲.۱٪\n\n"
        "💵 <b>دلار/تومان:</b>\n"
        "   تغییر هفته: -۰.۵٪\n\n"
        "🛢️ <b>نفت برنت:</b>\n"
        "   تغییر هفته: +۰.۸٪\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 بازارها این هفته تحت تأثیر تصمیمات فدرال رزرو و داده‌های تورم قرار گرفتند."
    )
    send_to_telegram(summary)


# ================= ECONOMIC CALENDAR =================
def economic_calendar():
    """Send upcoming economic events."""
    events = [
        ("امروز", "CPI آمریکا", "۱۶:۳۰", "🔴 بسیار مهم"),
        ("فردا", "NFP (اشتغال)", "۱۴:۳۰", "🔴 بسیار مهم"),
        ("سه‌شنبه", "تصمیم نرخ بهره فدرال رزرو", "۲۱:۰۰", "🔴 بسیار مهم"),
        ("چهارشنبه", "نشست بانک مرکزی اروپا", "۱۴:۰۰", "🟡 مهم"),
        ("پنج‌شنبه", "داده‌های تورم منطقه یورو", "۱۱:۰۰", "🟡 مهم"),
    ]
    
    msg = "📅 <b>رویدادهای اقتصادی پیش‌رو</b>\n"
    msg += "━━━━━━━━━━━━━━━\n\n"
    
    for day, event, time_, importance in events:
        msg += f"{importance} <b>{event}</b>\n"
        msg += f"   📆 {day} | 🕐 {time_}\n\n"
    
    msg += "━━━━━━━━━━━━━━━\n"
    msg += "💡 <i>زمان‌ها به وقت تهران</i>"
    
    send_to_telegram(msg)


# ================= MAIN =================
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "collect"
    
    print(f"🤖 Econews Bot - Mode: {mode}")
    print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"   Groq API: {'✓' if GROQ_API_KEY else '✗'}")
    print(f"   Telegram: {'✓' if TELEGRAM_BOT_TOKEN else '✗'}")
    print()
    
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
    elif mode == "run":
        # Full cycle: collect then post
        collect_news()
        time.sleep(5)
        post_one()
    else:
        print(f"Unknown mode: {mode}")
        print("Available modes: collect, post, chart, weekly, calendar, run")
