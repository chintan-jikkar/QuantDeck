# pages/2_Deep_Dive.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from utils.formatting import fmt_number, fmt_percent, fmt_large_number, fmt_currency
from utils.charts import candlestick, line, heatmap
from utils.theme import inject_css

st.set_page_config(page_title="Deep Dive — QuantDeck", layout="wide")
inject_css()
st.title("Layer 2 — Deep Dive")

# ── Ticker input ──────────────────────────────────────────────────────────────
default_ticker = st.session_state.get("deep_dive_ticker", "AAPL")
col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker = st.text_input("Ticker", value=default_ticker).upper().strip()
with col_btn:
    st.write("")
    run = st.button("Load", type="primary")

cache_key = f"deep_dive_{ticker}"
if not run and cache_key not in st.session_state:
    st.info("Enter any ticker: US/international equity (AAPL, BP.L), FX (EURUSD=X), or commodity (GC=F).")
    st.stop()

if run or cache_key not in st.session_state:
    with st.spinner(f"Loading data for {ticker}…"):
        try:
            from layers.deep_dive import run_deep_dive
            from data.prices import detect_asset_type, country_from_ticker
            detected_type = detect_asset_type(ticker)
            detected_country = country_from_ticker(ticker) if detected_type == "equity" else "US"
            data = run_deep_dive(ticker, country=detected_country, asset_type=detected_type)
            st.session_state[cache_key] = data
            st.session_state["deep_dive_ticker"] = ticker
        except Exception as e:
            st.error(f"Could not load data for {ticker!r}: {e}")
            st.stop()
else:
    data = st.session_state[cache_key]

asset_type = data.get("asset_type", "equity")

prices   = data.get("prices", pd.DataFrame())
income   = data.get("income", pd.DataFrame())
balance  = data.get("balance", pd.DataFrame())
cashflow = data.get("cashflow", pd.DataFrame())
margins  = data.get("margins", pd.DataFrame())
macro    = data.get("macro_regime", {})
curve    = data.get("yield_curve", pd.Series(dtype=float))

# ── Price chart ───────────────────────────────────────────────────────────────
st.subheader(f"{ticker} — Price")
period_map = {"1D": 1, "1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260}
period = st.radio("Range", list(period_map.keys()), index=4, horizontal=True)
n_bars = period_map[period]

_is_live = (period == "1D")
if _is_live:
    st_autorefresh(interval=60_000, key="deep_dive_refresh")
    st.markdown("🔴 **Live** (refreshes every 60s · 15-min delay on free tier)")
    intraday = data.get("intraday")
    price_slice = intraday if (intraday is not None and not intraday.empty) else prices.tail(78)
else:
    price_slice = prices.tail(n_bars) if len(prices) > n_bars else prices

c50, c200, cbb = st.columns(3)
show_sma50  = c50.checkbox("50 SMA", value=True)
show_sma200 = c200.checkbox("200 SMA", value=False)
show_bb     = cbb.checkbox("Bollinger Bands", value=False)

if not price_slice.empty:
    fig_price = candlestick(price_slice, volume=True)

    if show_sma50 and len(prices) >= 50:
        sma50 = prices["Close"].rolling(50).mean().tail(n_bars)
        fig_price.add_trace(
            go.Scatter(x=sma50.index, y=sma50.values, mode="lines",
                       name="50 SMA", line={"color": "#D9A441", "width": 1}),
            row=1, col=1,
        )
    if show_sma200 and len(prices) >= 200:
        sma200 = prices["Close"].rolling(200).mean().tail(n_bars)
        fig_price.add_trace(
            go.Scatter(x=sma200.index, y=sma200.values, mode="lines",
                       name="200 SMA", line={"color": "#7C5CFF", "width": 1}),
            row=1, col=1,
        )
    if show_bb and len(prices) >= 20:
        mid   = prices["Close"].rolling(20).mean().tail(n_bars)
        std   = prices["Close"].rolling(20).std().tail(n_bars)
        upper = mid + 2 * std
        lower = mid - 2 * std
        for band, name in [(upper, "BB Upper"), (lower, "BB Lower")]:
            fig_price.add_trace(
                go.Scatter(x=band.index, y=band.values, mode="lines",
                           name=name, line={"color": "#5A6376", "width": 1, "dash": "dot"}),
                row=1, col=1,
            )

    fig_price.update_layout(hovermode="x unified", height=500)
    st.plotly_chart(fig_price, use_container_width=True)
else:
    st.warning(f"No price data available for {ticker}.")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["Macro Context", "Micro Fundamentals"])

