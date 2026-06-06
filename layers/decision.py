# layers/decision.py — no Streamlit imports
"""Cross-layer decision signal: a structured framework, NOT financial advice.

Synthesizes Fundamental Health (Deep Dive), Valuation, and Simulation Odds into
1-5 sub-scores plus a combined reward/risk view. Each input dict carries only the
already-computed summary numbers from its layer.
"""


def compute_reward_risk(current: float, p50: float, p10: float) -> float:
    """Reward/Risk = (P50 upside) / (P10 downside). inf when no downside."""
    upside = (p50 - current) / current
    downside = (current - p10) / current
    if downside <= 0:
        return float("inf")
    return float(upside / downside) if upside > 0 else 0.0


def fundamental_health_score(dd: dict) -> tuple[int, str]:
    """1-5 fundamental health score from Beneish, net margin, leverage."""
    score = 3
    notes = []
    m = dd.get("beneish_mscore")
    if m is not None and m == m:
        if m < -2.22:
            score += 1; notes.append("clean Beneish M-Score")
        else:
            score -= 1; notes.append("Beneish flags earnings-quality risk")
    nm = dd.get("margins_net")
    if nm is not None and nm == nm:
        if nm > 0.12:
            score += 1; notes.append(f"healthy net margin ({nm:.0%})")
        elif nm < 0.03:
            score -= 1; notes.append("thin net margin")
    de = dd.get("debt_equity")
    if de is not None and de == de:
        if de < 0.5:
            notes.append("low leverage")
        elif de > 2.0:
            score -= 1; notes.append("high leverage")
    score = max(1, min(5, score))
    return score, "; ".join(notes) or "limited fundamental data"


def valuation_signal(current: float, fair_low: float, fair_high: float) -> tuple[int, str]:
    """1-5 valuation score from where price sits vs the fair-value range."""
    mid = (fair_low + fair_high) / 2
    upside = (mid / current - 1) if current else 0.0
    if upside > 0.20:
        return 5, f"~{upside:.0%} upside to fair-value midpoint"
    if upside > 0.05:
        return 4, f"modest {upside:.0%} upside"
    if upside > -0.05:
        return 3, "roughly fairly valued"
    if upside > -0.20:
        return 2, f"{upside:.0%} below fair value (overvalued)"
    return 1, f"{upside:.0%} - materially overvalued"


def simulation_signal(sim: dict) -> tuple[int, str]:
    """1-5 simulation-odds score from probability of profit."""
    pp = sim.get("prob_profit", 0.5)
    if pp >= 0.65:
        return 5, f"{pp:.0%} probability of profit"
    if pp >= 0.55:
        return 4, f"{pp:.0%} odds favorable"
    if pp >= 0.45:
        return 3, f"{pp:.0%} roughly even odds"
    if pp >= 0.35:
        return 2, f"{pp:.0%} odds unfavorable"
    return 1, f"{pp:.0%} poor odds"


def build_decision_signal(deep_dive: dict, valuation: dict, simulation: dict) -> dict:
    """Combine the three layer summaries into a structured signal dict."""
    f_score, f_ev = fundamental_health_score(deep_dive)
    v_score, v_ev = valuation_signal(
        valuation.get("current", 0), valuation.get("fair_low", 0), valuation.get("fair_high", 0))
    s_score, s_ev = simulation_signal(simulation)

    rr = compute_reward_risk(
        simulation.get("current", 0), simulation.get("p50", 0), simulation.get("p10", 0))

    avg = (f_score + v_score + s_score) / 3
    if avg >= 4:
        combined = "Constructive"
    elif avg >= 3:
        combined = "Neutral / Watch"
    else:
        combined = "Cautious"

    scores = [f_score, v_score, s_score]
    conflict = (max(scores) - min(scores)) >= 3

    return {
        "fundamental": {"score": f_score, "evidence": f_ev},
        "valuation":   {"score": v_score, "evidence": v_ev},
        "simulation":  {"score": s_score, "evidence": s_ev},
        "combined": combined,
        "reward_risk": rr,
        "conflict": conflict,
        "disclaimer": ("This signal is a quantitative framework, not financial advice. "
                       "It does not account for gap risk from earnings events, "
                       "regulatory changes, or macro regime shifts."),
    }
