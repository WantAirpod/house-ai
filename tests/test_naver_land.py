from home_decision_ai.collectors.naver_land import parse_korean_price_to_krw
from home_decision_ai.collectors.naver_land import extract_complex_number_from_url
from home_decision_ai.collectors.naver_land import parse_observation_response
from home_decision_ai.collectors.naver_land import parse_pyeong_list_response


def test_extract_complex_number_from_url() -> None:
    assert extract_complex_number_from_url("https://fin.land.naver.com/complexes/12345") == "12345"
    assert (
        extract_complex_number_from_url("https://fin.land.naver.com/map?complexNumber=67890")
        == "67890"
    )


def test_parse_korean_price_to_krw() -> None:
    assert parse_korean_price_to_krw("10억 5,000") == 1_050_000_000
    assert parse_korean_price_to_krw(105000) == 1_050_000_000


def test_parse_pyeong_list_response() -> None:
    data = {
        "result": {
            "pyeongList": [
                {
                    "pyeongTypeNumber": "1",
                    "pyeongName": "34평",
                    "exclusiveArea": "84.9",
                    "supplyArea": "112.1",
                }
            ]
        }
    }

    result = parse_pyeong_list_response(data)

    assert len(result) == 1
    assert result[0].pyeong_type_number == "1"
    assert result[0].exclusive_area_m2 == 84.9


def test_parse_observation_response() -> None:
    data = {
        "result": {
            "minPrice": "9억 8,000",
            "maxPrice": "10억 5,000",
            "articleCount": 7,
        }
    }

    result = parse_observation_response(
        data,
        complex_number="12345",
        pyeong_type_number="1",
        real_estate_type="APT",
        trade_type="A1",
    )

    assert result.lowest_asking_price_krw == 980_000_000
    assert result.highest_asking_price_krw == 1_050_000_000
    assert result.inventory_count == 7
