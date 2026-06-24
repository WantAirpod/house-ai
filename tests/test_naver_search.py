from home_decision_ai.collectors.naver_search import clean_html_text, parse_search_results


def test_clean_html_text() -> None:
    assert clean_html_text("<b>용인</b> 수지 &amp; 기흥") == "용인 수지 & 기흥"


def test_parse_search_results() -> None:
    data = {
        "items": [
            {
                "title": "<b>수지</b> 아파트",
                "originallink": "https://example.com/article",
                "description": "지역 <b>뉴스</b>",
                "pubDate": "Wed, 24 Jun 2026 10:00:00 +0900",
            }
        ]
    }

    results = parse_search_results(data)

    assert len(results) == 1
    assert results[0].title == "수지 아파트"
    assert results[0].description == "지역 뉴스"
    assert results[0].link == "https://example.com/article"
