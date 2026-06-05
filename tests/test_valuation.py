# tests/test_valuation.py
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
