from pathlib import Path

from scripts.review_rtms_candidates import exclusion_reasons, load_complex_metadata


def test_exclusion_reasons_for_small_officetel() -> None:
    reasons = exclusion_reasons(
        {"household_count": 180, "property_type": "officetel_apartment"},
        max_excluded_household_count=200,
        excluded_property_types={"officetel_apartment"},
    )

    assert "200세대 이하" in reasons
    assert "제외 주거유형: officetel_apartment" in reasons


def test_exclusion_override() -> None:
    reasons = exclusion_reasons(
        {
            "household_count": 250,
            "property_type": "officetel_apartment",
            "exclude_override": True,
        },
        max_excluded_household_count=200,
        excluded_property_types={"officetel_apartment"},
    )

    assert reasons == []


def test_large_mixed_use_apartment_is_not_excluded_by_scale() -> None:
    reasons = exclusion_reasons(
        {"household_count": 550, "property_type": "mixed_use_apartment"},
        max_excluded_household_count=200,
        excluded_property_types={"officetel_apartment"},
    )

    assert reasons == []


def test_load_complex_metadata() -> None:
    metadata = load_complex_metadata(Path("data/manual/complex_metadata.example.csv"))

    assert metadata[("용인 수지", "예시오피스텔아파트")]["household_count"] == 180
    assert metadata[("용인 수지", "예시오피스텔아파트")]["property_type"] == "officetel_apartment"
