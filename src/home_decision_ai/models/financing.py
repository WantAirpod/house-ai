from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
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
    purchase_price_krw: int = 1_017_000_000
    cash_krw: int = 290_000_000
    lease_deposit_krw: int = 0
    lease_loan_krw: int = 0
    lease_equity_included_in_cash: bool = True
    combined_gross_income_krw: int = 145_400_000
    borrower_gross_income_krw: int = 97_400_000
    spouse_gross_income_krw: int = 48_000_000
    borrower_mortgage_share_percent: float = 100.0
    mortgage_amount_krw: int = 600_000_000
    collateral_value_krw: int = 0
    ltv_ratio_percent: float = 70.0
    mortgage_policy_cap_krw: int = 600_000_000
    room_deduction_enabled: bool = False
    room_deduction_amount_krw: int = 48_000_000
    mortgage_rate_percent: float = 4.7
    mortgage_term_years: int = 40
    mortgage_stress_rate_percent: float = 3.0
    mortgage_stress_ratio_percent: float = 40.0
    credit_rate_percent: float = 6.5
    credit_term_years: int = 5
    credit_income_limit_ratio_percent: float = 100.0
    borrower_credit_income_limit_ratio_percent: float = 100.0
    spouse_credit_income_limit_ratio_percent: float = 80.0
    credit_stress_rate_percent: float = 1.5
    credit_stress_threshold_krw: int = 100_000_000
    family_loan_amount_krw: int = 65_000_000
    family_loan_rate_percent: float = 4.6
    family_loan_term_years: int = 10
    family_loan_repayment_type: str = "bullet"
    family_principal_reserve_enabled: bool = False
    acquisition_tax_rate_percent: float = 3.3
    first_time_homebuyer_eligible: bool = True
    first_time_homebuyer_price_limit_krw: int = 1_200_000_000
    first_time_acquisition_tax_discount_limit_krw: int = 2_000_000
    local_education_tax_discount_ratio_percent: float = 10.0
    brokerage_rate_percent: float = 0.55
    legal_cost_krw: int = 2_000_000
    card_acquisition_tax: bool = True
    card_brokerage: bool = False
    card_legal_cost: bool = False
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


def principal_for_annuity_payment(
    monthly_payment_krw: float, annual_rate_percent: float, months: int
) -> float:
    if monthly_payment_krw <= 0:
        return 0.0
    if months <= 0:
        raise ValueError("months must be positive")
    monthly_rate = annual_rate_percent / 100 / 12
    if monthly_rate == 0:
        return monthly_payment_krw * months
    factor = (1 + monthly_rate) ** months
    return monthly_payment_krw * (factor - 1) / (monthly_rate * factor)


def _mortgage_limits(
    values: FinancingScenarioInput, purchase_price_krw: int
) -> tuple[int, int, int, int]:
    collateral_value = values.collateral_value_krw or purchase_price_krw
    ltv_limit = round(collateral_value * values.ltv_ratio_percent / 100)
    policy_limit = values.mortgage_policy_cap_krw
    base_limit = min(ltv_limit, policy_limit)
    room_deduction = values.room_deduction_amount_krw if values.room_deduction_enabled else 0
    adjusted_limit = max(0, base_limit - room_deduction)
    effective_mortgage = min(values.mortgage_amount_krw, adjusted_limit)
    return collateral_value, ltv_limit, policy_limit, effective_mortgage


