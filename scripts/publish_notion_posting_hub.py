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
}

CATEGORIES = {
    "시장·정책": [
        "2021 상승과 2022 하락장 | 원인·충격·재연 조건",
        "정책 분석 | 2026 기흥 토허·규제지역 지정",
    ],
    "입지·전략": [
        "입지 선택 결론 | 기흥역 역세권 vs 수지 준역세권",
        "갈아타기 전략 | 기흥역 84㎡에서 성복역 84㎡로",
    ],
    "단지·임장": [
        "7/2 저녁임장",
        "기흥역센트럴푸르지오 심층 분석",
        "TOP10 후보 상세 분석",
    ],
}

SUMMARIES = {
    "2021 상승과 2022 하락장 | 원인·충격·재연 조건": "과거 하락 원인과 2026~2028 시나리오",
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

    latest = "2021 상승과 2022 하락장 | 원인·충격·재연 조건"
    blocks = [
        callout("부동산 분석 글을 시장·정책, 입지·전략, 단지·임장 세 주제로 정리했습니다. 계산기와 입력 정보는 홈에서 관리합니다.", "📚"),
        heading("최신 포스팅", 2),
        table(["게시일", "글", "핵심"], [["2026-07-01", (latest, page_url(pages[latest])), SUMMARIES[latest]]]),
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
