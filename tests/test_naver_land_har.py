import json
from pathlib import Path

from home_decision_ai.collectors.naver_land import parse_asking_price_har


def test_parse_asking_price_har(tmp_path: Path) -> None:
    har = {
        "log": {
            "entries": [
                {
                    "request": {
                        "url": (
                            "https://fin.land.naver.com/front-api/v1/complex/askingPrice"
                            "?complexNumber=123&pyeongTypeNumber=4&realEstateType=APT&tradeType=A1"
                        )
                    },
                    "response": {
                        "content": {
                            "text": json.dumps(
                                {
                                    "result": {
                                        "minPrice": "9억 5,000",
                                        "maxPrice": "10억",
                                        "articleCount": 3,
                                    }
                                }
                            )
                        }
                    },
                }
            ]
        }
    }
    path = tmp_path / "naver.har"
    path.write_text(json.dumps(har), encoding="utf-8")

    observations = parse_asking_price_har(str(path))

    assert len(observations) == 1
    assert observations[0].complex_number == "123"
    assert observations[0].pyeong_type_number == "4"
    assert observations[0].lowest_asking_price_krw == 950_000_000
    assert observations[0].inventory_count == 3
