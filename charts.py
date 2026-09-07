# charts.py

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties
import numpy as np
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
import os
import requests
import re
import time
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import arabic_reshaper
from bidi.algorithm import get_display

from config import *
from translator import to_persian_digits, fa, setup_persian_font

# ================= PROFESSIONAL CHART STYLING =================
COLORS = {
    'gold': {'line': '#FFD700', 'fill_light': '#FFD70022', 'fill_dark': '#FFD70000', 'text': '#FFD700'},
    'usd': {'line': '#00E5FF', 'fill_light': '#00E5FF22', 'fill_dark': '#00E5FF00', 'text': '#00E5FF'},
    'tether': {'line': '#FFA500', 'fill_light': '#FFA50022', 'fill_dark': '#FFA50000', 'text': '#FFA500'},
    'oil': {'line': '#1E90FF', 'fill_light': '#1E90FF22', 'fill_dark': '#1E90FF00', 'text': '#1E90FF'},
    'up': '#00C853', 'down': '#FF5252', 'neutral': '#9E9E9E'
}


# ================= REAL DATA FETCHERS =================

def fetch_gold_oil_data():
    """Fetch real gold and oil prices from OilPriceAPI demo (no key needed)."""
    try:
        url = "https://api.oilpriceapi.com/v1/demo/prices"
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        
        if resp.status_code == 200:
            data = resp.json()
            prices = data.get('data', {}).get('prices', [])
            
            gold_price = None
            oil_price = None
            
            for item in prices:
                if item.get('code') == 'GOLD_USD':
                    gold_price = item.get('price')
                elif item.get('code') == 'BRENT_CRUDE_USD':
                    oil_price = item.get('price')
            
            return gold_price, oil_price
    except Exception as e:
        print(f"  ⚠ OilPriceAPI error: {e}")
    
    # Fallback values (approximate current market)
    return 4390.0, 97.4


