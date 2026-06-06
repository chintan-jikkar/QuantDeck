# tests/test_valuation.py
from unittest import mock

import pandas as pd
import pytest


def test_compute_ke_damodaran():
    from layers.valuation import compute_ke
    ke = compute_ke(rf=0.04, beta=1.2, erp=0.0472, crp=0.0)
    assert ke == pytest.approx(0.09664, rel=1e-5)


def test_compute_ke_with_country_risk():
    from layers.valuation import compute_ke
    ke = compute_ke(rf=0.07, beta=1.0, erp=0.0472, crp=0.0234)
    assert ke == pytest.approx(0.1406, rel=1e-5)


def test_compute_wacc():
    from layers.valuation import compute_wacc
    wacc = compute_wacc(ke=0.10, kd=0.05, tax_rate=0.25, equity=800e6, debt=200e6)
    assert wacc == pytest.approx(0.0875, rel=1e-5)


def test_compute_wacc_all_equity():
    from layers.valuation import compute_wacc
    wacc = compute_wacc(ke=0.10, kd=0.05, tax_rate=0.25, equity=1000e6, debt=0)
    assert wacc == pytest.approx(0.10, rel=1e-5)


def test_compute_wacc_raises_on_zero_capital():
    from layers.valuation import compute_wacc
    with pytest.raises(ValueError, match="positive"):
        compute_wacc(ke=0.10, kd=0.05, tax_rate=0.25, equity=0, debt=0)


def test_compute_terminal_value():
    from layers.valuation import compute_terminal_value
    tv = compute_terminal_value(fcf_final=100e6, wacc=0.09, growth_rate=0.03)
    assert tv == pytest.approx(1716.67e6, rel=1e-4)


def test_compute_terminal_value_raises_when_g_exceeds_wacc():
    from layers.valuation import compute_terminal_value
    with pytest.raises(ValueError, match="growth rate"):
        compute_terminal_value(fcf_final=100e6, wacc=0.03, growth_rate=0.05)


def test_project_fcf_length():
    from layers.valuation import project_fcf
    fcfs = project_fcf(
        base_revenue=400e6, growth_rates=[0.08] * 5, ebit_margin=0.20,
        capex_pct=0.06, da_pct=0.05, tax_rate=0.25, years=5,
    )
    assert len(fcfs) == 5


def test_project_fcf_year1():
    from layers.valuation import project_fcf
    fcfs = project_fcf(
        base_revenue=400e6, growth_rates=[0.08] * 5, ebit_margin=0.20,
        capex_pct=0.06, da_pct=0.05, tax_rate=0.25, years=5,
    )
    assert fcfs[0] == pytest.approx(60.48e6, rel=1e-4)


def test_compute_dcf_price():
    from layers.valuation import compute_dcf_price, compute_terminal_value
    fcf_series = [50e6, 55e6, 60e6, 65e6, 70e6]
    wacc = 0.10
    tv = compute_terminal_value(fcf_final=70e6, wacc=wacc, growth_rate=0.03)
    price = compute_dcf_price(
        fcf_series=fcf_series, terminal_value=tv, wacc=wacc,
        net_debt=100e6, shares_outstanding=100e6,
    )
    assert price == pytest.approx(7.634, rel=1e-2)


def test_compute_ddm_price():
    from layers.valuation import compute_ddm_price
    price = compute_ddm_price(
        current_dividend=2.0, growth_rates=[0.08] * 5, ke=0.10, stable_growth=0.03,
    )
    assert price == pytest.approx(36.32, rel=1e-2)


def test_compute_ddm_raises_on_ke_le_stable_growth():
    from layers.valuation import compute_ddm_price
    with pytest.raises(ValueError, match="cost of equity"):
        compute_ddm_price(
            current_dividend=2.0, growth_rates=[0.05] * 5, ke=0.03, stable_growth=0.03,
        )


def test_compute_dcf_sensitivity_shape():
    from layers.valuation import compute_dcf_sensitivity
    fcf_series = [50e6, 55e6, 60e6]
    result = compute_dcf_sensitivity(
        fcf_series=fcf_series, base_fcf_final=60e6,
        wacc_values=[0.08, 0.09, 0.10, 0.11, 0.12],
        growth_values=[0.005, 0.01, 0.02, 0.03, 0.035],
        net_debt=50e6, shares_outstanding=100e6,
    )
    assert result.shape == (5, 5)
    assert isinstance(result, pd.DataFrame)


