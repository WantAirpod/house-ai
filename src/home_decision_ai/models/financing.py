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
    lease_deposit_krw: int = 0
    lease_loan_krw: int = 0
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
    credit_stress_threshold_krw: int = 100_000_000
    family_loan_amount_krw: int = 70_000_000
    family_loan_rate_percent: float = 4.6
    family_loan_term_years: int = 10
    family_loan_repayment_type: str = "bullet"
    family_principal_reserve_enabled: bool = False
    acquisition_tax_rate_percent: float = 3.3
    first_time_homebuyer_eligible: bool = False
    first_time_homebuyer_price_limit_krw: int = 1_200_000_000
    first_time_acquisition_tax_discount_limit_krw: int = 2_000_000
    local_education_tax_discount_ratio_percent: float = 10.0
    brokerage_rate_percent: float = 0.55
    legal_cost_krw: int = 2_000_000
    card_acquisition_tax: bool = True
    card_brokerage: bool = True
    card_legal_cost: bool = True
    card_payment_ratio_percent: float = 100.0
    card_installment_months: int = 12
    card_installment_rate_percent: float = 0.0
    dsr_warning_percent: float = 39.0
    dsr_limit_percent: float = 40.0


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
        values.first_time_homebuyer_price_limit_krw,
        values.first_time_acquisition_tax_discount_limit_krw,
        values.credit_stress_threshold_krw,
    ]
    if any(value < 0 for value in numeric_values):
        raise ValueError("amounts cannot be negative")
    if values.combined_gross_income_krw <= 0:
        raise ValueError("combined gross income must be positive")
    if values.lease_loan_krw > values.lease_deposit_krw:
        raise ValueError("lease loan cannot exceed lease deposit")
    if not 0 <= values.card_payment_ratio_percent <= 100:
        raise ValueError("card payment ratio must be between 0 and 100")
    if values.family_loan_repayment_type not in {"bullet", "amortizing"}:
        raise ValueError("unsupported family loan repayment type")

    lease_equity = values.lease_deposit_krw - values.lease_loan_krw
    available_cash = values.cash_krw
    if not values.lease_equity_included_in_cash:
        available_cash += lease_equity

    gross_acquisition_tax = round(
        values.purchase_price_krw * values.acquisition_tax_rate_percent / 100
    )
    first_time_discount_applied = (
        values.first_time_homebuyer_eligible
        and values.purchase_price_krw <= values.first_time_homebuyer_price_limit_krw
    )
    acquisition_tax_discount = (
        min(
            round(
                gross_acquisition_tax
                / (1 + values.local_education_tax_discount_ratio_percent / 100)
            ),
            values.first_time_acquisition_tax_discount_limit_krw,
        )
        if first_time_discount_applied
        else 0
    )
    local_education_tax_discount = round(
        acquisition_tax_discount * values.local_education_tax_discount_ratio_percent / 100
    )
    first_time_tax_discount = acquisition_tax_discount + local_education_tax_discount
    acquisition_tax = max(0, gross_acquisition_tax - first_time_tax_discount)
    brokerage = round(values.purchase_price_krw * values.brokerage_rate_percent / 100)
    card_ratio = values.card_payment_ratio_percent / 100
    card_items = {
        "acquisition_tax": (
            round(acquisition_tax * card_ratio) if values.card_acquisition_tax else 0
        ),
        "brokerage": round(brokerage * card_ratio) if values.card_brokerage else 0,
        "legal_cost": (
            round(values.legal_cost_krw * card_ratio) if values.card_legal_cost else 0
        ),
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
    family_months = values.family_loan_term_years * 12
    family_monthly_payment = (
        annuity_payment(
            values.family_loan_amount_krw,
            values.family_loan_rate_percent,
            family_months,
        )
        if values.family_loan_repayment_type == "amortizing"
        else family_monthly_interest
    )
    family_principal_reserve = (
        values.family_loan_amount_krw / family_months
        if values.family_loan_repayment_type == "bullet"
        and values.family_principal_reserve_enabled
        and family_months > 0
        else 0
    )
    card_payment = annuity_payment(
        card_payment_total,
        values.card_installment_rate_percent,
        values.card_installment_months,
    )

    credit_stress_applied = required_credit_loan > values.credit_stress_threshold_krw
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
    monthly_debt_payment = mortgage_payment + credit_payment + family_monthly_payment
    monthly_outflow_during_card_installment = (
        monthly_debt_payment + family_principal_reserve + card_payment
    )
    total_required = values.purchase_price_krw + total_transaction_cost

    warnings: list[str] = []
    if stress_dsr >= values.dsr_limit_percent:
        warnings.append(
            f"스트레스 DSR이 설정 한도 {values.dsr_limit_percent:g}% 이상입니다. "
            "대출 승인 가능성이 낮습니다."
        )
    elif stress_dsr >= values.dsr_warning_percent:
        warnings.append(
            f"스트레스 DSR이 설정 경고구간 {values.dsr_warning_percent:g}~"
            f"{values.dsr_limit_percent:g}%입니다."
        )
    if credit_stress_applied:
        warnings.append(
            f"신용대출이 설정 기준 {values.credit_stress_threshold_krw:,}원을 초과해 "
            "신용대출 스트레스 금리를 반영했습니다."
        )
    if values.first_time_homebuyer_eligible and not first_time_discount_applied:
        warnings.append("매매가가 12억원을 초과해 생애최초 취득세 감면을 적용하지 않았습니다.")
    if first_time_discount_applied:
        warnings.append(
            "생애최초 감면은 본인과 배우자의 과거 주택 소유 이력이 없다는 가정입니다. "
            "관할 시·군·구에서 자격과 최종 세액을 확인해야 합니다."
        )
        warnings.append(
            "취득일부터 3년 이내 매각·증여·임대 등 다른 용도로 사용하면 감면세액이 "
            "추징될 수 있습니다."
        )
    if card_payment_total > 0:
        warnings.append(
            "카드 결제분은 신용대출에서 제외했지만 카드 결제일까지 갚아야 하는 부채입니다."
        )
    if card_payment > combined_monthly_income(values) * 0.2:
        warnings.append("카드 월 납입액이 세전 월소득의 20%를 초과합니다.")
    if (
        values.family_loan_repayment_type == "bullet"
        and values.family_loan_amount_krw > 0
        and not values.family_principal_reserve_enabled
    ):
        warnings.append(
            f"부모 차용 만기 원금 {values.family_loan_amount_krw:,}원은 월 현금유출에 "
            "포함되지 않았습니다. 만기 상환재원을 별도로 준비해야 합니다."
        )

    result = {
        "lease_equity_krw": round(lease_equity),
        "available_cash_krw": round(available_cash),
        "gross_acquisition_tax_krw": gross_acquisition_tax,
        "first_time_discount_applied": first_time_discount_applied,
        "first_time_acquisition_tax_discount_krw": acquisition_tax_discount,
        "first_time_local_education_tax_discount_krw": local_education_tax_discount,
        "first_time_tax_discount_krw": first_time_tax_discount,
        "acquisition_tax_krw": acquisition_tax,
        "brokerage_krw": brokerage,
        "legal_cost_krw": values.legal_cost_krw,
        "total_transaction_cost_krw": round(total_transaction_cost),
        "total_required_krw": round(total_required),
        "card_items": card_items,
        "card_payment_ratio_percent": values.card_payment_ratio_percent,
        "card_payment_total_krw": round(card_payment_total),
        "cash_required_at_closing_krw": round(cash_required_at_closing),
        "required_credit_loan_krw": round(required_credit_loan),
        "cash_surplus_krw": round(cash_surplus),
        "mortgage_monthly_payment_krw": round(mortgage_payment),
        "credit_monthly_payment_krw": round(credit_payment),
        "family_loan_repayment_type": values.family_loan_repayment_type,
        "family_monthly_interest_krw": round(family_monthly_interest),
        "family_monthly_payment_krw": round(family_monthly_payment),
        "family_principal_reserve_krw": round(family_principal_reserve),
        "family_balloon_payment_krw": (
            values.family_loan_amount_krw
            if values.family_loan_repayment_type == "bullet"
            else 0
        ),
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
        "dsr_warning_percent": values.dsr_warning_percent,
        "dsr_limit_percent": values.dsr_limit_percent,
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
