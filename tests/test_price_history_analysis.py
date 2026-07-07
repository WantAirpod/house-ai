from datetime import date

from scripts.publish_notion_top10 import percentile, summarize_price_history, trailing_months


def test_trailing_months_returns_exact_count() -> None:
    months = trailing_months(date(2026, 6, 27), 60)

    assert len(months) == 60
    assert months[0] == "202107"
    assert months[-1] == "202606"


def test_percentile_interpolates_values() -> None:
    assert percentile([100, 200, 300, 400], 0.25) == 175
    assert percentile([100, 200, 300, 400], 0.50) == 250


def test_price_history_uses_recent_12_month_distribution() -> None:
    trades = [
        {"deal_ym": "202501", "price_krw": 700_000_000},
        {"deal_ym": "202601", "price_krw": 900_000_000},
        {"deal_ym": "202602", "price_krw": 950_000_000},
        {"deal_ym": "202603", "price_krw": 1_000_000_000},
    ]

    result = summarize_price_history(
        trades,
        recent_months={"202601", "202602", "202603"},
    )

    assert result["trade_count"] == 4
    assert result["recent_12m_count"] == 3
    assert result["fair_price_low_krw"] == 925_000_000
    assert result["fair_price_high_krw"] == 950_000_000
