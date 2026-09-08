# bot.py

import feedparser
import requests
import json
import os
import re
import time
import sys
import html as html_lib
from datetime import datetime
from bs4 import BeautifulSoup

from config import *
from translator import *
from charts import send_price_charts, fetch_current_gold_oil, fetch_usd_toman_current

# ---------- Optional settings (can be overridden in config.py) ----------
if 'MAX_POST_ATTEMPTS' not in globals():
    MAX_POST_ATTEMPTS = 10        # queue items tried per "post" run
if 'SCRAPE_PAGE_LIMIT' not in globals():
    SCRAPE_PAGE_LIMIT = 8         # max articles taken from each scraped site
if 'ENRICH_ARTICLES' not in globals():
    ENRICH_ARTICLES = True        # fetch full article text/media before posting
if 'MAX_POSTS_PER_RUN' not in globals():
    MAX_POSTS_PER_RUN = 5
if 'RSS_FEEDS' not in globals():
    RSS_FEEDS = []
if 'SCRAPE_SOURCES' not in globals():
    SCRAPE_SOURCES = [
        {'name': 'Farsnews Economy', 'type': 'farsnews'},
        {'name': 'Donya-e-Eqtesad', 'type': 'donya'},
    ]
if 'TELEGRAM_BOT_TOKEN' not in globals():
    TELEGRAM_BOT_TOKEN = ''
if 'CHANNEL_ID' not in globals():
    CHANNEL_ID = ''
if 'BULLISH_GOLD' not in globals(): BULLISH_GOLD = []
if 'BEARISH_GOLD' not in globals(): BEARISH_GOLD = []
if 'BULLISH_OIL' not in globals(): BULLISH_OIL = []
if 'BEARISH_OIL' not in globals(): BEARISH_OIL = []

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass


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

        history = []
        if os.path.exists(PRICE_HISTORY_FILE):
            with open(PRICE_HISTORY_FILE, 'r') as f:
                try:
                    history = json.load(f)
                except Exception:
                    history = []

        history.append(entry)
        if len(history) > 48:
            history = history[-48:]

        with open(PRICE_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)

        print(f"  ✓ Price history updated: Gold ${gold:.2f}, Oil ${oil:.2f}, USD {usd:,.0f}")
    except Exception as e:
        print(f"  ⚠ Failed to update price history: {e}")


# ================= SENTIMENT =================
OIL_KEYWORDS = ['oil', 'crude', 'brent', 'wti', 'opec', 'petroleum', 'energy', 'barrel',
                'نفت', 'برنت', 'اوپک', 'بشکه', 'انرژی']

def score_gold_sentiment(text):
    text = (text or '').lower()
    score = 0
    for term in BULLISH_GOLD:
        if term in text:
            score += 1
    for term in BEARISH_GOLD:
        if term in text:
            score -= 1
    return score


def score_oil_sentiment(text):
    text = (text or '').lower()
    score = 0
    for term in BULLISH_OIL:
        if term in text:
            score += 1
    for term in BEARISH_OIL:
        if term in text:
            score -= 1
    return score


def get_sentiment_labels(text):
    """Sentiment labels with proper up/down arrows (green up, red down)."""
    text = text or ''
    text_lower = text.lower()
    gold_score = score_gold_sentiment(text)
    oil_score = score_oil_sentiment(text)

    if gold_score >= 2:
        gold_label = "📊 اثر بر طلا: صعودی 🟢↗️"
    elif gold_score == 1:
        gold_label = "📊 اثر بر طلا: کمی صعودی 🟢↗"
    elif gold_score == 0:
        gold_label = "📊 اثر بر طلا: خنثی ⚪➡️"
    elif gold_score == -1:
        gold_label = "📊 اثر بر طلا: کمی نزولی 🔴↘"
    else:
        gold_label = "📊 اثر بر طلا: نزولی 🔴↘️"

    oil_label = ""
    if any(kw in text_lower for kw in OIL_KEYWORDS):
        if oil_score >= 2:
            oil_label = "🛢️ اثر بر نفت: صعودی 🟢↗️"
        elif oil_score == 1:
            oil_label = "🛢️ اثر بر نفت: کمی صعودی 🟢↗"
        elif oil_score == 0:
            oil_label = "🛢️ اثر بر نفت: خنثی ⚪➡️"
        elif oil_score == -1:
            oil_label = "🛢️ اثر بر نفت: کمی نزولی 🔴↘"
        else:
            oil_label = "🛢️ اثر بر نفت: نزولی 🔴↘️"

    return gold_label, oil_label


