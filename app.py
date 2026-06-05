# app.py
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

st.set_page_config(
    page_title="QuantDeck",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("QuantDeck")
st.markdown(
    "A single, coherent platform — walk in with a ticker, "
    "walk out with a full investment thesis.\n\n"
    "**Select a layer from the sidebar to begin.**"
)
st.divider()

cols = st.columns(5)
layers = [
    ("1 — Screener", "Rank and filter a universe"),
    ("2 — Deep Dive", "Complete picture of one name"),
    ("3 — Valuation", "DCF, comps, DDM"),
    ("4 — Simulation", "Monte Carlo path simulation"),
    ("5 — Backtester", "Full strategy tearsheet"),
]
for col, (label, desc) in zip(cols, layers):
    col.subheader(label)
    col.caption(desc)

st.divider()
st.caption(
    "QuantDeck is a quantitative analysis tool, not financial advice. "
    "All outputs are model results. Backtested performance is not indicative of future results."
)
