# pages/1_Screener.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.formatting import fmt_number, fmt_percent, fmt_large_number

st.set_page_config(page_title="Screener — QuantDeck", layout="wide")
st.title("Layer 1 — Screener")
st.caption("Narrow a universe down to a ranked shortlist worth investigating.")

with st.sidebar:
    st.header("Universe")
    universe = st.selectbox(
        "Select universe",
        ["Dow Jones 30", "S&P 500", "NASDAQ 100", "Custom"],
        index=0,
    )
    custom_tickers_input = ""
    if universe == "Custom":
        custom_tickers_input = st.text_area(
            "Paste tickers (one per line or comma-separated)",
            placeholder="AAPL\nMSFT\nGOOG",
        )

    st.header("Risk Appetite")
    risk_preset = st.select_slider(
        "Preset",
        options=["Conservative", "Balanced", "Aggressive"],
        value="Balanced",
    )
    preset_defaults = {
        "Conservative": {"pe_max": 15, "roe_min": 0.15, "debt_equity_max": 0.5},
        "Balanced":     {"pe_max": 25, "roe_min": 0.10, "debt_equity_max": 1.0},
        "Aggressive":   {"pe_max": 40, "roe_min": 0.05, "debt_equity_max": 2.0},
    }
    d = preset_defaults[risk_preset]

    st.header("Fundamental Filters")
    pe_max         = st.slider("Max P/E",            0, 60,  d["pe_max"])
    pb_max         = st.slider("Max P/B",            0, 15,  5)
    roe_min        = st.slider("Min ROE (%)",        0, 50,  int(d["roe_min"]*100)) / 100
    debt_eq_max    = st.slider("Max Debt/Equity",    0.0, 5.0, d["debt_equity_max"], step=0.1)
    rev_growth_min = st.slider("Min Rev Growth (%)", 0, 50,  0) / 100
    net_margin_min = st.slider("Min Net Margin (%)", 0, 30,  5) / 100

    st.header("Technical Filters")
    rsi_min = st.slider("RSI min", 0, 100, 0)
    rsi_max = st.slider("RSI max", 0, 100, 100)
    above_50sma  = st.checkbox("Price above 50 SMA")
    above_200sma = st.checkbox("Price above 200 SMA")

    run_btn = st.button("Run Screener", type="primary", use_container_width=True)

if not run_btn:
    st.info("Configure filters in the sidebar, then click **Run Screener**.")
    st.stop()

filters = {
    "pe_max":             pe_max,
    "pb_max":             pb_max,
    "roe_min":            roe_min,
    "debt_equity_max":    debt_eq_max,
    "revenue_growth_min": rev_growth_min,
    "net_margin_min":     net_margin_min,
    "rsi_min":            rsi_min,
    "rsi_max":            rsi_max,
    "above_50sma":        above_50sma,
    "above_200sma":       above_200sma,
}

custom_tickers = None
if universe == "Custom" and custom_tickers_input.strip():
    raw = custom_tickers_input.replace(",", "\n").split("\n")
    custom_tickers = [t.strip().upper() for t in raw if t.strip()]

with st.spinner("Fetching data and applying filters…"):
    try:
        from layers.screener import run_screener
        results = run_screener(
            universe if universe != "Custom" else "custom",
            filters,
            custom_tickers=custom_tickers,
        )
    except Exception as e:
        st.error(f"Screener error: {e}")
        st.stop()

if results.empty:
    st.warning("No tickers matched the current filters. Try relaxing the criteria.")
    st.stop()

st.success(f"**{len(results)} tickers** passed all filters.")
st.divider()

display_cols = {
    "composite_score": "Score",
    "peRatio":         "P/E",
    "pbRatio":         "P/B",
    "evToEbitda":      "EV/EBITDA",
    "roe":             "ROE",
    "revenueGrowth":   "Rev Growth",
    "netProfitMargin": "Net Margin",
    "rsi":             "RSI",
    "above_50sma":     "↑50 SMA",
    "above_200sma":    "↑200 SMA",
}
display_df = results[[c for c in display_cols if c in results.columns]].copy()
display_df.columns = [display_cols[c] for c in display_df.columns]


def _score_style(val):
    if isinstance(val, float):
        if val >= 70:
            return "background-color: #1a7a4a; color: white"
        if val >= 40:
            return "background-color: #b8860b; color: white"
        return "background-color: #8b1a1a; color: white"
    return ""


fmt_map = {}
for col, spec in [
    ("Score", "{:.0f}"), ("P/E", "{:.1f}"), ("P/B", "{:.2f}"),
    ("EV/EBITDA", "{:.1f}"), ("ROE", "{:.1%}"), ("Rev Growth", "{:.1%}"),
    ("Net Margin", "{:.1%}"), ("RSI", "{:.1f}"),
]:
    if col in display_df.columns:
        fmt_map[col] = spec

styled = display_df.style
if "Score" in display_df.columns:
    styled = styled.map(_score_style, subset=["Score"])
styled = styled.format(fmt_map)
st.dataframe(styled, use_container_width=True, height=400)

selected = st.selectbox(
    "Open a ticker in Deep Dive →",
    options=["(select)"] + results.index.tolist(),
)
if selected != "(select)":
    st.session_state["deep_dive_ticker"] = selected
    st.switch_page("pages/2_Deep_Dive.py")

st.subheader("Valuation vs Growth")
scatter_cols = ["peRatio", "revenueGrowth", "composite_score", "marketCap"]
scatter_df = results[[c for c in scatter_cols if c in results.columns]].dropna().copy()
if not scatter_df.empty and "peRatio" in scatter_df.columns and "revenueGrowth" in scatter_df.columns:
    fig = px.scatter(
        scatter_df.reset_index(),
        x="peRatio", y="revenueGrowth",
        size="marketCap" if "marketCap" in scatter_df.columns else None,
        color="composite_score" if "composite_score" in scatter_df.columns else None,
        hover_name=scatter_df.reset_index().columns[0],
        color_continuous_scale="RdYlGn",
        labels={"peRatio": "P/E Ratio", "revenueGrowth": "Revenue Growth (YoY)",
                "composite_score": "Score"},
        title="P/E vs Revenue Growth  (bubble size = market cap, colour = composite score)",
    )
    fig.update_layout(hovermode="closest")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Not enough data for scatter plot.")

st.caption(
    "QuantDeck is a quantitative analysis tool, not financial advice. "
    "Composite scores are relative ranks within the filtered universe."
)
