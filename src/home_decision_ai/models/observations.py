from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    MANUALLY_CHECKED = "manually_checked"
    NEEDS_VERIFICATION = "needs_verification"


class MarketObservationInput(BaseModel):
    """One observed market datapoint with explicit provenance."""

    observed_at: date
    complex_name: str = Field(min_length=1)
    region: str = Field(min_length=1)
    area_m2: float | None = None
    transaction_price_krw: int | None = None
    asking_price_krw: int | None = None
    inventory_count: int | None = None
    source_id: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    verification_status: VerificationStatus
    memo: str | None = None

    @model_validator(mode="after")
    def require_value_or_explanation(self) -> MarketObservationInput:
        has_market_value = any(
            value is not None
            for value in (
                self.transaction_price_krw,
                self.asking_price_krw,
                self.inventory_count,
            )
        )
        if not has_market_value and not self.memo:
            msg = "Observation without market values must include a memo."
            raise ValueError(msg)
        return self

    @property
    def can_drive_strong_opinion(self) -> bool:
        return self.verification_status in {
            VerificationStatus.VERIFIED,
            VerificationStatus.MANUALLY_CHECKED,
        }
