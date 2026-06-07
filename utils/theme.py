# utils/theme.py
"""QuantDeck shared visual theme (Quant Terminal).

Ports the mockup design system (docs/mockups/quantdeck.css) into Streamlit:
- design-token colour constants for reuse in widgets and Plotly
- inject_css(): Space Grotesk font, KPI-style metric cards, buttons, tabs
- PLOTLY_TEMPLATE + themed(): one consistent chart look across every page

The base palette (page/sidebar/text/primary) is set natively in
.streamlit/config.toml; this module layers on the typography and component
polish that config.toml cannot express.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

# ── Design tokens ─────────────────────────────────────────────────────────────
BG          = "#070610"
PANEL       = "#100D1B"
PANEL_2     = "#171327"
BORDER      = "rgba(168,148,255,0.09)"
BORDER_HARD = "rgba(168,148,255,0.16)"
TEXT        = "#E6E9EF"
TEXT_MUTED  = "#8A93A6"
TEXT_DIM    = "#5A6376"
VIOLET      = "#7C5CFF"
GREEN       = "#3FB950"
RED         = "#F85149"
GOLD        = "#D9A441"
TEAL        = "#2DD4BF"

# Chart colourway + brand-aligned continuous scales
COLORWAY    = [VIOLET, GREEN, RED, GOLD, TEAL, "#4F6BFF", "#C95CC8"]
SCORE_SCALE = [[0.0, RED], [0.5, GOLD], [1.0, GREEN]]   # red→gold→green (composite score)
VIOLET_SCALE = [[0.0, "#1E1832"], [1.0, VIOLET]]


def signal_color(value: float, good_high: bool = True) -> str:
    """Green/gold/red for a 0-100 style metric (flip with good_high=False)."""
    v = value if good_high else 100 - value
    if v >= 70:
        return GREEN
    if v >= 40:
        return GOLD
    return RED


_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="st-"], [class*="css"],
button, input, textarea, select, .stMarkdown {{
    font-family: 'Space Grotesk', system-ui, sans-serif;
}}
h1, h2, h3 {{ font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.5px; font-weight: 600; }}
h1 {{ font-size: 26px; }}

/* Tabular figures everywhere numbers matter */
[data-testid="stMetricValue"], [data-testid="stDataFrame"] {{ font-variant-numeric: tabular-nums; }}

/* Metric cards → KPI tiles (mockup .kpi) */
[data-testid="stMetric"] {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 16px 18px;
}}
[data-testid="stMetricValue"] {{ font-weight: 600; letter-spacing: -0.5px; }}
[data-testid="stMetricLabel"] {{
    color: {TEXT_MUTED}; text-transform: uppercase;
    letter-spacing: .8px; font-size: 11.5px; font-weight: 600;
}}

/* Primary button → violet with glow (mockup .btn-primary) */
.stButton > button[kind="primary"] {{
    background: {VIOLET}; border: 0; color: #fff; font-weight: 600;
    border-radius: 9px; box-shadow: 0 4px 14px rgba(124,92,255,0.35);
}}
.stButton > button[kind="primary"]:hover {{ background: #6d4af0; color: #fff; }}
.stButton > button[kind="secondary"] {{ border-radius: 9px; border-color: {BORDER_HARD}; }}

/* Tabs: violet active underline (mockup .tab.active) */
[data-baseweb="tab-highlight"] {{ background-color: {VIOLET} !important; }}
[data-baseweb="tab-border"] {{ background-color: {BORDER} !important; }}

/* Cards / expanders / dataframe a touch softer */
[data-testid="stExpander"], [data-testid="stDataFrame"] {{
    border-radius: 12px; border: 1px solid {BORDER};
}}

/* Sliders in the brand violet */
[data-testid="stSlider"] [role="slider"] {{ box-shadow: 0 0 0 4px rgba(124,92,255,0.25); }}
</style>
"""


def inject_css() -> None:
    """Inject the QuantDeck CSS. Call once near the top of every page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def setup_page(title: str, icon: str = "📊", layout: str = "wide") -> None:
    """st.set_page_config + inject_css in one call."""
    st.set_page_config(page_title=title, page_icon=icon, layout=layout)
    inject_css()


# ── Plotly ────────────────────────────────────────────────────────────────────
PLOTLY_TEMPLATE = go.layout.Template(
    layout=dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Space Grotesk, sans-serif", color=TEXT, size=13),
        colorway=COLORWAY,
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER_HARD, linecolor=BORDER_HARD),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER_HARD, linecolor=BORDER_HARD),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_MUTED)),
        margin=dict(l=52, r=20, t=52, b=42),
        hoverlabel=dict(bgcolor=PANEL_2, bordercolor=BORDER_HARD,
                        font=dict(family="Space Grotesk, sans-serif", color=TEXT)),
    )
)


def themed(fig: go.Figure) -> go.Figure:
    """Apply the QuantDeck Plotly template to a figure (in place) and return it."""
    fig.update_layout(template=PLOTLY_TEMPLATE)
    return fig


# Register as the global default so every Plotly figure picks up the QuantDeck
# look automatically (bg, font, gridlines, colorway) without per-figure wiring.
pio.templates["quantdeck"] = PLOTLY_TEMPLATE
pio.templates.default = "quantdeck"
