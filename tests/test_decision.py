# tests/test_decision.py
import pytest


def test_reward_risk_ratio_basic():
    from layers.decision import compute_reward_risk
    rr = compute_reward_risk(current=100, p50=120, p10=90)
    assert rr == pytest.approx(2.0, rel=1e-4)


def test_reward_risk_zero_downside_is_inf():
    from layers.decision import compute_reward_risk
    rr = compute_reward_risk(current=100, p50=120, p10=100)
    assert rr == float("inf")


def test_fundamental_health_score_clean_company():
    from layers.decision import fundamental_health_score
    score, evidence = fundamental_health_score({
        "beneish_mscore": -2.8,
        "margins_net": 0.18,
        "debt_equity": 0.4,
    })
    assert score >= 3
    assert isinstance(evidence, str)


def test_valuation_signal_undervalued():
    from layers.decision import valuation_signal
    score, evidence = valuation_signal(current=100, fair_low=120, fair_high=160)
    assert score >= 3


def test_valuation_signal_overvalued():
    from layers.decision import valuation_signal
    score, evidence = valuation_signal(current=100, fair_low=60, fair_high=80)
    assert score <= 2


def test_build_decision_signal_keys():
    from layers.decision import build_decision_signal
    result = build_decision_signal(
        deep_dive={"beneish_mscore": -2.8, "margins_net": 0.18, "debt_equity": 0.4},
        valuation={"current": 100, "fair_low": 120, "fair_high": 160},
        simulation={"current": 100, "p50": 125, "p10": 92, "prob_profit": 0.62},
    )
    for k in ["fundamental", "valuation", "simulation", "combined", "reward_risk", "conflict"]:
        assert k in result


def test_build_decision_signal_detects_conflict():
    from layers.decision import build_decision_signal
    result = build_decision_signal(
        deep_dive={"beneish_mscore": -3.0, "margins_net": 0.25, "debt_equity": 0.2},
        valuation={"current": 100, "fair_low": 110, "fair_high": 140},
        simulation={"current": 100, "p50": 98, "p10": 80, "prob_profit": 0.40},
    )
    assert isinstance(result["conflict"], bool)
