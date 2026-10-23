"""Carbon Design System theme and visual styling for Quarte dashboard.

Implements the Carbon Design System (Carbon White theme) design tokens:
- Clean, square, grid-based, data-dense, calm aesthetic.
- Color tokens: Page #ffffff, Layer #f4f4f4, Subtle border #e0e0e0, Strong border #8d8d8d.
- Interactive blue #0f62fe (hover #0353e9, active #002d9c).
- Typography: IBM Plex Sans and IBM Plex Mono (bundled locally for offline use).
- Chart palette: #6929c4, #1192e8, #005d5d, #9f1853, #fa4d56, #002d9c, #198038.
- Zero shadows, 0px border-radius, visible focus rings.
"""

from pathlib import Path
from typing import Any, List, Optional
import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import streamlit as st

# Color Palette (Carbon Design System)
CARBON_WHITE = {
    "page_bg": "#ffffff",
    "layer_bg": "#f4f4f4",
    "layer_accent": "#e8e8e8",
    "subtle_border": "#e0e0e0",
    "strong_border": "#8d8d8d",
    "text_primary": "#161616",
    "text_secondary": "#525252",
    "text_placeholder": "#a8a8a8",
    "interactive_primary": "#0f62fe",
    "interactive_hover": "#0353e9",
    "interactive_active": "#002d9c",
    "focus_ring": "#0f62fe",
    "status_success": "#198038",
    "status_success_bg": "#defbe6",
    "status_error": "#da1e28",
    "status_error_bg": "#fff1f1",
    "status_warning": "#f1c21b",
    "status_info": "#0043ce",
    "header_bg": "#161616",
    "header_text": "#ffffff",
}

# Carbon chart palette in required order
CARBON_PALETTE = [
    "#6929c4",  # purple
    "#1192e8",  # cyan
    "#005d5d",  # teal
    "#9f1853",  # magenta
    "#fa4d56",  # red
    "#002d9c",  # blue
    "#198038",  # green
]

# Register bundled fonts with matplotlib if available
FONTS_DIR = Path(__file__).resolve().parent / "static" / "fonts"
_FONTS_REGISTERED = False


