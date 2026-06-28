import pytest

from home_decision_ai.models.financing import (
    FinancingScenarioInput,
    annuity_payment,
    calculate_financing_scenario,
    classify_price,
)


def test_classify_price_comfortable() -> None:
    band = classify_price(920_000_000)

    assert band.id == "comfortable"


def test_classify_price_stretch() -> None:
    band = classify_price(1_045_000_000)

    assert band.id == "stretch"


def test_classify_price_over_budget() -> None:
    band = classify_price(1_700_000_000)

    assert band.id == "over_budget"


def test_annuity_payment() -> None:
    payment = annuity_payment(600_000_000, 5.0, 30 * 12)

    assert payment == pytest.approx(3_220_930, abs=1)


def test_card_costs_are_removed_from_required_credit_loan() -> None:
    result = calculate_financing_scenario(FinancingScenarioInput())

    assert result["total_required_krw"] == 1_030_115_000
    assert result["card_payment_total_krw"] == 40_115_000
    assert result["required_credit_loan_krw"] == 40_000_000
    assert result["card_monthly_payment_krw"] == 3_342_917


def test_cash_costs_are_included_in_required_credit_loan() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            card_acquisition_tax=False,
            card_brokerage=False,
            card_legal_cost=False,
        )
    )

    assert result["card_payment_total_krw"] == 0
    assert result["required_credit_loan_krw"] == 80_115_000


def test_separate_lease_equity_reduces_credit_need() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(lease_equity_included_in_cash=False)
    )

    assert result["available_cash_krw"] == 380_000_000
    assert result["required_credit_loan_krw"] == 0
    assert result["cash_surplus_krw"] == 60_000_000