# ================= RSS MEDIA EXTRACTION =================
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
    text = (title or '').lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = text.split()
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
                 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'}
    tokens = [t for t in tokens if t not in stopwords]
    return set(tokens)


def titles_are_similar(title1, title2, threshold=0.6):
    set1 = normalize_title(title1)
    set2 = normalize_title(title2)
    if not set1 or not set2:
        return False
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return union > 0 and (intersection / union) >= threshold


# ================= ROBUST HTTP HELPERS =================
BROWSER_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
    'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
               'image/avif,image/webp,*/*;q=0.8'),
    'Accept-Language': 'fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}


def _make_legacy_tls_session():
    """Session tolerant of the old TLS configurations used by some Iranian sites."""
    session = requests.Session()
    try:
        import ssl as _ssl
        from requests.adapters import HTTPAdapter
        try:
            from urllib3.util.ssl_ import create_urllib3_context
        except ImportError:
            return session

        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        try:
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass

        class LegacyTLSAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs['ssl_context'] = ctx
                return super().init_poolmanager(*args, **kwargs)

        session.mount('https://', LegacyTLSAdapter())
    except Exception as e:
        print(f"  ⚠ Legacy TLS adapter unavailable: {e}")
    return session


def robust_get(url, timeout=20, headers=None):
    """GET with browser headers; retry with legacy TLS session on SSL/network failure."""
    hdrs = dict(BROWSER_HEADERS)
    if headers:
        hdrs.update(headers)

    resp = None
    try:
        resp = requests.get(url, timeout=timeout, headers=hdrs)
        if resp.status_code == 200:
            return resp
        print(f"  ⚠ Status {resp.status_code} on {url[:60]}")
    except requests.exceptions.SSLError:
        print(f"  ⚠ SSL error on {url[:60]} - retrying with legacy TLS")
        resp = None
    except Exception as e:
        print(f"  ⚠ {type(e).__name__} on {url[:60]}")
        resp = None

    try:
        session = _make_legacy_tls_session()
        r2 = session.get(url, timeout=timeout, headers=hdrs, verify=False)
        if r2.status_code == 200:
            return r2
        print(f"  ⚠ Retry status {r2.status_code} on {url[:60]}")
    except Exception as e:
        print(f"  ⚠ Legacy retry failed on {url[:60]}: {type(e).__name__}")
    return None


# ================= SCRAPING FOR NON-RSS SOURCES =================
FARSNEWS_NEWS_LINK_RE = re.compile(r'/news/(\d{8,})')
_URL_KEYS = ('site_url', 'siteurl', 'url', 'link', 'href', 'path', 'news_url', 'newsurl')
_SHORT_KEYS = ('short_address', 'shortaddress', 'short_link', 'shortlink')


def _normalize_farsnews_link(href):
    if not href:
        return None, None
    href = href.strip().split('?')[0].split('#')[0]
    if href.startswith('//'):
        href = 'https:' + href
    m = FARSNEWS_NEWS_LINK_RE.search(href)
    if not m:
        return None, None
    news_id = m.group(1)
    if href.startswith('http'):
        link = href
    elif href.startswith('/'):
        link = 'https://farsnews.ir' + href
    else:
        link = f'https://farsnews.ir/news/{news_id}'
    return news_id, link


def _find_farsnews_link(node):
    """Find an article link inside a Farsnews JSON node."""
    for k, v in node.items():
        if not isinstance(v, str):
            continue
        kl = str(k).lower()
        val = v.strip()
        if not val:
            continue
        if kl in _URL_KEYS or kl in _SHORT_KEYS:
            if FARSNEWS_NEWS_LINK_RE.search(val):
                return val
            if kl in _SHORT_KEYS and re.match(r'^\d{8,}', val):
                return f"/news/{val}"
    # last resort: any string value that is a real /news/ path
    for v in node.values():
        if isinstance(v, str) and (v.startswith('http') or v.startswith('/')) \
                and FARSNEWS_NEWS_LINK_RE.search(v):
            return v
    return None


