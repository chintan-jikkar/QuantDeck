# pages/1_Screener.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.formatting import fmt_number, fmt_percent, fmt_large_number

st.set_page_config(page_title="Screener — QuantDeck", layout="wide")
st.title("Layer 1 — Screener")
st.caption("Narrow a universe down to a ranked shortlist worth investigating.")

tab_eq, tab_fx, tab_cmd = st.tabs(["📈 Equities", "💱 FX", "🛢 Commodities"])

# ── Equities tab ──────────────────────────────────────────────────────────────
with tab_eq:
    # ── Smart Suggestions panel ────────────────────────────────────────────────
    with st.expander("💡 Smart Suggestions — themed navigation from today's headlines", expanded=False):
        st.caption("Sectors getting attention today. Click a theme to add its tickers to the Custom universe. Not investment advice.")
        with st.spinner("Fetching headlines…"):
            try:
                from data.news import fetch_headlines, group_by_theme, suggest_tickers_for_themes
                _headlines = fetch_headlines()
                _grouped = group_by_theme(_headlines)
            except Exception:
                _grouped = {}
        if not _grouped:
            st.info("No headlines available. Set NEWSAPI_KEY in .env for live data, or check your connection.")
        else:
            _theme_list = list(_grouped.items())
            _cols = st.columns(min(len(_theme_list), 4))
            for i, (theme, hl) in enumerate(_theme_list):
                col = _cols[i % len(_cols)]
                # Equity-only tickers for the Screener (skip FX/commodity)
                _eq_tickers = [t for t in suggest_tickers_for_themes({theme: hl})
                               if "=F" not in t and "=X" not in t]
                _label = f"**{theme}** ({len(hl)} stories)"
                if _eq_tickers and col.button(_label, key=f"theme_{i}", use_container_width=True):
                    st.session_state["smart_suggest_tickers"] = _eq_tickers
                    st.session_state["smart_suggest_theme"] = theme
                    st.rerun()
        if "smart_suggest_theme" in st.session_state:
            st.success(
                f"Theme selected: **{st.session_state['smart_suggest_theme']}** — "
                f"tickers added to Custom universe. Clear with ✕."
            )
            if st.button("✕ Clear theme selection", key="clear_theme"):
                st.session_state.pop("smart_suggest_tickers", None)
                st.session_state.pop("smart_suggest_theme", None)
                st.rerun()

    with st.sidebar:
        st.header("Equity Universe")
        universe = st.selectbox(
            "Select universe",
            ["Dow Jones 30", "S&P 500", "NASDAQ 100", "Watchlist", "Custom"],
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
    else:
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
        universe_key = universe if universe != "Custom" else "custom"

        if universe == "Watchlist":
            from utils.watchlist import load_watchlist as _lwl
            custom_tickers = _lwl()
            if not custom_tickers:
                st.warning("Your watchlist is empty. Pin tickers from the results table below.")
                st.stop()
            universe_key = "custom"
        elif universe == "Custom" and custom_tickers_input.strip():
            raw = custom_tickers_input.replace(",", "\n").split("\n")
            custom_tickers = [t.strip().upper() for t in raw if t.strip()]
        elif not custom_tickers and "smart_suggest_tickers" in st.session_state:
            custom_tickers = st.session_state["smart_suggest_tickers"]
            universe_key = "custom"

        with st.spinner("Fetching data and applying filters…"):
            try:
                from layers.screener import run_screener
                results = run_screener(
                    universe_key,
                    filters,
                    custom_tickers=custom_tickers,
                )
            except Exception as e:
                st.error(f"Screener error: {e}")
                results = pd.DataFrame()

        if results.empty:
            st.warning("No tickers matched the current filters. Try relaxing the criteria.")
        else:
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

            # ── Watchlist pin buttons ──────────────────────────────────────────
            from utils.watchlist import load_watchlist, add_ticker, remove_ticker
            _wl = load_watchlist()
            st.caption("⭐ = in watchlist — click to pin/unpin")
            _pin_cols = st.columns(min(len(results), 8))
            for _ci, _t in enumerate(results.index[:8]):
                _pinned = _t in _wl
                if _pin_cols[_ci].button(f"{'⭐' if _pinned else '☆'} {_t}", key=f"pin_{_t}"):
                    if _pinned:
                        remove_ticker(_t)
                    else:
                        add_ticker(_t)
                    st.rerun()

            selected = st.selectbox(
                "Open a ticker in Deep Dive →",
                options=["(select)"] + results.index.tolist(),
            )
            if selected != "(select)":
                st.session_state["deep_dive_ticker"] = selected
                st.switch_page("pages/2_Deep_Dive.py")

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

    st.caption(
        "QuantDeck is a quantitative analysis tool, not financial advice. "
        "Composite scores are relative ranks within the filtered universe."
    )

# ── FX tab ────────────────────────────────────────────────────────────────────
with tab_fx:
    from config import FX_PAIRS
    fx_group = st.selectbox("FX group", list(FX_PAIRS.keys()), key="fx_group")
    run_fx = st.button("Screen FX", type="primary", key="run_fx")
    if run_fx:
        with st.spinner(f"Screening {fx_group}…"):
            try:
                from layers.screener import run_fx_screener
                fx_results = run_fx_screener(fx_group)
            except Exception as e:
                st.error(f"FX screener failed: {e}")
                fx_results = pd.DataFrame()
        if fx_results.empty:
            st.warning("No FX data returned.")
        else:
            st.dataframe(
                fx_results.style.background_gradient(subset=["composite_score"], cmap="RdYlGn"),
                use_container_width=True,
            )
    else:
        st.info("Select a group and click **Screen FX**.")

# ── Commodities tab ───────────────────────────────────────────────────────────
with tab_cmd:
    from config import COMMODITIES
    cmd_group = st.selectbox("Commodity group", ["all"] + list(COMMODITIES.keys()), key="cmd_group")
    run_cmd = st.button("Screen Commodities", type="primary", key="run_cmd")
    if run_cmd:
        with st.spinner(f"Screening {cmd_group}…"):
            try:
                from layers.screener import run_commodity_screener
                cmd_results = run_commodity_screener(cmd_group)
            except Exception as e:
                st.error(f"Commodity screener failed: {e}")
                cmd_results = pd.DataFrame()
        if cmd_results.empty:
            st.warning("No commodity data returned.")
        else:
            st.dataframe(
                cmd_results.style.background_gradient(subset=["composite_score"], cmap="RdYlGn"),
                use_container_width=True,
            )
    else:
        st.info("Select a group and click **Screen Commodities**.")
