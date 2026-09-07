# config.py

import os

# ================= API CONFIGURATION =================
OILPRICEAPI_URL = "https://api.oilpriceapi.com/v1/demo/prices"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
BONBAST_URL = "https://www.bonbast.com"

# ================= RSS FEEDS =================
RSS_FEEDS = [
    # Core financial (existing)
    "https://www.actionforex.com/feed",
    "https://www.fxstreet.com/rss/news",
    "https://www.kitco.com/news/rss",
    "https://oilprice.com/rss/main",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.eia.gov/rss/todayinenergy.xml",

    # Global news (business sections)
    "https://rss.dw.com/rdf/rss-en-bus",
    "https://www.france24.com/en/business/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/uk/business/rss",

    # Country‑specific business
    "https://www.telegraph.co.uk/business/rss.xml",
    "https://tass.com/rss/v2.xml",
    "https://scmp.com/rss/4/feed",

    # Additional financial
    "https://www.investing.com/rss/news_25.rss",
    "https://www.marketwatch.com/rss/topstories",
    [
    # ... (keep all existing) ...

    # ----- VATICAN / CATHOLIC NEWS (statements that may affect global sentiment) -----
    "https://www.vaticannews.va/en/rss.html",          # main Vatican news
    "https://www.vaticannews.va/en/vatican-city.rss",  # Vatican City specific
    "https://www.catholicnewsagency.com/rss",          # CNA (global Catholic news)
]

    # ----- PERSIAN ECONOMIC RSS (where available) -----
    "https://www.eghtesadonline.com/fa/updates/13",
    "https://www.eghtesadonline.com/fa/updates/27",
    "https://www.eghtesadonline.com/fa/updates/8",
    "https://www.mehrnews.com/rss/tp/25",          # اقتصاد
    "https://www.mehrnews.com/rss/tp/44",          # بانک و بورس
    "https://www.isna.ir/rss/tp/3",                # اقتصادی
    "https://www.irna.ir/rss/tp/3",                # اقتصادی
    "https://www.tasnimnews.com/fa/rss/feed/0/8/0/",   # اقتصادی
    "https://www.tabnak.ir/fa/rss/22",             # اقتصادی
    "https://www.shana.ir/rss/tp/14",              # نفت
    "https://www.shana.ir/rss/tp/18",              # گاز
    "https://www.shana.ir/rss/tp/4",               # پتروشیمی
    "https://www.shana.ir/rss/tp/5",               # بین‌الملل
    "https://www.irasin.ir/rss/tp/23",             # اقتصاد
    "https://www.irasin.ir/rss/tp/75",             # اقتصاد جهان
    "https://www.irasin.ir/rss/tp/80",             # بازارها
    "https://www.irasin.ir/rss/tp/34",             # نفت و گاز
    "https://www.sedayebourse.ir/rss/tp/9042",     # اخبار اقتصادی
    "https://www.sedayebourse.ir/rss/tp/2",        # بازار سهام
    "https://www.foodpress.ir/rss/tp/7034",        # اقتصادی
    "https://www.foodpress.ir/rss/tp/6033",        # بازار
    "https://eximland.ir/rss",                     # صادرات و واردات
    "https://cbi.ir/rss",                          # بانک مرکزی

    # ----- GLOBAL ADDITIONAL -----
    "http://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://www.reutersagency.com/feed/?best-regions=world&post_type=best",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.marketwatch.com/rss/marketpulse",
    "https://www.investing.com/rss/news_1063.rss",   # Stocks
    "https://www.investing.com/rss/news_14.rss",     # Forex
    "https://en.mercopress.com/rss/economy",
    "https://en.mercopress.com/rss/energy",
]

# Sites that do NOT provide RSS – we will scrape them separately
SCRAPE_SOURCES = [
    {
        'name': 'Farsnews Economy',
        'url': 'https://farsnews.ir/Economy/posts',
        'type': 'farsnews'
    },
    {
        'name': 'Donya-e-Eqtesad Economy',
        'url': 'https://donya-e-eqtesad.com',
        'type': 'donya'
    },
    # Add more if needed
]

# ================= PROHIBITED SOURCES =================
PROHIBITED_SOURCES = [
    'bbc.com/persian',
    'bbc.co.uk/persian',
    'iranintl.com',
    'voanews.com',
    'radiofarda.com',
    'persian.service',
    'bbcpersian.com',
    'manoto.tv',
    'iran-international.com',
    'iranwire.com',
]