def _extract_image_from_node(node):
    for k, v in node.items():
        kl = str(k).lower()
        if isinstance(v, str) and v.startswith('http') and \
                any(t in kl for t in ('image', 'picture', 'photo', 'img', 'thumb', 'cover')):
            return v
        if isinstance(v, dict) and any(t in kl for t in ('image', 'picture', 'photo', 'media', 'cover')):
            for kk in ('url', 'main', 'original', 'full', 'path', 'src'):
                u = v.get(kk)
                if isinstance(u, str) and u:
                    if u.startswith('http'):
                        return u
                    if u.startswith('//'):
                        return 'https:' + u
        if isinstance(v, list) and v and isinstance(v[0], dict) and \
                any(t in kl for t in ('image', 'picture', 'photo', 'media')):
            u = v[0].get('url') or v[0].get('main') or v[0].get('original')
            if isinstance(u, str) and u.startswith('http'):
                return u
    return None


def _collect_json_news_items(node, found):
    """Recursively collect article-like dicts from Next.js __NEXT_DATA__ / JSON-LD."""
    if isinstance(node, dict):
        title = None
        for k in ('title', 'Title', 'titr', 'headline', 'name'):
            v = node.get(k)
            if isinstance(v, str) and 10 <= len(v.strip()) <= 250:
                title = v.strip()
                break
        if title:
            raw_link = _find_farsnews_link(node)
            if raw_link:
                _, full_link = _normalize_farsnews_link(raw_link)
                if full_link:
                    lead = None
                    for k in ('lead', 'Lead', 'summary', 'description', 'abstract'):
                        v = node.get(k)
                        if isinstance(v, str) and 25 <= len(v.strip()) <= 1500:
                            lead = v.strip()
                            break
                    found.append({
                        'title': title,
                        'link': full_link,
                        'summary': lead or '',
                        'image_url': _extract_image_from_node(node) or ''
                    })
        values = node.values()
    elif isinstance(node, list):
        values = node
    else:
        return
    for v in values:
        if isinstance(v, (dict, list)):
            _collect_json_news_items(v, found)


def scrape_farsnews():
    """Scrape economy news from Farsnews (Next.js site - no RSS required)."""
    articles = []
    resp = None
    for url in ("https://farsnews.ir/Economy/posts",
                "https://www.farsnews.ir/Economy/posts",
                "https://farsnews.ir/economy/posts"):
        resp = robust_get(url, timeout=25)
        if resp is not None:
            break
    if resp is None:
        print("  ⚠ Farsnews: page fetch failed")
        return articles

    try:
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception as e:
        print(f"  ⚠ Farsnews HTML parse error: {e}")
        return articles

    # Strategy 1: embedded JSON (Next.js __NEXT_DATA__ + JSON-LD)
    json_payloads = []
    tag = soup.find('script', id='__NEXT_DATA__')
    if tag:
        raw = tag.string or tag.get_text()
        if raw:
            json_payloads.append(raw)
    for s in soup.find_all('script', type='application/ld+json'):
        raw = s.string or s.get_text()
        if raw:
            json_payloads.append(raw)

    for raw in json_payloads:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        found = []
        _collect_json_news_items(data, found)
        articles.extend(found)

    # Strategy 2: plain <a href="/news/..."> links in the rendered HTML
    if len(articles) < 3:
        seen = set()
        for a in soup.find_all('a', href=True):
            nid, link = _normalize_farsnews_link(a.get('href', ''))
            if not link or nid in seen:
                continue
            title = clean_text(a.get('title') or a.get_text(' ', strip=True))
            if len(title) < 15 or len(title) > 250:
                continue
            seen.add(nid)
            articles.append({'title': title, 'link': link,
                             'summary': '', 'image_url': ''})

    # Deduplicate by link (page order = newest first)
    unique, seen_links = [], set()
    for art in articles:
        if art['link'] in seen_links:
            continue
        seen_links.add(art['link'])
        unique.append(art)

    # Strategy 3: last resort - the site's RSS feed, if it exists
    if not unique:
        r = robust_get("https://farsnews.ir/rss", timeout=20)
        if r is not None:
            try:
                feed = feedparser.parse(r.content)
                for entry in feed.entries[:SCRAPE_PAGE_LIMIT]:
                    title = clean_text(entry.get('title', ''))
                    link = entry.get('link', '')
                    if title and link and '/news/' in link:
                        unique.append({
                            'title': title,
                            'link': link,
                            'summary': clean_text(entry.get('summary', ''))[:800],
                            'image_url': extract_image_url(entry)
                        })
            except Exception as e:
                print(f"  ⚠ Farsnews RSS fallback error: {e}")

    return unique[:SCRAPE_PAGE_LIMIT]


