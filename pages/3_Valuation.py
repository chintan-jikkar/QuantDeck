# pages/3_Valuation.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.formatting import fmt_currency, fmt_percent, fmt_number

st.set_page_config(page_title="Valuation — QuantDeck", layout="wide")
st.title("Layer 3 — Valuation Engine")
st.caption("Equity only. Price-target range, not a single number.")

default_ticker = st.session_state.get("deep_dive_ticker", "AAPL")
col_t, col_btn = st.columns([3, 1])
with col_t:
    ticker = st.text_input("Ticker", value=default_ticker).upper().strip()
with col_btn:
    st.write("")
    run = st.button("Value", type="primary")

from data.prices import detect_asset_type, country_from_ticker
asset_type = detect_asset_type(ticker)
if asset_type != "equity":
    st.info(
        f"**Valuation not applicable for {asset_type.upper()} instruments.**\n\n"
        f"DCF, DDM, and comparable company models require cash flow forecasts. "
        f"FX rates and commodity prices are driven by macro flows rather than "
        f"discounted earnings. Use the Deep Dive → Market Drivers panel for {ticker}."
    )
    st.stop()
country = country_from_ticker(ticker)

cache_key = f"val_{ticker}"
if not run and cache_key not in st.session_state:
    st.info("Enter an equity ticker and click **Value**.")
    st.stop()

if run or cache_key not in st.session_state:
    with st.spinner(f"Running valuation for {ticker}…"):
        try:
            from layers.valuation import run_valuation
            val = run_valuation(ticker, country=country)
            st.session_state[cache_key] = val
        except Exception as e:
            st.error(f"Valuation failed for {ticker!r}: {e}")
            st.stop()
else:
    val = st.session_state[cache_key]

wacc_in       = val.get("wacc_inputs", {})
dcf           = val.get("dcf_base")
sensitivity   = val.get("dcf_sensitivity", pd.DataFrame())
comps         = val.get("comps", pd.DataFrame())
comps_implied = val.get("comps_implied")
ddm           = val.get("ddm", {})
current_price = val.get("current_price", float("nan"))
shares        = val.get("shares_outstanding", float("nan"))

