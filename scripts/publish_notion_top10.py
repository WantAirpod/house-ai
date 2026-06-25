from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from home_decision_ai.collectors.molit_rtms import fetch_apartment_trades
from home_decision_ai.models.financing import classify_price


BUDGET_REALISTIC_KRW = 920_000_000
BUDGET_MAX_KRW = 1_050_000_000
MIN_HOUSEHOLD_COUNT = 300

REGIONS = {
    "용인 수지": {
        "priority": 1,
        "lawd_codes": {"용인 수지": "41465"},
        "memo": "1순위. 신분당선/자차 모두 검토.",
    },
    "용인 기흥": {
        "priority": 2,
        "lawd_codes": {"용인 기흥": "41463"},
        "memo": "2순위. 자차 출퇴근과 역세권 균형 확인.",
    },
    "용인 처인": {
        "priority": 3,
        "lawd_codes": {"용인 처인": "41461"},
        "memo": "3순위. 가격 메리트와 출퇴근 리스크를 분리.",
    },
    "서울 판교 출퇴근권": {
        "priority": 4,
        "lawd_codes": {
            "서울 강남구": "11680",
            "서울 서초구": "11650",
            "서울 송파구": "11710",
            "서울 강동구": "11740",
        },
        "memo": "서울은 예산 초과 가능성이 높아 59/구축 위주로 예외 탐색.",
    },
}

EXCLUDED_PROPERTY_TYPES = {
    "officetel",
    "officetel_apartment",
    "urban_living_housing",
    "non_apartment",
}


def read_env(path: Path = Path(".env")) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def month_range(start_ym: str, end_ym: str) -> list[str]:
    start_year, start_month = int(start_ym[:4]), int(start_ym[4:])
    end_year, end_month = int(end_ym[:4]), int(end_ym[4:])
    months: list[str] = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def default_months(today: date) -> list[str]:
    start_year = today.year - 1 if today.month <= 12 else today.year
    start_month = today.month
    return month_range(f"{start_year:04d}{start_month:02d}", f"{today.year:04d}{today.month:02d}")


def area_bucket(area_m2: float | None) -> str | None:
    if area_m2 is None:
        return None
    if 55 <= area_m2 <= 65:
        return "59"
    if 80 <= area_m2 <= 90:
        return "84"
    return None


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def parse_int(value: str | None) -> int | None:
    if not value or not value.strip():
        return None
    return int(value.strip())


