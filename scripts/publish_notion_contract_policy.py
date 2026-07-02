# ruff: noqa: E501
from pathlib import Path

from notion_posting_hub import ensure_posting_hub
from publish_notion_top10 import Notion, callout, heading, paragraph, read_env, table

PARENT_TITLE = "기흥센트럴푸르지오 202동 2406호 | 계약할 것인가"
PAGE_TITLE = "정책·허가·대출 실행 체크 | 202동 2406호"


def find_child_page(notion: Notion, parent_id: str, title: str) -> dict | None:
    for block in notion.children(parent_id):
        if block["type"] == "child_page" and block["child_page"].get("title") == title:
            return block
    return None


def build_blocks() -> list[dict]:
    return [
        callout("계약 전 결론 | 생애최초 자격, 토허 신청·취득 일정, 세입자 퇴거, 은행 한도까지 서면 확인되기 전에는 본계약과 중도금을 집행하지 않습니다.", "🚦"),
        paragraph("기준일 2026-07-02 · 매매가 9.65억 · 희망 잔금 2027년 4월 · 기존 임차인 만기 2027년 7월"),
        heading("한눈에 보는 정책 일정", 2),
        table(["시점", "정책", "이번 계약 영향"], [
            ["2026.07.01", "기흥구 규제지역", "투기과열지구·조정대상지역 대출 규제 적용"],
            ["2026.07.05", "토지거래허가 발효", "이후 공동 허가신청과 실거주계획 필요"],
            ["2026.12.31", "임차주택 유예 신청기한", "유예를 쓰려면 기한 내 신청 필요"],
            ["허가일+4개월", "취득기한", "2027년 4월 잔금과 허가일을 맞춰야 함"],
            ["2027.04", "희망 잔금", "전세보증금 반환·전세대출 상환·주담대 동시 실행"],
            ["2027.07", "기존 임대차 만기", "4월 조기퇴거 실패 시 입주 지연"],
        ]),
        heading("가장 큰 쟁점 4개", 2),
        table(["쟁점", "위험", "해결책"], [
            ["생애최초", "불인정 시 일반 LTV 40%, 약 3.86억", "부부 과거 주택·분양권·입주권 이력을 은행에 서면 확인"],
            ["토허 일정", "일찍 허가받으면 4월 취득이 4개월 기한 밖일 수 있음", "기흥구청에 신청일·허가일·4월 잔금 구조를 서면 질의"],
            ["세입자", "4월 퇴거는 7월 만기보다 3개월 빠른 별도 약속", "매도인·매수인·임차인 3자 합의와 미퇴거 해제권"],
            ["대출 실행", "2027년 정책·감정가·DSR로 6억 미달 가능", "은행 3곳 사전심사, 최소 승인액 미달 특약, 중도금 최소화"],
        ]),
        heading("LTV: 6억원이 가능한 조건", 2),
        table(["구분", "계산", "한도"], [
            ["일반 LTV 40%", "9.65억 × 40%", "3.86억"],
            ["생애최초 LTV 70%", "9.65억 × 70%", "6.755억"],
            ["15억 이하 정책상한", "가격 구간 상한", "6.0억"],
            ["6억 필요 담보평가액", "6억 ÷ 70%", "약 8.57억 이상"],
        ]),
        callout("생애최초가 아니면 현재의 주담대 6억원 계획은 성립하지 않습니다. LTV가 허용해도 스트레스 DSR, 인정소득, 기존 금융부채, 담보평가액 중 가장 보수적인 기준이 실제 한도가 됩니다.", "🏦"),
        heading("계약일과 허가일", 2),
        paragraph("7월 5일 이후에는 매도인과 매수인이 공동으로 토지거래허가를 신청합니다. 허가 전 계약은 법적으로 효력이 확정되지 않은 상태가 될 수 있으므로 계약일을 소급하거나 큰 금액을 먼저 지급하지 않습니다."),
        table(["구간", "계약 원칙"], [
            ["허가 전", "최소 가계약금, 불허 시 전액 반환, 양 당사자 신청 협력"],
            ["허가 확인 후", "본계약금 누적 9,650만원 이내"],
            ["중도금", "없음이 우선, 필요 시 최대 4,825만원 및 은행·퇴거 확인 후"],
            ["잔금", "공실·권리말소·전세대출 상환·주담대 실행을 같은 날 통제"],
        ]),
        heading("기흥구청에 그대로 물을 질문", 2),
        callout("2026년 12월 31일까지 허가를 신청하고 2027년 4월 잔금·취득, 기존 임차인은 2027년 4월 조기퇴거 합의 또는 7월 계약만료인 경우 실거주 유예와 허가일로부터 4개월 내 취득 요건을 충족하는가?", "🏛️"),
        heading("전세대출 3억원 체크", 2),
        table(["은행 확인사항", "이유"], [
            ["주택 취득으로 보는 시점", "계약·토허·등기 중 약정상 기준 확인"],
            ["소유권 이전 즉시상환 여부", "잔금 당일 부족 방지"],
            ["4월 보증금 반환과 동시상환", "전세 순자금 1억원 회수 구조"],
            ["주담대 한도 반영 방식", "전세대출이 심사 중 부채로 남는 문제"],
            ["은행 간 동시 실행 절차", "전세대출은행과 주담대은행이 다를 때 필요"],
        ]),
        heading("권장 실행 순서", 2),
        table(["순서", "시기", "완료 조건"], [
            ["1", "지금", "부부 생애최초·LTV·스트레스 DSR 은행 가심사"],
            ["2", "지금", "기흥구청 토허·4월 취득 서면답변"],
            ["3", "계약 전", "임차인 3자 퇴거합의·등기부·보증금 반환재원 확인"],
            ["4", "조건 충족 후", "허가·대출 실패 반환 특약을 둔 계약"],
            ["5", "2027.01~03", "감정·본심사·전세대출 동시상환 승인"],
            ["6", "2027.04", "공실 확인 후 말소·대출·잔금·소유권 이전"],
        ]),
        heading("계약 중단 조건", 2),
        table(["미확인 항목", "결정"], [
            ["생애최초 또는 주담대 6억", "계약 중단·자금계획 재설계"],
            ["허가일+4개월과 4월 잔금", "구청 답변 전 계약 중단"],
            ["세입자 4월 조기퇴거", "3자 서명 없으면 중단"],
            ["전세대출 동시상환", "은행 승인 없으면 잔금일 변경"],
            ["감정가 8.57억 이상", "미달분 추가 현금 또는 가격 재협상"],
            ["대출 미승인 반환 특약", "매도인이 거부하면 중단"],
        ]),
        heading("계약 전 체크리스트", 2),
        paragraph("□ 부부 모두 금융권 생애최초 확인\n□ 주담대 6억원 가심사\n□ 기흥구청의 4월 취득 가능 답변\n□ 임차인 3자 조기퇴거 합의\n□ 전세대출 3억원 동시상환 승인\n□ 현금 2.8억원과 전세 순자금 1억원의 중복 여부 확인\n□ 허가·대출 실패 시 지급금 반환 특약"),
        heading("공식 출처", 2),
        table(["자료", "링크"], [
            ["기흥구 규제지역 지정", ("국토교통부", "https://www.molit.go.kr/USR/NEWS/m_71/dtl.jsp?id=95092167")],
            ["규제지역 LTV 적용", ("금융위원회", "https://www.fsc.go.kr/po010101/87222")],
            ["기흥구 토지거래허가구역", ("경기도", "https://gnews.gg.go.kr/briefing/brief_gongbo_view.do?BS_CODE=S017&number=70759")],
            ["2026 가계부채 FAQ", ("금융위원회", "https://www.fsc.go.kr/po020201/87058")],
            ["토지거래허가 안내", ("경기부동산포털", "https://gris.gg.go.kr/gnPlan/selectLandTransaction.do")],
            ["허가 전 계약 판례", ("국가법령정보센터", "https://www.law.go.kr/판례/매매대금반환/(95다2487)")],
        ]),
        paragraph("정책은 계약일과 대출 실행일 사이에 바뀔 수 있습니다. 최종 판단은 기흥구청, 실행은행, 법무사·세무사의 서면 답변을 기준으로 합니다."),
    ]


def main() -> None:
    env = read_env(Path(".env"))
    key = env.get("NOTION_API_KEY")
    root = env.get("NOTION_PARENT_PAGE_ID")
    if not key or not root:
        raise SystemExit("Notion credentials are required")

    notion = Notion(key)
    hub_id = ensure_posting_hub(notion, root)
    parent = find_child_page(notion, hub_id, PARENT_TITLE)
    if not parent:
        raise SystemExit(f"Parent page not found: {PARENT_TITLE}")

    existing = find_child_page(notion, parent["id"], PAGE_TITLE)
    if existing:
        notion.request("PATCH", f"pages/{existing['id']}", {"archived": True})

    page = notion.create_child_page(parent_page_id=parent["id"], title=PAGE_TITLE, blocks=build_blocks())
    print(page["url"])


if __name__ == "__main__":
    main()
