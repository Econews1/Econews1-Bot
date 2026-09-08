# charts.py

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon
import os
import requests
import re
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

try:
    import yfinance as yf
    HAS_YFINANCE = True
except Exception:
    HAS_YFINANCE = False

from config import *
from translator import to_persian_digits, fa, setup_persian_font

if 'TELEGRAM_BOT_TOKEN' not in globals():
    TELEGRAM_BOT_TOKEN = ''
if 'CHANNEL_ID' not in globals():
    CHANNEL_ID = ''

# ================= PROFESSIONAL CHART STYLING =================
COLORS = {
    'gold': {'line': '#FFD700', 'text': '#FFD700'},
    'usd': {'line': '#00E5FF', 'text': '#00E5FF'},
    'tether': {'line': '#FFA500', 'text': '#FFA500'},
    'oil': {'line': '#1E90FF', 'text': '#1E90FF'},
    'up': '#00C853', 'down': '#FF5252', 'neutral': '#9E9E9E'
}

PRICE_HISTORY_FILE = "price_history.json"

# ================= LOAD PRICE HISTORY =================
def load_price_history():
    if os.path.exists(PRICE_HISTORY_FILE):
        with open(PRICE_HISTORY_FILE, 'r') as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

# ================= REAL DATA FETCHERS (fallback) =================
def fetch_current_gold_oil():
    try:
        url = "https://api.oilpriceapi.com/v1/demo/prices"
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            data = resp.json()
            prices = data.get('data', {}).get('prices', [])
            gold = None
            oil = None
            for item in prices:
                if item.get('code') == 'GOLD_USD':
                    gold = item.get('price')
                elif item.get('code') == 'BRENT_CRUDE_USD':
                    oil = item.get('price')
            if gold and oil:
                return gold, oil
    except Exception:
        pass
    return 4390.0, 97.4


def fetch_usd_toman_current():
    try:
        url = "https://www.bonbast.com"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, timeout=15, headers=headers)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        currency = cells[0].get_text(strip=True)
                        if 'US Dollar' in currency or 'USD' in currency:
                            price_text = cells[1].get_text(strip=True)
                            price_clean = re.sub(r'[^\d.]', '', price_text)
                            if price_clean:
                                return float(price_clean)
    except Exception:
        pass
    try:
        url = "https://www.navasan.net/latest"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            usd = data.get('usd', {}).get('p')
            if usd:
                return float(usd)
    except Exception:
        pass
    return 228000.0


def get_historical_from_yfinance(ticker, hours=24):
    if not HAS_YFINANCE:
        return None
    end = datetime.now()
    start = end - timedelta(hours=hours)
    try:
        df = yf.download(ticker, start=start, end=end, interval='1h', progress=False)
        if not df.empty:
            prices = df['Close'].values
            if len(prices) >= hours:
                prices = prices[-hours:]
            else:
                prices = np.pad(prices, (hours - len(prices), 0), mode='edge')
            return [float(p) for p in prices]
    except Exception:
        pass
    return None

# ================= MAIN DATA COMPOSITION =================
def get_24h_data_for_asset(asset_key):
    """24 hourly prices: recorded history -> yfinance -> synthetic fallback."""
    history = load_price_history()
    if history and len(history) >= 4:
        try:
            timestamps = [datetime.fromisoformat(e['timestamp']) for e in history]
            prices = [float(e[asset_key]) for e in history]
            pairs = sorted(zip(timestamps, prices), key=lambda p: p[0])
            timestamps = [p[0] for p in pairs]
            prices = [p[1] for p in pairs]
            now = datetime.now()
            hourly_times = [now - timedelta(hours=i) for i in range(23, -1, -1)]
            ts_sec = np.array([(t - datetime(1970, 1, 1)).total_seconds() for t in timestamps])
            hourly_sec = np.array([(t - datetime(1970, 1, 1)).total_seconds() for t in hourly_times])
            if len(np.unique(ts_sec)) > 1:
                return np.interp(hourly_sec, ts_sec, prices).tolist()
        except Exception as e:
            print(f"  ⚠ History interpolation failed: {e}")

    if asset_key in ('gold_usd', 'oil_usd') and HAS_YFINANCE:
        ticker = 'GC=F' if asset_key == 'gold_usd' else 'BZ=F'
        data = get_historical_from_yfinance(ticker, 24)
        if data:
            return data

    # Synthetic fallback around the current price
    try:
        if asset_key == 'gold_usd':
            base, vol = fetch_current_gold_oil()[0], 1.5
        elif asset_key == 'oil_usd':
            base, vol = fetch_current_gold_oil()[1], 1.2
        else:
            base, vol = fetch_usd_toman_current(), 0.8
    except Exception:
        base = 4390.0 if asset_key == 'gold_usd' else (97.4 if asset_key == 'oil_usd' else 228000.0)
        vol = 1.0

    seed_map = {'gold_usd': 42, 'oil_usd': 7, 'usd_toman': 21, 'tether_toman': 84}
    np.random.seed(seed_map.get(asset_key, 42))
    vol_val = base * (vol / 100)
    prices = []
    for i in range(24):
        hour_change = np.sin(i / 4) * (vol_val / 2)
        noise = np.random.normal(0, vol_val / 4)
        prices.append(base + hour_change + noise)
    prices[-1] = base
    return prices

