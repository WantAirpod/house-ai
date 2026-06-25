from __future__ import annotations

from dataclasses import dataclass


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
