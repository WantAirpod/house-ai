# ruff: noqa: E501
from pathlib import Path

from notion_posting_hub import ensure_posting_hub
from publish_notion_posting_hub import rebuild_hub
from publish_notion_top10 import Notion, callout, heading, paragraph, read_env, table

OLD_PAGE_TITLE = "2026 하반기 매수 전략 | 기흥 84㎡ vs 수지 59㎡"
PAGE_TITLE = "2026 하반기 매수 전략 | 9.65억 거래 불발 이후"
OLD_CONTRACT_TITLE = "기흥센트럴푸르지오 202동 2406호 | 계약할 것인가"
CLOSED_CONTRACT_TITLE = "종료된 검토 | 센트럴 202동 2406호 9.65억"


def build_blocks() -> list[dict]:
    return [
        callout("상황 정정 | 센트럴 202동 2406호 9.65억원 거래는 성사되지 않았습니다. 해당 매물 계약 결론은 폐기하고 특정 매물 없는 하반기 전략으로 다시 시작합니다.", "🔄"),
        paragraph("기준일 2026-07-04 · 현금 2.8억 · 부부 인정소득 약 1.6억 내외 확인 필요 · 주담대 목표 6억 · 기흥 84㎡와 수지 59㎡ 병행"),
        heading("새 결론", 2),
        callout("가격을 올려 대체 매물을 급히 잡지 않습니다. 7월 5일 토허 시행 후 첫 거래를 확인하면서 기흥 84㎡를 기본축으로 찾고, 조건 좋은 수지 59㎡를 함께 비교합니다.", "🧭"),
        table(["레드라인", "기준"], [
            ["센트럴 84㎡", "9.7억 이하"], ["전체 매매가", "9.8억 이하"],
            ["스트레스 DSR", "40% 미만·목표 37%"], ["필요 신용대출", "8천만원 이하"],
            ["역 도보", "23분 미만"], ["세대수", "300세대 초과·500세대 우선"],
        ]),
        heading("현재 구매력", 2),
        table(["구분", "가격"], [
            ["적정", "9.3~9.6억"], ["확장", "9.65~9.8억"], ["보류", "9.9억 이상"],
        ]),
        paragraph("이직 후 급여·상여가 은행 인정소득에 얼마나 반영되는지 확인합니다. 새 매물의 수리비·이주비·긴 잔금 조건까지 합친 총액으로 비교합니다."),
        heading("정책 전망", 2),
        table(["가능성", "예상", "영향"], [
            ["높음", "은행 총량·우대금리·신용한도", "접수·금리 불리"],
            ["중상", "스트레스 DSR·만기 관리", "주담대 6억 미달"],
            ["중간", "생애최초 상한·소득·가격 요건", "LTV 유지해도 한도 축소"],
            ["낮음", "생애최초 전면 폐지", "실수요 보호와 충돌"],
        ]),
        callout("생애최초가 완전히 막힐 가능성보다 혜택은 남아 있지만 실제 6억원이 줄어드는 위험이 더 큽니다.", "⚠️"),
        heading("센트럴 가격 해석", 2),
        table(["지표", "가격"], [
            ["6월 거래", "21건"], ["중앙값", "9.70억"], ["범위", "9.20~10.55억"],
            ["불발 매물", "24층·9.65억"], ["재진입 상한", "9.70억"],
        ]),
        paragraph("10.55억원은 고층 한 건이며 9.4~9.6억원 거래도 존재합니다. 새 매물이 더 좋은 향·조망·수리상태가 아닐 경우 불발 가격보다 높게 따라가지 않습니다."),
        heading("다시 구성한 후보", 2),
        table(["순서", "후보", "목표가격", "중단 조건"], [
            ["1", "센트럴 84㎡", "9.4~9.7억", "9.7억 초과·비선호 향"],
            ["2", "지웰 84㎡", "9.1~9.3억", "유형 혼동·9.4억 이상"],
            ["3", "파크 84㎡", "8.7~9.0억", "환승·소음 불리"],
            ["4", "수지 59㎡", "9.1~9.5억", "역 15분 초과·소규모"],
            ["5", "기흥역더샵 84㎡", "9.8억 이하", "10억 이상"],
            ["6", "동아솔레시티 84㎡", "8억 후반", "누수·배관·주차"],
        ]),
        heading("기흥 vs 수지", 2),
        table(["선택", "맞는 조건"], [
            ["기흥 84㎡", "7년 이상·자녀·공간·대단지·커뮤니티"],
            ["수지 59㎡", "3~5년 갈아타기·양재/강남 통근·입지 우선"],
        ]),
        paragraph("현재 기본안은 기흥 84㎡입니다. 다만 수지에서 500세대 이상, 실제 역 도보 15분 이내, 9.5억원 이하 59㎡가 나오면 같은 날 비교 임장합니다."),
        heading("시기별 행동", 2),
        table(["시기", "행동"], [
            ["7월", "토허 절차·매물 회수 확인"], ["8월", "규제 후 첫 84㎡ 거래 확인"],
            ["9~10월", "가격 조건 충족 매물 협상"], ["11~12월", "2027 대출정책·스트레스금리"],
            ["계약 후", "잔금 2개월 전 3개 은행 본심사"],
        ]),
        heading("매물 규칙", 2),
        paragraph("1. 동일 면적·층 3건 확인\n2. 향·조망·소음·수리비 금액화\n3. 세입자 3자합의 없으면 제외\n4. 장기 잔금 중도금 최소화\n5. 주담대 5.5억에도 이행 가능한지 계산\n6. 매매가와 거래비 총액 비교\n7. '오늘 안 사면 오른다'는 근거로 사용하지 않음"),
        heading("최종 전략", 2),
        callout("9.65억원 거래 불발은 매수 기회를 잃은 것이 아니라 특정 매물 검토가 종료된 것입니다. 기흥 84㎡를 기본으로 하되 센트럴 9.7억, 전체 9.8억을 넘지 않고 7~8월 규제 후 거래를 확인합니다.", "✅"),
        heading("출처", 2),
        table(["자료", "링크"], [
            ["기흥 대출규제", ("금융위원회", "https://www.fsc.go.kr/no010101/87222")],
            ["가계부채 FAQ", ("금융위원회", "https://www.fsc.go.kr/po020201/87058")],
            ["국토부 업무계획", ("국토교통부", "https://www.molit.go.kr/2026plan/sub3_realestate.html")],
            ["금리 전망", ("한국은행", "https://www.bok.or.kr/portal/bbs/B0000156/view.do?menuNo=200067&nttId=10096935")],
            ["실거래", ("국토교통부", "https://rt.molit.go.kr/")],
        ]),
        paragraph("정책 예상은 현재 방향에 근거한 추론입니다. 계약일에 실거래·대출규정을 다시 확인합니다."),
    ]


def rename_closed_contract(notion: Notion, hub_id: str) -> None:
    for block in notion.children(hub_id):
        if block["type"] == "child_page" and block["child_page"].get("title") == OLD_CONTRACT_TITLE:
            notion.request(
                "PATCH",
                f"pages/{block['id']}",
                {"properties": {"title": {"title": [{"text": {"content": CLOSED_CONTRACT_TITLE}}]}}},
            )


def main() -> None:
    env = read_env(Path(".env")); key = env.get("NOTION_API_KEY"); root = env.get("NOTION_PARENT_PAGE_ID")
    if not key or not root:
        raise SystemExit("Notion credentials are required")
    notion = Notion(key); hub = ensure_posting_hub(notion, root)
    rename_closed_contract(notion, hub)
    for block in notion.children(hub):
        if block["type"] == "child_page" and block["child_page"].get("title") in {OLD_PAGE_TITLE, PAGE_TITLE}:
            notion.request("PATCH", f"pages/{block['id']}", {"archived": True})
    page = notion.create_child_page(parent_page_id=hub, title=PAGE_TITLE, blocks=build_blocks())
    rebuild_hub(notion, hub)
    print(page["url"])


if __name__ == "__main__":
    main()
