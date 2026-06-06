# pages/4_Simulation.py
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from utils.formatting import fmt_percent, fmt_currency

st.set_page_config(page_title="Simulation — QuantDeck", layout="wide")
st.title("Layer 4 — Monte Carlo Simulation")
st.caption("Distributional reality (fat tails, clustering) is modeled; discrete jump risk is not.")

default_ticker = st.session_state.get("deep_dive_ticker", "AAPL")
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
ticker = c1.text_input("Ticker", value=default_ticker).upper().strip()
model = c2.selectbox("Model", ["GBM", "GARCH", "OU"],
                     help="GBM = bootstrap; GARCH = fat tails + clustering; OU = mean reversion")
n_paths = c3.select_slider("Paths", options=[1000, 5000, 10000], value=5000)
horizon = c4.select_slider("Horizon (days)", options=[21, 63, 126, 252], value=252)

run = st.button("Run Simulation", type="primary")

if not run and f"sim_{ticker}_{model}_{n_paths}_{horizon}" not in st.session_state:
    st.info("Choose a model and click **Run Simulation**.")
    st.stop()

cache_key = f"sim_{ticker}_{model}_{n_paths}_{horizon}"
if run or cache_key not in st.session_state:
    with st.spinner(f"Simulating {n_paths:,} paths…"):
        try:
            from layers.simulation import run_simulation
            sim = run_simulation(ticker, model=model.lower(), n_paths=n_paths,
                                 horizon=horizon, seed=42)
            st.session_state[cache_key] = sim
        except Exception as e:
            st.error(f"Simulation failed: {e}")
            st.stop()
else:
    sim = st.session_state[cache_key]

paths = sim["paths"]
bands = sim["bands"]
rm = sim["risk_metrics"]
start = sim["start_price"]

left, right = st.columns([3, 1])

with left:
    st.subheader("Simulation Cone")
    x = list(range(len(bands)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=bands["p90"], line={"width": 0}, showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=bands["p10"], fill="tonexty",
                             fillcolor="rgba(70,130,180,0.2)", line={"width": 0}, name="P10–P90"))
    fig.add_trace(go.Scatter(x=x, y=bands["p75"], line={"width": 0}, showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=bands["p25"], fill="tonexty",
                             fillcolor="rgba(70,130,180,0.35)", line={"width": 0}, name="P25–P75"))
    fig.add_trace(go.Scatter(x=x, y=bands["p50"], line={"color": "steelblue", "width": 2}, name="Median"))
    sample = paths[:, :min(40, paths.shape[1])]
    for i in range(sample.shape[1]):
        fig.add_trace(go.Scatter(x=x, y=sample[:, i],
                                 line={"color": "rgba(150,150,150,0.15)", "width": 1},
                                 showlegend=False, hoverinfo="skip"))
    fig.update_layout(height=450, hovermode="x unified",
                      yaxis_title="Price", xaxis_title="Trading days ahead")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Terminal Distribution")
    terminal = paths[-1, :]
    hist = go.Figure(go.Histogram(x=terminal, nbinsx=60, marker_color="steelblue"))
    hist.add_vline(x=start, line_dash="dash", line_color="black",
                   annotation_text=f"Start ${start:.0f}")
    hist.update_layout(height=300, xaxis_title="Terminal price", yaxis_title="Frequency")
    st.plotly_chart(hist, use_container_width=True)

with right:
    st.subheader("Risk Metrics")
    st.metric("VaR 95%", fmt_percent(rm["var_95"]), help="Worst 5% outcome")
    st.metric("CVaR 95%", fmt_percent(rm["cvar_95"]), help="Average of the worst 5%")
    st.metric("Prob. of Profit", fmt_percent(rm["prob_profit"]))
    st.metric("Expected Return (P50)", fmt_percent(rm["expected_return"]))
    st.metric("Median Price", fmt_currency(rm["p50_price"], "USD"))

st.divider()
st.subheader("Cross-Layer Decision Signal")
dd = st.session_state.get(f"deep_dive_result_{ticker}")
val = st.session_state.get(f"valuation_result_{ticker}")
if dd and val:
    try:
        from layers.decision import build_decision_signal
        margins = dd.get("margins")
        net_margin = float(margins["net_margin"].iloc[0]) if margins is not None and not margins.empty and "net_margin" in margins.columns else float("nan")
        bs = dd.get("balance_ratios")
        de = float(bs["debt_equity"].iloc[0]) if bs is not None and not bs.empty and "debt_equity" in bs.columns else float("nan")
        dcf = val.get("dcf_base") or {}
        fair_low = dcf.get("price_bear", val.get("current_price", start))
        fair_high = dcf.get("price_bull", val.get("current_price", start))
        signal = build_decision_signal(
            deep_dive={"beneish_mscore": dd.get("beneish_mscore"),
                       "margins_net": net_margin, "debt_equity": de},
            valuation={"current": val.get("current_price", start),
                       "fair_low": fair_low, "fair_high": fair_high},
            simulation={"current": start, "p50": rm["p50_price"],
                        "p10": float(np.percentile(terminal, 10)), "prob_profit": rm["prob_profit"]},
        )
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Fundamental Health", f"{signal['fundamental']['score']}/5", help=signal["fundamental"]["evidence"])
        sc2.metric("Valuation", f"{signal['valuation']['score']}/5", help=signal["valuation"]["evidence"])
        sc3.metric("Simulation Odds", f"{signal['simulation']['score']}/5", help=signal["simulation"]["evidence"])
        rr = signal["reward_risk"]
        st.metric("Combined", signal["combined"],
                  delta=f"Reward/Risk {rr:.2f}×" if rr != float('inf') else "Reward/Risk ∞")
        if signal["conflict"]:
            st.warning("Mixed signal: the layers disagree meaningfully. Read each sub-score before acting.")
        st.caption(signal["disclaimer"])
    except Exception as e:
        st.info(f"Could not build decision signal: {e}")
else:
    st.info("Run Deep Dive and Valuation for this ticker first to complete the decision signal.")

st.caption("QuantDeck is a quantitative analysis tool, not financial advice. "
           "Simulations do not model gap risk from earnings or macro shocks.")