DONYA_LINK_RE = re.compile(r'/(?:news|node)/(\d{4,})')

def scrape_donya():
    """Scrape economy news from Donya-e-Eqtesad main page."""
    articles = []
    resp = None
    for url in ("https://www.donya-e-eqtesad.com", "https://donya-e-eqtesad.com"):
        resp = robust_get(url, timeout=25)
        if resp is not None:
            break
    if resp is None:
        print("  ⚠ Donya: page fetch failed")
        return articles

    try:
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception as e:
        print(f"  ⚠ Donya HTML parse error: {e}")
        return articles

    base = 'https://www.donya-e-eqtesad.com'
    seen = set()

    def _add(href, title):
        m = DONYA_LINK_RE.search(href)
        if not m:
            return
        nid = m.group(1)
        if nid in seen:
            return
        if href.startswith('http'):
            link = href.split('#')[0]
        elif href.startswith('/'):
            link = base + href
        else:
            link = base + '/' + href
        title = clean_text(title)
        if len(title) < 12 or len(title) > 250:
            return
        seen.add(nid)
        articles.append({'title': title, 'link': link,
                         'summary': '', 'image_url': ''})

    # Strategy 1: headlines inside heading tags
    for h in soup.find_all(['h1', 'h2', 'h3']):
        a = h.find('a', href=True)
        if a is not None:
            _add(a.get('href', ''), a.get_text(' ', strip=True))

    # Strategy 2: any article-looking link
    if len(articles) < 3:
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if DONYA_LINK_RE.search(href):
                _add(href, a.get('title') or a.get_text(' ', strip=True))
            if len(articles) >= SCRAPE_PAGE_LIMIT:
                break

    return articles[:SCRAPE_PAGE_LIMIT]


def scrape_generic(source):
    """Generic scraper for any site configured in SCRAPE_SOURCES.

    Example config entry:
      {'name': 'Example Economy', 'type': 'generic',
       'url': 'https://example.com/economy',
       'link_pattern': r'/news/\\d+',        # regex matching article links
       'base_url': 'https://example.com'}
    """
    url = source.get('url', '')
    if not url:
        return []
    resp = robust_get(url, timeout=25)
    if resp is None:
        return []
    try:
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception as e:
        print(f"  ⚠ {source.get('name', 'generic')} parse error: {e}")
        return []

    try:
        link_re = re.compile(source.get('link_pattern', r'/news/\d+'))
    except re.error:
        link_re = re.compile(r'/news/\d+')

    base = (source.get('base_url') or url).rstrip('/')
    seen = set()
    articles = []
    for a in soup.find_all('a', href=True):
        href = (a.get('href') or '').strip()
        if not href or href.startswith('#') or href.startswith('javascript'):
            continue
        m = link_re.search(href)
        if not m:
            continue
        key = m.group(0)
        if key in seen:
            continue
        if href.startswith('http'):
            link = href.split('#')[0]
        elif href.startswith('//'):
            link = 'https:' + href
        elif href.startswith('/'):
            link = base + href
        else:
            link = base + '/' + href
        title = clean_text(a.get('title') or a.get_text(' ', strip=True))
        if len(title) < 12 or len(title) > 250:
            continue
        seen.add(key)
        articles.append({'title': title, 'link': link,
                         'summary': '', 'image_url': ''})
        if len(articles) >= SCRAPE_PAGE_LIMIT:
            break
    return articles