# ================= PERSIAN SOURCE DOMAINS =================
PERSIAN_SOURCE_DOMAINS = [
    # Existing
    'fardayeeghtesad.com',
    'eghtesadonline.com',
    'eghtesadnews.com',
    'donya-e-eqtesad.com',
    'tgju.org',
    'irna.ir',
    'isna.ir',
    'mehrnews.com',
    'farsnews.ir',
    'tehrantimes.com',
    'presstv.co.uk',
    'presstv.ir',
    # New additions
    'shana.ir',
    'irasin.ir',
    'sedayebourse.ir',
    'foodpress.ir',
    'shada.ir',
    'eximland.ir',
    'cbi.ir',
    'tasnimnews.com',
    'tabnak.ir',
]
# ================= BOT SETTINGS =================
POST_INTERVAL = 360          # 6 minutes between posts
MAX_POSTS_PER_RUN = 3        # Quality over quantity
MAX_RUNTIME = 20 * 60        # 20 minutes max per run

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")

# Translation model
TRANSLATION_MODEL = "openai/gpt-oss-20b"
FALLBACK_MODELS = ["llama-3.1-8b-instant", "qwen/qwen3-32b"]

MODEL_CACHE_FILE = "last_working_model.txt"

# ================= STRICT ECONOMIC FILTER =================
REQUIRED_ECONOMIC_TERMS = [
    # Central banks & monetary policy
    'fed', 'fomc', 'ecb', 'boj', 'boe', 'central bank',
    'interest rate', 'rate hike', 'rate cut', 'monetary policy',
    'federal reserve', 'bank of japan', 'bank of england',
    
    # Economic indicators
    'inflation', 'cpi', 'pce', 'nfp', 'nonfarm', 'unemployment',
    'gdp', 'recession', 'stagflation', 'deflation',
    'consumer price', 'producer price', 'employment report',
    
    # Gold & precious metals
    'gold', 'silver', 'precious metal', 'xau', 'xag',
    'bullion', 'gold price', 'gold market', 'gold reserve',
    
    # Oil & energy
    'oil', 'crude', 'brent', 'wti', 'opec',
    'petroleum', 'energy crisis', 'oil price', 'oil market',
    'oil production', 'oil export', 'oil sanction',
    
    # Currency & forex
    'dollar', 'dxy', 'currency', 'forex',
    'exchange rate', 'dollar index', 'us dollar',
    
    # Bonds & yields
    'treasury', 'yield', 'bond',
    
    # Trade & sanctions
    'sanction', 'trade war', 'tariff', 'embargo',
    
    # Market events
    'stock market', 'market crash', 'market volatility',
    'financial crisis', 'economic crisis',

    # ----- NEW: Geopolitics, War, and Strategic Moves (affect prices) -----
    'war', 'conflict', 'military', 'attack', 'strike',
    'escalation', 'peace', 'negotiation', 'ceasefire',
    'hormuz', 'strait', 'tanker', 'naval', 'warship',
    'missile', 'drone', 'air strike', 'ground operation',
    'intervention', 'sanctions relief', 'nuclear deal',
    'diplomacy', 'embassy', 'consulate', 'evacuation',
    'refugee', 'humanitarian crisis', 'hostage',
    'pope', 'vatican', 'catholic', 'holy see',  # Vatican statements often carry weight
]

