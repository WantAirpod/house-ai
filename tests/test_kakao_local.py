from home_decision_ai.collectors.kakao_local import parse_places


def test_parse_places() -> None:
    data = {
        "documents": [
            {
                "place_name": "NAVER그린팩토리",
                "address_name": "경기 성남시 분당구 정자동 178-1",
                "road_address_name": "경기 성남시 분당구 불정로 6",
                "x": "127.105017634512",
                "y": "37.3595305941092",
                "phone": "",
                "place_url": "https://place.map.kakao.com/123",
            }
        ]
    }

    places = parse_places(data)

    assert len(places) == 1
    assert places[0].place_name == "NAVER그린팩토리"
    assert places[0].longitude == 127.105017634512
    assert places[0].latitude == 37.3595305941092