def load_complex_metadata(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not path.exists():
        return {}

    metadata: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            region = (row.get("region") or "").strip()
            name = (row.get("complex_name") or "").strip()
            if not region or not name:
                continue
            metadata[(region, name)] = {
                "household_count": parse_int(row.get("household_count")),
                "property_type": (row.get("property_type") or "unknown").strip(),
                "exclude_override": parse_bool(row.get("exclude_override")),
                "source_url": (row.get("source_url") or "").strip() or None,
                "memo": (row.get("memo") or "").strip() or None,
            }
    return metadata


def exclusion_reasons(metadata: dict[str, Any] | None) -> list[str]:
    if not metadata or metadata.get("exclude_override"):
        return []

    reasons: list[str] = []
    household_count = metadata.get("household_count")
    if household_count is not None and household_count < MIN_HOUSEHOLD_COUNT:
        reasons.append("300세대 미만")

    property_type = metadata.get("property_type")
    if property_type in EXCLUDED_PROPERTY_TYPES:
        reasons.append(f"제외 주거유형: {property_type}")
    return reasons


def fetch_candidates(
    *,
    service_key: str,
    months: list[str],
    metadata_path: Path,
) -> list[dict[str, Any]]:
    trades_by_complex: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    metadata_by_complex = load_complex_metadata(metadata_path)

    for region_name, region in REGIONS.items():
        for subregion, lawd_cd in region["lawd_codes"].items():
            for month in months:
                trades = fetch_apartment_trades(
                    service_key=service_key,
                    lawd_cd=lawd_cd,
                    deal_ym=month,
                )
                for trade in trades:
                    bucket = area_bucket(trade.area_m2)
                    if bucket is None:
                        continue
                    item = asdict(trade)
                    item["region"] = region_name
                    item["subregion"] = subregion
                    item["area_bucket"] = bucket
                    trades_by_complex[(region_name, trade.apartment_name, bucket)].append(item)

    candidates: list[dict[str, Any]] = []
    for (region_name, name, bucket), trades in trades_by_complex.items():
        prices = [trade["price_krw"] for trade in trades if trade["price_krw"]]
        if not prices:
            continue

        trades_sorted = sorted(trades, key=lambda item: (item["deal_ym"], int(item["deal_day"] or 0)))
        latest = trades_sorted[-1]
        built_years = [trade["built_year"] for trade in trades if trade["built_year"]]
        built_year = max(set(built_years), key=built_years.count) if built_years else None
        min_price = min(prices)
        max_price = max(prices)
        latest_price = latest["price_krw"]
        financing_band = classify_price(latest_price)
        metadata = metadata_by_complex.get((region_name, name))
        reasons = exclusion_reasons(metadata)
        price_change_pct = round(((latest_price - min_price) / min_price) * 100, 1) if min_price else None

        if latest_price <= BUDGET_REALISTIC_KRW:
            budget_status = "현실 플랜"
        elif latest_price <= BUDGET_MAX_KRW:
            budget_status = "확장 플랜"
        else:
            budget_status = "예산 초과"

        candidates.append(
            {
                "region": region_name,
                "subregion": latest["subregion"],
                "name": name,
                "area_bucket": bucket,
                "built_year": built_year,
                "age_years": date.today().year - built_year if built_year else None,
                "trade_count": len(prices),
                "min_price_krw": min_price,
                "max_price_krw": max_price,
                "latest_price_krw": latest_price,
                "latest_deal_ym": latest["deal_ym"],
                "latest_deal_day": latest["deal_day"],
                "latest_area_m2": latest["area_m2"],
                "latest_floor": latest["floor"],
                "price_change_from_min_pct": price_change_pct,
                "budget_status": budget_status,
                "financing_band": financing_band.name,
                "financing_recommendation": financing_band.recommendation,
                "household_count": metadata.get("household_count") if metadata else None,
                "property_type": metadata.get("property_type") if metadata else "unknown",
                "excluded": bool(reasons),
                "exclusion_reasons": reasons,
            }
        )
    return candidates


def score_candidate(item: dict[str, Any], *, older_friendly: bool = False) -> float:
    latest_price = item["latest_price_krw"]
    if item["excluded"] or latest_price > BUDGET_MAX_KRW:
        return -1_000

    region_priority = REGIONS[item["region"]]["priority"]
    score = 0.0
    # Region preference reflects the couple's actual decision profile:
    # commute to Jeongja/Naver and Shinbundang access are more important than raw liquidity.
    score += {1: 32, 2: 18, 3: 8, 4: 5}.get(region_priority, 0)
    score += 16 if latest_price <= BUDGET_REALISTIC_KRW else 8
    score += 10 if item["area_bucket"] == "84" else 7
    score += min(item["trade_count"], 25) * 0.3

    built_year = item["built_year"] or 0
    if older_friendly:
        if built_year >= 2014:
            score += 10
        elif built_year >= 2006:
            score += 8
        elif built_year >= 1998:
            score += 6
        else:
            score += 2
    else:
        if built_year >= 2019:
            score += 15
        elif built_year >= 2014:
            score += 12
        elif built_year >= 2006:
            score += 5
        else:
            score -= 4

    if item["price_change_from_min_pct"] is not None and item["price_change_from_min_pct"] >= 25:
        score -= 3
    return round(score, 2)


def ranked(candidates: list[dict[str, Any]], *, older_friendly: bool = False) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for item in candidates:
        copy = dict(item)
        copy["score"] = score_candidate(copy, older_friendly=older_friendly)
        if copy["score"] < 0:
            continue
        scored.append(copy)
    return sorted(
        scored,
        key=lambda item: (
            item["score"],
            item["trade_count"],
            -item["latest_price_krw"],
        ),
        reverse=True,
    )


def regional_top10(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for region_name in REGIONS:
        region_candidates = [item for item in candidates if item["region"] == region_name]
        output[region_name] = ranked(region_candidates)[:10]
    return output


def won_eok(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value / 100_000_000:.2f}억"


def deal_date(item: dict[str, Any]) -> str:
    ym = item["latest_deal_ym"]
    return f"{ym[:4]}.{ym[4:]}.{int(item['latest_deal_day']):02d}"


def key_reason(item: dict[str, Any]) -> str:
    reasons: list[str] = []
    if item["latest_price_krw"] <= BUDGET_REALISTIC_KRW:
        reasons.append("현실 플랜")
    else:
        reasons.append("확장 플랜")
    reasons.append(f"{item['area_bucket']}형")
    if item["built_year"]:
        reasons.append(f"{item['built_year']}년식")
    reasons.append(f"거래 {item['trade_count']}건")
    if item["region"] == "서울 판교 출퇴근권":
        reasons.append("서울 예외 검토")
    return " · ".join(reasons)


def text(content: str, *, bold: bool = False) -> dict[str, Any]:
    return {"type": "text", "text": {"content": content}, "annotations": {"bold": bold}}


def rich_text(content: str, *, bold: bool = False) -> list[dict[str, Any]]:
    return [text(content[:2000], bold=bold)]


def heading(content: str, level: int = 2) -> dict[str, Any]:
    block_type = f"heading_{level}"
    return {"object": "block", "type": block_type, block_type: {"rich_text": rich_text(content)}}


def paragraph(content: str) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_text(content)}}


