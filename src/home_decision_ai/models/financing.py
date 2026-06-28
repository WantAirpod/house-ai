from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FinancingBand:
    id: str
    name: str
    recommendation: str
    min_price_krw: int | None = None
    max_price_krw: int | None = None


DEFAULT_BANDS = [
    FinancingBand(
        id="comfortable",
        name="현실 플랜 적합",
        max_price_krw=920_000_000,
        recommendation="우선 검토",
    ),
    FinancingBand(
        id="stretch",
        name="확장 플랜 필요",
        min_price_krw=920_000_001,
        max_price_krw=1_050_000_000,
        recommendation="월 부담과 호가 협상 여지 확인",
    ),
    FinancingBand(
        id="over_budget",
        name="예산 초과",
        min_price_krw=1_050_000_001,
        recommendation="제외 또는 급매만 관찰",
    ),
]


def classify_price(price_krw: int, bands: list[FinancingBand] | None = None) -> FinancingBand:
    active_bands = bands or DEFAULT_BANDS
    for band in active_bands:
        if band.min_price_krw is not None and price_krw < band.min_price_krw:
            continue
        if band.max_price_krw is not None and price_krw > band.max_price_krw:
            continue
        return band
    return active_bands[-1]


@dataclass(frozen=True)
class FinancingScenarioInput:
    purchase_price_krw: int = 990_000_000
    cash_krw: int = 280_000_000
    lease_deposit_krw: int = 400_000_000
    lease_loan_krw: int = 300_000_000
    lease_equity_included_in_cash: bool = True
    combined_gross_income_krw: int = 150_000_000
    mortgage_amount_krw: int = 600_000_000
    mortgage_rate_percent: float = 5.0
    mortgage_term_years: int = 30
    mortgage_stress_rate_percent: float = 3.0
    mortgage_stress_ratio_percent: float = 40.0
    credit_rate_percent: float = 6.0
    credit_term_years: int = 7
    credit_stress_rate_percent: float = 1.5
    family_loan_amount_krw: int = 70_000_000
    family_loan_rate_percent: float = 4.6
    family_loan_term_years: int = 10
    acquisition_tax_rate_percent: float = 3.3
    brokerage_rate_percent: float = 0.55
    legal_cost_krw: int = 2_000_000
    card_acquisition_tax: bool = True
    card_brokerage: bool = True
    card_legal_cost: bool = True
    card_installment_months: int = 12
    card_installment_rate_percent: float = 0.0


def annuity_payment(principal_krw: float, annual_rate_percent: float, months: int) -> float:
    if principal_krw <= 0:
        return 0.0
    if months <= 0:
        raise ValueError("months must be positive")
    monthly_rate = annual_rate_percent / 100 / 12
    if monthly_rate == 0:
        return principal_krw / months
    factor = (1 + monthly_rate) ** months
    return principal_krw * monthly_rate * factor / (factor - 1)


