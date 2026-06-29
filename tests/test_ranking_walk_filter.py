from scripts.publish_notion_top10 import (
    latest_trade_price_is_eligible,
    new_build_is_eligible,
    station_walk_is_eligible,
)


def test_verified_walk_under_23_minutes_is_eligible() -> None:
    assert station_walk_is_eligible({"station_walk_minutes": 22}, require_verified=True)


def test_verified_walk_at_or_above_23_minutes_is_excluded() -> None:
    assert not station_walk_is_eligible({"station_walk_minutes": 23}, require_verified=True)
    assert not station_walk_is_eligible({"station_walk_minutes": 25}, require_verified=True)


def test_unknown_walk_is_excluded_from_verified_rankings() -> None:
    assert not station_walk_is_eligible({"station_walk_minutes": None}, require_verified=True)


def test_unknown_walk_is_allowed_only_while_building_enrichment_pool() -> None:
    assert station_walk_is_eligible({"station_walk_minutes": None}, require_verified=False)


def test_latest_trade_price_must_be_between_900m_and_1050m() -> None:
    assert not latest_trade_price_is_eligible({"latest_price_krw": 899_999_999})
    assert latest_trade_price_is_eligible({"latest_price_krw": 900_000_000})
    assert latest_trade_price_is_eligible({"latest_price_krw": 1_050_000_000})
    assert not latest_trade_price_is_eligible({"latest_price_krw": 1_050_000_001})


def test_new_build_is_limited_to_12_years() -> None:
    assert new_build_is_eligible({"age_years": 12})
    assert not new_build_is_eligible({"age_years": 13})
    assert not new_build_is_eligible({"age_years": None})
