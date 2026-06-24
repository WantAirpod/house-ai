from home_decision_ai.collectors.bok_ecos import latest_base_rate, parse_base_rate_rows


def test_parse_base_rate_rows() -> None:
    data = {
        "StatisticSearch": {
            "row": [
                {"TIME": "20260621", "DATA_VALUE": "2.50"},
                {"TIME": "20260622", "DATA_VALUE": "2.50"},
            ]
        }
    }

    observations = parse_base_rate_rows(data)

    assert len(observations) == 2
    assert observations[0].observed_date == "20260621"
    assert observations[0].value_percent == 2.5


def test_latest_base_rate() -> None:
    observations = parse_base_rate_rows(
        {
            "StatisticSearch": {
                "row": [
                    {"TIME": "20260621", "DATA_VALUE": "2.50"},
                    {"TIME": "20260622", "DATA_VALUE": "2.75"},
                ]
            }
        }
    )

    latest = latest_base_rate(observations)

    assert latest is not None
    assert latest.observed_date == "20260622"
    assert latest.value_percent == 2.75
