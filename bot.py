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
    # Core Financial
    "https://www.actionforex.com/feed",
    "https://www.fxstreet.com/rss/news",
    "https://www.kitco.com/news/rss",
    "https://oilprice.com/rss/main",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.eia.gov/rss/todayinenergy.xml",

    # Global News Agencies
    "https://rss.dw.com/rdf/rss-en-world",
    "https://www.france24.com/en/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.bbci.co.uk/news/rss.xml",

    # UK Specialized
    "https://www.telegraph.co.uk/business/rss.xml",
    "https://www.theguardian.com/uk/business/rss",

    # France Specialized
    "https://www.france24.com/en/business/rss",

    # Germany Specialized
    "https://rss.dw.com/rdf/rss-en-ger",
    "https://rss.dw.com/rdf/rss-en-bus",

    # Russia Specialized
    "https://tass.com/rss/v2.xml",
    "https://www.themoscowtimes.com/rss/news",

    # China Specialized
    "https://scmp.com/rss/4/feed",

    # Asia/Japan
    "https://rss.dw.com/rdf/rss-en-asia",

    # Middle East / Gulf
    "https://www.france24.com/en/middle-east/rss",
]

POST_INTERVAL = 360          # 6 minutes
MAX_POSTS_PER_RUN = 5
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

# ================= KEYWORD FILTER =================
KEYWORDS = [
    'gold', 'xau', 'dollar', 'dxy', 'fed', 'rate', 'inflation',
    'cpi', 'oil', 'crude', 'brent', 'wti', 'opec', 'gdp', 'nfp',
    'treasury', 'yield', 'sanction', 'geopolitical', 'recession'
]

# Add Russian keywords (common financial terms)
RUSSIAN_KEYWORDS = [
    'золото', 'доллар', 'нефть', 'рубль', 'инфляция', 'ставка', 'фрс',
    'центральный банк', 'санкции', 'ввп', 'безработица', 'доходность',
    'опек', 'энергетический кризис'
]

IMPORTANT_COUNTRIES = [
    'united states', 'us', 'usa', 'china', 'japan', 'germany', 'france',
    'uk', 'united kingdom', 'britain', 'italy', 'canada', 'australia',
    'south korea', 'russia', 'india', 'brazil', 'mexico', 'indonesia',
    'turkey', 'saudi arabia', 'uae', 'iran', 'israel', 'south africa',
    'europe', 'eurozone', 'european union', 'eu'
]

