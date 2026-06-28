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


def test_financing_calculation_api_moves_card_costs_out_of_credit() -> None:
    client = TestClient(create_app())

    response = client.post("/api/financing/calculate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["required_credit_loan_krw"] == 40_000_000
    assert result["card_payment_total_krw"] == 40_115_000
