from __future__ import annotations

from pathlib import Path

from home_decision_ai.services.ai_opinion import DecisionFacts, generate_ai_opinion


def read_env_value(name: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1]
    return None


def main() -> None:
    api_key = read_env_value("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required.")

    model = read_env_value("OPENAI_MODEL") or "gpt-4.1-mini"
    opinion = generate_ai_opinion(
        api_key=api_key,
        model=model,
        facts=DecisionFacts(
            budget_upper_krw=1_050_000_000,
            base_rate_date="2026-06-22",
            base_rate_percent=2.5,
            transaction_data_status="국토부 API 키가 아직 401 Unauthorized 상태라 후보별 실거래가 미검증",
            asking_price_status="네이버부동산 API rate limit으로 자동 호가 미검증",
            current_focus="가격 검증 Queue의 후보를 실거래/호가 기준으로 재분류",
        ),
    )
    print(opinion)


if __name__ == "__main__":
    main()