# ================= CHART HELPERS =================
def _create_gradient_fill(ax, x, y, color_hex, alpha_top=0.25):
    """Fill under the line with a vertical gradient."""
    try:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        rgb = mcolors.to_rgb(color_hex)
        z = np.empty((100, 1, 4))
        z[:, :, :3] = rgb
        z[:, :, 3] = np.linspace(0.0, alpha_top, 100)[:, None]
        xmin, xmax = float(x.min()), float(x.max())
        y_min, y_max = float(y.min()), float(y.max())
        if y_max - y_min < 1e-9:
            y_min, y_max = y_min - 1, y_max + 1
        pad = (y_max - y_min) * 0.25
        im = ax.imshow(z, aspect='auto', extent=[xmin, xmax, y_min - pad, y_max],
                       origin='lower', zorder=1)
        xy = np.vstack([[xmin, y_min - pad], np.column_stack([x, y]), [xmax, y_min - pad]])
        clip = Polygon(xy, closed=True, facecolor='none', edgecolor='none')
        ax.add_patch(clip)
        im.set_clip_path(clip)
    except Exception as e:
        print(f"  ⚠ Gradient fill failed: {e}")


def _style_axis_professional(ax, font_prop=None):
    ax.set_facecolor('#0d1117')
    for spine in ax.spines.values():
        spine.set_color('#30363d')
    ax.grid(True, color='#21262d', linestyle='--', linewidth=0.8, alpha=0.9)
    ax.tick_params(colors='#8b949e', length=4)


def _add_price_annotation(ax, x, y, price, color, font_prop, currency='$'):
    try:
        label = fa(f"{currency}{price:,.2f}")
        ax.annotate(label,
                    xy=(float(x[-1]), float(y[-1])),
                    xytext=(-15, 22), textcoords='offset points',
                    color='white', fontsize=12, fontweight='bold',
                    fontproperties=font_prop,
                    bbox=dict(boxstyle='round,pad=0.35', facecolor=color,
                              alpha=0.9, edgecolor='none'),
                    ha='right', va='bottom', zorder=6)
    except Exception as e:
        print(f"  ⚠ Price annotation failed: {e}")


def _add_change_badge(ax, prices, font_prop):
    """Green badge for gains, red for losses."""
    try:
        prices = list(prices)
        if len(prices) < 2 or not prices[0]:
            return
        first, last = float(prices[0]), float(prices[-1])
        change_pct = (last - first) / abs(first) * 100
        if change_pct > 0.05:
            color, txt = COLORS['up'], f"+{change_pct:.2f}%"
        elif change_pct < -0.05:
            color, txt = COLORS['down'], f"{change_pct:.2f}%"
        else:
            color, txt = COLORS['neutral'], f"{change_pct:.2f}%"
        ax.text(0.02, 0.96, to_persian_digits(txt), transform=ax.transAxes,
                color='white', fontsize=14, fontweight='bold',
                fontproperties=font_prop, va='top', zorder=6,
                bbox=dict(boxstyle='round,pad=0.45', facecolor=color,
                          alpha=0.92, edgecolor='none'))
    except Exception as e:
        print(f"  ⚠ Change badge failed: {e}")


def _abbreviate_y_axis_for_usd(ax, font_prop=None):
    ticks = ax.get_yticks()
    labels = []
    for t in ticks:
        t = float(t)
        if abs(t) >= 1_000_000:
            s = f"{t / 1_000_000:.1f}M"
        elif abs(t) >= 1_000:
            s = f"{t / 1_000:.0f}K"
        else:
            s = f"{t:.0f}"
        labels.append(to_persian_digits(s))
    ax.set_yticklabels(labels, color='#8b949e', fontsize=11)

