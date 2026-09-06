# config.py

import os

# ================= CONFIGURATION =================
RSS_FEEDS = [
    # Core financial
    "https://www.actionforex.com/feed",
    "https://www.fxstreet.com/rss/news",
    "https://www.kitco.com/news/rss",
    "https://oilprice.com/rss/main",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.eia.gov/rss/todayinenergy.xml",

    # Global
    "https://rss.dw.com/rdf/rss-en-world",
    "https://www.france24.com/en/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.bbci.co.uk/news/rss.xml",

    # UK
    "https://www.telegraph.co.uk/business/rss.xml",
    "https://www.theguardian.com/uk/business/rss",

    # France
    "https://www.france24.com/en/business/rss",

    # Germany
    "https://rss.dw.com/rdf/rss-en-ger",
    "https://rss.dw.com/rdf/rss-en-bus",

    # Russia
    "https://tass.com/rss/v2.xml",
    "https://www.themoscowtimes.com/rss/news",

    # China/Asia
    "https://scmp.com/rss/4/feed",
    "https://rss.dw.com/rdf/rss-en-asia",

    # Middle East
    "https://www.france24.com/en/middle-east/rss",

    # Additional financial
    "https://www.investing.com/rss/news_25.rss",
    "https://www.marketwatch.com/rss/topstories",
    "https://feeds.feedburner.com/zerohedge/feed",
    "https://news.google.com/rss/search?q=gold+OR+oil+OR+dollar+when:1d&hl=en-US&gl=US&ceid=US:en",

    # Persian sources
    "https://www.fardayeeghtesad.com/rss",
    "https://www.eghtesadonline.com/fa/updates/13",
    "https://www.eghtesadonline.com/fa/updates/27",
    "https://www.eghtesadonline.com/fa/updates/8",
    "https://www.mehrnews.com/rss",
]

POST_INTERVAL = 360          # 6 minutes
MAX_POSTS_PER_RUN = 8
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")

PREFERRED_MODELS = [
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
]
FALLBACK_MODELS = [
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]
MODEL_CACHE_FILE = "last_working_model.txt"

# ================= CORE PRICE TERMS =================
CORE_PRICE_TERMS = [
    'fed', 'fomc', 'ecb', 'boj', 'boe', 'rate hike', 'rate cut',
    'interest rate decision', 'monetary policy', 'central bank',
    'inflation', 'cpi', 'nfp', 'unemployment', 'gdp',
    'recession', 'trade war', 'sanction', 'geopolitical',
    'oil price', 'crude oil', 'brent', 'wti', 'opec',
    'gold price', 'gold', 'dollar index', 'dxy',
    'treasury yield', 'bond yields', 'stock market crash',
    'currency crisis', 'energy crisis'
]

PERSIAN_KEYWORDS = [
    'طلا', 'دلار', 'نفت', 'ارز', 'سکه', 'بورس', 'سهام', 'تورم',
    'بانک مرکزی', 'نرخ بهره', 'تحریم', 'قیمت', 'اقتصاد', 'بازار',
    'صادرات', 'واردات', 'بیکاری', 'رشد اقتصادی', 'تولید ناخالص داخلی',
    'انرژی', 'گاز', 'پتروشیمی', 'فدرال رزرو', 'اوپک'
]

RUSSIAN_KEYWORDS = [
    'золото', 'доллар', 'нефть', 'рубль', 'инфляция', 'ставка', 'фрс',
    'центральный банк', 'санкции', 'ввп', 'безработица', 'доходность',
    'опек', 'энергетический кризис', 'газ', 'биржа', 'валюта', 'центробанк',
    'процентная ставка', 'фондовый рынок'
]

IMPORTANT_COUNTRIES = [
    'united states', 'us', 'usa', 'china', 'japan', 'germany', 'france',
    'uk', 'united kingdom', 'britain', 'italy', 'canada', 'australia',
    'south korea', 'russia', 'india', 'brazil', 'mexico', 'indonesia',
    'turkey', 'saudi arabia', 'uae', 'iran', 'israel', 'south africa',
    'europe', 'eurozone', 'european union', 'eu'
]

BULLISH = ['rate cut', 'weak dollar', 'geopolitical tension', 'recession',
           'inflation', 'safe haven', 'central bank buying', 'stimulus',
           'dovish', 'crisis', 'war']
BEARISH = ['rate hike', 'strong dollar', 'risk appetite', 'higher yields',
           'hawkish', 'economic growth', 'optimism', 'risk-on', 'tightening']

OIL_BULLISH = [
    'opec cut', 'oil supply', 'crude inventory draw', 'geopolitical risk',
    'middle east', 'sanctions', 'supply disruption', 'oil production cut',
    'drone attack', 'pipeline', 'war', 'embargo', 'energy crisis',
    'brent', 'wti', 'oil reserve', 'crude oil', 'petroleum'
]
OIL_BEARISH = [
    'opec increase', 'oil demand', 'recession', 'slowdown', 'supply glut',
    'inventory build', 'demand destruction', 'covid', 'economic weakness',
    'higher interest rates', 'strong dollar', 'risk-off', 'oil price drop',
    'lower oil demand', 'ev sales', 'alternative energy'
]

# ================= GLOSSARIES =================
ECONOMIC_GLOSSARY = {
    # ... (paste the entire economic glossary dictionary from the existing bot.py)
}

IRAN_RESPECT_GLOSSARY = {
    # ... (paste the entire Iran respect glossary dictionary)
}

PERSIAN_CORRECTIONS = {
    # ... (paste the entire Persian corrections dictionary)
}

IRAN_SPECIFIC_GLOSSARY = {
    # ... (paste the entire Iran specific glossary dictionary)
}

COUNTRY_GLOSSARY = {
    # ... (paste the entire country glossary dictionary)
}

PERSIAN_NAME_CORRECTIONS = {
    # ... (paste the entire Persian name corrections dictionary)
}

PROPER_NOUN_CORRECTIONS = {
    'حزب راستگرای دوردست': 'حزب راستگرای افراطی',
    'نودیدیا': 'انویدیا',
    'هاجینگ فیس': 'هاگینگ فیس',
}

CORRECT_TERMS = [
    'انویدیا',
    'هاگینگ فیس',
    'راستگرای افراطی',
    'نیروهای سپاه',
    'جزیره خارگ',
    'سنتکام',
    'فدرال رزرو',
    'بانک مرکزی اروپا',
    'اوپک',
]
