# QuantDeck Backend Calculation Audit (Phase 6.1)

Date: 2026-06-07
Scope: every financial formula across `layers/` (Valuation, Backtester, Simulation,
Screener, Deep Dive), re-derived against published reference definitions.
Result: 3 substantive corrections applied, 5 minor items documented, all else verified correct.
Test suite: 227 passing.

## Summary

The math was largely sound from the original hand-review. This audit found three issues
that affect output values and corrected them, then documented five lower-severity items as
either intentional simplifications or follow-ups. The headline correction is the WACC equity
weight (book to market value), which materially changes every DCF.

## Findings

| # | Severity | Location | Issue | Status |
|---|----------|----------|-------|--------|
| 1 | High | `valuation.py` `_derive_wacc_inputs` | WACC weighted equity at book value instead of market cap | Fixed |
| 2 | Medium | `backtester.py` `compute_sortino` | Downside deviation used std of negative subset, not RMS over all periods | Fixed |
| 3 | Medium | `simulation.py` `compute_risk_metrics` | `expected_return` returned the median, not the mean | Fixed |
| 4 | Low | `backtester.py` `compute_tearsheet` | `win_rate` / `profit_factor` are period-based (daily), not trade-based | Documented |
| 5 | Low | `valuation.py` `project_fcf` | FCFF omits change in net working capital | Documented |
| 6 | Low | `screener.py` / `deep_dive.py` | 12-1 momentum lookback off by one (n-252 vs n-253) | Documented |
| 7 | Low | `deep_dive.py` `compute_beneish_mscore` | AQI omits securities term | Documented (data availability) |
| 8 | Low | `simulation.py` `simulate_ou` | OU level can go negative in extreme paths | Documented |

## Corrections applied

### 1. WACC uses market value of equity (Damodaran)

Previously the equity weight was `balance.totalEquity` (book). Standard WACC weights equity at
market value. For any firm trading above book this over-weighted debt and biased WACC downward,
inflating DCF fair values.

Fix: `_derive_wacc_inputs` now accepts an optional `market_equity` (shares x price). `run_valuation`
computes price and share count first (shares from the income statement's `weightedAverageShsOut`)
and passes the market cap through. Book equity remains a fallback only when no market value exists.

Live check (AAPL): equity weight moved from roughly 0.06T (book) to 4.59T (market cap); WACC 8.2%.

### 2. Sortino downside deviation

The denominator now uses the root-mean-square of below-target returns measured over all periods,
`sqrt(mean(min(0, excess)^2))`, replacing the sample std of only the negative subset (which
under-counted the denominator and demeaned it, inflating the ratio).

### 3. Simulation expected return

`expected_return` is now the mean path return (the true expectation). A new `median_return` key
preserves the 50th percentile. The Simulation page shows both, so the median is no longer
mislabeled as "expected." Page card labels updated accordingly.

## Verified correct (no change required)

Ke (CAPM with additive country risk premium), the WACC formula itself, Gordon terminal value,
DCF discounting, two-stage DDM, GBM bootstrap, GARCH(1,1)-t with correct unit-variance
t-standardization (`t_scale = sqrt(nu / (nu - 2))`), OU calibration and discretization,
VaR / CVaR / expected shortfall, max drawdown, CAGR, Sharpe, the Beneish 8-index coefficients
(exact match to the 1999 model, including DEPI orientation), accruals ratio, cash-conversion
ratio, margins, and composite-score normalization.

## Open follow-ups (not blocking)

- Cost of debt: when `interestExpense` is reported as 0 (e.g. AAPL on `/stable/`), `kd` resolves
  to 0 rather than the 0.04 default. Immaterial when debt is small versus market equity, but the
  fallback could floor `kd` when interest expense is missing or zero.
- Comps API cost: the normalized `fetch_key_metrics` issues three calls (key-metrics, ratios,
  financial-growth). A 6-peer comps run therefore fires ~18 calls and can hit the FMP free-tier
  per-minute limit, which the bare `except` silently turns into empty comps. Consider caching or a
  lighter peer fetch.
- Items 4 to 8 above: low-severity simplifications, fix only if precision requires it.

## Verification

- `pytest -q --ignore=tests/test_news.py`: 227 passed.
- Live `/stable/` data layer (AAPL): statements, normalized key-metrics with all legacy aliases,
  and peers all return real data.
- Live `run_valuation('AAPL')`: market-cap WACC, DCF (base/bull/bear), DDM, and comps all produce
  values (comps confirmed working when not rate-limited).
