from home_decision_ai.services.ai_opinion import DecisionFacts, build_ai_opinion_prompt


def test_build_ai_opinion_prompt_includes_data_guardrails() -> None:
    prompt = build_ai_opinion_prompt(
        DecisionFacts(
            budget_upper_krw=1_050_000_000,
            base_rate_date="2026-06-22",
            base_rate_percent=2.5,
            transaction_data_status="미검증",
            asking_price_status="미검증",
            current_focus="가격 검증",
        )
    )

    assert "추정 실거래가" in prompt
    assert "판단 보류" in prompt
    assert "1,050,000,000원" in prompt