def scrape_all_sources():
    """Collect articles from all non-RSS sources defined in SCRAPE_SOURCES."""
    all_articles = []
    for source in SCRAPE_SOURCES:
        stype = source.get('type', '')
        try:
            if stype == 'farsnews':
                articles = scrape_farsnews()
            elif stype == 'donya':
                articles = scrape_donya()
            elif stype == 'generic':
                articles = scrape_generic(source)
            else:
                print(f"  ⚠ Unknown scrape source type: {stype}")
                continue
        except Exception as e:
            print(f"  ⚠ {source.get('name', stype)} scraping error: {e}")
            continue
        if articles:
            print(f"  Scraped {len(articles)} from {source.get('name', stype)}")
            all_articles.extend(articles)
        else:
            print(f"  ⚠ 0 articles from {source.get('name', stype)}")
    return all_articles


# ================= ARTICLE ENRICHMENT (full text / media) =================
def _meta_content(soup, names):
    for n in names:
        tag = soup.find('meta', attrs={'property': n}) or soup.find('meta', attrs={'name': n})
        if tag and tag.get('content'):
            c = tag.get('content').strip()
            if c:
                return c
    return None


def extract_main_text(soup):
    """Extract the main article body text from a parsed page."""
    for tag in soup(['script', 'style', 'noscript', 'nav', 'header',
                     'footer', 'aside', 'form', 'iframe']):
        tag.decompose()

    candidates = []
    selectors = ['article', '[itemprop="articleBody"]', '.item-body', '.news-body',
                 '.article-body', '.entry-content', '.post-content', '.news-text',
                 '.full-text', '.body-fulltext', '#news-body', '.story-body']
    for sel in selectors:
        try:
            el = soup.select_one(sel)
        except Exception:
            el = None
        if el is not None:
            paras = [p.get_text(' ', strip=True) for p in el.find_all(['p', 'li'])]
            text = ' '.join(t for t in paras if len(t) > 25)
            if len(text) > 200:
                candidates.append(text)

    if not candidates:
        paras = [p.get_text(' ', strip=True) for p in soup.find_all('p')]
        text = ' '.join(t for t in paras if len(t) > 40)
        if len(text) > 200:
            candidates.append(text)

    if not candidates:
        return ""
    candidates.sort(key=len, reverse=True)
    return candidates[0][:4500]


def enrich_article(article):
    """Fetch the article page to get full text, image and video when missing."""
    url = article.get('link', '') or ''
    if not url.startswith('http'):
        return article

    content_now = article.get('content') or ''
    summary_now = article.get('summary') or ''
    has_content = len(content_now) > 300
    has_image = bool(article.get('image_url'))
    has_summary = len(summary_now) > 80

    if has_content and has_image:
        return article

    print("  ⤵ Fetching full article content...")
    resp = robust_get(url, timeout=25)
    if resp is None:
        print("  ⚠ Could not fetch article page")
        return article

    try:
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception:
        return article

    if not has_image:
        img = _meta_content(soup, ['og:image', 'twitter:image', 'image'])
        if img:
            if img.startswith('//'):
                img = 'https:' + img
            article['image_url'] = img

    if not has_summary:
        desc = _meta_content(soup, ['og:description', 'description', 'twitter:description'])
        if desc:
            article['summary'] = clean_text(desc)[:800]

    if not has_content:
        text = extract_main_text(soup)
        if text:
            article['content'] = text

    video = _meta_content(soup, ['og:video', 'og:video:url', 'og:video:secure_url'])
    if video and '.mp4' in video.lower():
        article['video_url'] = video

    return article


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
        if is_prohibited_source(feed_url):
            print(f"  ⚠ Skipping prohibited: {feed_url}")
            continue
        try:
            print(f"  Fetching: {feed_url}")
            resp = requests.get(
                feed_url,
                timeout=15,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                entries = feed.entries[:5]  # 5 most recent per feed

                for entry in entries:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    if not title or not link:
                        continue
                    if is_prohibited_source(link):
                        continue
                    if link in processed:
                        continue
                    if any(titles_are_similar(title, t) for t in posted_titles):
                        continue

                    summary = clean_text(entry.get('summary', ''))[:800]
                    content = ''
                    if entry.get('content'):
                        try:
                            content = clean_text(entry['content'][0].get('value', ''))[:4000]
                        except Exception:
                            content = ''
                    image_url = extract_image_url(entry)

                    all_articles.append({
                        'title': title,
                        'summary': summary,
                        'content': content,
                        'link': link,
                        'image_url': image_url,
                    })
            else:
                print(f"  ✗ Status {resp.status_code}")
        except requests.exceptions.Timeout:
            print(f"  ✗ Timeout")
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:60]}")

    # ---- SCRAPED SOURCES ----
    scraped = scrape_all_sources()
    for art in scraped:
        if art['link'] in processed:
            continue
        if any(titles_are_similar(art['title'], t) for t in posted_titles):
            continue
        all_articles.append(art)

    print(f"  Total articles: {len(all_articles)}")

    # Add to queue
    new_count = 0
    for article in all_articles:
        if article['link'] in processed:
            continue
        queue.append(article)
        processed.add(article['link'])
        posted_titles.append(article['title'])
        new_count += 1
        if new_count >= MAX_POSTS_PER_RUN:
            break

    # --- UPDATE PRICE HISTORY ---
    update_price_history()

    save_queue(queue)
    save_processed(processed)
    save_posted_titles(posted_titles)

    print(f"✅ Collected {new_count} new articles. Queue: {len(queue)}")