# Terms that BLOCK news
BLOCKED_TERMS = [
    # Entertainment & culture
    'film', 'movie', 'festival', 'cinema', 'actor', 'actress',
    'music', 'concert', 'celebrity', 'entertainment',
    'sport', 'football', 'basketball', 'soccer', 'olympic',
    'fashion', 'award', 'red carpet', 'premiere',
    'art', 'culture', 'museum', 'gallery', 'exhibition',
    'literature', 'poetry', 'novel', 'book fair',
    
    # Non-economic news
    'earthquake', 'hurricane', 'tornado', 'flood', 'wildfire',
    'police', 'crime', 'murder', 'shooting', 'accident',
    'school', 'student', 'teacher', 'university', 'education',
    'hospital', 'patient', 'medical', 'health', 'disease',
    'charity', 'donation', 'volunteer', 'humanitarian',
    'weather', 'traffic', 'transport', 'aviation',
    'recipe', 'food', 'restaurant', 'cooking',
    'travel', 'tourism', 'vacation', 'hotel',
    'wedding', 'birthday', 'funeral', 'obituary',
    'technology', 'gadget', 'smartphone', 'app',
    'gaming', 'video game', 'esports',
    
    # Low-value financial news
    'earnings', 'quarterly report', 'stock split', 'dividend',
    'ipo', 'merger', 'acquisition', 'buyout',
    'real estate', 'property', 'housing market',
    'cryptocurrency', 'bitcoin', 'ethereum', 'crypto', 'nft',
    
    # Persian non-economic terms
    'فیلم', 'سینما', 'ورزش', 'جشنواره', 'هنرمند', 'فرهنگی',
    'دانش‌آموز', 'مدرسه', 'دانشگاه', 'آموزش', 'معلم',
    'بیمارستان', 'درمان', 'پزشکی', 'بیمار', 'سلامت',
    'خیریه', 'اهدای', 'کمک‌رسانی', 'بشردوستانه',
    'ورزشگاه', 'تیم ملی', 'بازی', 'فوتبال', 'بسکتبال',
    'آتش‌سوزی', 'زلزله', 'سیل', 'طوفان', 'خرابی',
    'پلیس', 'جنایی', 'قتل', 'تصادف', 'جرم',
    'سفر', 'گردشگری', 'هتل', 'تفریحی',
    'ازدواج', 'تولد', 'مراسم', 'خاکسپاری',
    'موسیقی', 'کنسرت', 'تئاتر', 'نمایش',
    'کتاب', 'ادبیات', 'شعر', 'رمان',
    'هنر', 'موزه', 'گالری', 'نمایشگاه',
]

