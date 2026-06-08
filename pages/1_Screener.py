# pages/1_Screener.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.formatting import fmt_number, fmt_percent, fmt_large_number
from utils.theme import inject_css, themed, SCORE_SCALE, logo_url

st.set_page_config(page_title="Screener — QuantDeck", layout="wide")
inject_css()
st.title("Layer 1 — Screener")
st.caption("Narrow a universe down to a ranked shortlist worth investigating.")


def _asset_table(df):
    """Render an FX/commodity screen result as a themed column_config table."""
    view = df.copy()
    for pct in ("momentum_12_1", "realized_vol_30d"):
        if pct in view.columns:
            view[pct] = view[pct] * 100.0
    view = view.rename(columns={
        "composite_score": "Score", "momentum_12_1": "Momentum 12-1",
        "realized_vol_30d": "Realized Vol", "rsi": "RSI", "last_price": "Last",
    })
    cfg = {
        "Score":         st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "Momentum 12-1": st.column_config.NumberColumn("Momentum 12-1", format="%.1f%%"),
        "Realized Vol":  st.column_config.NumberColumn("Realized Vol", format="%.1f%%"),
        "RSI":           st.column_config.NumberColumn("RSI", format="%.0f"),
        "Last":          st.column_config.NumberColumn("Last", format="%.4f"),
    }
    st.dataframe(view, column_config={k: v for k, v in cfg.items() if k in view.columns},
                 use_container_width=True, height=360)


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

            # KPI tiles (themed metric cards)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Matches", len(results))
            if "composite_score" in results.columns:
                k2.metric("Avg Score", f"{results['composite_score'].mean():.0f}")
                k3.metric("Top Pick", str(results.index[0]),
                          f"{results.iloc[0]['composite_score']:.0f} score")
            if "peRatio" in results.columns:
                k4.metric("Median P/E", f"{results['peRatio'].median():.1f}")
            st.divider()

            view = results.copy()
            view.insert(0, "Logo", [logo_url(t) for t in view.index])
            rename = {
                "composite_score": "Score", "peRatio": "P/E", "pbRatio": "P/B",
                "evToEbitda": "EV/EBITDA", "roe": "ROE", "revenueGrowth": "Rev Growth",
                "netProfitMargin": "Net Margin", "rsi": "RSI",
                "above_50sma": "↑50 SMA", "above_200sma": "↑200 SMA",
            }
            keep = ["Logo"] + [rename[c] for c in rename if c in results.columns]
            view = view.rename(columns=rename)
            view = view[[c for c in keep if c in view.columns]]
            for pct in ("ROE", "Rev Growth", "Net Margin"):
                if pct in view.columns:
                    view[pct] = view[pct] * 100.0

            col_cfg = {
                "Logo":       st.column_config.ImageColumn(" ", width="small"),
                "Score":      st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                "P/E":        st.column_config.NumberColumn("P/E", format="%.1f"),
                "P/B":        st.column_config.NumberColumn("P/B", format="%.2f"),
                "EV/EBITDA":  st.column_config.NumberColumn("EV/EBITDA", format="%.1f"),
                "ROE":        st.column_config.NumberColumn("ROE", format="%.1f%%"),
                "Rev Growth": st.column_config.NumberColumn("Rev Growth", format="%.1f%%"),
                "Net Margin": st.column_config.NumberColumn("Net Margin", format="%.1f%%"),
                "RSI":        st.column_config.NumberColumn("RSI", format="%.0f"),
            }
            st.dataframe(
                view,
                column_config={k: v for k, v in col_cfg.items() if k in view.columns},
                use_container_width=True, height=420,
            )

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
                    color_continuous_scale=SCORE_SCALE,
                    labels={"peRatio": "P/E Ratio", "revenueGrowth": "Revenue Growth (YoY)",
                            "composite_score": "Score"},
                    title="P/E vs Revenue Growth  (bubble size = market cap, colour = composite score)",
                )
                fig.update_layout(hovermode="closest")
                st.plotly_chart(themed(fig), use_container_width=True)

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
            _asset_table(fx_results)
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
            _asset_table(cmd_results)
    else:
        st.info("Select a group and click **Screen Commodities**.")
