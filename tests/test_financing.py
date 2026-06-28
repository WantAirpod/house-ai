import pytest

from home_decision_ai.models.financing import (
    FinancingScenarioInput,
    annuity_payment,
    calculate_financing_scenario,
    classify_price,
    principal_for_annuity_payment,
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


def test_annuity_payment_can_be_inverted() -> None:
    payment = annuity_payment(80_000_000, 6.0, 7 * 12)

    principal = principal_for_annuity_payment(payment, 6.0, 7 * 12)

    assert principal == pytest.approx(80_000_000, abs=1)


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


def test_transaction_costs_can_be_split_between_card_and_credit() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(card_payment_ratio_percent=50)
    )

    assert result["card_payment_ratio_percent"] == 50
    assert result["card_payment_total_krw"] == 20_057_500
    assert result["required_credit_loan_krw"] == 60_057_500
    assert result["card_monthly_payment_krw"] == 1_671_458


def test_zero_card_ratio_moves_all_transaction_costs_to_credit_need() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(card_payment_ratio_percent=0)
    )

    assert result["card_payment_total_krw"] == 0
    assert result["required_credit_loan_krw"] == 80_115_000


def test_separate_lease_equity_reduces_credit_need() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            lease_deposit_krw=400_000_000,
            lease_loan_krw=300_000_000,
            lease_equity_included_in_cash=False,
        )
    )

    assert result["available_cash_krw"] == 380_000_000
    assert result["required_credit_loan_krw"] == 0
    assert result["cash_surplus_krw"] == 60_000_000


def test_lease_values_are_ignored_until_user_enters_them() -> None:
    result = calculate_financing_scenario(FinancingScenarioInput())

    assert result["lease_equity_krw"] == 0
    assert result["available_cash_krw"] == 280_000_000


def test_first_time_homebuyer_discount_reduces_tax_and_credit_need() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            first_time_homebuyer_eligible=True,
            card_acquisition_tax=False,
            card_brokerage=False,
            card_legal_cost=False,
        )
    )

    assert result["first_time_discount_applied"] is True
    assert result["first_time_acquisition_tax_discount_krw"] == 2_000_000
    assert result["first_time_local_education_tax_discount_krw"] == 200_000
    assert result["first_time_tax_discount_krw"] == 2_200_000
    assert result["acquisition_tax_krw"] == 30_470_000
    assert result["required_credit_loan_krw"] == 77_915_000


def test_first_time_homebuyer_discount_does_not_apply_over_price_limit() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            purchase_price_krw=1_210_000_000,
            first_time_homebuyer_eligible=True,
        )
    )

    assert result["first_time_discount_applied"] is False
    assert result["first_time_tax_discount_krw"] == 0


def test_policy_thresholds_are_configurable() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            credit_stress_threshold_krw=30_000_000,
            dsr_warning_percent=20,
            dsr_limit_percent=25,
        )
    )

    assert result["credit_stress_applied"] is True
    assert result["dsr_warning_percent"] == 20
    assert result["dsr_limit_percent"] == 25


def test_dsr_limit_reports_maximum_credit_and_purchase_price() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            purchase_price_krw=1_030_000_000,
            card_payment_ratio_percent=0,
        )
    )

    assert result["stress_dsr_percent"] > 40
    assert result["credit_loan_excess_krw"] > 0
    assert result["max_credit_loan_by_dsr_krw"] < result["required_credit_loan_krw"]
    assert result["max_purchase_price_by_dsr_krw"] < 1_030_000_000
    assert result["purchase_price_excess_krw"] > 0


def test_family_loan_bullet_repayment_only_counts_monthly_interest() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            family_loan_repayment_type="bullet",
            family_principal_reserve_enabled=False,
        )
    )

    assert result["family_monthly_payment_krw"] == 268_333
    assert result["family_principal_reserve_krw"] == 0
    assert result["family_balloon_payment_krw"] == 70_000_000


def test_family_loan_principal_reserve_is_optional() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(
            family_loan_repayment_type="bullet",
            family_principal_reserve_enabled=True,
        )
    )

    assert result["family_principal_reserve_krw"] == 583_333


def test_family_loan_can_use_amortizing_repayment() -> None:
    result = calculate_financing_scenario(
        FinancingScenarioInput(family_loan_repayment_type="amortizing")
    )

    assert result["family_monthly_payment_krw"] == pytest.approx(728_848, abs=1)
    assert result["family_principal_reserve_krw"] == 0
    assert result["family_balloon_payment_krw"] == 0