# Persian keywords for economic content
PERSIAN_ECONOMIC_KEYWORDS = [
    'طلا', 'دلار', 'نفت', 'ارز', 'سکه', 'بورس', 'سهام', 'تورم',
    'بانک مرکزی', 'نرخ بهره', 'تحریم', 'قیمت', 'اقتصاد', 'بازار',
    'صادرات', 'واردات', 'بیکاری', 'رشد اقتصادی', 'تولید ناخالص داخلی',
    'انرژی', 'گاز', 'پتروشیمی', 'فدرال رزرو', 'اوپک', 'یورو',
    'پوند', 'ین', 'یوان', 'شاخص', 'بازار سرمایه', 'بازار مالی',
    'حواله', 'مبادله', 'صرافی', 'ذخایر ارزی', 'ترازنامه',
    'سیاست پولی', 'سیاست مالی', 'کسری بودجه', 'بدهی',
]
[
    # ... (keep existing) ...
    # New geopolitical terms
    'جنگ', 'درگیری', 'نظامی', 'حمله', 'عملیات',
    'تنش', 'برجام', 'تحریم', 'مذاکره', 'آتش‌بس',
    'هرمز', 'نفت‌کش', 'نیروی دریایی', 'موشک',
    'پهپاد', 'گفتگو', 'صلح', 'روسیه', 'اوکراین',
    'اسرائیل', 'فلسطین', 'غزه', 'لبنان', 'سوریه',
    'یمن', 'عراق', 'افغانستان', 'ترکیه',
    'پاپ', 'واتیکان', 'کاتولیک', 'بیانیه', 'سخنرانی',
]
# ================= GEOGRAPHIC NAMES =================
GEO_NAMES = {
    # Countries
    'United States': 'ایالات متحده', 'USA': 'ایالات متحده', 'US': 'ایالات متحده',
    'America': 'آمریکا', 'China': 'چین', 'Japan': 'ژاپن', 'Germany': 'آلمان',
    'France': 'فرانسه', 'United Kingdom': 'بریتانیا', 'UK': 'بریتانیا',
    'Britain': 'بریتانیا', 'England': 'انگلستان', 'Italy': 'ایتالیا',
    'Canada': 'کانادا', 'Australia': 'استرالیا', 'South Korea': 'کره جنوبی',
    'North Korea': 'کره شمالی', 'Russia': 'روسیه', 'India': 'هند',
    'Brazil': 'برزیل', 'Mexico': 'مکزیک', 'Indonesia': 'اندونزی',
    'Turkey': 'ترکیه', 'Saudi Arabia': 'عربستان سعودی', 'UAE': 'امارات',
    'Iran': 'ایران', 'Israel': 'اسرائیل', 'South Africa': 'آفریقای جنوبی',
    'Europe': 'اروپا', 'Eurozone': 'منطقه یورو', 'European Union': 'اتحادیه اروپا',
    'EU': 'اتحادیه اروپا', 'Ukraine': 'اوکراین', 'Iraq': 'عراق',
    'Syria': 'سوریه', 'Lebanon': 'لبنان', 'Yemen': 'یمن',
    'Qatar': 'قطر', 'Kuwait': 'کویت', 'Oman': 'عمان',
    'Bahrain': 'بحرین', 'Egypt': 'مصر', 'Libya': 'لیبی',
    'Nigeria': 'نیجریه', 'Venezuela': 'ونزوئلا', 'Argentina': 'آرژانتین',
    'Netherlands': 'هلند', 'Belgium': 'بلژیک', 'Switzerland': 'سوئیس',
    'Sweden': 'سوئد', 'Norway': 'نروژ', 'Denmark': 'دانمارک',
    'Finland': 'فنلاند', 'Poland': 'لهستان', 'Spain': 'اسپانیا',
    'Portugal': 'پرتغال', 'Greece': 'یونان', 'Austria': 'اتریش',
    'Czech Republic': 'جمهوری چک', 'Hungary': 'مجارستان',
    'Romania': 'رومانی', 'Bulgaria': 'بلغارستان', 'Thailand': 'تایلند',
    'Vietnam': 'ویتنام', 'Malaysia': 'مالزی', 'Philippines': 'فیلیپین',
    'Singapore': 'سنگاپور', 'Pakistan': 'پاکستان', 'Afghanistan': 'افغانستان',
    'Bangladesh': 'بنگلادش', 'Sri Lanka': 'سری‌لانکا', 'Myanmar': 'میانمار',
    'Kazakhstan': 'قزاقستان', 'Uzbekistan': 'ازبکستان', 'Azerbaijan': 'آذربایجان',
    'Armenia': 'ارمنستان', 'Georgia': 'گرجستان', 'Belarus': 'بلاروس',
    
    # Cities
    'Washington': 'واشنگتن', 'Washington D.C.': 'واشنگتن', 'London': 'لندن',
    'Paris': 'پاریس', 'Berlin': 'برلین', 'Beijing': 'پکن', 'Tokyo': 'توکیو',
    'Moscow': 'مسکو', 'Kyiv': 'کی‌یف', 'Kiev': 'کی‌یف',
    'Brussels': 'بروکسل', 'Tehran': 'تهران', 'Dubai': 'دبی',
    'Riyadh': 'ریاض', 'Ankara': 'آنکارا', 'Istanbul': 'استانبول',
    'New York': 'نیویورک', 'Wall Street': 'وال‌استریت',
    'Frankfurt': 'فرانکفورت', 'Zurich': 'زوریخ', 'Geneva': 'ژنو',
    'Amsterdam': 'آمستردام', 'Milan': 'میلان', 'Madrid': 'مادرید',
    'Rome': 'رم', 'Lisbon': 'لیسبون', 'Vienna': 'وین',
    'Stockholm': 'استکهلم', 'Oslo': 'اسلو', 'Copenhagen': 'کپنهاگ',
    'Helsinki': 'هلسینکی', 'Warsaw': 'ورشو', 'Prague': 'پراگ',
    'Budapest': 'بوداپست', 'Athens': 'آتن', 'Seoul': 'سئول',
    'Hong Kong': 'هنگ‌کنگ', 'Shanghai': 'شانگهای', 'Shenzhen': 'شنژن',
    'Singapore': 'سنگاپور', 'Bangkok': 'بانکوک', 'Jakarta': 'جاکارتا',
    'Manila': 'مانیل', 'Mumbai': 'بمبئی', 'New Delhi': 'دهلی نو',
    'Karachi': 'کراچی', 'Lahore': 'لاهور', 'Dhaka': 'داکا',
    'Cairo': 'قاهره', 'Casablanca': 'کازابلانکا', 'Lagos': 'لاگوس',
    'Johannesburg': 'ژوهانسبورگ', 'Cape Town': 'کیپ‌تاون',
    'São Paulo': 'سائوپائولو', 'Rio de Janeiro': 'ریودوژانیرو',
    'Buenos Aires': 'بوئنوس‌آیرس', 'Santiago': 'سانتیاگو',
    'Bogotá': 'بوگوتا', 'Lima': 'لیما', 'Caracas': 'کاراکاس',
    'Toronto': 'تورنتو', 'Vancouver': 'ونکوور', 'Montreal': 'مونترال',
    'Sydney': 'سیدنی', 'Melbourne': 'ملبورن', 'Brisbane': 'بریزبن',
    'Perth': 'پرت', 'Auckland': 'اوکلند',
    
    # German states
    'Saxony-Anhalt': 'زاکسن-آنهالت', 'Saxony': 'زاکسن', 'Anhalt': 'آنهالت',
    'Bavaria': 'بایرن', 'Brandenburg': 'براندنبورگ',
    'Baden-Württemberg': 'بادن-وورتمبرگ', 'North Rhine-Westphalia': 'نوردراین-وستفالن',
    'Hesse': 'هسن', 'Lower Saxony': 'نیدرزاکسن',
    
    # Institutions
    'Federal Reserve': 'فدرال رزرو', 'Fed': 'فدرال رزرو',
    'European Central Bank': 'بانک مرکزی اروپا', 'ECB': 'بانک مرکزی اروپا',
    'Bank of England': 'بانک مرکزی انگلستان', 'BoE': 'بانک مرکزی انگلستان',
    'Bank of Japan': 'بانک مرکزی ژاپن', 'BoJ': 'بانک مرکزی ژاپن',
    "People's Bank of China": 'بانک مرکزی چین', 'PBoC': 'بانک مرکزی چین',
    'IMF': 'صندوق بین‌المللی پول', 'World Bank': 'بانک جهانی',
    'OPEC': 'اوپک', 'IEA': 'آژانس بین‌المللی انرژی',
    'White House': 'کاخ سفید', 'Pentagon': 'پنتاگون',
    'Kremlin': 'کرملین', 'NATO': 'ناتو',
    'European Commission': 'کمیسیون اروپا',
    'UN Security Council': 'شورای امنیت سازمان ملل',
    'WTO': 'سازمان تجارت جهانی',
    
    # People
    'Zelensky': 'زلنسکی', 'Zelenskyy': 'زلنسکی', 'Putin': 'پوتین',
    'Biden': 'بایدن', 'Trump': 'ترامپ', 'Macron': 'ماکرون',
    'Scholz': 'شولتز', 'Xi Jinping': 'شی جین‌پینگ', 'Merkel': 'مرکل',
    'Khamenei': 'خامنه‌ای', 'Pezeshkian': 'پزشکیان', 'Araghchi': 'عراقچی',
    'Lagarde': 'لاگارد', 'Powell': 'پاول', 'Yellen': 'یلن',
    'Witkoff': 'ویتکوف', 'Kushner': 'کوشنر', 'Netanyahu': 'نتانیاهو',
    'Erdogan': 'اردوغان', 'MBS': 'بن سلمان', 'Crown Prince': 'ولیعهد',
    'Lavrov': 'لاوروف', 'Mishustin': 'میخوستین',
    
    # Organizations & companies
    'Gazprom': 'گازپروم', 'Rosneft': 'روسنفت', 'Saudi Aramco': 'آرامکو',
    'BP': 'بی‌پی', 'Shell': 'شل', 'Chevron': 'شورون',
    'ExxonMobil': 'اکسان‌موبیل', 'TotalEnergies': 'توتال‌انرژی',
}