with st.expander("WACC Breakdown (Damodaran)", expanded=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Risk-Free Rate (Rf)", fmt_percent(wacc_in.get("rf", 0)))
    c2.metric("Beta (β)",            fmt_number(wacc_in.get("beta", 0)))
    c3.metric("ERP",                 fmt_percent(wacc_in.get("erp", 0)))
    c4.metric("Country Risk (CRP)",  fmt_percent(wacc_in.get("crp", 0)))
    c5.metric("Cost of Equity (Ke)", fmt_percent(wacc_in.get("ke", 0)))
    c6, c7, c8 = st.columns(3)
    c6.metric("Cost of Debt (Kd)",   fmt_percent(wacc_in.get("kd", 0)))
    c7.metric("Tax Rate",            fmt_percent(wacc_in.get("tax_rate", 0)))
    c8.metric("WACC",                fmt_percent(wacc_in.get("wacc", 0)))
    st.caption("Ke = Rf + β × ERP + CRP   |   WACC = Ke×E/(D+E) + Kd×(1−t)×D/(D+E)")

tab_dcf, tab_comps, tab_ddm = st.tabs(["DCF", "Comps", "DDM"])

with tab_dcf:
    if dcf is None:
        st.warning("Could not compute DCF — check FMP data availability for this ticker.")
    else:
        col_base, col_bull, col_bear = st.columns(3)
        col_base.metric("Base Case", fmt_currency(dcf.get("price_base"), "USD"))
        col_bull.metric("Bull Case", fmt_currency(dcf.get("price_bull"), "USD"))
        col_bear.metric("Bear Case", fmt_currency(dcf.get("price_bear"), "USD"))
        col_base.metric("Current Price", fmt_currency(current_price, "USD"))

        if not sensitivity.empty:
            st.subheader("WACC × Terminal Growth Sensitivity")
            st.caption("Each cell = implied price per share. Green = higher, red = lower.")
            from utils.charts import heatmap as _heatmap
            fig_heat = _heatmap(sensitivity.astype(float).round(2), colorscale="RdYlGn", title="")
            fig_heat.update_layout(height=300,
                                   xaxis_title="Terminal Growth", yaxis_title="WACC")
            st.plotly_chart(fig_heat, use_container_width=True)

with tab_comps:
    if comps.empty:
        st.warning("No peer data available.")
    else:
        st.subheader("Peer Multiples")
        st.dataframe(
            comps.style.highlight_max(color="lightgreen", axis=0)
                       .highlight_min(color="#ffcccc", axis=0),
            use_container_width=True,
        )
        if comps_implied:
            c1, c2 = st.columns(2)
            c1.metric("Implied from P/E",       fmt_currency(comps_implied.get("price_from_pe"), "USD"))
            c2.metric("Implied from EV/EBITDA", fmt_currency(comps_implied.get("price_from_ev_ebitda"), "USD"))

with tab_ddm:
    if not ddm.get("applicable"):
        st.info(f"DDM not applicable: {ddm.get('reason', 'insufficient dividend history')}")
    else:
        st.metric("DDM Implied Price", fmt_currency(ddm.get("price"), "USD"))
        st.metric("Current Dividend / Share", fmt_currency(ddm.get("current_dividend_per_share"), "USD"))

st.divider()
st.subheader("Football Field — Implied Value Range")


def _ok(v):
    return v is not None and v == v  # not None and not NaN


ranges = []
if dcf:
    bear = dcf.get("price_bear")
    bull = dcf.get("price_bull")
    base = dcf.get("price_base")
    if _ok(bear) and _ok(bull):
        lo, hi = sorted([bear, bull])
        ranges.append(("DCF Bear–Bull", lo, hi))
    if _ok(base):
        ranges.append(("DCF Base", base, base))

if comps_implied:
    pe_p = comps_implied.get("price_from_pe")
    ev_p = comps_implied.get("price_from_ev_ebitda")
    if _ok(pe_p):
        ranges.append(("Comps (P/E)", pe_p * 0.9, pe_p * 1.1))
    if _ok(ev_p):
        ranges.append(("Comps (EV/EBITDA)", ev_p * 0.9, ev_p * 1.1))

if ddm.get("applicable") and _ok(ddm.get("price")):
    p = ddm["price"]
    ranges.append(("DDM", p * 0.9, p * 1.1))

# Keep only ranges with sensible positive prices
ranges = [(label, lo, hi) for (label, lo, hi) in ranges if _ok(lo) and _ok(hi) and hi >= lo]

if ranges:
    fig_ff = go.Figure()
    colors = ["steelblue", "orange", "green", "purple", "teal"]
    for i, (label, lo, hi) in enumerate(ranges):
        fig_ff.add_trace(go.Bar(
            x=[max(hi - lo, 0.01)], y=[label], base=[lo],
            orientation="h", marker_color=colors[i % len(colors)], name=label,
            hovertemplate=f"{label}: ${lo:.2f} – ${hi:.2f}<extra></extra>",
        ))
    if _ok(current_price):
        fig_ff.add_vline(x=current_price, line_color="black", line_dash="dash",
                         annotation_text=f"Current ${current_price:.2f}", annotation_position="top")
    fig_ff.update_layout(barmode="overlay", height=300, showlegend=False,
                         xaxis_title="Implied Price (USD)", title="Valuation Range by Method")
    st.plotly_chart(fig_ff, use_container_width=True)

    all_lo = min(r[1] for r in ranges)
    all_hi = max(r[2] for r in ranges)
    if _ok(current_price) and current_price:
        upside   = all_hi / current_price - 1
        downside = all_lo / current_price - 1
        st.metric("Implied Fair Value Range", f"${all_lo:.2f} – ${all_hi:.2f}",
                  delta=f"Upside {upside:.1%} / Downside {downside:.1%}")
    else:
        st.metric("Implied Fair Value Range", f"${all_lo:.2f} – ${all_hi:.2f}")
else:
    st.warning("Not enough data to build a football field chart.")

st.session_state[f"valuation_result_{ticker}"] = val

st.caption(
    "QuantDeck is a quantitative analysis tool. Valuations are model outputs based on "
    "historical data and user assumptions. They are not financial advice."
)