with tab1:
    st.subheader("Macro Regime")
    _SHAPE_LABELS = {
        "normal":   "Normal (upward sloping)",
        "flat":     "Flat (transition zone)",
        "inverted": "Inverted (risk-off signal)",
        "unknown":  "Unknown",
    }
    shape_label = _SHAPE_LABELS.get(macro.get("yield_curve_shape", "unknown"), "Unknown")
    spread = macro.get("credit_spread_level", float("nan"))
    if isinstance(spread, float) and spread == spread:
        if spread < 1.5:
            spread_label = "Risk-On (<1.5%)"
        elif spread > 2.5:
            spread_label = "Risk-Off (>2.5%)"
        else:
            spread_label = "Neutral"
    else:
        spread_label = "N/A"

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Yield Curve", shape_label)
    r2.metric("Credit Spreads", spread_label,
              delta=f"{spread:.2f}%" if isinstance(spread, float) and spread == spread else "N/A")
    pol = macro.get("policy_rate", float("nan"))
    inf = macro.get("inflation_yoy", float("nan"))
    r3.metric("Policy Rate", fmt_percent(pol / 100) if isinstance(pol, float) and pol == pol else "N/A")
    r4.metric("Inflation (YoY)", fmt_percent(inf / 100) if isinstance(inf, float) and inf == inf else "N/A")

    if not curve.empty and not curve.isna().all():
        st.subheader("US Yield Curve")
        fig_curve = go.Figure()
        fig_curve.add_trace(go.Scatter(
            x=curve.index.tolist(), y=curve.values,
            mode="lines+markers", name="Current", line={"color": "#7C5CFF", "width": 2},
        ))
        fig_curve.update_layout(yaxis_title="Yield (%)", hovermode="x unified",
                                height=300, margin={"t": 30})
        st.plotly_chart(fig_curve, use_container_width=True)

    themes = data.get("news_themes", {})
    if themes:
        st.subheader("Recent Market Themes")
        st.caption("Based on recent headlines — not investment advice.")
        for theme, headlines in list(themes.items())[:4]:
            with st.expander(theme):
                for h in headlines[:3]:
                    st.markdown(f"- [{h.get('title','')}]({h.get('url','')})")

    peers = data.get("peers", [])
    if peers:
        st.subheader("Peer Comparison")
        st.caption(f"Peers: {', '.join(peers[:6])}")
        km = data.get("key_metrics", pd.DataFrame())
        if not km.empty:
            compare_cols = ["peRatio", "pbRatio", "evToEbitda", "roe", "revenueGrowth"]
            available = [c for c in compare_cols if c in km.columns]
            if available:
                st.dataframe(km[available].head(1), use_container_width=True)

