# ruff: noqa: E501
from pathlib import Path

from notion_posting_hub import ensure_posting_hub
from publish_notion_posting_hub import rebuild_hub
from publish_notion_top10 import Notion, callout, heading, paragraph, read_env, table

PAGE_TITLE = "싸게 사서 비싸게 판다 | 부동산은 무엇이 다른가"


def build_blocks() -> list[dict]:
    return [
        callout("결론 | 부동산도 싸게 사서 비싸게 파는 자산입니다. 다만 가장 싼 집이 아니라 오래 살 수 있는 좋은 집을 대체재보다 싸게 사고, 부채를 견디며, 필요할 때 쉽게 팔 수 있게 사야 합니다.", "🏠"),
        paragraph("기준일 2026-07-05 · 실거주 1주택 · 기흥 84㎡와 수지 59㎡에 적용"),
        heading("금융자산과 다른 점", 2),
        table(["항목", "주식·금·채권", "실거주 부동산"], [
            ["사용 가치", "제한적", "매일 주거서비스 소비"], ["거래", "분할·즉시 가능", "한 채·수주 이상"],
            ["비용", "상대적으로 낮음", "취득·중개·이사·수리"], ["레버리지", "선택", "주담대가 일반적"],
            ["상품", "표준화 용이", "동·층·향마다 다름"], ["실패 대응", "일부 매도", "분할 매도 불가"],
        ]),
        heading("부동산에서 진짜 싸다는 뜻", 2),
        table(["기준", "확인 방법"], [
            ["대체재보다 싸다", "같은 예산·통근·면적·연식 비교"], ["정상가격보다 싸다", "유사 층 최근 정상거래 3건"],
            ["총비용이 싸다", "취득·이자·수리·이사비 포함"], ["오래 살수록 싸다", "7년 이상 거주 가능"],
            ["하락장에도 싸다", "10% 하락에도 강제매도 불필요"],
        ]),
        callout("싼 이유가 일시적이면 기회일 수 있지만, 역 거리·소규모·소음·수요 부족처럼 구조적이면 팔 때도 계속 쌉니다.", "⚠️"),
        heading("실거주 수익의 공식", 2),
        paragraph("매도가격 - 매수가격 + 절감한 임대료 + 거주 효용 - 이자 - 세금 - 수리비 - 거래·이사비용"),
        paragraph("출퇴근 단축, 방 하나 추가, 안정적인 생활권은 실제로 소비하는 서비스입니다. 반대로 만족도가 낮아 일찍 갈아타면 거래비용을 두 번 부담합니다."),
        heading("레버리지", 2),
        paragraph("자기자본 4억원으로 10억원 주택을 사면 10% 상승은 비용 전 자기자본 25% 증가지만, 10% 하락도 자기자본 25% 감소입니다. 레버리지는 수익률과 실패 확률을 함께 키웁니다."),
        table(["충격", "방어 기준"], [
            ["가격 -10%", "매도하지 않고 7년 이상 거주"], ["금리 +1%p", "월 현금흐름 유지"],
            ["주담대 -5천만원", "잔금 대체자금 확보"], ["거래절벽", "실수요가 많은 대단지 선택"],
        ]),
        heading("기흥과 수지에 적용", 2),
        table(["선택", "가치", "싸다고 판단할 조건"], [
            ["수지 59㎡", "양재·강남 통근·환금성", "역세권 대단지·정상거래 이하"],
            ["기흥 84㎡", "공간·신축급·장기거주", "수지보다 충분히 저렴·대출 안정"],
        ]),
        paragraph("기흥 84㎡와 조건 좋은 수지 59㎡의 차이가 3천만원 이내면 수지를 재검토합니다. 기흥이 5천만원 이상 저렴하고 주담대 5.5억원으로도 유지되면 기흥의 실거주 가치가 우세합니다."),
        heading("싼 집과 가격만 낮은 집", 2),
        table(["일시적 할인", "구조적 할인"], [
            ["급한 잔금", "역에서 멀고 개선 불가"], ["내부 수리", "소규모·거래 희소"],
            ["규제 직후 위축", "소음·생활환경 문제"], ["비선호 계절", "통근 수요 부족"],
        ]),
        paragraph("우리 조건에서는 300세대 이하, 역 도보 23분 이상, 세입자 퇴거가 불명확한 매물은 가격이 낮아도 제외합니다."),
        heading("매수 원칙", 2),
        paragraph("1. 7년 이상 살 수 있는 집만 선택\n2. 최근 정상 실거래 3건으로 상단 설정\n3. 같은 날 기흥 84㎡와 수지 59㎡ 비교\n4. 가격 -10%·금리 +1%p 동시 계산\n5. 주담대 5천만원 감소에도 잔금 가능\n6. 매도할 때 살 사람이 많은 단지 선택\n7. 호재가 가격에 이미 반영됐는지 확인\n8. 놓친 신고가를 다음 매물 추격 근거로 쓰지 않음"),
        heading("계약 전 네 가지 질문", 2),
        table(["질문", "통과 기준"], [
            ["왜 싼가?", "일시적 사유를 설명 가능"], ["안 오르면 살 수 있나?", "7년 거주·현금흐름 유지"],
            ["급히 팔면 누가 사나?", "역·통근·대단지 실수요"], ["대체재가 없나?", "동일 예산 후보 동시 비교"],
        ]),
        heading("최종 생각", 2),
        callout("바닥에서 사려고 하지 말고, 좋은 집을 감당 가능한 가격에 사서 시간의 편을 만듭니다. 하락장에도 팔지 않아도 되는 조건이 실거주자의 가장 큰 경쟁력입니다.", "📌"),
        heading("출처", 2),
        table(["자료", "링크"], [
            ["주택가격 통계", ("한국부동산원", "https://www.reb.or.kr/reb/cm/cntnts/cntntsView.do?cntntsId=1033&mi=10333")],
            ["양도소득세", ("국세청", "https://www.nts.go.kr/tax/yangdo_1.html")],
            ["실거래가 양도차익", ("국세청", "https://j.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=8639&mi=12270")],
            ["경제전망·주택 기대심리", ("한국은행", "https://www.bok.or.kr/portal/bbs/B0000156/list.do?menuNo=200067")],
        ]),
        paragraph("세금과 대출 규정은 바뀔 수 있습니다. 실제 계약 전 세무사·은행·법무사를 통해 개별 조건을 확인합니다."),
    ]


def main() -> None:
    env = read_env(Path(".env")); key = env.get("NOTION_API_KEY"); root = env.get("NOTION_PARENT_PAGE_ID")
    if not key or not root:
        raise SystemExit("Notion credentials are required")
    notion = Notion(key); hub = ensure_posting_hub(notion, root)
    for block in notion.children(hub):
        if block["type"] == "child_page" and block["child_page"].get("title") == PAGE_TITLE:
            notion.request("PATCH", f"pages/{block['id']}", {"archived": True})
    page = notion.create_child_page(parent_page_id=hub, title=PAGE_TITLE, blocks=build_blocks())
    rebuild_hub(notion, hub)
    print(page["url"])


if __name__ == "__main__":
    main()