def test_compute_dcf_sensitivity_higher_wacc_lower_price():
    from layers.valuation import compute_dcf_sensitivity
    fcf_series = [50e6, 55e6, 60e6]
    result = compute_dcf_sensitivity(
        fcf_series=fcf_series, base_fcf_final=60e6,
        wacc_values=[0.08, 0.12], growth_values=[0.02],
        net_debt=0, shares_outstanding=100e6,
    )
    assert result.iloc[0, 0] > result.iloc[1, 0]


# ── _derive_wacc_inputs: live-data glue with the clamping logic ────────────────

def _prices_stub():
    return pd.DataFrame(
        {"Close": [100.0, 101.0, 102.0]},
        index=pd.date_range("2024-01-01", periods=3, freq="B"),
    )


def _patch_wacc_data(rf_series, beta_series, prices_side_effect=None):
    """Patch the three external fetches in layers.valuation as a context manager.

    Patched on the module object so the function-under-test sees the stubs
    regardless of how it imported them.
    """
    import layers.valuation as val
    prices_kw = (
        {"side_effect": prices_side_effect}
        if prices_side_effect is not None
        else {"return_value": _prices_stub()}
    )
    return [
        mock.patch.object(val, "fetch_fred_series", return_value=rf_series),
        mock.patch.object(val, "fetch_prices", **prices_kw),
        mock.patch.object(val, "compute_rolling_beta", return_value=beta_series),
    ]


def test_derive_wacc_inputs_hand_computed():
    """ke/kd/tax_rate/wacc match values computed by hand from small fixtures.

    rf = 4.0/100 = 0.04; beta = 1.2; US erp=0.0472, crp=0.0
      → ke = 0.04 + 1.2×0.0472 = 0.09664
    kd = 5M/100M = 0.05 (below the 0.20 cap)
    tax_rate = 15M/60M = 0.25 (within [0, 0.5])
    wacc = 0.09664×(300/400) + 0.05×(1−0.25)×(100/400) = 0.081855
    """
    import layers.valuation as val
    income = pd.DataFrame([{
        "interestExpense": 5_000_000,
        "incomeTaxExpense": 15_000_000,
        "incomeBeforeTax": 60_000_000,
    }])
    balance = pd.DataFrame([{
        "totalDebt": 100_000_000,
        "totalEquity": 300_000_000,
    }])
    patches = _patch_wacc_data(pd.Series([3.9, 4.0]), pd.Series([1.1, 1.2]))
    with patches[0], patches[1], patches[2]:
        out = val._derive_wacc_inputs("TEST", income, balance, "US")

    assert out["rf"]       == pytest.approx(0.04, rel=1e-9)
    assert out["beta"]     == pytest.approx(1.2, rel=1e-9)
    assert out["ke"]       == pytest.approx(0.09664, rel=1e-6)
    assert out["kd"]       == pytest.approx(0.05, rel=1e-9)
    assert out["tax_rate"] == pytest.approx(0.25, rel=1e-9)
    assert out["wacc"]     == pytest.approx(0.081855, rel=1e-6)


def test_derive_wacc_inputs_loss_year_clamps_tax_to_zero():
    """A loss year (negative incomeBeforeTax) would yield a nonsense negative
    tax rate; the [0, 0.5] clamp must floor it at 0, not pass −0.2 through."""
    import layers.valuation as val
    income = pd.DataFrame([{
        "interestExpense": 5_000_000,
        "incomeTaxExpense": 10_000_000,   # raw 10M / −50M = −0.2
        "incomeBeforeTax": -50_000_000,
    }])
    balance = pd.DataFrame([{
        "totalDebt": 100_000_000,
        "totalEquity": 300_000_000,
    }])
    patches = _patch_wacc_data(pd.Series([4.0]), pd.Series([1.0]))
    with patches[0], patches[1], patches[2]:
        out = val._derive_wacc_inputs("TEST", income, balance, "US")

    assert out["tax_rate"] == 0
    assert out["tax_rate"] >= 0


def test_derive_wacc_inputs_kd_capped_at_twenty_percent():
    """An outsized interest/debt ratio is capped at 0.20."""
    import layers.valuation as val
    income = pd.DataFrame([{
        "interestExpense": 50_000_000,    # raw 50M / 100M = 0.50
        "incomeTaxExpense": 15_000_000,
        "incomeBeforeTax": 60_000_000,
    }])
    balance = pd.DataFrame([{
        "totalDebt": 100_000_000,
        "totalEquity": 300_000_000,
    }])
    patches = _patch_wacc_data(pd.Series([4.0]), pd.Series([1.0]))
    with patches[0], patches[1], patches[2]:
        out = val._derive_wacc_inputs("TEST", income, balance, "US")

    assert out["kd"] == pytest.approx(0.20, rel=1e-9)


