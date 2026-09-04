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
_persian_font_prop = None

def setup_persian_font():
    """Download and register Persian font, return FontProperties."""
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
    """Convert Western Arabic numerals (0-9) to Eastern Arabic numerals (۰-۹)."""
    if not text:
        return text
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    western_digits = '0123456789'
    translation = str.maketrans(western_digits, persian_digits)
    return text.translate(translation)

def fa(text):
    """
    Convert Persian/Arabic text for correct rendering in matplotlib.
    Reshape letters, convert digits, but do NOT reverse (font handles RTL).
    """
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

# Known Persian text corrections
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

def try_translate_with_model(text, model):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are a professional financial translator. "
        "First, rewrite the user's financial news text into complete, grammatically correct English sentences. "
        "Then translate the rewritten English into Persian (Farsi). "
        "Use standard Persian financial terminology. "
        "Convert all Western numerals (0-9) to Persian numerals (۰-۹) in the Persian output. "
        "If the text mentions the Iranian government or officials, use respectful language: "
        "refer to the 'Islamic Republic of Iran' as 'جمهوری اسلامی ایران', "
        "and Iranian officials as 'مقامات ایرانی' or 'دولت ایران'. "
        "Never refuse, never apologize, just output the final Persian translation without reasoning or thinking."
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

# ================= CHART GENERATION (3 SEPARATE CHARTS) =================
def _set_dark_style():
    plt.style.use('dark_background')
    plt.rcParams['axes.unicode_minus'] = False
    fig = plt.figure(figsize=(10, 6), facecolor='#1a1a2e')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#1a1a2e')
    ax.grid(True, linestyle='--', alpha=0.3, color='#aaaaaa')
    for spine in ax.spines.values():
        spine.set_color('#aaaaaa')
    return fig, ax

def _set_persian_ticks(ax, x_ticks, y_ticks, font_prop):
    x_labels = [to_persian_digits(str(h)) for h in x_ticks]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels, color='white', fontsize=10, fontproperties=font_prop)
    y_ticks_filtered = [t for t in y_ticks if t >= 0]
    y_labels = [to_persian_digits(str(int(t))) for t in y_ticks_filtered]
    ax.set_yticks(y_ticks_filtered)
    ax.set_yticklabels(y_labels, color='white', fontsize=10, fontproperties=font_prop)

def generate_gold_chart(font_prop):
    hours = list(range(0, 24, 2))
    gold_prices = [2030 + i*2 for i in range(len(hours))]

    fig, ax = _set_dark_style()
    ax.plot(hours, gold_prices, color='#ffd700', linewidth=2.5, marker='o', markersize=5)
    ax.set_title(fa('قیمت طلا'), color='white', fontsize=16, fontproperties=font_prop, pad=15)
    ax.set_xlabel(fa('ساعت'), color='white', fontsize=12, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (دلار)'), color='white', fontsize=12, fontproperties=font_prop)
    _set_persian_ticks(ax, hours, ax.get_yticks(), font_prop)

    mid_idx = len(hours) // 2
    ax.text(hours[mid_idx], gold_prices[mid_idx] + 2, fa('طلا'), color='#ffd700',
            fontsize=12, fontproperties=font_prop, ha='center', va='bottom')

    plt.tight_layout()
    path = "gold_chart.png"
    plt.savefig(path, dpi=150, facecolor='#1a1a2e', bbox_inches='tight', pad_inches=0.3)
    plt.close()
    return path

def generate_oil_chart(font_prop):
    hours = list(range(0, 24, 2))
    oil_prices = [82 + i*0.5 for i in range(len(hours))]

    fig, ax = _set_dark_style()
    # Blue line
    ax.plot(hours, oil_prices, color='#1e90ff', linewidth=2.5, marker='^', markersize=5)
    ax.set_title(fa('قیمت نفت برنت'), color='white', fontsize=16, fontproperties=font_prop, pad=15)
    ax.set_xlabel(fa('ساعت'), color='white', fontsize=12, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (دلار/بشکه)'), color='white', fontsize=12, fontproperties=font_prop)
    _set_persian_ticks(ax, hours, ax.get_yticks(), font_prop)

    mid_idx = len(hours) // 2
    ax.text(hours[mid_idx], oil_prices[mid_idx] + 0.5, fa('نفت'), color='#1e90ff',
            fontsize=12, fontproperties=font_prop, ha='center', va='bottom')

    plt.tight_layout()
    path = "oil_chart.png"
    plt.savefig(path, dpi=150, facecolor='#1a1a2e', bbox_inches='tight', pad_inches=0.3)
    plt.close()
    return path

def generate_usd_chart(font_prop):
    hours = list(range(0, 24, 2))
    # Mock data: USD/Toman and Tether/Toman
    usd_toman = [52000 + i*100 for i in range(len(hours))]
    tether_toman = [51500 + i*120 for i in range(len(hours))]

    fig, ax = _set_dark_style()
    # USD line green, Tether line blue
    ax.plot(hours, usd_toman, color='#39ff14', linewidth=2.5, marker='s', markersize=5)
    ax.plot(hours, tether_toman, color='#1e90ff', linewidth=2.5, marker='o', markersize=5)

    ax.set_title(fa('قیمت دلار و تتر'), color='white', fontsize=16, fontproperties=font_prop, pad=15)
    ax.set_xlabel(fa('ساعت'), color='white', fontsize=12, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (تومان)'), color='white', fontsize=12, fontproperties=font_prop)
    _set_persian_ticks(ax, hours, ax.get_yticks(), font_prop)

    # Calculate vertical offsets proportional to data range
    y_min = min(min(usd_toman), min(tether_toman))
    y_max = max(max(usd_toman), max(tether_toman))
    y_range = y_max - y_min
    offset = y_range * 0.03

    mid_idx = len(hours) // 2

    # USD label (green)
    ax.text(hours[mid_idx], usd_toman[mid_idx] + offset, '$', color='#39ff14',
            fontsize=14, fontweight='bold', ha='center', va='bottom',
            fontfamily='DejaVu Sans')

    # Tether label (blue)
    ax.text(hours[mid_idx], tether_toman[mid_idx] - offset, '₮', color='#1e90ff',
            fontsize=14, fontweight='bold', ha='center', va='top',
            fontfamily='DejaVu Sans')

    plt.tight_layout()
    path = "usd_chart.png"
    plt.savefig(path, dpi=150, facecolor='#1a1a2e', bbox_inches='tight', pad_inches=0.3)
    plt.close()
    return path

def generate_all_charts():
    font_prop = setup_persian_font()
    paths = []
    paths.append(generate_gold_chart(font_prop))
    paths.append(generate_oil_chart(font_prop))
    paths.append(generate_usd_chart(font_prop))
    return paths

def send_price_charts():
    paths = generate_all_charts()
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("Telegram not configured. Charts saved locally:")
        for p in paths:
            print(f"  - {p}")
        return
    for path, caption in zip(paths, ["📊 قیمت طلا", "📊 قیمت نفت برنت", "📊 دلار و تتر"]):
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
        send_price_charts()
    elif mode == "weekly":
        weekly_summary()
    elif mode == "calendar":
        economic_calendar()
    else:
        print("Unknown mode. Use: news, chart, weekly, calendar")