def callout(content: str, icon: str = "🏠") -> dict[str, Any]:
    return {
        "object": "block",
        "type": "callout",
        "callout": {"rich_text": rich_text(content), "icon": {"type": "emoji", "emoji": icon}},
    }


def divider() -> dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def table(headers: list[str], rows: list[list[str]]) -> dict[str, Any]:
    children = [
        {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [[text(cell, bold=True)] for cell in headers]},
        }
    ]
    for row in rows:
        children.append(
            {
                "object": "block",
                "type": "table_row",
                "table_row": {"cells": [[text(cell)] for cell in row]},
            }
        )
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "has_row_header": False,
            "children": children,
        },
    }


def top_rows(items: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for idx, item in enumerate(items, 1):
        rows.append(
            [
                str(idx),
                item["region"],
                item["name"],
                item["area_bucket"],
                str(item["built_year"] or "-"),
                won_eok(item["latest_price_krw"]),
                deal_date(item),
                str(item["trade_count"]),
                key_reason(item),
            ]
        )
    return rows


def regional_rows(items: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for idx, item in enumerate(items, 1):
        rows.append(
            [
                str(idx),
                item["name"],
                item["area_bucket"],
                str(item["built_year"] or "-"),
                won_eok(item["latest_price_krw"]),
                deal_date(item),
                item["budget_status"],
                str(item["trade_count"]),
            ]
        )
    return rows


def build_blocks(
    *,
    months: list[str],
    final_top10: list[dict[str, Any]],
    region_tops: dict[str, list[dict[str, Any]]],
    older_top10: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    start_month, end_month = months[0], months[-1]
    blocks: list[dict[str, Any]] = [
        callout(
            "첫 화면은 추천과 인사이트만 남겼습니다. 원본 조건/자금계획/API 정보는 입력 정보 아카이브에 보관합니다. "
            f"랭킹 기준: 국토부 실거래 {start_month[:4]}.{start_month[4:]}~{end_month[:4]}.{end_month[4:]}, "
            "59/84형, 10.5억 이하, 300세대 미만/오피스텔형은 메타데이터가 있을 때 제외.",
        ),
        heading("최종 TOP10", 2),
        paragraph("부부 조건을 종합한 1차 추천입니다. 호가와 매물 수가 붙기 전까지는 실거래 기반 후보군으로 봅니다."),
        table(
            ["순위", "지역", "단지", "평형", "연식", "최근 실거래", "거래일", "거래수", "판단 근거"],
            top_rows(final_top10),
        ),
        divider(),
        heading("지역별 TOP10", 2),
    ]

    for region_name, items in region_tops.items():
        blocks.append(heading(region_name, 3))
        blocks.append(paragraph(REGIONS[region_name]["memo"]))
        if items:
            blocks.append(
                table(
                    ["순위", "단지", "평형", "연식", "최근 실거래", "거래일", "예산", "거래수"],
                    regional_rows(items),
                )
            )
        else:
            blocks.append(paragraph("최근 13개월 실거래 기준으로 10.5억 이하 59/84 후보가 부족합니다."))

    blocks.extend(
        [
            divider(),
            heading("구축 포함 TOP10", 2),
            paragraph("신축 가점을 낮추고 가격/입지/거래량을 더 본 확장 후보입니다. 구축은 수리비, 주차, 관리상태 확인이 필수입니다."),
            table(
                ["순위", "지역", "단지", "평형", "연식", "최근 실거래", "거래일", "거래수", "판단 근거"],
                top_rows(older_top10),
            ),
            divider(),
            heading("이번 주 확인할 것", 2),
            paragraph("1. 최종 TOP10의 현재 최저호가와 매물 수를 같은 날짜 기준으로 입력"),
            paragraph("2. 단지별 세대수와 주거유형을 메타데이터로 보강해서 300세대 미만/오피스텔형 제외 규칙 확정"),
            paragraph("3. 실거래가보다 호가가 5% 이상 높은 단지는 보류로 이동"),
            paragraph("4. 구축 후보는 수리비, 주차, 동간거리, 엘리베이터/배관 이슈를 별도 체크"),
            heading("바로가기", 2),
            paragraph("입력 정보 아카이브는 이 페이지 상단 child page에 보관되어 있습니다."),
            paragraph("출처: 국토교통부 실거래가 공개시스템 API. 호가/매물 수는 아직 자동 반영 전입니다."),
        ]
    )
    return blocks


class Notion:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(
            f"https://api.notion.com/v1/{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Notion API failed: {exc.code} {detail}") from exc

    def children(self, block_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            query = urlencode({"page_size": 100, **({"start_cursor": cursor} if cursor else {})})
            data = self.request("GET", f"blocks/{block_id}/children?{query}")
            results.extend(data["results"])
            if not data.get("has_more"):
                return results
            cursor = data["next_cursor"]

    def archive_dashboard_blocks(self, page_id: str) -> None:
        for block in self.children(page_id):
            block_type = block["type"]
            # Keep the actual archive child page alive. Everything else is regenerated.
            if block_type == "child_page" and block[block_type].get("title") == "입력 정보 아카이브":
                continue
            self.request("PATCH", f"blocks/{block['id']}", {"archived": True})

    def append_children(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
        for start in range(0, len(blocks), 80):
            self.request("PATCH", f"blocks/{page_id}/children", {"children": blocks[start : start + 80]})


def write_outputs(
    *,
    candidates: list[dict[str, Any]],
    final_top10: list[dict[str, Any]],
    region_tops: dict[str, list[dict[str, Any]]],
    older_top10: list[dict[str, Any]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_date": date.today().isoformat(),
        "source": "MOLIT RTMS apartment trade API",
        "candidate_count": len(candidates),
        "final_top10": final_top10,
        "regional_top10": region_tops,
        "older_included_top10": older_top10,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish data-backed TOP10 rankings to Notion.")
    parser.add_argument("--months", nargs="+", help="YYYYMM values. Defaults to same month last year through current month.")
    parser.add_argument("--metadata", type=Path, default=Path("data/manual/complex_metadata.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/recommendation_rankings.json"))
    parser.add_argument("--skip-notion", action="store_true")
    args = parser.parse_args()

    env = read_env()
    service_key = env.get("PUBLIC_DATA_API_KEY")
    if not service_key:
        raise SystemExit("PUBLIC_DATA_API_KEY is required in .env")

    months = args.months or default_months(date.today())
    candidates = fetch_candidates(service_key=service_key, months=months, metadata_path=args.metadata)
    final_top10 = ranked(candidates)[:10]
    region_tops = regional_top10(candidates)
    older_top10 = ranked(candidates, older_friendly=True)[:10]

    write_outputs(
        candidates=candidates,
        final_top10=final_top10,
        region_tops=region_tops,
        older_top10=older_top10,
        output_path=args.output,
    )

    if not args.skip_notion:
        notion_key = env.get("NOTION_API_KEY")
        page_id = env.get("NOTION_PARENT_PAGE_ID")
        if not notion_key or not page_id:
            raise SystemExit("NOTION_API_KEY and NOTION_PARENT_PAGE_ID are required in .env")
        notion = Notion(notion_key)
        notion.archive_dashboard_blocks(page_id)
        notion.append_children(
            page_id,
            build_blocks(
                months=months,
                final_top10=final_top10,
                region_tops=region_tops,
                older_top10=older_top10,
            ),
        )

    print(json.dumps({"final_top10": final_top10, "older_top10": older_top10}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