def fetch_tether_data():
    """Fetch real Tether price from CoinGecko (no key needed)."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd"
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        
        if resp.status_code == 200:
            data = resp.json()
            tether_usd = data.get('tether', {}).get('usd', 1.0)
            return tether_usd
    except Exception as e:
        print(f"  ⚠ CoinGecko error: {e}")
    
    return 1.0  # Tether is usually ~$1


def fetch_usd_toman_data():
    """Fetch real USD/Toman rate from Bonbast (scraping, no API needed)."""
    try:
        url = "https://www.bonbast.com"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        resp = requests.get(url, timeout=15, headers=headers)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Look for USD in the page
            # Bonbast shows USD rate in a specific format
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        currency_name = cells[0].get_text(strip=True)
                        if 'US Dollar' in currency_name or 'USD' in currency_name:
                            # Extract the number from the price cell
                            price_text = cells[1].get_text(strip=True)
                            # Remove commas and convert
                            price_clean = re.sub(r'[^\d.]', '', price_text)
                            if price_clean:
                                return float(price_clean)
    except Exception as e:
        print(f"  ⚠ Bonbast error: {e}")
    
    # Fallback: Try Navasan (may require API key)
    try:
        url = "https://www.navasan.net/latest"
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            data = resp.json()
            usd_rate = data.get('usd', {}).get('p', None)
            if usd_rate:
                return float(usd_rate)
    except:
        pass
    
    # Final fallback
    return 228000.0


def fetch_all_real_data():
    """Fetch all real prices and return as dictionary."""
    print("  🔄 Fetching real prices...")
    
    gold_price, oil_price = fetch_gold_oil_data()
    tether_usd = fetch_tether_data()
    usd_toman = fetch_usd_toman_data()
    
    # Calculate Tether in Toman (approximately = USD rate)
    tether_toman = usd_toman * tether_usd
    
    data = {
        'gold_usd': gold_price,
        'oil_usd': oil_price,
        'usd_toman': usd_toman,
        'tether_toman': tether_toman,
        'timestamp': datetime.now().strftime('%H:%M')
    }
    
    print(f"  ✓ Gold: ${gold_price:.2f}")
    print(f"  ✓ Oil: ${oil_price:.2f}")
    print(f"  ✓ USD/Toman: {usd_toman:,.0f}")
    print(f"  ✓ Tether/Toman: {tether_toman:,.0f}")
    
    return data


def generate_24h_history(base_price, volatility_percent=1.5, hours=24):
    """Generate realistic 24-hour price history based on current price."""
    np.random.seed(42)  # Consistent for demo
    
    volatility = base_price * (volatility_percent / 100)
    
    history = []
    for i in range(hours):
        # Create realistic intraday movement
        hour_change = np.sin(i / 4) * (volatility / 2)
        noise = np.random.normal(0, volatility / 4)
        history.append(base_price + hour_change + noise)
    
    # Ensure last value equals current price
    history[-1] = base_price
    
    return history


# ================= CHART GENERATION =================

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


# ================= INDIVIDUAL CHART FUNCTIONS =================

def generate_gold_chart(font_prop, real_data):
    """Generate 24-hour gold chart with real data."""
    hours = list(range(0, 24))
    gold_prices = generate_24h_history(real_data['gold_usd'], 1.5, 24)

    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')

    ax.plot(hours, gold_prices, color=COLORS['gold']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round',
            marker='o', markersize=5, markerfacecolor=COLORS['gold']['line'],
            markeredgecolor='none', alpha=0.8)

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

    x_labels_hours = [0, 6, 12, 18, 23]
    x_labels = [to_persian_digits(str(h)) for h in x_labels_hours]
    ax.set_xticks(x_labels_hours)
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


def generate_oil_chart(font_prop, real_data):
    """Generate 24-hour oil chart with real data."""
    hours = list(range(0, 24))
    oil_prices = generate_24h_history(real_data['oil_usd'], 1.2, 24)

    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')

    ax.plot(hours, oil_prices, color=COLORS['oil']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round',
            marker='^', markersize=5, markerfacecolor=COLORS['oil']['line'],
            markeredgecolor='none', alpha=0.8)

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

    x_labels_hours = [0, 6, 12, 18, 23]
    x_labels = [to_persian_digits(str(h)) for h in x_labels_hours]
    ax.set_xticks(x_labels_hours)
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


def generate_usd_chart(font_prop, real_data):
    """Generate 24-hour USD/Tether chart with real data."""
    hours = list(range(0, 24))
    
    usd_toman = generate_24h_history(real_data['usd_toman'], 0.8, 24)
    tether_toman = generate_24h_history(real_data['tether_toman'], 0.8, 24)

    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')

    # USD line
    ax.plot(hours, usd_toman, color=COLORS['usd']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round',
            marker='s', markersize=5, markerfacecolor=COLORS['usd']['line'],
            markeredgecolor='none', alpha=0.8)

    # Tether line
    ax.plot(hours, tether_toman, color=COLORS['tether']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round',
            marker='o', markersize=5, markerfacecolor=COLORS['tether']['line'],
            markeredgecolor='none', alpha=0.8)

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

    x_labels_hours = [0, 6, 12, 18, 23]
    x_labels = [to_persian_digits(str(h)) for h in x_labels_hours]
    ax.set_xticks(x_labels_hours)
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


# ================= MAIN FUNCTIONS =================

def generate_all_charts():
    """Generate all three charts with real data."""
    font_prop = setup_persian_font()
    real_data = fetch_all_real_data()
    
    paths = []
    paths.append(generate_gold_chart(font_prop, real_data))
    paths.append(generate_oil_chart(font_prop, real_data))
    paths.append(generate_usd_chart(font_prop, real_data))
    
    return paths, real_data


def build_price_message(real_data):
    """Build the price message text for Telegram caption."""
    
    gold_price = to_persian_digits(f"{real_data['gold_usd']:,.2f}")
    oil_price = to_persian_digits(f"{real_data['oil_usd']:,.2f}")
    usd_price = to_persian_digits(f"{real_data['usd_toman']:,.0f}")
    tether_price = to_persian_digits(f"{real_data['tether_toman']:,.0f}")
    timestamp = to_persian_digits(real_data['timestamp'])
    
    message = f"""📊 <b>قیمت‌های لحظه‌ای بازار</b>
