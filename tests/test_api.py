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