# ================= POST NEWS =================
def post_one():
    """Post one article from the queue (retries several items if they fail)."""
    queue = load_queue()
    if not queue:
        print("ℹ Queue is empty.")
        return

    for attempt in range(MAX_POST_ATTEMPTS):
        if not queue:
            print("ℹ Queue exhausted.")
            break

        article = queue.pop(0)
        save_queue(queue)  # persist our place immediately

        print(f"\n📢 [{attempt + 1}] Processing: {(article.get('title') or '')[:60]}...")

        # Fetch the full article text + media (picture/video) if needed
        if ENRICH_ARTICLES:
            try:
                enrich_article(article)
            except Exception as e:
                print(f"  ⚠ Enrichment error: {e}")

        persian_title, persian_summary = translate_news_article(article)

        if not persian_title:
            print("  ✗ Skipping (no valid translation)")
            continue

        print(f"  ✓ Persian title: {persian_title[:60]}")
        if persian_summary:
            print(f"  ✓ Summary: {len(persian_summary)} chars")
        else:
            print("  ℹ No summary available - posting title only")

        sentiment_input = (article.get('title', '') + ' ' +
                           (article.get('content') or article.get('summary') or ''))[:4000]
        gold_label, oil_label = get_sentiment_labels(sentiment_input)

        image_url = article.get('image_url') or ''
        video_url = article.get('video_url') or ''
        limit = 1000 if (image_url or video_url) else 4000
        message = build_post_message(persian_title, persian_summary,
                                     gold_label, oil_label,
                                     article.get('link', ''), limit)

        ok = send_to_telegram(message, image_url=image_url, video_url=video_url)
        if ok:
            print(f"✅ Posted. Queue remaining: {len(queue)}")
            return
        print("  ⚠ Send failed - trying next article...")

    print("✅ Post run finished (nothing could be posted).")


# ================= MESSAGE FORMATTING =================
def format_message(persian_title, persian_summary, gold_label, oil_label, link=""):
    """Format the final Telegram message (HTML, escaped, with source link)."""
    text_lower = f"{persian_title} {persian_summary or ''}".lower()
    if any(w in text_lower for w in ['طلا', 'سکه', 'نقره', 'اونس']):
        emoji = "🥇"
    elif any(w in text_lower for w in ['نفت', 'برنت', 'اوپک', 'بشکه']):
        emoji = "🛢️"
    elif any(w in text_lower for w in ['دلار', 'ارز', 'یورو', 'تومان', 'تتر', 'ین']):
        emoji = "💵"
    else:
        emoji = "📊"

    msg = f"{emoji} <b>{html_lib.escape(persian_title or '')}</b>\n\n"

    if persian_summary:
        msg += f"{html_lib.escape(persian_summary)}\n\n"

    parts = [p for p in (gold_label, oil_label) if p]
    if parts:
        msg += '\n'.join(parts) + "\n"

    if link:
        safe_link = html_lib.escape(link, quote=True)
        msg += f"\n🔗 <a href=\"{safe_link}\">ادامه خبر در منبع اصلی</a>"

    return msg


