from __future__ import annotations

from dataclasses import dataclass

from home_decision_ai.integrations.openai_responses import create_text_response


@dataclass(frozen=True)
class DecisionFacts:
    budget_upper_krw: int
    base_rate_date: str
    base_rate_percent: float
    transaction_data_status: str
    asking_price_status: str
    current_focus: str


def build_ai_opinion_prompt(facts: DecisionFacts) -> str:
    """Build a strict prompt that forbids unsupported price claims."""
    return f"""
당신은 실거주 아파트 매수를 돕는 부동산 데이터 애널리스트다.

반드시 아래 사실만 근거로 사용하라.
추정 실거래가, 추정 호가, 출처 없는 시세, 단정적 매수 추천은 금지한다.
데이터가 부족하면 '판단 보류'라고 써라.

확인된 사실:
- 예산 상한: {facts.budget_upper_krw:,}원
- 한국은행 기준금리: {facts.base_rate_date} 기준 연 {facts.base_rate_percent}%
- 실거래 데이터 상태: {facts.transaction_data_status}
- 호가/매물 데이터 상태: {facts.asking_price_status}
- 현재 작업 초점: {facts.current_focus}

출력 형식:
1. 오늘의 결론: 한 문장
2. 매수 판단: 매수/보류/검증필요 중 하나
3. 이유: 3개 bullet
4. 다음 액션: 3개 bullet
""".strip()


def generate_ai_opinion(
    *,
    api_key: str,
    model: str,
    facts: DecisionFacts,
) -> str:
    response = create_text_response(
        api_key=api_key,
        model=model,
        input_text=build_ai_opinion_prompt(facts),
        max_output_tokens=700,
    )
    return response.output_text.strip()