with tab2:
    if asset_type == "fx":
        md = data.get("market_drivers", {})
        st.subheader(f"FX Market Drivers — {md.get('pair', ticker)}")
        c1, c2, c3 = st.columns(3)
        c1.metric("12-1 Month Momentum", fmt_percent(md.get("momentum_12_1")))
        c2.metric("RSI (14)", fmt_number(md.get("rsi")))
        c3.metric("30d Realized Vol (ann.)", fmt_percent(md.get("realized_vol_30d")))
        prices_chart = md.get("prices")
        if prices_chart is not None and not prices_chart.empty:
            fig_fx = go.Figure(go.Scatter(x=prices_chart.index, y=prices_chart["Close"],
                                          line={"color": "#7C5CFF"}, name=ticker))
            fig_fx.update_layout(height=350, title=f"{ticker} Price", hovermode="x unified")
            st.plotly_chart(fig_fx, use_container_width=True)
    elif asset_type == "commodity":
        md = data.get("market_drivers", {})
        st.subheader(f"Commodity Market Drivers — {ticker}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("12-1 Month Momentum", fmt_percent(md.get("momentum_12_1")))
        c2.metric("RSI (14)", fmt_number(md.get("rsi")))
        c3.metric("30d Realized Vol (ann.)", fmt_percent(md.get("realized_vol_30d")))
        c4.metric("Price vs 5Y Mean", fmt_percent(md.get("price_vs_5y_mean_pct")),
                  help="+ = historically expensive vs 5Y average")
        prices_chart = md.get("prices")
        if prices_chart is not None and not prices_chart.empty:
            fig_cmd = go.Figure(go.Scatter(x=prices_chart.index, y=prices_chart["Close"],
                                            line={"color": "#D9A441"}, name=ticker))
            fig_cmd.update_layout(height=350, title=f"{ticker} Price", hovermode="x unified")
            st.plotly_chart(fig_cmd, use_container_width=True)
    elif income.empty:
        st.warning(f"No fundamental data available for {ticker} from FMP.")
    else:
        st.subheader("Revenue & Margins")
        if not margins.empty and "revenue" in income.columns:
            rev_dates = income["date"].tolist()
            rev_vals  = income["revenue"].tolist()
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(x=rev_dates, y=rev_vals, name="Revenue",
                                     marker_color="#7C5CFF", yaxis="y1"))
            for col, color, name in [
                ("gross_margin",     "#3FB950", "Gross Margin"),
                ("operating_margin", "#D9A441", "Operating Margin"),
                ("net_margin",       "#F85149", "Net Margin"),
            ]:
                if col in margins.columns:
                    fig_rev.add_trace(go.Scatter(
                        x=rev_dates, y=margins[col].tolist(),
                        name=name, mode="lines+markers",
                        line={"color": color}, yaxis="y2",
                    ))
            fig_rev.update_layout(
                yaxis ={"title": "Revenue ($)", "side": "left"},
                yaxis2={"title": "Margin (%)", "side": "right", "overlaying": "y",
                        "tickformat": ".0%"},
                hovermode="x unified", height=400, legend={"orientation": "h"},
            )
            st.plotly_chart(fig_rev, use_container_width=True)

        st.subheader("Earnings Quality")
        eq = data.get("earnings_quality", pd.DataFrame())
        mscore = data.get("beneish_mscore", float("nan"))
        col_ccr, col_accruals, col_mscore = st.columns(3)
        if not eq.empty and "ccr" in eq.columns:
            col_ccr.metric("Cash Conversion Ratio", fmt_number(float(eq["ccr"].iloc[0])),
                           help="CFO / Net Income. >1.0 = earnings backed by cash.")
            acc = eq["accruals_ratio"].iloc[0]
            col_accruals.metric("Accruals Ratio",
                                fmt_percent(float(acc)) if acc == acc else "N/A",
                                help="(NI − CFO) / Avg Assets. Negative = cash-backed earnings.")
        if isinstance(mscore, float) and mscore == mscore:
            flag = "⚠️ Potential Manipulator" if mscore > -2.22 else "✅ Clean Signal"
            col_mscore.metric("Beneish M-Score", f"{mscore:.2f}",
                              delta=flag, delta_color="off",
                              help="Beneish (1999): score > -2.22 flags potential earnings manipulation.")

        st.subheader("Balance Sheet Health")
        bs_ratios = data.get("balance_ratios", pd.DataFrame())
        if not bs_ratios.empty:
            bs_dates = bs_ratios["date"].tolist() if "date" in bs_ratios.columns else list(range(len(bs_ratios)))
            fig_bs = go.Figure()
            thresholds = {"debt_equity": 1.5, "current_ratio": 1.0, "interest_coverage": 3.0}
            for col, label in [("debt_equity", "Debt/Equity"), ("current_ratio", "Current Ratio"),
                               ("interest_coverage", "Interest Coverage")]:
                if col in bs_ratios.columns:
                    fig_bs.add_trace(go.Scatter(
                        x=bs_dates, y=bs_ratios[col].tolist(),
                        mode="lines+markers", name=label,
                    ))
                    fig_bs.add_hline(y=thresholds[col], line_dash="dot",
                                     annotation_text=f"{label} threshold", line_color="grey")
            fig_bs.update_layout(hovermode="x unified", height=350)
            st.plotly_chart(fig_bs, use_container_width=True)

        st.subheader("Capital Allocation")
        capalloc = data.get("capital_allocation", pd.DataFrame())
        if not capalloc.empty:
            pct_cols = [c for c in ["capex_pct", "dividends_pct", "buybacks_pct", "retained_pct"]
                        if c in capalloc.columns]
            if pct_cols:
                ca_dates = income["date"].tolist()[:len(capalloc)]
                fig_ca = go.Figure()
                colors = {"capex_pct": "#7C5CFF", "dividends_pct": "#3FB950",
                          "buybacks_pct": "#D9A441", "retained_pct": "#5A6376"}
                labels = {"capex_pct": "Capex", "dividends_pct": "Dividends",
                          "buybacks_pct": "Buybacks", "retained_pct": "Retained"}
                for col in pct_cols:
                    fig_ca.add_trace(go.Bar(
                        x=ca_dates, y=capalloc[col].tolist(),
                        name=labels[col], marker_color=colors[col],
                    ))
                fig_ca.update_layout(barmode="stack", yaxis_tickformat=".0%",
                                     hovermode="x unified", height=350)
                st.plotly_chart(fig_ca, use_container_width=True)