def build_post_message(persian_title, persian_summary, gold_label, oil_label, link="", limit=4000):
    """Build the message and make sure it fits (photo captions are limited to 1024)."""
    msg = format_message(persian_title, persian_summary, gold_label, oil_label, link)
    if len(msg) <= limit:
        return msg
    if not persian_summary:
        return msg[:limit]

    base = format_message(persian_title, "", gold_label, oil_label, link)
    allowed = limit - len(base) - 120
    if allowed < 120:
        return base

    cut = persian_summary[:allowed]
    last_end = 0
    for m in re.finditer(r'[.!?؟…]\s', cut):
        last_end = m.end()
    if last_end > 60:
        cut = cut[:last_end].strip()

    trimmed = format_message(persian_title, cut + ' …', gold_label, oil_label, link)
    if len(trimmed) <= limit:
        return trimmed
    return base


# ================= TELEGRAM =================
def send_to_telegram(message, image_url=None, video_url=None):
    """Send message to the Telegram channel (video -> photo -> text fallbacks)."""
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("  ⚠ Telegram not configured. Preview:")
        print(f"  {message[:500]}")
        return True  # treat preview as success so the queue isn't drained

    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    # 1) Video (if the article's main media is an mp4)
    if video_url:
        try:
            resp = requests.post(
                f"{api}/sendVideo",
                json={'chat_id': CHANNEL_ID, 'video': video_url,
                      'caption': message[:1024], 'parse_mode': 'HTML'},
                timeout=90)
            if resp.status_code == 200:
                print("  ✓ Posted with video")
                return True
            print(f"  ⚠ Video send failed: {resp.status_code}")
        except Exception as e:
            print(f"  ⚠ Video error: {e}")

    # 2) Photo - download it ourselves first (some CDNs block Telegram's servers)
    if image_url:
        caption = message[:1024]
        sent = False
        photo_data = None
        try:
            r = robust_get(image_url, timeout=30)
            if r is not None and len(r.content) > 2000 and \
                    r.headers.get('Content-Type', '').startswith('image'):
                photo_data = r.content
        except Exception:
            photo_data = None

        if photo_data:
            try:
                resp = requests.post(
                    f"{api}/sendPhoto",
                    data={'chat_id': CHANNEL_ID, 'caption': caption, 'parse_mode': 'HTML'},
                    files={'photo': ('photo.jpg', photo_data, 'image/jpeg')},
                    timeout=90)
                sent = resp.status_code == 200
            except Exception as e:
                print(f"  ⚠ Photo upload error: {e}")
        else:
            try:
                resp = requests.post(
                    f"{api}/sendPhoto",
                    json={'chat_id': CHANNEL_ID, 'photo': image_url,
                          'caption': caption, 'parse_mode': 'HTML'},
                    timeout=90)
                sent = resp.status_code == 200
            except Exception as e:
                print(f"  ⚠ Photo error: {e}")

        if sent:
            print("  ✓ Posted with image")
            return True
        print("  ⚠ Photo failed - falling back to text")

    # 3) Plain text
    payload = {'chat_id': CHANNEL_ID, 'text': message[:4096], 'parse_mode': 'HTML'}
    try:
        resp = requests.post(f"{api}/sendMessage", json=payload, timeout=30)
        if resp.status_code == 200:
            print("  ✓ Posted successfully")
            return True
        if resp.status_code == 400:
            # HTML parse problem -> retry as plain text
            plain = re.sub(r'<[^>]+>', '', message)
            try:
                resp2 = requests.post(
                    f"{api}/sendMessage",
                    json={'chat_id': CHANNEL_ID, 'text': plain[:4096]},
                    timeout=30)
                if resp2.status_code == 200:
                    print("  ✓ Posted (plain text)")
                    return True
            except Exception:
                pass
        print(f"  ✗ Telegram failed: {resp.status_code} {resp.text[:120]}")
        return False
    except Exception as e:
        print(f"  ✗ Telegram error: {e}")
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
        collect_news()
        time.sleep(5)
        post_one()
    else:
        print(f"Unknown mode: {mode}")
        print("Available modes: collect, post, chart, weekly, calendar, run")