# ================= IRAN RESPECT GLOSSARY =================
IRAN_RESPECT = {
    'Iranian regime': 'جمهوری اسلامی ایران',
    'Iranian government': 'دولت ایران',
    'Iranian theocracy': 'نظام جمهوری اسلامی',
    'Supreme Leader': 'رهبر معظم',
    'Ayatollah Khamenei': 'حضرت آیت‌الله خامنه‌ای',
    'President Pezeshkian': 'رئیس‌جمهور پزشکیان',
    'Masoud Pezeshkian': 'دکتر مسعود پزشکیان',
    'Foreign Minister Araghchi': 'وزیر خارجه عراقچی',
    'Abbas Araghchi': 'سید عباس عراقچی',
    "Iran's nuclear program": 'برنامه هسته‌ای صلح‌آمیز ایران',
    'Iran nuclear deal': 'برنامه جامع اقدام مشترک',
    'JCPOA': 'برنامه جامع اقدام مشترک',
    'Iran sanctions': 'تحریم‌های علیه جمهوری اسلامی ایران',
    'Central Bank of Iran': 'بانک مرکزی جمهوری اسلامی ایران',
    'National Iranian Oil Company': 'شرکت ملی نفت ایران',
    'NIOC': 'شرکت ملی نفت ایران',
}