def test_derive_wacc_inputs_beta_falls_back_to_one_on_fetch_failure():
    """When the price fetch raises, beta degrades to 1.0 and ke uses it."""
    import layers.valuation as val
    income = pd.DataFrame([{
        "interestExpense": 5_000_000,
        "incomeTaxExpense": 15_000_000,
        "incomeBeforeTax": 60_000_000,
    }])
    balance = pd.DataFrame([{
        "totalDebt": 100_000_000,
        "totalEquity": 300_000_000,
    }])
    patches = _patch_wacc_data(
        pd.Series([4.0]), pd.Series([1.5]),
        prices_side_effect=Exception("no price data"),
    )
    with patches[0], patches[1], patches[2]:
        out = val._derive_wacc_inputs("TEST", income, balance, "US")

    assert out["beta"] == pytest.approx(1.0, rel=1e-9)
    # ke = 0.04 + 1.0×0.0472 = 0.0872
    assert out["ke"] == pytest.approx(0.0872, rel=1e-6)


# ── Valuation not-applicable gate ─────────────────────────────────────────────

def test_run_valuation_not_applicable_for_fx():
    from layers.valuation import run_valuation
    result = run_valuation("EURUSD=X")
    assert result["applicable"] is False
    assert "fx" in result["reason"].lower()
    assert result["asset_type"] == "fx"


def test_run_valuation_not_applicable_for_commodity():
    from layers.valuation import run_valuation
    result = run_valuation("GC=F")
    assert result["applicable"] is False
    assert "commodity" in result["reason"].lower()
    assert result["asset_type"] == "commodity"


def test_run_valuation_not_applicable_returns_no_dcf():
    from layers.valuation import run_valuation
    result = run_valuation("CL=F")
    assert "dcf_base" not in result


def test_run_valuation_not_applicable_returns_immediately_no_network():
    # detect_asset_type is pure string logic — no network calls needed.
    # If FX gate is working, this should return instantly without errors.
    from layers.valuation import run_valuation
    result = run_valuation("NZDUSD=X")
    assert result.get("applicable") is False


def test_derive_wacc_inputs_uk_uses_local_rf_and_crp():
    """For UK: rf from FRED IRLTLT01GBM156N; crp=0.0051; local index=^FTSE.

    Hand-computed:
      rf=0.045; beta=0.9; erp=0.0472; crp=0.0051
      ke = 0.045 + 0.9×0.0472 + 0.0051 = 0.09258
    """
    import layers.valuation as val
    income = pd.DataFrame([{
        "interestExpense": 5_000_000,
        "incomeTaxExpense": 15_000_000,
        "incomeBeforeTax": 60_000_000,
    }])
    balance = pd.DataFrame([{
        "totalDebt": 100_000_000,
        "totalEquity": 300_000_000,
    }])
    patches = _patch_wacc_data(pd.Series([4.5]), pd.Series([0.9]))
    with patches[0], patches[1], patches[2]:
        out = val._derive_wacc_inputs("BP.L", income, balance, "UK")

    assert out["rf"]  == pytest.approx(0.045, rel=1e-9)
    assert out["crp"] == pytest.approx(0.0051, rel=1e-9)
    assert out["ke"]  == pytest.approx(0.09258, rel=1e-5)


def test_derive_wacc_inputs_india_uses_high_crp():
    """India CRP = 0.0234 — a visibly larger ke bump than US."""
    import layers.valuation as val
    income = pd.DataFrame([{
        "interestExpense": 5_000_000,
        "incomeTaxExpense": 15_000_000,
        "incomeBeforeTax": 60_000_000,
    }])
    balance = pd.DataFrame([{
        "totalDebt": 100_000_000,
        "totalEquity": 300_000_000,
    }])
    patches = _patch_wacc_data(pd.Series([7.0]), pd.Series([1.1]))
    with patches[0], patches[1], patches[2]:
        out = val._derive_wacc_inputs("RELIANCE.NS", income, balance, "India")

    # ke = 0.07 + 1.1×0.0472 + 0.0234 = 0.07 + 0.05192 + 0.0234 = 0.14532
    assert out["crp"] == pytest.approx(0.0234, rel=1e-9)
    assert out["ke"]  == pytest.approx(0.14532, rel=1e-5)
