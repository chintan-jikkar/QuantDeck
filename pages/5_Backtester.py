# pages/5_Backtester.py
import streamlit as st
import plotly.graph_objects as go
from utils.formatting import fmt_percent, fmt_number

st.set_page_config(page_title="Backtester — QuantDeck", layout="wide")
st.title("Layer 5 — Backtester")
st.caption("Run a strategy over history and read the full performance tearsheet.")

from strategies import STRATEGY_REGISTRY, list_strategies

with st.sidebar:
    st.header("Strategy")
    strat_name = st.selectbox("Strategy", list(STRATEGY_REGISTRY.keys()))
    descs = {d["name"]: d for d in list_strategies()}
    if strat_name in descs:
        st.caption(descs[strat_name]["description"])

    st.header("Execution")
    ticker = st.text_input("Ticker", value=st.session_state.get("deep_dive_ticker", "AAPL")).upper().strip()
    start = st.text_input("Start date", value="2021-01-01")
    end = st.text_input("End date", value="2024-12-31")
    capital = st.number_input("Initial capital", value=100_000, step=10_000)
    commission = st.slider("Commission (bps)", 0, 50, 10)
    slippage = st.slider("Slippage (%)", 0.0, 1.0, 0.1) / 100

    st.header("Parameters")
    params = {}
    if strat_name == "MA Crossover":
        params["fast"] = st.slider("Fast MA", 5, 100, 50)
        params["slow"] = st.slider("Slow MA", 50, 300, 200)
    elif strat_name == "RSI Mean Reversion":
        params["period"] = st.slider("RSI period", 5, 30, 14)
        params["oversold"] = st.slider("Oversold", 10, 40, 30)
        params["overbought"] = st.slider("Overbought", 60, 90, 70)
    elif strat_name == "12-1 Momentum":
        params["lookback"] = st.slider("Lookback (days)", 60, 300, 252)
        params["skip"] = st.slider("Skip (days)", 0, 42, 21)

    run = st.button("Run Backtest", type="primary", use_container_width=True)

if not run:
    st.info("Configure the strategy in the sidebar, then click **Run Backtest**.")
    st.stop()

with st.spinner("Running backtest…"):
    try:
        from layers.backtester import run_backtest
        result = run_backtest(strat_name, ticker, start, end, params,
                              initial_capital=capital, commission_bps=commission,
                              slippage_pct=slippage)
    except Exception as e:
        st.error(f"Backtest failed: {e}")
        st.stop()

eq = result["equity_curve"]
ts = result["tearsheet"]

main, side = st.columns([3, 1])

with main:
    st.subheader("Equity Curve")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq.index, y=eq.values, name="Strategy",
                             line={"color": "steelblue", "width": 2}))
    bench_curve = result.get("benchmark_curve")
    bench_ticker = result.get("benchmark_ticker", "Benchmark")
    if bench_curve is not None:
        fig.add_trace(go.Scatter(x=bench_curve.index, y=bench_curve.values,
                                 name=f"Benchmark ({bench_ticker})",
                                 line={"color": "gray", "width": 1.5, "dash": "dot"}))
    log = st.checkbox("Log scale")
    fig.update_layout(height=400, hovermode="x unified", yaxis_title="Portfolio value",
                      yaxis_type="log" if log else "linear")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Drawdown")
    running_max = eq.cummax()
    dd = eq / running_max - 1.0
    fig_dd = go.Figure(go.Scatter(x=dd.index, y=dd.values, fill="tozeroy",
                                  line={"color": "indianred"}, name="Drawdown"))
    fig_dd.update_layout(height=250, yaxis_tickformat=".0%", hovermode="x unified")
    st.plotly_chart(fig_dd, use_container_width=True)

with side:
    st.subheader("Tearsheet")
    st.metric("CAGR", fmt_percent(ts["cagr"]))
    st.metric("Total Return", fmt_percent(ts["total_return"]))
    st.metric("Sharpe", fmt_number(ts["sharpe"]))
    st.metric("Sortino", fmt_number(ts["sortino"]))
    st.metric("Max Drawdown", fmt_percent(ts["max_drawdown"]))
    st.metric("Win Rate", fmt_percent(ts["win_rate"]))
    pf = ts["profit_factor"]
    st.metric("Profit Factor", fmt_number(pf) if pf != float("inf") else "∞")
    cal = ts["calmar"]
    st.metric("Calmar", fmt_number(cal) if cal != float("inf") else "∞")

st.caption("Backtested performance is not indicative of future results. "
           "QuantDeck is a quantitative analysis tool, not financial advice.")