def register_offline_fonts() -> None:
    """Register bundled IBM Plex fonts with matplotlib for offline rendering."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    if FONTS_DIR.exists():
        for font_file in FONTS_DIR.glob("*.ttf"):
            try:
                fm.fontManager.addfont(str(font_file))
            except Exception:
                pass
    _FONTS_REGISTERED = True


def setup_matplotlib_carbon() -> None:
    """Configure matplotlib global rcParams for Carbon visual guidelines."""
    register_offline_fonts()
    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = [
        "IBM Plex Sans",
        "-apple-system",
        "BlinkMacSystemFont",
        "Segoe UI",
        "Roboto",
        "DejaVu Sans",
        "Arial",
        "sans-serif",
    ]
    mpl.rcParams["font.monospace"] = [
        "IBM Plex Mono",
        "DejaVu Sans Mono",
        "Courier New",
        "monospace",
    ]
    mpl.rcParams["figure.facecolor"] = "#ffffff"
    mpl.rcParams["axes.facecolor"] = "#ffffff"
    mpl.rcParams["axes.edgecolor"] = "#e0e0e0"
    mpl.rcParams["axes.linewidth"] = 1.0
    mpl.rcParams["axes.grid"] = True
    mpl.rcParams["grid.color"] = "#e0e0e0"
    mpl.rcParams["grid.linestyle"] = "--"
    mpl.rcParams["grid.alpha"] = 0.6
    mpl.rcParams["axes.spines.top"] = False
    mpl.rcParams["axes.spines.right"] = False
    mpl.rcParams["axes.spines.left"] = True
    mpl.rcParams["axes.spines.bottom"] = True
    mpl.rcParams["axes.labelcolor"] = "#161616"
    mpl.rcParams["xtick.color"] = "#525252"
    mpl.rcParams["ytick.color"] = "#525252"
    mpl.rcParams["xtick.labelsize"] = 10
    mpl.rcParams["ytick.labelsize"] = 10
    mpl.rcParams["axes.titlesize"] = 12
    mpl.rcParams["axes.titleweight"] = "bold"
    mpl.rcParams["legend.frameon"] = False
    mpl.rcParams["legend.fontsize"] = 10


def style_carbon_ax(ax: Any) -> None:
    """Format a matplotlib axis to strictly match Carbon guidelines.

    Removes top and right spines, applies subtle gridlines, sets tick colors.
    """
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#8d8d8d")
    ax.spines["bottom"].set_color("#8d8d8d")
    ax.grid(True, linestyle="--", alpha=0.5, color="#e0e0e0", axis="y")
    ax.tick_params(colors="#525252", which="both")
    ax.yaxis.label.set_color("#161616")
    ax.xaxis.label.set_color("#161616")
    ax.title.set_color("#161616")


def apply_carbon_theme() -> None:
    """Inject comprehensive Carbon Design System CSS rules into the Streamlit app."""
    setup_matplotlib_carbon()

    css = """
    <style>
    /* -------------------------------------------------------------------------
       Carbon Typography (@font-face with local /app/static/ fallback)
       ------------------------------------------------------------------------- */
    @font-face {
        font-family: 'IBM Plex Sans';
        src: url('/app/static/fonts/IBMPlexSans.ttf') format('truetype');
        font-weight: 100 900;
        font-style: normal;
        font-display: swap;
    }
    @font-face {
        font-family: 'IBM Plex Mono';
        src: url('/app/static/fonts/IBMPlexMono-Regular.ttf') format('truetype');
        font-weight: 400;
        font-style: normal;
        font-display: swap;
    }
    @font-face {
        font-family: 'IBM Plex Mono';
        src: url('/app/static/fonts/IBMPlexMono-SemiBold.ttf') format('truetype');
        font-weight: 600;
        font-style: normal;
        font-display: swap;
    }

    /* Global reset to Carbon White tokens */
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
        background-color: #ffffff !important;
        color: #161616 !important;
        font-size: 14px;
        line-height: 1.42857;
    }

    /* Headings: sentence case, left-aligned, weight 400-600 */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'IBM Plex Sans', -apple-system, sans-serif !important;
        color: #161616 !important;
        font-weight: 600 !important;
        text-align: left !important;
        text-transform: none !important;
        letter-spacing: -0.2px;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    h1 { font-size: 28px !important; font-weight: 400 !important; }
    h2 { font-size: 20px !important; font-weight: 600 !important; border-bottom: 1px solid #e0e0e0; padding-bottom: 8px; }
    h3 { font-size: 16px !important; font-weight: 600 !important; }
    h4 { font-size: 14px !important; font-weight: 600 !important; }

    /* Carbon Grid Padding & 48px Header offset */
    .main .block-container {
        padding-top: 56px !important;
        padding-bottom: 64px !important;
        max-width: 1440px !important;
    }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
        height: 0px !important;
        visibility: hidden;
    }

    /* -------------------------------------------------------------------------
       Carbon Top Header Bar (#161616, 48px height)
       ------------------------------------------------------------------------- */
    .carbon-top-header {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        height: 48px !important;
        background-color: #161616 !important;
        color: #ffffff !important;
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        padding: 0 24px !important;
        z-index: 99999999 !important;
        box-sizing: border-box !important;
        border-bottom: 1px solid #393939 !important;
    }
    .carbon-top-header .brand-title {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #ffffff !important;
        letter-spacing: 0.2px !important;
    }
    .carbon-top-header .header-tag {
        font-size: 12px !important;
        color: #f4f4f4 !important;
        background-color: #262626 !important;
        border: 1px solid #525252 !important;
        padding: 2px 10px !important;
        border-radius: 12px !important;
        letter-spacing: 0.2px !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Sidebar & Side Navigation
       ------------------------------------------------------------------------- */
    section[data-testid="stSidebar"],
    div[data-testid="stSidebarContent"],
    div[data-testid="stSidebarUserContent"],
    section[data-testid="stSidebar"] > div {
        background-color: #f4f4f4 !important;
    }
    section[data-testid="stSidebar"] {
        top: 48px !important;
        height: calc(100vh - 48px) !important;
        border-right: 1px solid #e0e0e0 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #525252 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        border-bottom: none !important;
    }

    /* Sidebar Radio styling as Carbon Side Nav */
    div[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 0px !important;
        display: flex !important;
        flex-direction: column !important;
        border-top: 1px solid #e0e0e0 !important;
        border-bottom: 1px solid #e0e0e0 !important;
        background-color: #f4f4f4 !important;
    }
    /* Hide the BaseWeb/Streamlit visual radio circle indicator */
    div[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-of-type,
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:first-of-type,
    div[data-testid="stSidebar"] div[role="radiogroup"] label svg,
    div[data-testid="stSidebar"] div[role="radiogroup"] input {
        display: none !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] > label,
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        height: 40px !important;
        padding: 0 16px !important;
        margin: 0 !important;
        border-left: 3px solid transparent !important;
        background-color: transparent !important;
        color: #161616 !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        border-radius: 0px !important;
        cursor: pointer !important;
        transition: all 110ms ease-in-out !important;
        border-bottom: 1px solid #e8e8e8 !important;
        box-sizing: border-box !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] > label:hover,
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
        background-color: #e5e5e5 !important;
        color: #161616 !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked),
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {
        border-left: 3px solid #0f62fe !important;
        background-color: #e8e8e8 !important;
        color: #161616 !important;
        font-weight: 600 !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] div[data-testid="stMarkdownContainer"] {
        padding: 0 !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Tiles, Cards, and Metrics (0px radius, 1px #e0e0e0 border)
       ------------------------------------------------------------------------- */
    div[data-testid="stMetric"] {
        background-color: #f4f4f4 !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: 0px !important;
        padding: 16px !important;
        box-shadow: none !important;
    }
    div[data-testid="stMetricValue"] > div {
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-size: 32px !important;
        font-weight: 300 !important;
        color: #161616 !important;
        line-height: 1.15 !important;
    }
    div[data-testid="stMetricLabel"] > div,
    div[data-testid="stMetricLabel"] label {
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        color: #525252 !important;
        text-transform: none !important;
    }
    div[data-testid="stMetricDelta"] > div {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 500 !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Buttons (Square 0px radius, 48px height, Primary #0f62fe)
       ------------------------------------------------------------------------- */
    div[data-testid="stButton"] > button,
    button[kind="primary"],
    button[kind="secondary"] {
        border-radius: 0px !important;
        min-height: 48px !important;
        height: 48px !important;
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        padding: 0 24px !important;
        box-shadow: none !important;
        transition: background-color 110ms ease-in-out, border-color 110ms ease-in-out, color 110ms ease-in-out !important;
    }
    div[data-testid="stButton"] > button[kind="primary"],
    button[kind="primary"] {
        background-color: #0f62fe !important;
        color: #ffffff !important;
        border: 1px solid #0f62fe !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover,
    button[kind="primary"]:hover {
        background-color: #0353e9 !important;
        border-color: #0353e9 !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:active,
    button[kind="primary"]:active {
        background-color: #002d9c !important;
        border-color: #002d9c !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"],
    button[kind="secondary"] {
        background-color: transparent !important;
        color: #0f62fe !important;
        border: 1px solid #0f62fe !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover,
    button[kind="secondary"]:hover {
        background-color: #0f62fe !important;
        color: #ffffff !important;
    }
    button:focus,
    button:focus-visible {
        outline: 2px solid #0f62fe !important;
        outline-offset: -2px !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Form Inputs (Select, Textarea, Text input)
       ------------------------------------------------------------------------- */
    input, textarea, select, div[data-baseweb="select"] {
        border-radius: 0px !important;
        border-color: #8d8d8d !important;
        background-color: #ffffff !important;
        color: #161616 !important;
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-size: 14px !important;
    }
    div[data-baseweb="select"] > div {
        border-radius: 0px !important;
        border-color: #8d8d8d !important;
        background-color: #ffffff !important;
        min-height: 40px !important;
    }
    input:focus, textarea:focus, div[data-baseweb="select"]:focus-within {
        border-color: #0f62fe !important;
        outline: 2px solid #0f62fe !important;
        outline-offset: -2px !important;
    }
    textarea {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 13px !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Inline Notifications (3px left border)
       ------------------------------------------------------------------------- */
    .carbon-notification {
        border-left: 3px solid #0f62fe;
        background-color: #edf5ff;
        padding: 12px 16px;
        margin: 12px 0;
        font-size: 14px;
        color: #161616;
        display: flex;
        flex-direction: column;
        border-radius: 0px;
    }
    .carbon-notification.success {
        border-left-color: #198038;
        background-color: #defbe6;
    }
    .carbon-notification.error {
        border-left-color: #da1e28;
        background-color: #fff1f1;
    }
    .carbon-notification.warning {
        border-left-color: #f1c21b;
        background-color: #fdf5d6;
    }
    .carbon-notification-title {
        font-weight: 600;
        color: #161616;
        margin-bottom: 2px;
    }
    .carbon-notification-desc {
        color: #525252;
        font-size: 13px;
    }

    /* Streamlit Alert overrides */
    div[data-testid="stAlert"] {
        border-radius: 0px !important;
        border-top: none !important;
        border-right: none !important;
        border-bottom: none !important;
        border-left-width: 3px !important;
        box-shadow: none !important;
        padding: 12px 16px !important;
    }
    div[data-testid="stAlert"] * {
        font-size: 13px !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Data Tables (Compact, Zebra Striping, Monospace numbers)
       ------------------------------------------------------------------------- */
    div[data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0 !important;
        border-radius: 0px !important;
        background-color: #ffffff !important;
    }
    div[data-testid="stDataFrame"] table {
        border-collapse: collapse !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Status Tags (Pills)
       ------------------------------------------------------------------------- */
    .carbon-tag {
        display: inline-block;
        padding: 2px 8px;
        font-size: 12px;
        font-weight: 500;
        border-radius: 12px;
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .carbon-tag-completed {
        background-color: #defbe6;
        color: #0e6027;
        border: 1px solid #a7f0ba;
    }
    .carbon-tag-simulation {
        background-color: #e0e0e0;
        color: #161616;
        border: 1px solid #8d8d8d;
    }

    /* -------------------------------------------------------------------------
       Carbon Expanders (0px radius, clean accordion)
       ------------------------------------------------------------------------- */
    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0 !important;
        border-radius: 0px !important;
        background-color: #f4f4f4 !important;
        margin-top: 12px;
    }
    div[data-testid="stExpander"] summary {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #161616 !important;
        padding: 12px 16px !important;
        background-color: #f4f4f4 !important;
    }

    /* -------------------------------------------------------------------------
       Carbon Footer
       ------------------------------------------------------------------------- */
    .carbon-footer {
        margin-top: 48px;
        padding-top: 16px;
        border-top: 1px solid #e0e0e0;
        font-size: 12px;
        color: #525252;
        line-height: 1.5;
        text-align: left;
    }

    /* Code & Pre */
    code, pre {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 12px !important;
        border-radius: 0px !important;
    }

    /* Spinners & Progress (Simple, calm, no gradients) */
    div[data-testid="stSpinner"] {
        color: #0f62fe !important;
    }
    </style>

    <!-- Top Header Bar (Fixed, 48px, #161616) -->
    <div class="carbon-top-header">
        <span class="brand-title">Quarte</span>
        <span class="header-tag">Noisy simulation + saved hardware runs</span>
    </div>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_equivalence_notification(equivalent: bool) -> None:
    """Render an inline Carbon notification bar for circuit equivalence results."""
    if equivalent:
        html = """
        <div class="carbon-notification success">
            <span class="carbon-notification-title">Equivalent: PASS</span>
            <span class="carbon-notification-desc">Unitary equivalence verified up to global phase.</span>
        </div>
        """
    else:
        html = """
        <div class="carbon-notification error">
            <span class="carbon-notification-title">Equivalent: FAIL</span>
            <span class="carbon-notification-desc">Unitary mismatch between original and optimized circuit.</span>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)


def render_footer() -> None:
    """Render the mandatory Carbon and trademark attribution footer."""
    html = """
    <div class="carbon-footer">
        Interface styled after the open-source Carbon Design System. Not affiliated with or endorsed by IBM.
        Hardware results come from jobs run on IBM Quantum through a user account.
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
