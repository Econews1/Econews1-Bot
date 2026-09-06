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
from matplotlib.font_manager import FontProperties
from datetime import datetime, timedelta
import arabic_reshaper
from bidi.algorithm import get_display
import numpy as np
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

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
    "https://www.eghtesadonline.com/fa/updates/13",   # gold & currency
    "https://www.eghtesadonline.com/fa/updates/27",   # oil & energy
    "https://www.eghtesadonline.com/fa/updates/8",    # macro
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

# ================= CORE PRICE TERMS (Strict filter) =================
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

# ================= PERSIAN FONT SETUP =================
_persian_font_prop = None

def setup_persian_font():
    global _persian_font_prop
    if _persian_font_prop is not None:
        return _persian_font_prop

    font_path = "persian_font.ttf"
    urls = [
        "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Regular.ttf",
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf",
        "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Regular.ttf",
        "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf",
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf",
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

    print("Warning: Persian font not loaded. Using default.")
    _persian_font_prop = None
    return None

# ================= PERSIAN TEXT PROCESSING =================
def to_persian_digits(text):
    if not text:
        return text
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    western_digits = '0123456789'
    translation = str.maketrans(western_digits, persian_digits)
    return text.translate(translation)

def fa(text):
    if not text:
        return text
    try:
        text = to_persian_digits(text)
        reshaped = arabic_reshaper.reshape(text)
        return reshaped
    except Exception as e:
        print(f"Error in fa(): {e}")
        return text

# ================= COMPREHENSIVE ECONOMIC GLOSSARY =================
ECONOMIC_GLOSSARY = {
    'Gold': 'طلا', 'Spot Gold': 'طلا نقدی', 'Gold Bar': 'شمش طلا',
    'Gold Bullion': 'طلای آبشده', 'Gold Coin': 'سکه طلا',
    'Gold Futures': 'قرارداد آتی طلا', 'Gold Reserve': 'ذخایر طلای بانک مرکزی',
    'Gold Standard': 'استاندارد طلا', 'Gold ETF': 'صندوق قابل معامله طلا',
    'Precious Metals': 'فلزات گرانبها', 'Silver': 'نقره', 'Platinum': 'پلاتین',
    'Palladium': 'پالادیوم', 'Bullion': 'آبشده / شمش',
    'Safe Haven Asset': 'دارایی امن / پناهگاه امن', 'Inflation Hedge': 'پوشش تورمی',
    'Gold-to-Oil Ratio': 'نسبت طلا به نفت', 'Karat': 'عیار',
    '24 Karat Gold': 'طلای ۲۴ عیار', '18 Karat Gold': 'طلای ۱۸ عیار',
    'Mesghal': 'مثقال', 'Gold Assay': 'آزمون عیار طلا',
    'Central Bank Gold Purchases': 'خرید طلا توسط بانک مرکزی',
    'Gold Price Forecast': 'پیش‌بینی قیمت طلا', 'Gold Mining': 'استخراج طلا',
    'Gold Refinery': 'پالایشگاه طلا', 'Goldsmith': 'طلاساز',
    'Bull Market (Gold)': 'بازار صعودی طلا', 'Bear Market (Gold)': 'بازار نزولی طلا',
    'Gold Rally': 'جهش قیمت طلا', 'Currency': 'ارز / پول',
    'US Dollar': 'دلار آمریکا', 'USD': 'دلار آمریکا', 'Euro': 'یورو',
    'EUR': 'یورو', 'British Pound': 'پوند استرلینگ', 'GBP': 'پوند انگلیس',
    'Japanese Yen': 'ین ژاپن', 'JPY': 'ین ژاپن', 'Swiss Franc': 'فرانک سوئیس',
    'CHF': 'فرانک سوئیس', 'Chinese Yuan': 'یوان چین', 'CNY': 'یوان چین',
    'Russian Ruble': 'روبل روسیه', 'RUB': 'روبل روسیه', 'Iranian Rial': 'ریال ایران',
    'IRR': 'ریال ایران', 'Iranian Toman': 'تومان', 'UAE Dirham': 'درهم امارات',
    'AED': 'درهم امارات', 'Turkish Lira': 'لیر ترکیه', 'TRY': 'لیر ترکیه',
    'Indian Rupee': 'روپیه هند', 'INR': 'روپیه هند',
    'Exchange Rate': 'نرخ ارز / نرخ برابری', 'Floating Exchange Rate': 'نرخ ارز شناور',
    'Fixed Exchange Rate': 'نرخ ارز ثابت', 'Currency Devaluation': 'کاهش ارزش پول',
    'Currency Appreciation': 'افزایش ارزش ارز', 'Currency Depreciation': 'کاهش ارزش ارز',
    'Dollar Index': 'شاخص دلار', 'DXY': 'شاخص دلار', 'Dollar Strength': 'قدرت دلار',
    'Dollar Weakness': 'ضعف دلار', 'Currency Pair': 'جفت ارز',
    'Major Currency Pair': 'جفت ارز اصلی', 'Cross Currency Pair': 'جفت ارز متقاطع',
    'Pip': 'پیپ', 'Spread': 'اسپرد', 'Leverage': 'اهرم / لوریج',
    'Margin': 'مارجین / وجه تضمین', 'Lot': 'لات', 'Bid Price': 'قیمت خرید',
    'Ask Price': 'قیمت فروش', 'Buy Order': 'سفارش خرید', 'Sell Order': 'سفارش فروش',
    'Long Position': 'موقعیت خرید / پوزیشن لانگ', 'Short Position': 'موقعیت فروش / پوزیشن شورت',
    'Stop Loss': 'حد ضرر', 'Take Profit': 'حد سود', 'Currency Reserve': 'ذخایر ارزی',
    'Foreign Exchange': 'ارز خارجی', 'Central Bank Intervention': 'مداخله بانک مرکزی',
    'Currency Crisis': 'بحران ارزی', 'Capital Flight': 'فرار سرمایه',
    'Currency Swap': 'مبادله ارز', 'Forward Contract': 'قرارداد آتی ارز',
    'Hedging': 'پوشش ریسک / هجینگ', 'Carry Trade': 'معامله حمل / کری ترید',
    'Crude Oil': 'نفت خام', 'Brent Crude': 'نفت برنت', 'WTI Crude': 'نفت وست تگزاس اینترمیدیت',
    'OPEC': 'اوپک', 'OPEC+': 'اوپک پلاس', 'Oil Production': 'تولید نفت',
    'Oil Export': 'صادرات نفت', 'Oil Import': 'واردات نفت',
    'Oil Refinery': 'پالایشگاه نفت', 'Oil Reserve': 'ذخایر نفت',
    'Strategic Petroleum Reserve': 'ذخایر راهبردی نفت', 'Oil Price': 'قیمت نفت',
    'Oil Barrel': 'بشکه نفت', 'Barrels Per Day': 'بشکه در روز', 'BPD': 'بشکه در روز',
    'Oil Field': 'میدان نفتی', 'Oil Pipeline': 'خط لوله نفت', 'Oil Tanker': 'نفتکش',
    'Oil Embargo': 'تحریم نفتی', 'Oil Sanctions': 'تحریم‌های نفتی',
    'Energy Market': 'بازار انرژی', 'Energy Security': 'امنیت انرژی',
    'Natural Gas': 'گاز طبیعی', 'LNG': 'گاز مایع شده',
    'Liquefied Natural Gas': 'گاز مایع شده', 'Gasoline': 'بنزین',
    'Diesel': 'گازوئیل / دیزل', 'Petrochemical': 'پتروشیمی',
    'Petrodollar': 'پترو دلار', 'Shale Oil': 'نفت شیل', 'Fracking': 'شکست هیدرولیکی',
    'Oil Cartel': 'کارتل نفت', 'Crude Oil Inventory': 'موجودی نفت خام',
    'Oil Price Shock': 'شوک قیمت نفت', 'Energy Crisis': 'بحران انرژی',
    'Oil Benchmark': 'معیار قیمت نفت', 'Oil Futures': 'قرارداد آتی نفت',
    'Oil Spot Price': 'قیمت نقدی نفت', 'Oil Price Volatility': 'نوسان قیمت نفت',
    'Petroleum Products': 'فرآورده‌های نفتی', 'Oil Field Services': 'خدمات میدان نفتی',
    'Central Bank': 'بانک مرکزی', 'Federal Reserve': 'فدرال رزرو', 'Fed': 'فدرال رزرو',
    'Federal Reserve System': 'سیستم فدرال رزرو', 'FOMC': 'کمیته بازار باز فدرال',
    'Federal Open Market Committee': 'کمیته بازار باز فدرال',
    'European Central Bank': 'بانک مرکزی اروپا', 'ECB': 'بانک مرکزی اروپا',
    'Bank of England': 'بانک مرکزی انگلستان', 'BoE': 'بانک مرکزی انگلیس',
    'Bank of Japan': 'بانک مرکزی ژاپن', 'BoJ': 'بانک مرکزی ژاپن',
    "People's Bank of China": 'بانک مرکزی چین', 'PBoC': 'بانک مرکزی چین',
    'Central Bank of Iran': 'بانک مرکزی جمهوری اسلامی ایران',
    'CBI': 'بانک مرکزی جمهوری اسلامی ایران', 'Monetary Policy': 'سیاست پولی',
    'Expansionary Monetary Policy': 'سیاست پولی انبساطی',
    'Contractionary Monetary Policy': 'سیاست پولی انقباضی',
    'Interest Rate': 'نرخ بهره', 'Policy Rate': 'نرخ سیاستی',
    'Federal Funds Rate': 'نرخ بهره فدرال', 'Base Rate': 'نرخ پایه',
    'Benchmark Rate': 'نرخ مرجع', 'Interest Rate Hike': 'افزایش نرخ بهره',
    'Interest Rate Cut': 'کاهش نرخ بهره', 'Rate Decision': 'تصمیم نرخ بهره',
    'Hawkish': 'انقباضی / هاوکیش', 'Dovish': 'انبساطی / داویش',
    'Quantitative Easing': 'تسهیل کمّی', 'QE': 'تسهیل کمّی',
    'Quantitative Tightening': 'تنگ کردن کمّی', 'QT': 'تنگ کردن کمّی',
    'Tapering': 'کاهش تدریجی خرید اوراق', 'Open Market Operations': 'عملیات بازار باز',
    'Reserve Requirement': 'نسبت ذخیره قانونی', 'Discount Rate': 'نرخ تنزیل',
    'Forward Guidance': 'راهنمایی پیش‌رو', 'Money Supply': 'حجم پول / نقدینگی',
    'Monetary Base': 'پایه پولی', 'Inflation Targeting': 'هدف‌گذاری تورم',
    'Central Bank Independence': 'استقلال بانک مرکزی', 'Central Bank Speech': 'سخنرانی بانک مرکزی',
    'Central Bank Meeting': 'نشست بانک مرکزی', 'Minutes of Meeting': 'صورتجلسه',
    'Central Bank Balance Sheet': 'ترازنامه بانک مرکزی', 'Bank Stress Test': 'آزمون استرس بانکی',
    'Banking Supervision': 'نظارت بانکی', 'Emergency Liquidity': 'نقدینگی اضطراری',
    'Currency Intervention': 'مداخله ارزی', 'Gross Domestic Product': 'تولید ناخالص داخلی',
    'GDP': 'تولید ناخالص داخلی', 'Nominal GDP': 'تولید ناخالص داخلی اسمی',
    'Real GDP': 'تولید ناخالص داخلی واقعی', 'GDP Growth Rate': 'نرخ رشد اقتصادی',
    'GDP Per Capita': 'تولید ناخالص داخلی سرانه', 'GNP': 'تولید ناخالص ملی',
    'Inflation': 'تورم', 'Inflation Rate': 'نرخ تورم', 'Hyperinflation': 'تورم لگام‌گسیخته',
    'Deflation': 'تورم منفی / دیفلیشن', 'Disinflation': 'کاهش تورم',
    'Core Inflation': 'تورم هسته', 'Consumer Price Index': 'شاخص قیمت مصرف‌کننده',
    'CPI': 'شاخص قیمت مصرف‌کننده', 'Producer Price Index': 'شاخص قیمت تولیدکننده',
    'PPI': 'شاخص قیمت تولیدکننده', 'Personal Consumption Expenditures': 'هزینه‌های مصرف شخصی',
    'PCE': 'هزینه‌های مصرف شخصی', 'Core PCE': 'شاخص PCE هسته',
    'Inflation Expectations': 'انتظارات تورمی', 'Unemployment Rate': 'نرخ بیکاری',
    'Nonfarm Payrolls': 'اشتغال غیرکشاورزی', 'NFP': 'آمار اشتغال غیرکشاورزی',
    'Jobless Claims': 'ادعاهای بیمه بیکاری', 'Labor Force': 'نیروی کار',
    'Labor Force Participation Rate': 'نرخ مشارکت نیروی کار',
    'Employment Report': 'گزارش اشتغال', 'Job Creation': 'ایجاد شغل',
    'Unemployment Claims': 'مدعیان بیکاری', 'Recession': 'رکود اقتصادی',
    'Economic Recession': 'رکود اقتصادی', 'Stagflation': 'رکود تورمی',
    'Depression': 'رکود عمیق', 'Economic Growth': 'رشد اقتصادی',
    'Economic Contraction': 'انقباض اقتصادی', 'Economic Expansion': 'انبساط اقتصادی',
    'Business Cycle': 'چرخه تجاری', 'Economic Indicator': 'شاخص اقتصادی',
    'Leading Indicator': 'شاخص پیشرو', 'Lagging Indicator': 'شاخص پسرو',
    'PMI': 'شاخص مدیران خرید', 'Purchasing Managers Index': 'شاخص مدیران خرید',
    'Manufacturing PMI': 'شاخص مدیران خرید صنعت', 'Services PMI': 'شاخص مدیران خرید خدمات',
    'ISM Index': 'شاخص ISM', 'ISM': 'آی‌اس‌ام',
    'Consumer Confidence': 'اعتماد مصرف‌کننده', 'Consumer Sentiment': 'احساسات مصرف‌کننده',
    'Retail Sales': 'فروش خرده‌فروشی', 'Industrial Production': 'تولید صنعتی',
    'Capacity Utilization': 'نرخ استفاده از ظرفیت', 'Durable Goods Orders': 'سفارشات کالاهای بادوام',
    'Housing Starts': 'شروع ساخت خانه', 'Building Permits': 'مجوزهای ساخت',
    'Existing Home Sales': 'فروش خانه‌های موجود', 'New Home Sales': 'فروش خانه‌های جدید',
    'Trade Balance': 'تراز تجاری', 'Trade Deficit': 'کسری تجاری',
    'Trade Surplus': 'مازاد تجاری', 'Current Account': 'حساب جاری',
    'Current Account Deficit': 'کسری حساب جاری', 'Capital Account': 'حساب سرمایه',
    'Budget Deficit': 'کسری بودجه', 'Budget Surplus': 'مازاد بودجه',
    'Fiscal Policy': 'سیاست مالی', 'Government Debt': 'بدهی دولت',
    'Public Debt': 'بدهی عمومی', 'National Debt': 'بدهی ملی',
    'Debt-to-GDP Ratio': 'نسبت بدهی به تولید ناخالص داخلی', 'Fiscal Stimulus': 'محرک مالی',
    'Austerity': 'ریاضت اقتصادی', 'Stock Market': 'بازار سهام / بورس',
    'Bull Market': 'بازار صعودی / بازار گاوی', 'Bear Market': 'بازار نزولی / بازار خرسی',
    'Market Rally': 'جهش بازار', 'Market Selloff': 'فروش سنگین / افت بازار',
    'Market Correction': 'اصلاح بازار', 'Market Crash': 'سقوط بازار',
    'Market Volatility': 'نوسان بازار', 'Market Sentiment': 'احساسات بازار',
    'Risk Appetite': 'اشتهای ریسک', 'Risk Aversion': 'گریز از ریسک',
    'Risk-On': 'افزایش ریسک‌پذیری', 'Risk-Off': 'کاهش ریسک‌پذیری',
    'Safe Haven': 'پناهگاه امن / دارایی امن', 'Market Liquidity': 'نقدشوندگی بازار',
    'Trading Volume': 'حجم معاملات', 'Market Capitalization': 'ارزش بازار',
    'P/E Ratio': 'نسبت قیمت به سود', 'Earnings Per Share': 'سود هر سهم',
    'EPS': 'سود هر سهم', 'Dividend': 'سود تقسیمی', 'Stock Index': 'شاخص سهام',
    'S&P 500': 'شاخص اس اند پی ۵۰۰', 'Dow Jones': 'داو جونز', 'NASDAQ': 'نزدک',
    'FTSE 100': 'فوتسی ۱۰۰', 'DAX': 'دکس', 'Nikkei': 'نیکی',
    'Bond Market': 'بازار اوراق قرضه', 'Government Bond': 'اوراق قرضه دولتی',
    'Treasury Bond': 'اوراق قرضه خزانه', 'T-Bond': 'اوراق قرضه خزانه',
    'Treasury Yield': 'بازدهی اوراق خزانه', 'Yield Curve': 'منحنی بازدهی',
    'Inverted Yield Curve': 'منحنی بازدهی معکوس', 'Credit Rating': 'رتبه اعتباری',
    'Credit Rating Agency': 'آژانس رتبه‌بندی اعتباری', 'Speculation': 'سفته‌بازی',
    'Arbitrage': 'آربیتراژ / سوداگری', 'Market Maker': 'بازارساز',
    'Day Trading': 'معامله روزانه', 'Swing Trading': 'معامله موجی',
    'Position Trading': 'معامله موقعیتی', 'Technical Analysis': 'تحلیل تکنیکال',
    'Fundamental Analysis': 'تحلیل بنیادی', 'Support Level': 'سطح حمایت',
    'Resistance Level': 'سطح مقاومت', 'Breakout': 'شکست', 'Trend': 'روند',
    'Uptrend': 'روند صعودی', 'Downtrend': 'روند نزولی', 'Sideways Trend': 'روند خنثی',
    'Market Depth': 'عمق بازار', 'Order Book': 'دفتر سفارش',
    'Liquidity Crisis': 'بحران نقدینگی', 'Margin Call': 'درخواست افزایش وجه تضمین',
    'Short Squeeze': 'فشار خرید / مچاله شدن شورت‌ها', 'Market Manipulation': 'دستکاری بازار',
    'Insider Trading': 'معامله بر مبنای اطلاعات نهانی', 'Sanctions': 'تحریم‌ها',
    'Economic Sanctions': 'تحریم‌های اقتصادی', 'Trade War': 'جنگ تجاری',
    'Trade Tension': 'تنش تجاری', 'Tariff': 'تعرفه / عوارض گمرکی',
    'Import Tariff': 'تعرفه واردات', 'Export Tariff': 'تعرفه صادرات',
    'Trade Barrier': 'مانع تجاری', 'Protectionism': 'حمایت‌گرایی',
    'Free Trade': 'تجارت آزاد', 'Trade Agreement': 'توافق تجاری',
    'Geopolitical Tension': 'تنش ژئوپلیتیکی', 'Geopolitical Risk': 'ریسک ژئوپلیتیکی',
    'Political Crisis': 'بحران سیاسی', 'War': 'جنگ', 'Armed Conflict': 'درگیری مسلحانه',
    'Military Conflict': 'درگیری نظامی', 'Election': 'انتخابات',
    'Government Shutdown': 'تعطیلی دولت', 'Political Instability': 'بی‌ثباتی سیاسی',
    'Economic Warfare': 'جنگ اقتصادی', 'Currency War': 'جنگ ارزی',
    'Capital Controls': 'کنترل سرمایه', 'Brain Drain': 'مهاجرت نخبگان / فرار مغزها',
    'Economic Blockade': 'محاصره اقتصادی', 'Embargo': 'تحریم / امبارگو',
    'International Sanctions': 'تحریم‌های بین‌المللی', 'UN Sanctions': 'تحریم‌های سازمان ملل',
    'Multilateral Sanctions': 'تحریم‌های چندجانبه', 'Unilateral Sanctions': 'تحریم‌های یک‌جانبه',
    'Sanctions Evasion': 'دور زدن تحریم‌ها', 'Sanctions Relief': 'رفع تحریم‌ها',
    'Supply Chain Disruption': 'اختلال در زنجیره تأمین', 'Strategic Commodity': 'کالای راهبردی',
    'National Security': 'امنیت ملی', 'Sovereign Risk': 'ریسک حاکمیتی',
    'Country Risk': 'ریسک کشور', 'Political Risk': 'ریسک سیاسی',
    'Diplomatic Crisis': 'بحران دیپلماتیک', 'Regional Conflict': 'درگیری منطقه‌ای',
    'Food Security': 'امنیت غذایی', 'Commercial Bank': 'بانک تجاری',
    'Investment Bank': 'بانک سرمایه‌گذاری', 'Development Bank': 'بانک توسعه',
    'Islamic Banking': 'بانکداری اسلامی', 'Bank Deposit': 'سپرده بانکی',
    'Bank Loan': 'وام بانکی', 'Bank Credit': 'اعتبار بانکی', 'Bank Reserve': 'ذخایر بانکی',
    'Bank Profit': 'سود بانکی', 'Bank Interest': 'بهره بانکی',
    'Islamic Bank': 'بانک اسلامی', 'Interest-Free Banking': 'بانکداری بدون بهره',
    'Bank Run': 'هجوم به بانک', 'Bank Failure': 'ورشکستگی بانک',
    'Bank Nationalization': 'ملی شدن بانک', 'International Monetary Fund': 'صندوق بین‌المللی پول',
    'IMF': 'صندوق بین‌المللی پول', 'World Bank': 'بانک جهانی', 'WB': 'بانک جهانی',
    'Bank for International Settlements': 'بانک تسویه بین‌المللی', 'BIS': 'بانک تسویه بین‌المللی',
    'Investment': 'سرمایه‌گذاری', 'Return on Investment': 'نرخ بازگشت سرمایه',
    'ROI': 'نرخ بازگشت سرمایه', 'Diversification': 'متنوع‌سازی پرتفوی',
    'Portfolio': 'پرتفوی / سبد سرمایه‌گذاری', 'Asset Allocation': 'تخصیص دارایی',
    'Risk Management': 'مدیریت ریسک', 'Capital Gain': 'سود سرمایه',
    'Capital Loss': 'زیان سرمایه', 'Mutual Fund': 'صندوق سرمایه‌گذاری مشترک',
    'Exchange-Traded Fund': 'صندوق قابل معامله در بورس', 'ETF': 'صندوق قابل معامله',
    'Hedge Fund': 'صندوق پوشش ریسک', 'Sovereign Wealth Fund': 'صندوق ثروت حاکمیتی',
    'Private Equity': 'سرمایه‌گذاری خصوصی', 'Venture Capital': 'سرمایه‌گذاری خطرپذیر',
    'Foreign Direct Investment': 'سرمایه‌گذاری مستقیم خارجی', 'FDI': 'سرمایه‌گذاری مستقیم خارجی',
    'Cash Flow': 'جریان نقدی', 'Balance Sheet': 'ترازنامه', 'Income Statement': 'صورت سود و زیان',
    'Market Value': 'ارزش بازار', 'Book Value': 'ارزش دفتری', 'Intrinsic Value': 'ارزش ذاتی',
    'Bubble': 'حباب اقتصادی', 'Financial Crisis': 'بحران مالی',
    'Credit Crunch': 'تنگنای اعتباری', 'Liquidity Trap': 'تله نقدینگی',
    'Debt Ceiling': 'سقف بدهی', 'Default': 'نکول / توقف پرداخت',
    'Bankruptcy': 'ورشکستگی', 'Restructuring': 'بازسازی / تجدید ساختار',
    'Bailout': 'نجات مالی / بیل‌اوت', 'Stimulus Package': 'بسته محرک',
    'Fiscal Deficit': 'کسری مالی', 'Public Spending': 'هزینه‌کرد عمومی',
    'Government Revenue': 'درآمد دولت', 'Tax Revenue': 'درآمد مالیاتی',
    'Tax Cut': 'کاهش مالیات', 'Tax Increase': 'افزایش مالیات',
    'Progressive Tax': 'مالیات تصاعدی', 'Flat Tax': 'مالیات ثابت',
    'Capital Gains Tax': 'مالیات سود سرمایه', 'AI': 'هوش مصنوعی',
    'FX': 'بازار ارز', 'SMA': 'میانگین متحرک ساده', 'EMA': 'میانگین متحرک نمایی',
    'MACD': 'مکدی', 'RSI': 'شاخص قدرت نسبی', 'RSS': 'فید خبری',
    'JPMorgan': 'جی‌پی مورگان', 'MUFG': 'ام‌یواف‌جی', 'BNY': 'بی‌ان‌وای',
    'Commerzbank': 'کومرتس‌بانک', 'OilPrice.com': 'اویل‌پرایس', 'Reuters': 'رویترز',
    'Bloomberg': 'بلومبرگ', 'CNBC': 'سی‌ان‌بی‌سی', 'FT': 'فایننشال تایمز',
    'WSJ': 'وال‌استریت ژورنال',
    'BLS': 'اداره آمار کار آمریکا',
    'OCBC': 'اوسی‌بی‌سی',
    'Governor': 'رئیس کل',
    'Central Bank Governor': 'رئیس کل بانک مرکزی',
    'UST': 'اوراق خزانه آمریکا',
    'IDR': 'روپیه اندونزی',
    'USD/CHF': 'دلار آمریکا/فرانک سوئیس',
    'RBNZ': 'بانک مرکزی نیوزیلند',
    'RBI': 'بانک مرکزی هند',
}

# ================= IRAN SPECIFIC GLOSSARY =================
IRAN_SPECIFIC_GLOSSARY = {
    'سپاه': 'نیروهای سپاه',
    'سپاه پاسداران': 'نیروهای سپاه پاسداران',
    'ارتش': 'نیروهای ارتش',
    'خارگ': 'خارگ',
    'بندرعباس': 'بندرعباس',
    'تنگه هرمز': 'تنگه هرمز',
    'سنتکام': 'سنتکام',
    'وزارت نفت': 'وزارت نفت',
    'شرکت ملی نفت': 'شرکت ملی نفت',
    'بانک مرکزی': 'بانک مرکزی',
    'مجلس': 'مجلس شورای اسلامی',
    'دولت': 'دولت',
    'رئیس‌جمهور': 'رئیس‌جمهور',
    'رهبر': 'رهبر معظم',
    'تحریم': 'تحریم',
    'برجام': 'برنامه جامع اقدام مشترک',
    'هسته‌ای': 'برنامه هسته‌ای صلح‌آمیز',
}

# ================= COUNTRY SPECIFIC GLOSSARIES =================
COUNTRY_GLOSSARY = {
    'USA': {
        'Federal Reserve': 'فدرال رزرو',
        'FOMC': 'کمیته بازار باز فدرال',
        'CPI': 'شاخص قیمت مصرف‌کننده',
        'NFP': 'آمار اشتغال غیرکشاورزی',
        'GDP': 'تولید ناخالص داخلی',
        'Treasury': 'وزارت خزانه‌داری',
        'White House': 'کاخ سفید',
        'Pentagon': 'پنتاگون',
    },
    'UK': {
        'Bank of England': 'بانک مرکزی انگلستان',
        'BoE': 'بانک مرکزی انگلستان',
        'Parliament': 'پارلمان',
        'Downing Street': 'دفتر نخست‌وزیری',
    },
    'Europe': {
        'ECB': 'بانک مرکزی اروپا',
        'European Commission': 'کمیسیون اروپا',
        'Eurozone': 'منطقه یورو',
    },
    'Russia': {
        'Kremlin': 'کرملین',
        'Gazprom': 'گازپروم',
        'Rosneft': 'روسنفت',
        'Central Bank of Russia': 'بانک مرکزی روسیه',
    },
    'China': {
        'PBOC': 'بانک مرکزی چین',
        'Communist Party': 'حزب کمونیست',
        'NPC': 'کنگره ملی خلق',
    },
    'Japan': {
        'BOJ': 'بانک مرکزی ژاپن',
        'Ministry of Finance': 'وزارت دارایی',
        'Yen': 'ین',
    }
}

# ================= PERSIAN NAME CORRECTIONS =================
PERSIAN_NAME_CORRECTIONS = {
    'جزیره خرج': 'جزیره خارگ',
    'سلاح‌خیزان سپاه': 'نیروهای سپاه',
    'سپاه پاسداران': 'نیروهای سپاه پاسداران',
    'ستاد فرماندهی مرکزی': 'سنتکام',
}

# ================= TRANSLATION IMPROVEMENTS =================
def apply_all_glossaries(text):
    # Apply Persian corrections
    for wrong, right in PERSIAN_CORRECTIONS.items():
        text = text.replace(wrong, right)
    # Iran respect glossary
    for eng, fa_text in IRAN_RESPECT_GLOSSARY.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    # Economic glossary
    for eng, fa_text in ECONOMIC_GLOSSARY.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    # Iranian specific Persian corrections
    for eng, fa_text in IRAN_SPECIFIC_GLOSSARY.items():
        text = text.replace(eng, fa_text)
    # Country specific glossaries
    for country_dict in COUNTRY_GLOSSARY.values():
        for eng, fa_text in country_dict.items():
            text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    # Persian name corrections
    for wrong, right in PERSIAN_NAME_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text

def detect_language(text):
    if not text:
        return "en"
    if re.search(r'[\u0600-\u06FF]', text):
        return "fa"
    elif re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    else:
        return "en"

def simplify_to_english(text):
    if not text:
        return ""
    prompt = (
        "You are a professional news editor. "
        "Rewrite the following text into simple, complete English sentences. "
        "Use short sentences with clear subject-verb-object order. "
        "Avoid complex clauses. "
        "If the text is not English, first translate it into simple English. "
        "Output only the simplified English, nothing else."
    )
    return translate_with_custom_prompt(prompt, text)

def translate_english_to_persian(english_text):
    if not english_text:
        return ""
    prompt = (
        "You are a professional Persian translator specializing in financial and political news. "
        "Translate the following English text into Persian. "
        "Use natural Persian sentence structure: verb at the end of the sentence, object before subject if needed. "
        "Do NOT include any English words. Transliterate any remaining English terms into Persian letters. "
        "Output only the Persian translation, nothing else."
    )
    result = translate_with_custom_prompt(prompt, english_text)
    return result

def summarize_persian(persian_text):
    if not persian_text:
        return ""
    prompt = (
        "You are a professional Persian financial news summarizer. "
        "Summarize the following Persian news text into 2-3 concise Persian sentences. "
        "Focus on key economic data, price impact, and important actors. "
        "Keep the original Persian, do not translate. "
        "Output only the summary, nothing else."
    )
    return translate_with_custom_prompt(prompt, persian_text)

# ... (rest of functions and main dispatcher as before, but using apply_all_glossaries)