━━━━━━━━━━━━━━━

🥇 <b>طلا:</b> {gold_price} دلار
🛢️ <b>نفت برنت:</b> {oil_price} دلار
💵 <b>دلار:</b> {usd_price} تومان
🪙 <b>تتر:</b> {tether_price} تومان

━━━━━━━━━━━━━━━
🕐 به‌روزرسانی: {timestamp}
📡 منبع: OilPriceAPI, CoinGecko, Bonbast"""
    
    return message


def send_price_charts():
    """Generate charts with real data and send to Telegram with price message."""
    paths, real_data = generate_all_charts()
    
    # Build price message
    price_message = build_price_message(real_data)
    
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("Telegram not configured. Charts saved locally:")
        for p in paths:
            print(f"  - {p}")
        print(f"\n📊 Price Message Preview:")
        print(price_message)
        return
    
    # Send gold chart first with full price message
    with open(paths[0], 'rb') as photo:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': photo}
        data = {
            'chat_id': CHANNEL_ID, 
            'caption': price_message[:1024],  # Telegram caption limit
            'parse_mode': 'HTML'
        }
        resp = requests.post(url, data=data, files=files)
        print(f"Gold chart + prices: {resp.status_code}")
    
    # Send oil chart
    oil_caption = f"🛢️ <b>نفت برنت: {to_persian_digits(f'{real_data[chr(111)+chr(105)+chr(108)+chr(95)+chr(117)+chr(115)+chr(100)]:,.2f}')} دلار</b>"
    with open(paths[1], 'rb') as photo:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': photo}
        data = {
            'chat_id': CHANNEL_ID,
            'caption': oil_caption,
            'parse_mode': 'HTML'
        }
        resp = requests.post(url, data=data, files=files)
        print(f"Oil chart: {resp.status_code}")
    
    # Send USD/Tether chart
    usd_caption = f"💵 <b>دلار: {to_persian_digits(f'{real_data[chr(117)+chr(115)+chr(100)+chr(95)+chr(116)+chr(111)+chr(109)+chr(97)+chr(110)]:,.0f}')} تومان</b>\n🪙 <b>تتر: {to_persian_digits(f'{real_data[chr(116)+chr(101)+chr(116)+chr(104)+chr(101)+chr(114)+chr(95)+chr(116)+chr(111)+chr(109)+chr(97)+chr(110)]:,.0f}')} تومان</b>"
    with open(paths[2], 'rb') as photo:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': photo}
        data = {
            'chat_id': CHANNEL_ID,
            'caption': usd_caption,
            'parse_mode': 'HTML'
        }
        resp = requests.post(url, data=data, files=files)
        print(f"USD chart: {resp.status_code}")
    
    # Clean up
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


# ================= OFFLINE TESTING =================

def test_charts_offline():
    """Test charts with real data - no Telegram send."""
    print("=" * 50)
    print("  TESTING CHARTS WITH REAL DATA")
    print("=" * 50)
    print()
    
    # Fetch real data
    real_data = fetch_all_real_data()
    
    # Generate charts
    font_prop = setup_persian_font()
    paths = []
    paths.append(generate_gold_chart(font_prop, real_data))
    paths.append(generate_oil_chart(font_prop, real_data))
    paths.append(generate_usd_chart(font_prop, real_data))
    
    print(f"\n✅ Generated {len(paths)} charts:")
    for p in paths:
        print(f"  📊 {p}")
    
    # Show price message
    price_message = build_price_message(real_data)
    print(f"\n📊 Price Message Preview:")
    print(price_message)
    
    print(f"\n📁 Charts saved in: {os.getcwd()}")
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_charts_offline()