def _closing_case_summary(
    values: FinancingScenarioInput,
    *,
    label: str,
    room_deduction_enabled: bool,
    card_acquisition_tax: bool,
) -> dict[str, object]:
    scenario = replace(
        values,
        room_deduction_enabled=room_deduction_enabled,
        card_acquisition_tax=card_acquisition_tax,
    )
    gross_tax = round(scenario.purchase_price_krw * scenario.acquisition_tax_rate_percent / 100)
    discount_applied = (
        scenario.first_time_homebuyer_eligible
        and scenario.purchase_price_krw <= scenario.first_time_homebuyer_price_limit_krw
    )
    acquisition_discount = (
        min(
            round(
                gross_tax / (1 + scenario.local_education_tax_discount_ratio_percent / 100)
            ),
            scenario.first_time_acquisition_tax_discount_limit_krw,
        )
        if discount_applied
        else 0
    )
    education_discount = round(
        acquisition_discount * scenario.local_education_tax_discount_ratio_percent / 100
    )
    net_tax = max(0, gross_tax - acquisition_discount - education_discount)
    brokerage = round(scenario.purchase_price_krw * scenario.brokerage_rate_percent / 100)
    card_ratio = scenario.card_payment_ratio_percent / 100
    card_total = sum(
        (
            round(net_tax * card_ratio) if scenario.card_acquisition_tax else 0,
            round(brokerage * card_ratio) if scenario.card_brokerage else 0,
            round(scenario.legal_cost_krw * card_ratio) if scenario.card_legal_cost else 0,
        )
    )
    _, _, _, effective_mortgage = _mortgage_limits(scenario, scenario.purchase_price_krw)
    transaction_cost = net_tax + brokerage + scenario.legal_cost_krw
    cash_required = scenario.purchase_price_krw + transaction_cost - card_total
    non_credit_funds = (
        scenario.cash_krw + effective_mortgage + scenario.family_loan_amount_krw
    )
    required_credit = max(0, round(cash_required - non_credit_funds))
    room_deduction = scenario.room_deduction_amount_krw if room_deduction_enabled else 0
    return {
        "label": label,
        "room_deduction_enabled": room_deduction_enabled,
        "room_deduction_krw": room_deduction,
        "card_acquisition_tax": card_acquisition_tax,
        "effective_mortgage_krw": effective_mortgage,
        "card_payment_total_krw": round(card_total),
        "cash_required_at_closing_krw": round(cash_required),
        "required_credit_loan_krw": required_credit,
    }


def _individual_credit_capacity(
    *,
    income_krw: int,
    allocated_mortgage_stress_payment_krw: float,
    values: FinancingScenarioInput,
    credit_months: int,
) -> int:
    monthly_dsr_capacity = income_krw * values.dsr_limit_percent / 100 / 12
    monthly_credit_capacity = max(0, monthly_dsr_capacity - allocated_mortgage_stress_payment_krw)
    base_credit_capacity = principal_for_annuity_payment(
        monthly_credit_capacity, values.credit_rate_percent, credit_months
    )
    stressed_credit_capacity = principal_for_annuity_payment(
        monthly_credit_capacity,
        values.credit_rate_percent + values.credit_stress_rate_percent,
        credit_months,
    )
    threshold_supported = (
        annuity_payment(
            values.credit_stress_threshold_krw,
            values.credit_rate_percent,
            credit_months,
        )
        <= monthly_credit_capacity
    )
    max_credit = max(
        min(base_credit_capacity, values.credit_stress_threshold_krw),
        values.credit_stress_threshold_krw if threshold_supported else 0,
        stressed_credit_capacity
        if stressed_credit_capacity > values.credit_stress_threshold_krw
        else 0,
    )
    return max(0, int(max_credit) - 1_000)


def _income_limited_credit_capacity(income_krw: int, ratio_percent: float) -> int:
    return max(0, round(income_krw * ratio_percent / 100))


def _required_credit_for_price(values: FinancingScenarioInput, purchase_price_krw: int) -> int:
    gross_tax = round(purchase_price_krw * values.acquisition_tax_rate_percent / 100)
    discount_applied = (
        values.first_time_homebuyer_eligible
        and purchase_price_krw <= values.first_time_homebuyer_price_limit_krw
    )
    acquisition_discount = (
        min(
            round(
                gross_tax / (1 + values.local_education_tax_discount_ratio_percent / 100)
            ),
            values.first_time_acquisition_tax_discount_limit_krw,
        )
        if discount_applied
        else 0
    )
    education_discount = round(
        acquisition_discount * values.local_education_tax_discount_ratio_percent / 100
    )
    net_tax = max(0, gross_tax - acquisition_discount - education_discount)
    brokerage = round(purchase_price_krw * values.brokerage_rate_percent / 100)
    card_ratio = values.card_payment_ratio_percent / 100
    card_total = sum(
        (
            round(net_tax * card_ratio) if values.card_acquisition_tax else 0,
            round(brokerage * card_ratio) if values.card_brokerage else 0,
            round(values.legal_cost_krw * card_ratio) if values.card_legal_cost else 0,
        )
    )
    transaction_cost = net_tax + brokerage + values.legal_cost_krw
    lease_equity = values.lease_deposit_krw - values.lease_loan_krw
    available_cash = values.cash_krw + (
        0 if values.lease_equity_included_in_cash else lease_equity
    )
    _, _, _, effective_mortgage = _mortgage_limits(values, purchase_price_krw)
    non_credit_funds = available_cash + effective_mortgage + values.family_loan_amount_krw
    cash_required = purchase_price_krw + transaction_cost - card_total
    return max(0, round(cash_required - non_credit_funds))


