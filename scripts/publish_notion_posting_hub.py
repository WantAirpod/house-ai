# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

from notion_posting_hub import ensure_posting_hub, move_page
from publish_notion_top10 import Notion, callout, heading, paragraph, read_env, table

POST_TITLES = {
    "기흥역센트럴푸르지오 심층 분석",
    "TOP10 후보 상세 분석",
    "갈아타기 전략 | 기흥역 84㎡에서 성복역 84㎡로",
    "입지 선택 결론 | 기흥역 역세권 vs 수지 준역세권",
    "정책 분석 | 2026 기흥 토허·규제지역 지정",
    "7/2 저녁임장",
    "2021 상승과 2022 하락장 | 원인·충격·재연 조건",
    "신분당선 밖의 답 | 구성·보정이 의외의 1순위인 이유",
    "행원마을동아솔레시티 84㎡ | 실거주·가격·커뮤니티 심층 분석",
    "기흥센트럴푸르지오 202동 2406호 | 계약할 것인가",
    "2026 하반기 매수 전략 | 9.65억 거래 불발 이후",
    "2026 하반기 아파트 가격 전망 | 기흥·수지",
    "싸게 사서 비싸게 판다 | 부동산은 무엇이 다른가",
    "기흥 호가 급등 이후 | 새 후보 4곳 비교",
    "용인 핵심 입지 점수 | 수지·구성보정·기흥",
    "지금 전세 매물이 씨가 마르는 이유",
}

CATEGORIES = {
    "시장·정책": [
        "지금 전세 매물이 씨가 마르는 이유",
        "2026 하반기 아파트 가격 전망 | 기흥·수지",
        "2026 하반기 매수 전략 | 9.65억 거래 불발 이후",
        "2021 상승과 2022 하락장 | 원인·충격·재연 조건",
        "정책 분석 | 2026 기흥 토허·규제지역 지정",
    ],
    "입지·전략": [
        "용인 핵심 입지 점수 | 수지·구성보정·기흥",
        "싸게 사서 비싸게 판다 | 부동산은 무엇이 다른가",
        "신분당선 밖의 답 | 구성·보정이 의외의 1순위인 이유",
        "입지 선택 결론 | 기흥역 역세권 vs 수지 준역세권",
        "갈아타기 전략 | 기흥역 84㎡에서 성복역 84㎡로",
    ],
    "단지·임장": [
        "기흥 호가 급등 이후 | 새 후보 4곳 비교",
        "기흥센트럴푸르지오 202동 2406호 | 계약할 것인가",
        "행원마을동아솔레시티 84㎡ | 실거주·가격·커뮤니티 심층 분석",
        "7/2 저녁임장",
        "기흥역센트럴푸르지오 심층 분석",
        "TOP10 후보 상세 분석",
    ],
}

SUMMARIES = {
    "지금 전세 매물이 씨가 마르는 이유": "재계약·매수 지연·토허·월세 전환이 만든 전세 공급 감소",
    "용인 핵심 입지 점수 | 수지·구성보정·기흥": "일반 수요 기준 3개 권역과 7개 역의 입지 점수",
    "기흥 호가 급등 이후 | 새 후보 4곳 비교": "성복·만현·보정 4개 단지의 5년 실거래와 최종 순위",
    "싸게 사서 비싸게 판다 | 부동산은 무엇이 다른가": "실거주 효용·레버리지·거래비용을 포함한 매수 원칙",
    "2026 하반기 아파트 가격 전망 | 기흥·수지": "금리·규제·실수요를 반영한 지역별 시나리오와 매수 기준",
    "2021 상승과 2022 하락장 | 원인·충격·재연 조건": "과거 하락 원인과 2026~2028 시나리오",
    "2026 하반기 매수 전략 | 9.65억 거래 불발 이후": "거래 불발 후 가격 상한과 기흥·수지 병행 전략",
    "신분당선 밖의 답 | 구성·보정이 의외의 1순위인 이유": "두 직장 통근과 플랫폼시티를 함께 잡는 숨은 생활권",
    "행원마을동아솔레시티 84㎡ | 실거주·가격·커뮤니티 심층 분석": "84㎡ 가격·통근·주차·노후 리스크와 18개 출처 검증",
    "기흥센트럴푸르지오 202동 2406호 | 계약할 것인가": "9.65억 가격·세입자 조기퇴거·4월 잔금 리스크 판단",
    "정책 분석 | 2026 기흥 토허·규제지역 지정": "토허·대출규제가 기흥 가격과 거래에 미치는 영향",
    "입지 선택 결론 | 기흥역 역세권 vs 수지 준역세권": "정자·양재 통근을 반영한 입지 선택",
    "갈아타기 전략 | 기흥역 84㎡에서 성복역 84㎡로": "첫 집과 다음 집을 연결하는 장기 전략",
    "7/2 저녁임장": "신분당선 역별 전체 후보와 제외 사유",
    "기흥역센트럴푸르지오 심층 분석": "실거래·상품·통근·호재·리스크 분석",
    "TOP10 후보 상세 분석": "최종 후보별 5년 가격과 자료 출처",
}


def page_url(page_id: str) -> str:
    return f"https://www.notion.so/{page_id.replace('-', '')}"


def rebuild_hub(notion: Notion, hub_id: str) -> None:
    pages = {
        block["child_page"].get("title"): block["id"]
        for block in notion.children(hub_id)
        if block["type"] == "child_page"
    }
    for block in notion.children(hub_id):
        if block["type"] != "child_page":
            notion.request("PATCH", f"blocks/{block['id']}", {"archived": True})

    latest = "지금 전세 매물이 씨가 마르는 이유"
    blocks = [
        callout("부동산 분석 글을 시장·정책, 입지·전략, 단지·임장 세 주제로 정리했습니다. 계산기와 입력 정보는 홈에서 관리합니다.", "📚"),
        heading("최신 포스팅", 2),
        table(["게시일", "글", "핵심"], [["2026-07-07", (latest, page_url(pages[latest])), SUMMARIES[latest]]]),
    ]
    for category, titles in CATEGORIES.items():
        rows = [[(title, page_url(pages[title])), SUMMARIES[title]] for title in titles if title in pages]
        if rows:
            blocks.extend([heading(category, 2), table(["포스팅", "내용"], rows)])
    blocks.append(paragraph("새 분석 글은 이 페이지 아래 한 단계로 게시됩니다. 홈 화면에는 이 허브만 표시합니다."))
    notion.append_children(hub_id, blocks)


def main() -> None:
    env = read_env(Path(".env"))
    api_key = env.get("NOTION_API_KEY")
    root_page_id = env.get("NOTION_PARENT_PAGE_ID")
    if not api_key or not root_page_id:
        raise SystemExit("NOTION_API_KEY and NOTION_PARENT_PAGE_ID are required")
    notion = Notion(api_key)
    hub_id = ensure_posting_hub(notion, root_page_id)
    for page in notion.children(root_page_id):
        if page["type"] == "child_page" and page["child_page"].get("title") in POST_TITLES:
            move_page(notion, page["id"], hub_id)
    rebuild_hub(notion, hub_id)
    print(notion.request("GET", f"pages/{hub_id}")["url"])


if __name__ == "__main__":
    main()
