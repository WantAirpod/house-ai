from fastapi.testclient import TestClient

from home_decision_ai.api.app import create_app


def test_health() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_financing_calculator_page() -> None:
    client = TestClient(create_app())

    response = client.get("/financing-calculator")

    assert response.status_code == 200
    assert "자금·대출 계산기" in response.text
    assert "생애최초 취득세 감면 가정" in response.text
    assert "LTV 한도율" in response.text
    assert "정책상 주담대 상한" in response.text
    assert "빠른 입력 · 직접 수정 가능" in response.text
    assert "DSR 초과 시 매매가 자동 조정" not in response.text
    assert "DSR 40% 이하 추천" in response.text


def test_dashboard_is_a_clean_navigation_hub() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "의사결정 홈" in response.text
    assert "후보 단지" in response.text
    assert "관심 지역" not in response.text


def test_research_page_keeps_region_and_watchlist_details() -> None:
    client = TestClient(create_app())

    response = client.get("/research")

    assert response.status_code == 200
    assert "후보 단지 리서치" in response.text
    assert "관심 지역" in response.text


def test_financing_plan_page() -> None:
    client = TestClient(create_app())

    response = client.get("/financing-plan")

    assert response.status_code == 200
    assert "월 741만원의 원인" in response.text
    assert "추천 자금 플랜" in response.text


def test_financing_calculation_api_moves_card_costs_out_of_credit() -> None:
    client = TestClient(create_app())

    response = client.post("/api/financing/calculate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["required_credit_loan_krw"] == 40_000_000
    assert result["card_payment_total_krw"] == 40_115_000


def test_financing_api_keeps_arbitrary_purchase_price_and_recommends_dsr_actions() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/financing/calculate",
        json={"purchase_price_krw": 1_137_000_000, "card_payment_ratio_percent": 0},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total_required_krw"] > 1_137_000_000
    assert result["dsr_limit_exceeded"] is True
    assert result["required_income_by_dsr_krw"] > 150_000_000
    assert result["dsr_recommendations"]