def _maximum_purchase_price(values: FinancingScenarioInput, max_credit_krw: int) -> int:
    low = 0
    high = max(values.purchase_price_krw * 2, 2_000_000_000)
    while _required_credit_for_price(values, high) <= max_credit_krw and high < 20_000_000_000:
        high *= 2
    while low < high:
        middle = (low + high + 1) // 2
        if _required_credit_for_price(values, middle) <= max_credit_krw:
            low = middle
        else:
            high = middle - 1
    return low


def calculate_financing_scenario(values: FinancingScenarioInput) -> dict[str, object]:
    numeric_values = [
        values.purchase_price_krw,
        values.cash_krw,
        values.lease_deposit_krw,
        values.lease_loan_krw,
        values.combined_gross_income_krw,
        values.borrower_gross_income_krw,
        values.spouse_gross_income_krw,
        values.mortgage_amount_krw,
        values.collateral_value_krw,
        values.mortgage_policy_cap_krw,
        values.family_loan_amount_krw,
        values.legal_cost_krw,
        values.room_deduction_amount_krw,
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
    if not 0 <= values.ltv_ratio_percent <= 100:
        raise ValueError("LTV ratio must be between 0 and 100")
    if values.credit_income_limit_ratio_percent < 0:
        raise ValueError("credit income limit ratio cannot be negative")
    if values.borrower_credit_income_limit_ratio_percent < 0:
        raise ValueError("borrower credit income limit ratio cannot be negative")
    if values.spouse_credit_income_limit_ratio_percent < 0:
        raise ValueError("spouse credit income limit ratio cannot be negative")
    if not 0 <= values.borrower_mortgage_share_percent <= 100:
        raise ValueError("borrower mortgage share must be between 0 and 100")
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
    collateral_value, ltv_limit, mortgage_policy_cap, effective_mortgage = _mortgage_limits(
        values, values.purchase_price_krw
    )
    mortgage_limit = min(ltv_limit, mortgage_policy_cap)
    room_deduction = values.room_deduction_amount_krw if values.room_deduction_enabled else 0
    adjusted_mortgage_limit = max(0, mortgage_limit - room_deduction)
    mortgage_limit_excess = max(0, values.mortgage_amount_krw - mortgage_limit)
    adjusted_mortgage_limit_excess = max(0, values.mortgage_amount_krw - adjusted_mortgage_limit)
    actual_ltv = effective_mortgage / collateral_value * 100 if collateral_value else 0
    non_credit_funds = available_cash + effective_mortgage + values.family_loan_amount_krw
    required_credit_loan = max(0, cash_required_at_closing - non_credit_funds)
    cash_surplus = max(0, non_credit_funds - cash_required_at_closing)

    mortgage_months = values.mortgage_term_years * 12
    credit_months = values.credit_term_years * 12
    mortgage_payment = annuity_payment(
        effective_mortgage, values.mortgage_rate_percent, mortgage_months
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
        effective_mortgage, mortgage_stress_rate, mortgage_months
    )
    credit_stress_payment = annuity_payment(required_credit_loan, credit_stress_rate, credit_months)
    contract_dsr = (mortgage_payment + credit_payment) * 12 / values.combined_gross_income_krw * 100
    stress_dsr = (
        (mortgage_stress_payment + credit_stress_payment)
        * 12
        / values.combined_gross_income_krw
        * 100
    )
    dsr_limit_exceeded = stress_dsr > values.dsr_limit_percent
    monthly_dsr_capacity = values.combined_gross_income_krw * values.dsr_limit_percent / 100 / 12
    monthly_credit_capacity = max(0, monthly_dsr_capacity - mortgage_stress_payment)
    base_credit_capacity = principal_for_annuity_payment(
        monthly_credit_capacity, values.credit_rate_percent, credit_months
    )
    stressed_credit_capacity = principal_for_annuity_payment(
        monthly_credit_capacity,
        values.credit_rate_percent + values.credit_stress_rate_percent,
        credit_months,
    )
    threshold_supported = (
        annuity_payment(
            values.credit_stress_threshold_krw,
            values.credit_rate_percent,
            credit_months,
        )
        <= monthly_credit_capacity
    )
    max_credit_loan = max(
        min(base_credit_capacity, values.credit_stress_threshold_krw),
        values.credit_stress_threshold_krw if threshold_supported else 0,
        stressed_credit_capacity
        if stressed_credit_capacity > values.credit_stress_threshold_krw
        else 0,
    )
    # Keep a small won-level margin so floating-point inversion never lands just above the limit.
    max_credit_loan_krw = max(0, int(max_credit_loan) - 1_000)
    rough_credit_income_limit = round(
        values.combined_gross_income_krw
        * values.credit_income_limit_ratio_percent
        / 100
    )
    rough_credit_loan_max = min(rough_credit_income_limit, max_credit_loan_krw)
    credit_loan_excess = max(0, required_credit_loan - max_credit_loan_krw)
    max_purchase_price = _maximum_purchase_price(values, max_credit_loan_krw)
    purchase_price_excess = max(0, values.purchase_price_krw - max_purchase_price)
    annual_dsr_capacity = values.combined_gross_income_krw * values.dsr_limit_percent / 100
    annual_stress_debt_service = (mortgage_stress_payment + credit_stress_payment) * 12
    required_income_by_dsr = (
        annual_stress_debt_service / (values.dsr_limit_percent / 100)
        if values.dsr_limit_percent > 0
        else 0
    )
    income_shortfall_by_dsr = max(0, required_income_by_dsr - values.combined_gross_income_krw)

    mortgage_payment_capacity = max(0, monthly_dsr_capacity - credit_stress_payment)
    max_mortgage_by_dsr = principal_for_annuity_payment(
        mortgage_payment_capacity, mortgage_stress_rate, mortgage_months
    )
    max_mortgage_by_dsr_krw = max(0, int(max_mortgage_by_dsr) - 1_000)
    mortgage_excess_by_dsr = max(0, effective_mortgage - max_mortgage_by_dsr_krw)

    minimum_mortgage_term_years_by_dsr: int | None = None
    for candidate_years in range(values.mortgage_term_years, 51):
        candidate_payment = annuity_payment(
            effective_mortgage, mortgage_stress_rate, candidate_years * 12
        )
        candidate_dsr = (
            (candidate_payment + credit_stress_payment)
            * 12
            / values.combined_gross_income_krw
            * 100
        )
        if candidate_dsr <= values.dsr_limit_percent:
            minimum_mortgage_term_years_by_dsr = candidate_years
            break

    max_mortgage_stress_ratio_by_dsr: float | None = None
    dsr_with_no_mortgage_stress = (
        (
            annuity_payment(
                effective_mortgage, values.mortgage_rate_percent, mortgage_months
            )
            + credit_stress_payment
        )
        * 12
        / values.combined_gross_income_krw
        * 100
    )
    if dsr_with_no_mortgage_stress <= values.dsr_limit_percent:
        low_ratio = 0.0
        high_ratio = 100.0
        for _ in range(40):
            middle_ratio = (low_ratio + high_ratio) / 2
            candidate_rate = values.mortgage_rate_percent + (
                values.mortgage_stress_rate_percent * middle_ratio / 100
            )
            candidate_payment = annuity_payment(
                effective_mortgage, candidate_rate, mortgage_months
            )
            candidate_dsr = (
                (candidate_payment + credit_stress_payment)
                * 12
                / values.combined_gross_income_krw
                * 100
            )
            if candidate_dsr <= values.dsr_limit_percent:
                low_ratio = middle_ratio
            else:
                high_ratio = middle_ratio
        max_mortgage_stress_ratio_by_dsr = low_ratio

    borrower_mortgage_share = values.borrower_mortgage_share_percent / 100
    spouse_mortgage_share = 1 - borrower_mortgage_share
    borrower_allocated_mortgage_payment = mortgage_stress_payment * borrower_mortgage_share
    spouse_allocated_mortgage_payment = mortgage_stress_payment * spouse_mortgage_share
    borrower_credit_capacity_by_dsr = _individual_credit_capacity(
        income_krw=values.borrower_gross_income_krw,
        allocated_mortgage_stress_payment_krw=borrower_allocated_mortgage_payment,
        values=values,
        credit_months=credit_months,
    )
    spouse_credit_capacity_by_dsr = _individual_credit_capacity(
        income_krw=values.spouse_gross_income_krw,
        allocated_mortgage_stress_payment_krw=spouse_allocated_mortgage_payment,
        values=values,
        credit_months=credit_months,
    )
    borrower_credit_capacity_by_income = _income_limited_credit_capacity(
        values.borrower_gross_income_krw, values.borrower_credit_income_limit_ratio_percent
    )
    spouse_credit_capacity_by_income = _income_limited_credit_capacity(
        values.spouse_gross_income_krw, values.spouse_credit_income_limit_ratio_percent
    )
    borrower_credit_capacity = min(
        borrower_credit_capacity_by_dsr, borrower_credit_capacity_by_income
    )
    spouse_credit_capacity = min(spouse_credit_capacity_by_dsr, spouse_credit_capacity_by_income)
    borrower_credit_capacity_bands = {
        "conservative_80pct_krw": _income_limited_credit_capacity(
            values.borrower_gross_income_krw, 80
        ),
        "base_100pct_krw": _income_limited_credit_capacity(values.borrower_gross_income_krw, 100),
        "aggressive_120pct_krw": _income_limited_credit_capacity(
            values.borrower_gross_income_krw, 120
        ),
    }
    spouse_credit_capacity_bands = {
        "conservative_60pct_krw": _income_limited_credit_capacity(
            values.spouse_gross_income_krw, 60
        ),
        "base_80pct_krw": _income_limited_credit_capacity(values.spouse_gross_income_krw, 80),
        "aggressive_100pct_krw": _income_limited_credit_capacity(
            values.spouse_gross_income_krw, 100
        ),
    }
    spouse_suggested_credit = min(required_credit_loan, spouse_credit_capacity)
    borrower_suggested_credit = min(
        max(0, required_credit_loan - spouse_suggested_credit), borrower_credit_capacity
    )
    individual_credit_shortfall = max(
        0, required_credit_loan - spouse_suggested_credit - borrower_suggested_credit
    )
    borrower_stress_dsr = (
        (
            borrower_allocated_mortgage_payment
            + annuity_payment(
                borrower_suggested_credit,
                values.credit_rate_percent
                + (
                    values.credit_stress_rate_percent
                    if borrower_suggested_credit > values.credit_stress_threshold_krw
                    else 0
                ),
                credit_months,
            )
        )
        * 12
        / values.borrower_gross_income_krw
        * 100
        if values.borrower_gross_income_krw > 0
        else 0
    )
    spouse_stress_dsr = (
        (
            spouse_allocated_mortgage_payment
            + annuity_payment(
                spouse_suggested_credit,
                values.credit_rate_percent
                + (
                    values.credit_stress_rate_percent
                    if spouse_suggested_credit > values.credit_stress_threshold_krw
                    else 0
                ),
                credit_months,
            )
        )
        * 12
        / values.spouse_gross_income_krw
        * 100
        if values.spouse_gross_income_krw > 0
        else 0
    )

    dsr_recommendations: list[str] = []
    if dsr_limit_exceeded:
        if credit_loan_excess > 0:
            dsr_recommendations.append(
                f"신용대출을 {credit_loan_excess:,.0f}원 줄이고 같은 금액을 현금·가격인하로 대체"
            )
        if income_shortfall_by_dsr > 0:
            dsr_recommendations.append(
                f"은행 인정 연소득을 최소 {required_income_by_dsr:,.0f}원 확보"
                f"(현재 대비 {income_shortfall_by_dsr:,.0f}원 추가)"
            )
        if (
            minimum_mortgage_term_years_by_dsr is not None
            and minimum_mortgage_term_years_by_dsr > values.mortgage_term_years
        ):
            dsr_recommendations.append(
                f"은행이 허용하면 주담대 만기를 최소 "
                f"{minimum_mortgage_term_years_by_dsr}년으로 연장"
            )
        if (
            max_mortgage_stress_ratio_by_dsr is not None
            and max_mortgage_stress_ratio_by_dsr < values.mortgage_stress_ratio_percent
        ):
            dsr_recommendations.append(
                "장기 고정형·주기형 상품으로 주담대 스트레스 반영률을 "
                f"{max_mortgage_stress_ratio_by_dsr:.1f}% 이하로 낮출 수 있는지 확인"
            )
        if mortgage_excess_by_dsr > 0:
            dsr_recommendations.append(
                f"주담대 중 {mortgage_excess_by_dsr:,.0f}원을 추가 현금으로 대체하면 "
                f"DSR 기준 주담대 {max_mortgage_by_dsr_krw:,.0f}원 이하"
            )
    else:
        dsr_margin = max(0, annual_dsr_capacity - annual_stress_debt_service)
        dsr_recommendations.append(
            f"현재 입력은 DSR {values.dsr_limit_percent:g}% 이하이며 연간 원리금 여유는 "
            f"약 {dsr_margin:,.0f}원"
        )
    monthly_debt_payment = mortgage_payment + credit_payment + family_monthly_payment
    monthly_outflow_during_card_installment = (
        monthly_debt_payment + family_principal_reserve + card_payment
    )
    total_required = values.purchase_price_krw + total_transaction_cost

    warnings: list[str] = []
    if adjusted_mortgage_limit_excess > 0:
        warnings.append(
            f"희망 주담대가 LTV·정책·방공제 반영 한도를 약 {adjusted_mortgage_limit_excess:,}원 초과해 "
            f"실제 자금에는 {effective_mortgage:,}원만 반영했습니다."
        )
    if values.room_deduction_enabled and room_deduction > 0:
        warnings.append(
            f"방공제 {room_deduction:,}원을 반영했습니다. MCI/MCG 가능 은행이면 이 차감이 없어질 수 있습니다."
        )
    if dsr_limit_exceeded:
        warnings.append(
            f"스트레스 DSR이 설정 한도 {values.dsr_limit_percent:g}%를 초과했습니다. "
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
    if credit_loan_excess > 0:
        warnings.append(
            f"DSR 한도에 맞추려면 신용대출을 약 {credit_loan_excess:,}원 줄여야 합니다. "
            "같은 금액의 현금을 추가하거나 매매가를 낮춰야 합니다."
        )
    if individual_credit_shortfall > 0:
        warnings.append(
            f"개인별 DSR 기준으로는 필요 신용대출 중 약 {individual_credit_shortfall:,}원이 부족합니다. "
            "주담대 분담, 현금 추가, 카드납부, 부모 차용 확대를 다시 조정해야 합니다."
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
    warnings.append(
        "신용대출 러프 MAX는 부부합산소득을 계획용으로 단순 적용한 값입니다. "
        "실제 한도는 배우자별 소득·기존 신용대출·신용점수·은행 내규로 각각 심사됩니다."
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
        "collateral_value_krw": collateral_value,
        "ltv_ratio_percent": values.ltv_ratio_percent,
        "ltv_limit_krw": ltv_limit,
        "mortgage_policy_cap_krw": mortgage_policy_cap,
        "mortgage_limit_krw": mortgage_limit,
        "room_deduction_enabled": values.room_deduction_enabled,
        "room_deduction_amount_krw": values.room_deduction_amount_krw,
        "room_deduction_applied_krw": room_deduction,
        "adjusted_mortgage_limit_krw": adjusted_mortgage_limit,
        "requested_mortgage_krw": values.mortgage_amount_krw,
        "effective_mortgage_krw": effective_mortgage,
        "mortgage_limit_excess_krw": adjusted_mortgage_limit_excess,
        "actual_ltv_percent": round(actual_ltv, 1),
        "mortgage_limit_exceeded": adjusted_mortgage_limit_excess > 0,
        "required_credit_loan_krw": round(required_credit_loan),
        "max_credit_loan_by_dsr_krw": max_credit_loan_krw,
        "rough_credit_income_limit_krw": rough_credit_income_limit,
        "rough_credit_loan_max_krw": rough_credit_loan_max,
        "credit_income_limit_ratio_percent": values.credit_income_limit_ratio_percent,
        "credit_loan_excess_krw": round(credit_loan_excess),
        "max_purchase_price_by_dsr_krw": round(max_purchase_price),
        "purchase_price_excess_krw": round(purchase_price_excess),
        "annual_dsr_capacity_krw": round(annual_dsr_capacity),
        "annual_stress_debt_service_krw": round(annual_stress_debt_service),
        "required_income_by_dsr_krw": round(required_income_by_dsr),
        "income_shortfall_by_dsr_krw": round(income_shortfall_by_dsr),
        "max_mortgage_by_dsr_krw": max_mortgage_by_dsr_krw,
        "mortgage_excess_by_dsr_krw": round(mortgage_excess_by_dsr),
        "minimum_mortgage_term_years_by_dsr": minimum_mortgage_term_years_by_dsr,
        "max_mortgage_stress_ratio_by_dsr_percent": (
            round(max_mortgage_stress_ratio_by_dsr, 1)
            if max_mortgage_stress_ratio_by_dsr is not None
            else None
        ),
        "dsr_recommendations": dsr_recommendations,
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
        "dsr_limit_exceeded": dsr_limit_exceeded,
        "mortgage_stress_rate_percent": round(mortgage_stress_rate, 2),
        "credit_stress_rate_percent": round(credit_stress_rate, 2),
        "credit_stress_applied": credit_stress_applied,
        "dsr_warning_percent": values.dsr_warning_percent,
        "dsr_limit_percent": values.dsr_limit_percent,
        "combined_monthly_income_krw": round(combined_monthly_income(values)),
        "borrower_gross_income_krw": values.borrower_gross_income_krw,
        "spouse_gross_income_krw": values.spouse_gross_income_krw,
        "borrower_mortgage_share_percent": values.borrower_mortgage_share_percent,
        "borrower_credit_capacity_krw": borrower_credit_capacity,
        "spouse_credit_capacity_krw": spouse_credit_capacity,
        "borrower_credit_capacity_by_dsr_krw": borrower_credit_capacity_by_dsr,
        "spouse_credit_capacity_by_dsr_krw": spouse_credit_capacity_by_dsr,
        "borrower_credit_capacity_by_income_krw": borrower_credit_capacity_by_income,
        "spouse_credit_capacity_by_income_krw": spouse_credit_capacity_by_income,
        "borrower_credit_income_limit_ratio_percent": values.borrower_credit_income_limit_ratio_percent,
        "spouse_credit_income_limit_ratio_percent": values.spouse_credit_income_limit_ratio_percent,
        "borrower_credit_capacity_bands": borrower_credit_capacity_bands,
        "spouse_credit_capacity_bands": spouse_credit_capacity_bands,
        "borrower_suggested_credit_krw": round(borrower_suggested_credit),
        "spouse_suggested_credit_krw": round(spouse_suggested_credit),
        "individual_credit_shortfall_krw": round(individual_credit_shortfall),
        "borrower_stress_dsr_percent": round(borrower_stress_dsr, 1),
        "spouse_stress_dsr_percent": round(spouse_stress_dsr, 1),
        "warnings": warnings,
        "closing_case_summaries": [
            _closing_case_summary(
                values,
                label="MCI/MCG 가능 · 취득세 현금",
                room_deduction_enabled=False,
                card_acquisition_tax=False,
            ),
            _closing_case_summary(
                values,
                label="MCI/MCG 가능 · 취득세 카드",
                room_deduction_enabled=False,
                card_acquisition_tax=True,
            ),
            _closing_case_summary(
                values,
                label="방공제 적용 · 취득세 현금",
                room_deduction_enabled=True,
                card_acquisition_tax=False,
            ),
            _closing_case_summary(
                values,
                label="방공제 적용 · 취득세 카드",
                room_deduction_enabled=True,
                card_acquisition_tax=True,
            ),
        ],
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