# ================= CHART GENERATION =================
def generate_gold_chart(font_prop):
    prices = get_24h_data_for_asset('gold_usd')
    hours = list(range(0, 24))
    fig = plt.figure(figsize=(10, 5.5), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')
    ax.plot(hours, prices, color=COLORS['gold']['line'], linewidth=2.5, zorder=3,
            marker='o', markersize=5, markerfacecolor=COLORS['gold']['line'],
            markeredgecolor='none', alpha=0.8)
    _create_gradient_fill(ax, hours, prices, COLORS['gold']['line'])
    ax.fill_between(hours, prices, min(prices) - 20, alpha=0.1,
                    color=COLORS['gold']['line'], zorder=2)
    _style_axis_professional(ax, font_prop)
    _add_price_annotation(ax, hours, prices, prices[-1], COLORS['gold']['line'], font_prop, currency='$')
    _add_change_badge(ax, prices, font_prop)
    ax.set_title(fa('قیمت جهانی طلا'), color='white', fontsize=20,
                 fontweight='bold', fontproperties=font_prop, pad=20)
    ax.set_xlabel(fa('ساعت'), color='#888888', fontsize=14, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (دلار)'), color='#888888', fontsize=14, fontproperties=font_prop)
    x_labels = [0, 6, 12, 18, 23]
    ax.set_xticks(x_labels)
    ax.set_xticklabels([to_persian_digits(str(h)) for h in x_labels],
                       color='#888888', fontsize=12, fontproperties=font_prop)
    y_padding = (max(prices) - min(prices)) * 0.15
    ax.set_ylim(min(prices) - y_padding, max(prices) + y_padding)
    y_ticks = ax.get_yticks()
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([to_persian_digits(f"{tick:,.0f}") for tick in y_ticks],
                       color='#888888', fontsize=12, fontproperties=font_prop)
    plt.tight_layout()
    path = "gold_chart.png"
    plt.savefig(path, dpi=150, facecolor='#0d1117', bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    return path


def generate_oil_chart(font_prop):
    prices = get_24h_data_for_asset('oil_usd')
    hours = list(range(0, 24))
    fig = plt.figure(figsize=(10, 5.5), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')
    ax.plot(hours, prices, color=COLORS['oil']['line'], linewidth=2.5, zorder=3,
            marker='^', markersize=5, markerfacecolor=COLORS['oil']['line'],
            markeredgecolor='none', alpha=0.8)
    _create_gradient_fill(ax, hours, prices, COLORS['oil']['line'])
    ax.fill_between(hours, prices, min(prices) - 2, alpha=0.1,
                    color=COLORS['oil']['line'], zorder=2)
    _style_axis_professional(ax, font_prop)
    _add_price_annotation(ax, hours, prices, prices[-1], COLORS['oil']['line'], font_prop, currency='$')
    _add_change_badge(ax, prices, font_prop)
    ax.set_title(fa('قیمت جهانی نفت برنت'), color='white', fontsize=20,
                 fontweight='bold', fontproperties=font_prop, pad=20)
    ax.set_xlabel(fa('ساعت'), color='#888888', fontsize=14, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (دلار/بشکه)'), color='#888888', fontsize=14, fontproperties=font_prop)
    x_labels = [0, 6, 12, 18, 23]
    ax.set_xticks(x_labels)
    ax.set_xticklabels([to_persian_digits(str(h)) for h in x_labels],
                       color='#888888', fontsize=12, fontproperties=font_prop)
    y_padding = (max(prices) - min(prices)) * 0.15
    ax.set_ylim(min(prices) - y_padding, max(prices) + y_padding)
    y_ticks = ax.get_yticks()
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([to_persian_digits(f"{tick:,.1f}") for tick in y_ticks],
                       color='#888888', fontsize=12, fontproperties=font_prop)
    plt.tight_layout()
    path = "oil_chart.png"
    plt.savefig(path, dpi=150, facecolor='#0d1117', bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    return path


def generate_usd_chart(font_prop):
    usd_prices = get_24h_data_for_asset('usd_toman')
    tether_prices = get_24h_data_for_asset('tether_toman')
    hours = list(range(0, 24))
    fig = plt.figure(figsize=(10, 5.5), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')
    ax.plot(hours, usd_prices, color=COLORS['usd']['line'], linewidth=2.5, zorder=3,
            marker='s', markersize=5, markerfacecolor=COLORS['usd']['line'],
            markeredgecolor='none', alpha=0.8)
    ax.plot(hours, tether_prices, color=COLORS['tether']['line'], linewidth=2.5, zorder=3,
            marker='o', markersize=5, markerfacecolor=COLORS['tether']['line'],
            markeredgecolor='none', alpha=0.8)
    _create_gradient_fill(ax, hours, usd_prices, COLORS['usd']['line'])
    _create_gradient_fill(ax, hours, tether_prices, COLORS['tether']['line'])
    _style_axis_professional(ax, font_prop)
    _add_change_badge(ax, usd_prices, font_prop)

    usd_price_text = to_persian_digits(f"{usd_prices[-1]:,.0f}")
    ax.text(0.95, 0.95, fa('دلار') + '\n' + usd_price_text + ' ت',
            transform=ax.transAxes, color='white', fontsize=13,
            bbox=dict(boxstyle='round,pad=0.4', facecolor=COLORS['usd']['line'],
                      alpha=0.85, edgecolor='none'),
            ha='right', va='top', fontproperties=font_prop, linespacing=1.5)
    tether_price_text = to_persian_digits(f"{tether_prices[-1]:,.0f}")
    ax.text(0.95, 0.82, fa('تتر') + '\n' + tether_price_text + ' ت',
            transform=ax.transAxes, color='white', fontsize=13,
            bbox=dict(boxstyle='round,pad=0.4', facecolor=COLORS['tether']['line'],
                      alpha=0.85, edgecolor='none'),
            ha='right', va='top', fontproperties=font_prop, linespacing=1.5)

    ax.set_title(fa('دلار و تتر به تومان'), color='white', fontsize=20,
                 fontweight='bold', fontproperties=font_prop, pad=20)
    ax.set_xlabel(fa('ساعت'), color='#888888', fontsize=14, fontproperties=font_prop)
    ax.set_ylabel(fa('قیمت (تومان)'), color='#888888', fontsize=14, fontproperties=font_prop)
    x_labels = [0, 6, 12, 18, 23]
    ax.set_xticks(x_labels)
    ax.set_xticklabels([to_persian_digits(str(h)) for h in x_labels],
                       color='#888888', fontsize=12, fontproperties=font_prop)
    all_prices = list(usd_prices) + list(tether_prices)
    y_padding = (max(all_prices) - min(all_prices)) * 0.15
    ax.set_ylim(min(all_prices) - y_padding, max(all_prices) + y_padding)
    _abbreviate_y_axis_for_usd(ax, font_prop)
    plt.tight_layout()
    path = "usd_chart.png"
    plt.savefig(path, dpi=150, facecolor='#0d1117', bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    return path

# ================= MAIN FUNCTIONS =================
def generate_all_charts():
    font_prop = setup_persian_font()
    paths = [generate_gold_chart(font_prop),
             generate_oil_chart(font_prop),
             generate_usd_chart(font_prop)]
    history = load_price_history()
    if history:
        last = history[-1]
        gold = last['gold_usd']
        oil = last['oil_usd']
        usd = last['usd_toman']
        tether = last['tether_toman']
    else:
        gold, oil = fetch_current_gold_oil()
        usd = fetch_usd_toman_current()
        tether = usd
    real_data = {
        'gold_usd': gold, 'oil_usd': oil, 'usd_toman': usd, 'tether_toman': tether,
        'timestamp': datetime.now().strftime('%H:%M')
    }
    return paths, real_data


def build_price_message(real_data):
    gold_price = to_persian_digits(f"{real_data['gold_usd']:,.2f}")
    oil_price = to_persian_digits(f"{real_data['oil_usd']:,.2f}")
    usd_price = to_persian_digits(f"{real_data['usd_toman']:,.0f}")
    tether_price = to_persian_digits(f"{real_data['tether_toman']:,.0f}")
    timestamp = to_persian_digits(real_data['timestamp'])
    return f"""📊 <b>قیمت‌های لحظه‌ای بازار</b>
━━━━━━━━━━━━━━━

🥇 <b>طلا:</b> {gold_price} دلار
🛢️ <b>نفت برنت:</b> {oil_price} دلار
💵 <b>دلار:</b> {usd_price} تومان
🪙 <b>تتر:</b> {tether_price} تومان

━━━━━━━━━━━━━━━
🕐 به‌روزرسانی: {timestamp}"""


def send_price_charts():
    """Generate the three price charts and send them to the Telegram channel."""
    print("📈 Generating price charts...")
    try:
        paths, real_data = generate_all_charts()
    except Exception as e:
        print(f"  ⚠ Chart generation failed: {e}")
        return False

    message = build_price_message(real_data)
    print(message)

    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("  ⚠ Telegram not configured - charts saved locally only")
        return False

    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    sent_any = False
    for i, path in enumerate(paths):
        try:
            caption = message if i == 0 else ''
            with open(path, 'rb') as f:
                resp = requests.post(
                    f"{api}/sendPhoto",
                    data={'chat_id': CHANNEL_ID, 'caption': caption, 'parse_mode': 'HTML'},
                    files={'photo': f},
                    timeout=90)
            if resp.status_code == 200:
                print(f"  ✓ Chart sent: {os.path.basename(path)}")
                sent_any = True
            else:
                print(f"  ✗ Chart send failed ({resp.status_code}): {resp.text[:120]}")
        except Exception as e:
            print(f"  ✗ Chart send error: {e}")
    return sent_any


def test_charts_offline():
    print("🧪 Offline chart test")
    font_prop = setup_persian_font()
    for gen in (generate_gold_chart, generate_oil_chart, generate_usd_chart):
        try:
            p = gen(font_prop)
            print(f"  ✓ saved {p}")
        except Exception as e:
            print(f"  ✗ {gen.__name__} failed: {e}")


if __name__ == "__main__":
    test_charts_offline()