CRITICAL_TERMS = [
    'sanction', 'war', 'conflict', 'attack', 'coup', 'nuclear', 'oil supply',
    'opec', 'embargo', 'geopolitical', 'central bank', 'fed', 'fomc', 'ecb',
    'rate hike', 'rate cut', 'inflation', 'recession', 'gdp', 'unemployment',
    'default', 'debt', 'trade war', 'currency crisis', 'stock crash',
    'energy crisis', 'pipeline', 'drone', 'missile', 'election', 'political crisis'
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

# ================= RESPECTFUL IRAN TERMINOLOGY =================
IRAN_RESPECT_GLOSSARY = {
    'Iranian regime': 'جمهوری اسلامی ایران',
    'Iranian Regime': 'جمهوری اسلامی ایران',
    "Iran's clerical rule": 'نظام جمهوری اسلامی',
    "Iran's theocracy": 'نظام جمهوری اسلامی',
    'Iranian theocracy': 'نظام جمهوری اسلامی',
    "Iran's rulers": 'رهبران جمهوری اسلامی',
    "Iran's hardliners": 'عناصر محافظه‌کار جمهوری اسلامی',
    'Mullahs': 'علمای دینی',
    'Clerics': 'علمای دینی',
    'Supreme Leader': 'رهبر معظم',
    'Supreme Leader of Iran': 'رهبر معظم جمهوری اسلامی ایران',
    "Iran's leader": 'رهبر معظم',
    'Ayatollah Khamenei': 'حضرت آیت‌الله خامنه‌ای',
    'Khamenei': 'حضرت آیت‌الله خامنه‌ای',
    'Iranian president': 'رئیس‌جمهور محترم ایران',
    'Pezeshkian': 'دکتر مسعود پزشکیان',
    'Masoud Pezeshkian': 'دکتر مسعود پزشکیان',
    'President Pezeshkian': 'رئیس‌جمهور دکتر مسعود پزشکیان',
    "Iran's FM": 'وزیر خارجه محترم ایران',
    'Araghchi': 'سید عباس عراقچی',
    'Abbas Araghchi': 'سید عباس عراقچی',
    "Iran's foreign minister": 'وزیر خارجه ایران',
    'Iranian parliament': 'مجلس شورای اسلامی',
    "Iran's parliament": 'مجلس شورای اسلامی',
    'Majles': 'مجلس شورای اسلامی',
    'Guardian Council': 'شورای نگهبان',
    'Assembly of Experts': 'مجلس خبرگان رهبری',
    'Expediency Council': 'مجمع تشخیص مصلحت نظام',
    'Bank Markazi': 'بانک مرکزی جمهوری اسلامی ایران',
    'National Iranian Oil Company': 'شرکت ملی نفت ایران',
    'NIOC': 'شرکت ملی نفت ایران',
    "Iran's oil ministry": 'وزارت نفت جمهوری اسلامی ایران',
    "Iran's foreign ministry": 'وزارت امور خارجه جمهوری اسلامی ایران',
    "Iran's finance ministry": 'وزارت امور اقتصادی و دارایی',
    "Iran's nuclear program": 'برنامه هسته‌ای صلح‌آمیز ایران',
    'Iran nuclear deal': 'برنامه جامع اقدام مشترک',
    'JCPOA': 'برنامه جامع اقدام مشترک',
    'Iran sanctions': 'تحریم‌های علیه جمهوری اسلامی ایران',
    'Iranian nuclear threat': 'فعالیت‌های هسته‌ای ایران',
    "Iran's proxies": 'شرکای منطقه‌ای ایران',
    "Iran's malign activities": 'سیاست‌های منطقه‌ای ایران',
}

PERSIAN_CORRECTIONS = {
    'بر بره': 'بر بشکه',
    'بره ': 'بشکه ',
    'اواس‌دی': 'دلار آمریکا',
    'یو‌اس‌دی': 'دلار آمریکا',
    'جپای': 'ین ژاپن',
    'جی‌پی‌وی': 'ین ژاپن',
    'اواس-ژاپن': 'آمریکا-ژاپن',
    'سکه‌ی ژاپنی': 'ین ژاپن',
    'داده‌های گرم': 'داده‌های قوی',
    'موقعیت کوتاه': 'پوزیشن فروش',
    'موقعیت بلند': 'پوزیشن خرید',
}

# ================= TRANSLATION FUNCTIONS =================
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
    refusal_phrases = [
        "i'm sorry", "i am sorry", "i can't", "i cannot",
        "can't help", "cannot help", "not able to", "unable to",
        "i apologize", "sorry, but", "i'm not able", "i am not able",
        "i won't", "i will not"
    ]
    lower = text.lower()
    return any(phrase in lower for phrase in refusal_phrases)

def apply_glossaries(text):
    for wrong, right in PERSIAN_CORRECTIONS.items():
        text = text.replace(wrong, right)
    for eng, fa_text in IRAN_RESPECT_GLOSSARY.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    for eng, fa_text in ECONOMIC_GLOSSARY.items():
        text = re.sub(r'\b' + re.escape(eng) + r'\b', fa_text, text)
    return text

def load_cached_model():
    if os.path.exists(MODEL_CACHE_FILE):
        with open(MODEL_CACHE_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_cached_model(model_id):
    with open(MODEL_CACHE_FILE, 'w') as f:
        f.write(model_id)

def has_latin(text):
    return bool(re.search(r'[A-Za-z]', text))

def force_persian(text):
    prompt = (
        "The following text contains some English words or Latin characters. "
        "Rewrite it entirely in Persian script, translating any remaining English terms into Persian. "
        "Use standard Persian financial terminology. Do not include any Latin letters. "
        "Keep the meaning intact. Output only the Persian text."
    )
    result = translate_with_custom_prompt(prompt, text)
    if result and not has_latin(result):
        return result
    result = re.sub(r'[A-Za-z]+', '', text)
    result = re.sub(r'\s+', ' ', result).strip()
    return result

def try_translate_with_model(text, model, custom_prompt=None):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    if custom_prompt:
        system_prompt = custom_prompt
    else:
        system_prompt = (
            "You are a professional financial translator. "
            "Detect the language of the input (English, Russian, or any other). "
            "If the input is not English, first rewrite it into simple, complete English sentences. "
            "Then translate the text into Persian (Farsi). "
            "Use simple, natural Persian sentence structure with the verb at the end. "
            "Convert all Western numerals to Persian digits. "
            "If the text mentions Iranian officials or government, use respectful language (e.g., 'جمهوری اسلامی ایران', 'مقامات ایرانی'). "
            "Important: Do NOT include any English words or Latin characters in the output. "
            "If you encounter an English term, transliterate it into Persian letters. "
            "Never refuse, never apologize, just output the final Persian translation."
        )
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
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
            if any(phrase in cleaned for phrase in ["متن خبری مالی را", "لطفاً متن خبری", "Translate the user's financial news"]):
                print("  Model returned system prompt, skipping.")
                return None
            if is_refusal(cleaned):
                print("  Model refused, skipping.")
                return None
            if cleaned and len(cleaned) > 5:
                cleaned = apply_glossaries(cleaned)
                cleaned = to_persian_digits(cleaned)
                if has_latin(cleaned):
                    print("  Latin detected, forcing Persian...")
                    forced = force_persian(cleaned)
                    if forced:
                        cleaned = forced
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

def translate_to_persian(text, custom_prompt=None):
    if not GROQ_API_KEY:
        return text
    cached = load_cached_model()
    if cached:
        print(f"Trying cached model: {cached}")
        result = try_translate_with_model(text, cached, custom_prompt)
        if result:
            return result
        else:
            if os.path.exists(MODEL_CACHE_FILE):
                os.remove(MODEL_CACHE_FILE)
    for model in PREFERRED_MODELS:
        result = try_translate_with_model(text, model, custom_prompt)
        if result:
            save_cached_model(model)
            return result
    for model in FALLBACK_MODELS:
        result = try_translate_with_model(text, model, custom_prompt)
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
        result = try_translate_with_model(text, model, custom_prompt)
        if result:
            save_cached_model(model)
            return result
    return text

def translate_summary_to_persian(title_en, summary_en):
    if not summary_en:
        return ""
    prompt = (
        "You are a professional financial news writer. "
        "Based on the title and the provided summary, write a concise Persian summary (2-3 sentences max) that explains the main event, involved country/actor, key numbers, and reason. "
        "Do NOT repeat the title. Use simple Persian sentences with verbs at the end. "
        "Convert all numbers to Persian digits. Do NOT include any English words or Latin characters. "
        "If the summary is in a language other than English, first rewrite it into simple English, then translate to Persian. "
        "Never refuse, never apologize, just output the final Persian summary."
    )
    user_content = f"Title: {title_en}\nSummary: {summary_en}"
    result = translate_with_custom_prompt(prompt, user_content)
    if result and has_latin(result):
        forced = force_persian(result)
        if forced:
            result = forced
    return result

def translate_with_custom_prompt(system_prompt, user_content):
    if not GROQ_API_KEY:
        return ""
    cached = load_cached_model()
    if cached:
        result = try_translate_with_model(user_content, cached, system_prompt)
        if result:
            return result
        else:
            if os.path.exists(MODEL_CACHE_FILE):
                os.remove(MODEL_CACHE_FILE)
    for model in PREFERRED_MODELS:
        result = try_translate_with_model(user_content, model, system_prompt)
        if result:
            save_cached_model(model)
            return result
    for model in FALLBACK_MODELS:
        result = try_translate_with_model(user_content, model, system_prompt)
        if result:
            save_cached_model(model)
            return result
    active_models = get_groq_models()
    def is_preferred(m):
        lower = m.lower()
        return 'qwen' not in lower and 'reason' not in lower
    sorted_models = sorted(active_models, key=lambda m: not is_preferred(m))
    for model in sorted_models:
        result = try_translate_with_model(user_content, model, system_prompt)
        if result:
            save_cached_model(model)
            return result
    return ""

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
            if media.get('medium') == 'image' or mtype.startswith('image/'):
                if not image_url:
                    image_url = media.get('url', '')
            elif media.get('medium') == 'video' or mtype.startswith('video/'):
                if not video_url:
                    video_url = media.get('url', '')
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
    if any(term in text for term in CRITICAL_TERMS):
        score += 12
    gold_score = score_sentiment(text)
    oil_score = score_oil_sentiment(text) if any(kw in text for kw in ['oil', 'crude', 'brent', 'wti', 'opec', 'petroleum', 'energy']) else 0
    if abs(gold_score) >= 1 or abs(oil_score) >= 1:
        score += 8
    high_impact = ['fed', 'fomc', 'ecb', 'boj', 'boe', 'rate hike', 'rate cut', 'inflation', 'cpi',
                   'nfp', 'gdp', 'unemployment', 'opec', 'sanctions', 'war', 'geopolitical']
    if any(kw in text for kw in high_impact):
        score += 6
    return score

# ================= FORMAT MESSAGE =================
def format_message(article):
    title_en = article.get('title', '')
    summary_en = article.get('summary', '')[:200]
    persian_title = translate_to_persian(title_en)

    persian_summary = translate_summary_to_persian(title_en, summary_en) if summary_en else ""

    # check similarity
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
    is_oil_related = any(kw in text_lower for kw in ['oil', 'crude', 'brent', 'wti', 'opec', 'petroleum', 'energy'])
    oil_label = oil_sentiment_label(score_oil_sentiment(text_lower)) if is_oil_related else ""

    emoji = "📰"
    if is_oil_related:
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

    sentiment_parts = []
    if gold_label:
        sentiment_parts.append(gold_label)
    if oil_label:
        sentiment_parts.append(oil_label)
    if sentiment_parts:
        msg += "\n\n" + "\n".join(sentiment_parts)

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

# ================= PROFESSIONAL CHART STYLING =================
COLORS = {
    'gold': {'line': '#FFD700', 'fill_light': '#FFD70022', 'fill_dark': '#FFD70000', 'text': '#FFD700'},
    'usd': {'line': '#00E5FF', 'fill_light': '#00E5FF22', 'fill_dark': '#00E5FF00', 'text': '#00E5FF'},
    'tether': {'line': '#FFA500', 'fill_light': '#FFA50022', 'fill_dark': '#FFA50000', 'text': '#FFA500'},
    'oil': {'line': '#1E90FF', 'fill_light': '#1E90FF22', 'fill_dark': '#1E90FF00', 'text': '#1E90FF'},
    'up': '#00C853', 'down': '#FF5252', 'neutral': '#9E9E9E'
}

def _create_gradient_fill(ax, x, y, line_color):
    cmap = LinearSegmentedColormap.from_list(
        'gradient',
        [(0, mcolors.to_rgba(line_color, 0.0)),
         (1, mcolors.to_rgba(line_color, 0.3))]
    )
    gradient = np.linspace(0, 1, 256).reshape(-1, 1)
    im = ax.imshow(
        gradient,
        extent=[min(x), max(x), 0, max(y)],
        aspect='auto',
        origin='lower',
        cmap=cmap,
        zorder=1
    )
    verts = list(zip(x, y)) + [(x[-1], 0), (x[0], 0)]
    clip_path = plt.Polygon(verts, closed=True, transform=ax.transData)
    im.set_clip_path(clip_path)

def _style_axis_professional(ax, font_prop):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#555555')
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['bottom'].set_color('#555555')
    ax.spines['bottom'].set_linewidth(0.5)
    ax.grid(True, axis='y', linestyle='--', alpha=0.15, color='#888888', linewidth=0.5)
    ax.grid(False, axis='x')
    ax.tick_params(axis='both', which='both', length=0)
    ax.tick_params(axis='x', colors='#888888', labelsize=10)
    ax.tick_params(axis='y', colors='#888888', labelsize=10)
    if font_prop:
        for label in ax.get_xticklabels():
            label.set_fontproperties(font_prop)
        for label in ax.get_yticklabels():
            label.set_fontproperties(font_prop)

def _add_price_annotation(ax, x, y, price, color, font_prop, currency='$', label=None):
    ax.plot([x[-1], x[-1] + 0.5], [y[-1], y[-1]],
            color=color, linewidth=1, linestyle='-', alpha=0.7)
    price_text = f"{price:,.0f}{currency}"
    price_text_fa = to_persian_digits(price_text)
    if label:
        annotation_text = f"{label}\n{price_text_fa}"
    else:
        annotation_text = price_text_fa
    ax.annotate(
        annotation_text,
        xy=(x[-1], y[-1]),
        xytext=(15, 0),
        textcoords='offset points',
        color='white',
        fontsize=11,
        va='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor=color, alpha=0.85, edgecolor='none'),
        fontproperties=font_prop if font_prop else None,
        linespacing=1.5
    )

def _add_change_badge(ax, y_data, font_prop):
    if len(y_data) < 2:
        return
    change = ((y_data[-1] - y_data[0]) / y_data[0]) * 100
    if change >= 0:
        color = COLORS['up']
        sign = '+'
    else:
        color = COLORS['down']
        sign = ''
    change_text = f"{sign}{abs(change):.1f}%"
    change_text_fa = to_persian_digits(change_text)
    ax.text(
        0.5, 0.92,
        change_text_fa,
        transform=ax.transAxes,
        fontsize=13,
        fontweight='bold',
        color=color,
        ha='center',
        va='top',
        fontproperties=font_prop if font_prop else None
    )

def _abbreviate_y_axis_for_usd(ax):
    y_ticks = ax.get_yticks()
    new_labels = []
    for tick in y_ticks:
        if tick >= 1000:
            value_in_thousands = tick / 1000
            label = f"{to_persian_digits(f'{value_in_thousands:.1f}')} هزار"
        else:
            label = to_persian_digits(str(int(tick)))
        new_labels.append(label)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(new_labels)

def generate_professional_gold_chart(font_prop):
    hours = list(range(0, 24, 2))
    gold_prices = [2030 + i*2 + np.sin(i/3)*10 for i in range(len(hours))]
    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')
    ax.plot(hours, gold_prices, color=COLORS['gold']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round')
    _create_gradient_fill(ax, hours, gold_prices, COLORS['gold']['line'])
    ax.fill_between(hours, gold_prices, min(gold_prices) - 20,
                     alpha=0.1, color=COLORS['gold']['line'], zorder=2)
    _style_axis_professional(ax, font_prop)
    _add_price_annotation(ax, hours, gold_prices, gold_prices[-1],
                          COLORS['gold']['line'], font_prop, currency='$')
    _add_change_badge(ax, gold_prices, font_prop)
    title_text = fa('قیمت جهانی طلا')
    ax.set_title(title_text, color='white', fontsize=18, fontweight='bold',
                 fontproperties=font_prop, pad=20)
    ax.set_xlabel(fa('ساعت'), color='#888888', fontsize=12, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (دلار)'), color='#888888', fontsize=12, fontproperties=font_prop)
    x_labels = [to_persian_digits(str(h)) for h in hours]
    ax.set_xticks(hours)
    ax.set_xticklabels(x_labels, color='#888888', fontsize=10, fontproperties=font_prop)
    y_padding = (max(gold_prices) - min(gold_prices)) * 0.15
    ax.set_ylim(min(gold_prices) - y_padding, max(gold_prices) + y_padding)
    y_ticks = ax.get_yticks()
    y_labels = [to_persian_digits(f"{tick:,.0f}") for tick in y_ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, color='#888888', fontsize=10, fontproperties=font_prop)
    plt.tight_layout()
    path = "gold_chart.png"
    plt.savefig(path, dpi=150, facecolor='#0d1117',
                bbox_inches='tight', pad_inches=0.2)
    plt.close()
    return path

def generate_professional_oil_chart(font_prop):
    hours = list(range(0, 24, 2))
    oil_prices = [82 + i*0.5 + np.sin(i/2.5)*1.5 for i in range(len(hours))]
    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')
    ax.plot(hours, oil_prices, color=COLORS['oil']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round')
    _create_gradient_fill(ax, hours, oil_prices, COLORS['oil']['line'])
    ax.fill_between(hours, oil_prices, min(oil_prices) - 2,
                     alpha=0.1, color=COLORS['oil']['line'], zorder=2)
    _style_axis_professional(ax, font_prop)
    _add_price_annotation(ax, hours, oil_prices, oil_prices[-1],
                          COLORS['oil']['line'], font_prop, currency='$')
    _add_change_badge(ax, oil_prices, font_prop)
    title_text = fa('قیمت جهانی نفت برنت')
    ax.set_title(title_text, color='white', fontsize=18, fontweight='bold',
                 fontproperties=font_prop, pad=20)
    ax.set_xlabel(fa('ساعت'), color='#888888', fontsize=12, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (دلار/بشکه)'), color='#888888', fontsize=12, fontproperties=font_prop)
    x_labels = [to_persian_digits(str(h)) for h in hours]
    ax.set_xticks(hours)
    ax.set_xticklabels(x_labels, color='#888888', fontsize=10, fontproperties=font_prop)
    y_padding = (max(oil_prices) - min(oil_prices)) * 0.15
    ax.set_ylim(min(oil_prices) - y_padding, max(oil_prices) + y_padding)
    y_ticks = ax.get_yticks()
    y_labels = [to_persian_digits(f"{tick:,.0f}") for tick in y_ticks]
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, color='#888888', fontsize=10, fontproperties=font_prop)
    plt.tight_layout()
    path = "oil_chart.png"
    plt.savefig(path, dpi=150, facecolor='#0d1117',
                bbox_inches='tight', pad_inches=0.2)
    plt.close()
    return path

def generate_professional_usd_chart(font_prop):
    hours = list(range(0, 24, 2))
    usd_toman = [52000 + i*80 + np.sin(i/2)*200 for i in range(len(hours))]
    tether_toman = [51500 + i*90 + np.cos(i/2.5)*150 for i in range(len(hours))]
    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')
    ax.plot(hours, usd_toman, color=COLORS['usd']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round')
    ax.plot(hours, tether_toman, color=COLORS['tether']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round')
    _create_gradient_fill(ax, hours, usd_toman, COLORS['usd']['line'])
    _create_gradient_fill(ax, hours, tether_toman, COLORS['tether']['line'])
    _style_axis_professional(ax, font_prop)
    _add_price_annotation(ax, hours, usd_toman, usd_toman[-1],
                          COLORS['usd']['line'], font_prop,
                          currency=' ت', label=fa('دلار'))
    _add_price_annotation(ax, hours, tether_toman, tether_toman[-1],
                          COLORS['tether']['line'], font_prop,
                          currency=' ت', label=fa('تتر'))
    _add_change_badge(ax, usd_toman, font_prop)
    title_text = fa('دلار و تتر به تومان')
    ax.set_title(title_text, color='white', fontsize=18, fontweight='bold',
                 fontproperties=font_prop, pad=20)
    ax.set_xlabel(fa('ساعت'), color='#888888', fontsize=12, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (تومان)'), color='#888888', fontsize=12, fontproperties=font_prop)
    x_labels = [to_persian_digits(str(h)) for h in hours]
    ax.set_xticks(hours)
    ax.set_xticklabels(x_labels, color='#888888', fontsize=10, fontproperties=font_prop)
    y_padding = (max(usd_toman + tether_toman) - min(usd_toman + tether_toman)) * 0.15
    ax.set_ylim(min(usd_toman + tether_toman) - y_padding,
                max(usd_toman + tether_toman) + y_padding)
    _abbreviate_y_axis_for_usd(ax)
    plt.tight_layout()
    path = "usd_chart.png"
    plt.savefig(path, dpi=150, facecolor='#0d1117',
                bbox_inches='tight', pad_inches=0.2)
    plt.close()
    return path

def generate_all_charts_professional():
    font_prop = setup_persian_font()
    paths = []
    paths.append(generate_professional_gold_chart(font_prop))
    paths.append(generate_professional_oil_chart(font_prop))
    paths.append(generate_professional_usd_chart(font_prop))
    return paths

def send_price_charts():
    paths = generate_all_charts_professional()
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("Telegram not configured. Charts saved locally:")
        for p in paths:
            print(f"  - {p}")
        return
    captions = [
        "🥇 <b>قیمت جهانی طلا</b>",
        "🛢️ <b>قیمت جهانی نفت برنت</b>",
        "💵 <b>دلار و تتر به تومان</b>"
    ]
    for path, caption in zip(paths, captions):
        with open(path, 'rb') as photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            files = {'photo': photo}
            data = {'chat_id': CHANNEL_ID, 'caption': caption, 'parse_mode': 'HTML'}
            resp = requests.post(url, data=data, files=files)
            print(f"{caption}: {resp.status_code}")
            os.remove(path)

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

# ================= COLLECT NEWS =================
def collect_news():
    processed = load_processed()
    queue = load_queue()

    print("Fetching feeds...")
    all_articles = []
    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:3]:
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
        # Check English keywords
        if any(kw in text for kw in KEYWORDS):
            relevant.append(art)
            continue
        # Check Russian keywords (if any Russian text present)
        if any(kw in text for kw in RUSSIAN_KEYWORDS):
            relevant.append(art)

    relevant_sorted = sorted(relevant, key=priority_score, reverse=True)
    new_articles = relevant_sorted[:MAX_POSTS_PER_RUN]

    for art in new_articles:
        if art not in queue:
            queue.append(art)
            processed.add(art['id'])

    save_queue(queue)
    save_processed(processed)
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