# ================= PERSIAN GRAMMAR FIXES =================
GRAMMAR_FIXES = {
    # Meaningless phrases -> natural Persian
    'پاسخ ایجاد خواهد کرد': 'پاسخ خواهد داد',
    'پاسخ ارائه خواهد کرد': 'پاسخ خواهد داد',
    'خوشحال می‌کند': 'حمایت می‌کند',
    'خوشحال می‌شود': 'حمایت می‌کند',
    'قایق را ضبط کرد': 'کشتی را توقیف کرد',
    'در حال حرکت به سمت تصادف است': 'تصادف کرد',
    'موفقیت بزرگی را به دست آورد': 'به پیروزی بزرگی دست یافت',
    'در حال انجام شدن است': 'در حال انجام است',
    'قابل توجه و عمیق': 'مهم و جدی',
    'رهبر معظم معظم': 'رهبر معظم',
    'شورای اسلامی شورای اسلامی': 'شورای اسلامی',
    'نیروهای نیروهای': 'نیروهای',
    'مقامات مقامات': 'مقامات',
    'ارزش از ارزش': 'ارزش',
    'پاسخ ایجاد': 'پاسخ',
    
    # Better Persian equivalents
    'اعلام شد که': 'اعلام کرد',
    'گفته می‌شود که': 'گفته شد',
    'اظهار داشت': 'گفت',
    'بیان کرد': 'گفت',
    'تصریح کرد': 'گفت',
    'اظهارنظر کرد': 'گفت',
    'وارد حمله شد': 'حمله کرد',
    'مورد حمله قرار گرفت': 'حمله کرد',
    
    # Fix country names
    'ساکسونی-آنها': 'زاکسن-آنهالت',
    'ساکسونی آنهالت': 'زاکسن-آنهالت',
    'ساکسونی-آنهالت': 'زاکسن-آنهالت',
    'آلمان باختری': 'آلمان غربی',
    
    # Fix people names
    'زلنزی': 'زلنسکی',
    'ویتکاف': 'ویتکوف',
    'بوتن': 'پوتین',
}

# ================= LLM ARTIFACT PATTERNS =================
LLM_ARTIFACT_PATTERNS = [
    r'ترجمه[‌\s]*:',
    r'خلاصه[‌\s]*:',
    r'نکات ترجمه',
    r'ساختار طبیعی فارسی',
    r'دلیل‌پردازی و نکات',
    r'تحلیل ادعاها',
    r'چرا بیانیه‌های',
    r'نتیجه‌گیری',
    r'###\s',
    r'\|.*?\|',
    r'Here\s+is',
    r'Translation\s*:',
    r'Note\s*:',
    r'I\s+have\s+translated',
    r'The\s+following',
    r'-\s+\*\*.*?\*\*\s*:',
    r'^\s*\d+\.\s',
]

# Repeated word pattern
REPEATED_WORD_PATTERN = r'\b(\w+)(\s+\1\b)+'

# ================= SENTIMENT KEYWORDS =================
BULLISH_GOLD = [
    'rate cut', 'weak dollar', 'geopolitical tension', 'recession',
    'inflation', 'safe haven', 'central bank buying', 'stimulus',
    'dovish', 'crisis', 'war', 'uncertainty', 'conflict',
]

BEARISH_GOLD = [
    'rate hike', 'strong dollar', 'risk appetite', 'higher yields',
    'hawkish', 'economic growth', 'optimism', 'risk-on',
]

BULLISH_OIL = [
    'opec cut', 'oil supply', 'crude inventory draw', 'geopolitical risk',
    'middle east', 'sanctions', 'supply disruption', 'production cut',
    'drone attack', 'pipeline', 'war', 'embargo', 'energy crisis',
]

BEARISH_OIL = [
    'opec increase', 'oil demand', 'recession', 'slowdown', 'supply glut',
    'inventory build', 'demand destruction', 'economic weakness',
    'higher interest rates', 'strong dollar', 'oil price drop',
]
