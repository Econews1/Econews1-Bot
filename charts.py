# charts.py

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties
import numpy as np
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
import os
import requests
import re
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


def _generate_24h_data(base_price, volatility, hours=24):
    """Generate realistic 24-hour price data."""
    np.random.seed(42)  # For consistent demo data
    data = []
    for i in range(hours):
        # Add trend + random noise
        change = np.sin(i / 4) * volatility + np.random.normal(0, volatility * 0.3)
        data.append(base_price + change)
    return data


# ================= CHART GENERATION FUNCTIONS =================

def generate_professional_gold_chart(font_prop):
    """Generate 24-hour gold price chart with hourly dots."""
    hours = list(range(0, 24))  # 24 hours = 1 day
    gold_prices = _generate_24h_data(2030, 8, 24)  # Base: $2030, volatility: $8

    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')

    # Plot line with dots at every hour
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

    # X-axis: Show label every 6 hours, but dots on every hour
    x_labels_hours = [0, 6, 12, 18, 23]  # 0, 6, 12, 18, 23
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


def generate_professional_oil_chart(font_prop):
    """Generate 24-hour oil price chart with hourly dots."""
    hours = list(range(0, 24))  # 24 hours = 1 day
    oil_prices = _generate_24h_data(82, 1.2, 24)  # Base: $82, volatility: $1.2

    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')

    # Plot line with dots at every hour
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

    # X-axis: Show label every 6 hours, but dots on every hour
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


def generate_professional_usd_chart(font_prop):
    """Generate 24-hour USD/IRT and Tether chart with hourly dots."""
    hours = list(range(0, 24))  # 24 hours = 1 day

    # Generate 24-hour data
    usd_toman = _generate_24h_data(52000, 300, 24)
    tether_toman = _generate_24h_data(51500, 280, 24)

    fig = plt.figure(figsize=(12, 7), facecolor='#0d1117')
    ax = fig.add_subplot(111)
    ax.set_facecolor('#0d1117')

    # Plot USD line with dots
    ax.plot(hours, usd_toman, color=COLORS['usd']['line'],
            linewidth=2.5, zorder=3, solid_capstyle='round',
            marker='s', markersize=5, markerfacecolor=COLORS['usd']['line'],
            markeredgecolor='none', alpha=0.8)

    # Plot Tether line with dots
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

    # X-axis: Show label every 6 hours, but dots on every hour
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


def generate_all_charts_professional():
    """Generate all three charts with 24-hour data."""
    font_prop = setup_persian_font()
    paths = []
    paths.append(generate_professional_gold_chart(font_prop))
    paths.append(generate_professional_oil_chart(font_prop))
    paths.append(generate_professional_usd_chart(font_prop))
    return paths


def send_price_charts():
    """Generate and send charts to Telegram."""
    paths = generate_all_charts_professional()
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("Telegram not configured. Charts saved locally:")
        for p in paths:
            print(f"  - {p}")
        return
    captions = [
        "🥇 <b>قیمت جهانی طلا - ۲۴ ساعت گذشته</b>",
        "🛢️ <b>قیمت جهانی نفت برنت - ۲۴ ساعت گذشته</b>",
        "💵 <b>دلار و تتر به تومان - ۲۴ ساعت گذشته</b>"
    ]
    for path, caption in zip(paths, captions):
        with open(path, 'rb') as photo:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            files = {'photo': photo}
            data = {'chat_id': CHANNEL_ID, 'caption': caption, 'parse_mode': 'HTML'}
            resp = requests.post(url, data=data, files=files)
            print(f"{caption}: {resp.status_code}")
            os.remove(path)


# ================= OFFLINE TESTING =================
def test_charts_offline():
    """Test charts offline - generates and saves locally without sending to Telegram."""
    print("=" * 50)
    print("  TESTING CHARTS OFFLINE")
    print("=" * 50)
    print()

    # Generate charts
    paths = generate_all_charts_professional()

    print(f"\n✅ Generated {len(paths)} charts:")
    for p in paths:
        print(f"  📊 {p}")

    print(f"\n📁 Charts saved in: {os.getcwd()}")
    print("\nTo view the charts, open the PNG files in your file explorer.")
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_charts_offline()
