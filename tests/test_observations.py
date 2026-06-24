from datetime import date

import pytest
from pydantic import ValidationError

from home_decision_ai.models.observations import MarketObservationInput, VerificationStatus


def test_verified_observation_can_drive_strong_opinion() -> None:
    observation = MarketObservationInput(
        observed_at=date(2026, 6, 24),
        complex_name="성복역 롯데캐슬 골드타운",
        region="용인 수지",
        area_m2=84,
        transaction_price_krw=1_000_000_000,
        source_id="molit_rtms",
        source_url="https://rt.molit.go.kr/",
        verification_status=VerificationStatus.VERIFIED,
    )

    assert observation.can_drive_strong_opinion is True


def test_unverified_empty_observation_requires_memo() -> None:
    with pytest.raises(ValidationError):
        MarketObservationInput(
            observed_at=date(2026, 6, 24),
            complex_name="e편한세상 수지",
            region="용인 수지",
            source_id="molit_rtms",
            source_url="https://rt.molit.go.kr/",
            verification_status=VerificationStatus.NEEDS_VERIFICATION,
        )
