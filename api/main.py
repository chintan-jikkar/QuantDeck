# api/main.py
"""QuantDeck backend: exposes the existing layers/ as JSON endpoints and serves
the vanilla frontend. Run from the project root:

    uvicorn api.main:app --reload --port 8000
"""
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from api.serialize import to_jsonable

app = FastAPI(title="QuantDeck API")
_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Permissive defaults: the API returns the full ranked universe; the UI narrows it.
_WIDE_FILTERS = {
    "pe_max": 1e9, "pb_max": 1e9, "ev_ebitda_max": 1e9, "roe_min": -1e9,
    "debt_equity_max": 1e9, "revenue_growth_min": -1e9, "net_margin_min": -1e9,
    "current_ratio_min": -1e9, "rsi_min": 0, "rsi_max": 100,
}


@app.get("/api/screener")
def screener(universe: str = "Dow Jones 30", custom: str | None = None):
    """Composite-score screen for a universe (or a comma-separated custom list)."""
    from layers.screener import run_screener
    tickers = [t.strip().upper() for t in custom.split(",") if t.strip()] if custom else None
    key = "custom" if tickers else universe
    df = run_screener(key, dict(_WIDE_FILTERS), custom_tickers=tickers)
    return JSONResponse(to_jsonable({"universe": universe, "rows": df}))


# Static frontend, mounted last so /api/* routes take precedence.
# html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")