def calculate_financing_scenario(values: FinancingScenarioInput) -> dict[str, object]:
    numeric_values = [
        values.purchase_price_krw,
        values.cash_krw,
        values.lease_deposit_krw,
        values.lease_loan_krw,
        values.combined_gross_income_krw,
        values.mortgage_amount_krw,
        values.family_loan_amount_krw,
        values.legal_cost_krw,
    ]
    if any(value < 0 for value in numeric_values):
        raise ValueError("amounts cannot be negative")
    if values.combined_gross_income_krw <= 0:
        raise ValueError("combined gross income must be positive")
    if values.lease_loan_krw > values.lease_deposit_krw:
        raise ValueError("lease loan cannot exceed lease deposit")

    lease_equity = values.lease_deposit_krw - values.lease_loan_krw
    available_cash = values.cash_krw
    if not values.lease_equity_included_in_cash:
        available_cash += lease_equity

    acquisition_tax = round(values.purchase_price_krw * values.acquisition_tax_rate_percent / 100)
    brokerage = round(values.purchase_price_krw * values.brokerage_rate_percent / 100)
    card_items = {
        "acquisition_tax": acquisition_tax if values.card_acquisition_tax else 0,
        "brokerage": brokerage if values.card_brokerage else 0,
        "legal_cost": values.legal_cost_krw if values.card_legal_cost else 0,
    }
    card_payment_total = sum(card_items.values())
    total_transaction_cost = acquisition_tax + brokerage + values.legal_cost_krw
    cash_required_at_closing = (
        values.purchase_price_krw + total_transaction_cost - card_payment_total
    )
    non_credit_funds = available_cash + values.mortgage_amount_krw + values.family_loan_amount_krw
    required_credit_loan = max(0, cash_required_at_closing - non_credit_funds)
    cash_surplus = max(0, non_credit_funds - cash_required_at_closing)

    mortgage_months = values.mortgage_term_years * 12
    credit_months = values.credit_term_years * 12
    mortgage_payment = annuity_payment(
        values.mortgage_amount_krw, values.mortgage_rate_percent, mortgage_months
    )
    credit_payment = annuity_payment(
        required_credit_loan, values.credit_rate_percent, credit_months
    )
    family_monthly_interest = (
        values.family_loan_amount_krw * values.family_loan_rate_percent / 100 / 12
    )
    family_principal_reserve = (
        values.family_loan_amount_krw / (values.family_loan_term_years * 12)
        if values.family_loan_term_years > 0
        else 0
    )
    card_payment = annuity_payment(
        card_payment_total,
        values.card_installment_rate_percent,
        values.card_installment_months,
    )

    credit_stress_applied = required_credit_loan > 100_000_000
    mortgage_stress_rate = values.mortgage_rate_percent + (
        values.mortgage_stress_rate_percent * values.mortgage_stress_ratio_percent / 100
    )
    credit_stress_rate = values.credit_rate_percent + (
        values.credit_stress_rate_percent if credit_stress_applied else 0
    )
    mortgage_stress_payment = annuity_payment(
        values.mortgage_amount_krw, mortgage_stress_rate, mortgage_months
    )
    credit_stress_payment = annuity_payment(required_credit_loan, credit_stress_rate, credit_months)
    contract_dsr = (mortgage_payment + credit_payment) * 12 / values.combined_gross_income_krw * 100
    stress_dsr = (
        (mortgage_stress_payment + credit_stress_payment)
        * 12
        / values.combined_gross_income_krw
        * 100
    )
    monthly_debt_payment = mortgage_payment + credit_payment + family_monthly_interest
    monthly_outflow_during_card_installment = (
        monthly_debt_payment + family_principal_reserve + card_payment
    )
    total_required = values.purchase_price_krw + total_transaction_cost

    warnings: list[str] = []
    if stress_dsr >= 40:
        warnings.append("스트레스 DSR이 40% 이상입니다. 대출 승인 가능성이 낮습니다.")
    elif stress_dsr >= 39:
        warnings.append("스트레스 DSR이 내부 경계구간인 39~40%입니다.")
    if credit_stress_applied:
        warnings.append("신용대출이 1억원을 초과해 신용대출 스트레스 금리를 반영했습니다.")
    if card_payment_total > 0:
        warnings.append(
            "카드 결제분은 신용대출에서 제외했지만 카드 결제일까지 갚아야 하는 부채입니다."
        )
    if card_payment > combined_monthly_income(values) * 0.2:
        warnings.append("카드 월 납입액이 세전 월소득의 20%를 초과합니다.")

    result = {
        "lease_equity_krw": round(lease_equity),
        "available_cash_krw": round(available_cash),
        "acquisition_tax_krw": acquisition_tax,
        "brokerage_krw": brokerage,
        "legal_cost_krw": values.legal_cost_krw,
        "total_transaction_cost_krw": round(total_transaction_cost),
        "total_required_krw": round(total_required),
        "card_items": card_items,
        "card_payment_total_krw": round(card_payment_total),
        "cash_required_at_closing_krw": round(cash_required_at_closing),
        "required_credit_loan_krw": round(required_credit_loan),
        "cash_surplus_krw": round(cash_surplus),
        "mortgage_monthly_payment_krw": round(mortgage_payment),
        "credit_monthly_payment_krw": round(credit_payment),
        "family_monthly_interest_krw": round(family_monthly_interest),
        "family_principal_reserve_krw": round(family_principal_reserve),
        "card_monthly_payment_krw": round(card_payment),
        "monthly_debt_payment_krw": round(monthly_debt_payment),
        "monthly_outflow_during_card_installment_krw": round(
            monthly_outflow_during_card_installment
        ),
        "contract_dsr_percent": round(contract_dsr, 1),
        "stress_dsr_percent": round(stress_dsr, 1),
        "mortgage_stress_rate_percent": round(mortgage_stress_rate, 2),
        "credit_stress_rate_percent": round(credit_stress_rate, 2),
        "credit_stress_applied": credit_stress_applied,
        "combined_monthly_income_krw": round(combined_monthly_income(values)),
        "warnings": warnings,
    }
    if not all(
        isfinite(value)
        for value in result.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ):
        raise ValueError("calculation produced a non-finite result")
    return result


def combined_monthly_income(values: FinancingScenarioInput) -> float:
    return values.combined_gross_income_krw / 12