# ── Investment Memo Card (equity only) ───────────────────────────────────────
if asset_type != "equity":
    st.session_state[f"deep_dive_result_{ticker}"] = data
    st.caption("QuantDeck is a quantitative analysis tool, not financial advice.")
    st.stop()

st.divider()
st.subheader("Investment Memo")

mscore = data.get("beneish_mscore", float("nan"))
bull_points = []
bear_points = []
if not margins.empty:
    gm = margins["gross_margin"].iloc[0] if "gross_margin" in margins.columns else None
    if gm is not None and gm == gm:
        if gm > 0.40:
            bull_points.append(f"High gross margin ({gm:.1%}) — strong pricing power")
        elif gm < 0.20:
            bear_points.append(f"Low gross margin ({gm:.1%}) — thin margins at risk")
    rg = margins["revenue_yoy"].iloc[0] if "revenue_yoy" in margins.columns else None
    if rg is not None and rg == rg:
        if rg > 0.10:
            bull_points.append(f"Strong revenue growth ({rg:.1%} YoY)")
        elif rg < 0:
            bear_points.append(f"Revenue declining ({rg:.1%} YoY)")

if isinstance(mscore, float) and mscore == mscore:
    if mscore < -2.22:
        bull_points.append("Beneish M-Score clean — no earnings manipulation signal")
    else:
        bear_points.append(f"Beneish M-Score {mscore:.2f} — potential earnings quality concern")

if macro.get("yield_curve_shape") == "inverted":
    bear_points.append("Inverted yield curve — historically precedes economic slowdown")
elif macro.get("yield_curve_shape") == "normal":
    bull_points.append("Normal yield curve — constructive macro backdrop")

col_bull, col_bear = st.columns(2)
with col_bull:
    st.markdown("**🟢 Bull Case**")
    for pt in (bull_points or ["Insufficient data for bull case"]):
        st.markdown(f"- {pt}")
with col_bear:
    st.markdown("**🔴 Bear Case**")
    for pt in (bear_points or ["No obvious bear case from available data"]):
        st.markdown(f"- {pt}")

st.session_state[f"deep_dive_result_{ticker}"] = data

st.caption(
    "Investment memo is auto-populated from quantitative data. "
    "It is not financial advice and does not account for qualitative factors."
)
