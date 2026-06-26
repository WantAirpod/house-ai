from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from home_decision_ai.collectors.molit_rtms import ApartmentTrade
from home_decision_ai.collectors.molit_rtms import fetch_apartment_trades
from home_decision_ai.models.financing import classify_price


BUDGET_REALISTIC_KRW = 920_000_000
BUDGET_MAX_KRW = 1_050_000_000
MAX_EXCLUDED_HOUSEHOLD_COUNT = 200
PREFERRED_MIN_HOUSEHOLD_COUNT = 500
WALKING_DISTANCE_PER_MINUTE_M = 60
STATION_SEARCH_RADIUS_M = 5000
STATION_CACHE_PATH = Path("data/processed/station_access_cache.json")

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
            "서울 동작구": "11590",
            "서울 관악구": "11620",
        },
        "memo": "10.5억 이하 59/84 실거래만 추림. 생활권·연식·면적 타협 가능성 확인.",
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
    return int(float(value.strip().replace(",", "")))


def parse_float(value: str | None) -> float | None:
    if not value or not value.strip():
        return None
    return float(value.strip().replace(",", ""))


def candidate_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (item["region"], item["subregion"], item["name"], item["area_bucket"])


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


def load_market_observations(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    if not path.exists():
        return {}

    observations: dict[tuple[str, str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            region = (row.get("region") or "").strip()
            name = (row.get("complex_name") or "").strip()
            area_value = parse_float(row.get("area_m2"))
            bucket = area_bucket(area_value)
            if not region or not name or bucket is None:
                continue
            key = (region, name, bucket)
            observed_at = (row.get("observed_at") or "").strip()
            current = observations.get(key)
            if current and current.get("observed_at", "") > observed_at:
                continue
            observations[key] = {
                "observed_at": observed_at or None,
                "asking_price_krw": parse_int(row.get("asking_price_krw")),
                "inventory_count": parse_int(row.get("inventory_count")),
                "source_id": (row.get("source_id") or "").strip() or None,
                "source_url": (row.get("source_url") or "").strip() or None,
                "verification_status": (row.get("verification_status") or "").strip() or None,
                "memo": (row.get("memo") or "").strip() or None,
            }
    return observations


def exclusion_reasons(metadata: dict[str, Any] | None) -> list[str]:
    if not metadata or metadata.get("exclude_override"):
        return []

    reasons: list[str] = []
    household_count = metadata.get("household_count")
    if household_count is not None and household_count <= MAX_EXCLUDED_HOUSEHOLD_COUNT:
        reasons.append("200세대 이하")

    property_type = metadata.get("property_type")
    if property_type in EXCLUDED_PROPERTY_TYPES:
        reasons.append(f"제외 주거유형: {property_type}")
    return reasons


def fetch_trades_with_retry(
    *,
    service_key: str,
    lawd_cd: str,
    deal_ym: str,
    attempts: int = 3,
) -> list[ApartmentTrade]:
    for attempt in range(1, attempts + 1):
        try:
            return fetch_apartment_trades(
                service_key=service_key,
                lawd_cd=lawd_cd,
                deal_ym=deal_ym,
            )
        except (TimeoutError, URLError, HTTPError):
            if attempt == attempts:
                return []
            time.sleep(1.5 * attempt)
    return []


def kakao_get(path: str, *, rest_api_key: str, params: dict[str, Any]) -> dict[str, Any] | None:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    request = Request(
        f"https://dapi.kakao.com/v2/local/{path}?{query}",
        headers={"Authorization": f"KakaoAK {rest_api_key}"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (TimeoutError, URLError, HTTPError):
        return None


def load_json_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def station_access_cache_key(item: dict[str, Any]) -> str:
    return "|".join(candidate_key(item))


def estimate_walk_minutes(distance_m: int | None) -> int | None:
    if distance_m is None:
        return None
    return math.ceil(distance_m / WALKING_DISTANCE_PER_MINUTE_M)


def resolve_station_access(
    item: dict[str, Any],
    *,
    rest_api_key: str,
    cache: dict[str, Any],
) -> dict[str, Any]:
    key = station_access_cache_key(item)
    if key in cache:
        return cache[key]

    query = f"{item['subregion']} {item['name']} 아파트"
    place_data = kakao_get(
        "search/keyword.json",
        rest_api_key=rest_api_key,
        params={"query": query, "size": 1},
    )
    documents = (place_data or {}).get("documents", [])
    if not documents:
        cache[key] = {
            "nearest_station_name": None,
            "station_distance_m": None,
            "station_walk_minutes": None,
            "station_source": "kakao_local_keyword_not_found",
        }
        return cache[key]

    place = documents[0]
    station_data = kakao_get(
        "search/category.json",
        rest_api_key=rest_api_key,
        params={
            "category_group_code": "SW8",
            "x": place.get("x"),
            "y": place.get("y"),
            "radius": STATION_SEARCH_RADIUS_M,
            "sort": "distance",
            "size": 1,
        },
    )
    stations = (station_data or {}).get("documents", [])
    if not stations:
        cache[key] = {
            "nearest_station_name": None,
            "station_distance_m": None,
            "station_walk_minutes": None,
            "station_source": "kakao_local_station_not_found",
        }
        return cache[key]

    station = stations[0]
    distance_m = parse_int(station.get("distance"))
    cache[key] = {
        "nearest_station_name": station.get("place_name"),
        "station_distance_m": distance_m,
        "station_walk_minutes": estimate_walk_minutes(distance_m),
        "station_source": "kakao_local_straight_distance_estimate",
    }
    return cache[key]


def enrich_station_access(
    candidates: list[dict[str, Any]],
    *,
    rest_api_key: str | None,
    cache_path: Path = STATION_CACHE_PATH,
) -> None:
    if not rest_api_key:
        return

    cache = load_json_cache(cache_path)
    for item in candidates:
        item.update(resolve_station_access(item, rest_api_key=rest_api_key, cache=cache))
    save_json_cache(cache_path, cache)


def fetch_candidates(
    *,
    service_key: str,
    months: list[str],
    metadata_path: Path,
    observations_path: Path,
) -> list[dict[str, Any]]:
    trades_by_complex: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    metadata_by_complex = load_complex_metadata(metadata_path)
    observations_by_complex = load_market_observations(observations_path)

    for region_name, region in REGIONS.items():
        for subregion, lawd_cd in region["lawd_codes"].items():
            for month in months:
                trades = fetch_trades_with_retry(
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
                    trades_by_complex[(region_name, subregion, trade.apartment_name, bucket)].append(item)

    candidates: list[dict[str, Any]] = []
    for (region_name, subregion, name, bucket), trades in trades_by_complex.items():
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
        metadata = metadata_by_complex.get((subregion, name)) or metadata_by_complex.get((region_name, name))
        observation = (
            observations_by_complex.get((subregion, name, bucket))
            or observations_by_complex.get((region_name, name, bucket))
        )
        reasons = exclusion_reasons(metadata)
        price_change_pct = round(((latest_price - min_price) / min_price) * 100, 1) if min_price else None
        price_position_pct = (
            round(((latest_price - min_price) / (max_price - min_price)) * 100, 1)
            if max_price > min_price
            else 0.0
        )

        if latest_price <= BUDGET_REALISTIC_KRW:
            budget_status = "현실 플랜"
        elif latest_price <= BUDGET_MAX_KRW:
            budget_status = "확장 플랜"
        else:
            budget_status = "예산 초과"

        candidates.append(
            {
                "region": region_name,
                "subregion": subregion,
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
                "price_position_pct": price_position_pct,
                "budget_status": budget_status,
                "financing_band": financing_band.name,
                "financing_recommendation": financing_band.recommendation,
                "asking_price_krw": observation.get("asking_price_krw") if observation else None,
                "asking_observed_at": observation.get("observed_at") if observation else None,
                "inventory_count": observation.get("inventory_count") if observation else None,
                "asking_source_url": observation.get("source_url") if observation else None,
                "asking_verification_status": observation.get("verification_status") if observation else None,
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

    household_count = item["household_count"]
    if household_count is not None:
        if household_count >= 1000:
            score += 4
        elif household_count >= 500:
            score += 2
        elif household_count <= MAX_EXCLUDED_HOUSEHOLD_COUNT:
            score -= 20
        elif household_count < PREFERRED_MIN_HOUSEHOLD_COUNT:
            score -= 2
    else:
        score -= 6

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
    if item["price_position_pct"] >= 85:
        score -= 2
    walk_minutes = item.get("station_walk_minutes")
    if walk_minutes is not None:
        if walk_minutes <= 10:
            score += 4
        elif walk_minutes <= 15:
            score += 2
        elif walk_minutes <= 20:
            score -= 2
        else:
            score -= 12

    hoga_gap = asking_gap_pct(item)
    if hoga_gap is not None:
        if hoga_gap <= 0:
            score += 2
        elif hoga_gap <= 5:
            score += 1
        elif hoga_gap <= 10:
            score -= 4
        else:
            score -= 8
    return round(score, 2)


def score_seoul_plan(item: dict[str, Any]) -> float:
    latest_price = item["latest_price_krw"]
    if item["region"] != "서울 판교 출퇴근권" or item["excluded"] or latest_price > BUDGET_MAX_KRW:
        return -1_000

    score = 0.0
    score += 18 if latest_price <= BUDGET_REALISTIC_KRW else 8
    score += 10 if item["area_bucket"] == "84" else 8
    score += min(item["trade_count"], 20) * 0.4

    built_year = item["built_year"] or 0
    if built_year >= 2014:
        score += 10
    elif built_year >= 2000:
        score += 7
    elif built_year >= 1990:
        score += 4
    else:
        score += 1

    if item["subregion"] in {"서울 강남구", "서울 서초구"}:
        score += 7
    elif item["subregion"] in {"서울 송파구", "서울 동작구"}:
        score += 5
    elif item["subregion"] in {"서울 관악구", "서울 강동구"}:
        score += 3

    household_count = item["household_count"]
    if household_count is not None:
        if household_count >= 1000:
            score += 3
        elif household_count >= 500:
            score += 2
        elif household_count <= MAX_EXCLUDED_HOUSEHOLD_COUNT:
            score -= 20
        elif household_count < PREFERRED_MIN_HOUSEHOLD_COUNT:
            score -= 2
    else:
        score -= 6

    if item["price_position_pct"] >= 85:
        score -= 2
    walk_minutes = item.get("station_walk_minutes")
    if walk_minutes is not None:
        if walk_minutes <= 10:
            score += 4
        elif walk_minutes <= 15:
            score += 2
        elif walk_minutes <= 20:
            score -= 2
        else:
            score -= 12

    hoga_gap = asking_gap_pct(item)
    if hoga_gap is not None:
        if hoga_gap <= 5:
            score += 1
        elif hoga_gap <= 10:
            score -= 4
        else:
            score -= 8
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


def ranked_seoul_plan(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for item in candidates:
        copy = dict(item)
        copy["score"] = score_seoul_plan(copy)
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


def station_enrichment_pool(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {candidate_key(item): item for item in candidates}
    selected: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for item in ranked(candidates)[:80]:
        selected[candidate_key(item)] = by_key[candidate_key(item)]
    for item in ranked(candidates, older_friendly=True)[:60]:
        selected[candidate_key(item)] = by_key[candidate_key(item)]
    for item in ranked_seoul_plan(candidates)[:80]:
        selected[candidate_key(item)] = by_key[candidate_key(item)]
    for region_name in REGIONS:
        region_candidates = [item for item in candidates if item["region"] == region_name]
        for item in ranked(region_candidates)[:30]:
            selected[candidate_key(item)] = by_key[candidate_key(item)]

    return list(selected.values())


def won_eok(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value / 100_000_000:.2f}억"


def asking_gap_pct(item: dict[str, Any]) -> float | None:
    asking_price = item.get("asking_price_krw")
    latest_price = item.get("latest_price_krw")
    if not asking_price or not latest_price:
        return None
    return round(((asking_price - latest_price) / latest_price) * 100, 1)


def deal_date(item: dict[str, Any]) -> str:
    ym = item["latest_deal_ym"]
    return f"{ym[:4]}.{ym[4:]}.{int(item['latest_deal_day']):02d}"


def display_region(item: dict[str, Any]) -> str:
    if item["region"] == "서울 판교 출퇴근권":
        return item["subregion"]
    return item["region"]


def key_reason(item: dict[str, Any]) -> str:
    reasons: list[str] = []
    reasons.append(item["budget_status"])
    if item["built_year"]:
        reasons.append(f"{item['built_year']}년식")
    reasons.append(liquidity_label(item))
    reasons.append(price_position_label(item))
    reasons.append(station_preference_label(item))
    reasons.append(asking_preference_label(item))
    reasons.append(scale_label(item))
    return " · ".join(reasons)


def household_label(item: dict[str, Any]) -> str:
    household_count = item.get("household_count")
    if household_count is None:
        return "확인 필요"
    return f"{household_count:,}세대"


def liquidity_label(item: dict[str, Any]) -> str:
    trade_count = item["trade_count"]
    if trade_count >= 30:
        return "거래 활발"
    if trade_count >= 10:
        return "거래 보통"
    return "거래 적음"


def price_position_label(item: dict[str, Any]) -> str:
    position = item.get("price_position_pct")
    if position is None:
        return "가격위치 확인 필요"
    if position >= 85:
        return "최근 고점권"
    if position <= 35:
        return "저점권"
    return "중간권"


def scale_label(item: dict[str, Any]) -> str:
    household_count = item.get("household_count")
    if household_count is None:
        return "세대수 검수 미완료"
    if household_count >= 1000:
        return "대단지"
    if household_count >= 500:
        return "중대형 단지"
    if household_count >= PREFERRED_MIN_HOUSEHOLD_COUNT:
        return "중형 단지"
    if household_count > MAX_EXCLUDED_HOUSEHOLD_COUNT:
        return "소형 검토"
    return "소규모 제외"


def asking_price_label(item: dict[str, Any]) -> str:
    asking_price = item.get("asking_price_krw")
    if asking_price is None:
        return "조사 필요"
    observed_at = item.get("asking_observed_at")
    suffix = f"({observed_at})" if observed_at else ""
    return f"{won_eok(asking_price)}{suffix}"


def asking_gap_label(item: dict[str, Any]) -> str:
    gap = asking_gap_pct(item)
    if gap is None:
        return "-"
    return f"{gap:+.1f}%"


def inventory_label(item: dict[str, Any]) -> str:
    inventory_count = item.get("inventory_count")
    if inventory_count is None:
        return "조사 필요"
    return str(inventory_count)


def station_label(item: dict[str, Any]) -> str:
    station_name = item.get("nearest_station_name")
    if not station_name:
        return "확인 필요"
    return station_name


def station_walk_label(item: dict[str, Any]) -> str:
    walk_minutes = item.get("station_walk_minutes")
    if walk_minutes is None:
        return "확인 필요"
    return f"약 {walk_minutes}분"


def station_preference_label(item: dict[str, Any]) -> str:
    walk_minutes = item.get("station_walk_minutes")
    if walk_minutes is None:
        return "역 접근 확인 필요"
    if walk_minutes <= 10:
        return "초역세권"
    if walk_minutes <= 15:
        return "역세권"
    if walk_minutes <= 20:
        return "역 도보권"
    return "역세권 약함"


def asking_preference_label(item: dict[str, Any]) -> str:
    gap = asking_gap_pct(item)
    if gap is None:
        return "호가 조사 필요"
    if gap <= 0:
        return "호가 우호"
    if gap <= 5:
        return "호가 보통"
    if gap <= 10:
        return "호가 부담"
    return "호가 과열"


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
                display_region(item),
                item["name"],
                item["area_bucket"],
                str(item["built_year"] or "-"),
                household_label(item),
                won_eok(item["latest_price_krw"]),
                asking_price_label(item),
                asking_gap_label(item),
                inventory_label(item),
                station_label(item),
                station_walk_label(item),
                deal_date(item),
                str(item["trade_count"]),
                f"{item['price_position_pct']}%",
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
                household_label(item),
                won_eok(item["latest_price_krw"]),
                asking_price_label(item),
                asking_gap_label(item),
                inventory_label(item),
                station_label(item),
                station_walk_label(item),
                deal_date(item),
                item["budget_status"],
                str(item["trade_count"]),
                price_position_label(item),
            ]
        )
    return rows


def count_price_high(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if item.get("price_position_pct", 0) >= 85)


def count_unknown_households(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if item.get("household_count") is None)


def count_unknown_asking(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if item.get("asking_price_krw") is None)


def count_station_over_20(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if (item.get("station_walk_minutes") or 0) > 20)


def insight_rows(final_top10: list[dict[str, Any]], seoul_top10: list[dict[str, Any]]) -> list[list[str]]:
    final_suji_count = sum(1 for item in final_top10 if item["region"] == "용인 수지")
    final_84_count = sum(1 for item in final_top10 if item["area_bucket"] == "84")
    seoul_prices = [item["latest_price_krw"] for item in seoul_top10 if item["latest_price_krw"]]
    seoul_median = int(median(seoul_prices)) if seoul_prices else None
    unknown_scale_count = count_unknown_households(final_top10 + seoul_top10)

    return [
        ["최종 TOP10 수지 비중", f"{final_suji_count}/10", "출퇴근·선호지역 가중치 반영"],
        ["최종 TOP10 84형 비중", f"{final_84_count}/10", "실거주 면적 안정성 확인"],
        ["최근 고점권 후보", f"{count_price_high(final_top10)}/10", "호가 추격 주의"],
        ["역 도보 20분 초과", f"{count_station_over_20(final_top10)}/10", "역세권 선호도 크게 하락"],
        ["호가 미조사", f"{count_unknown_asking(final_top10)}/10", "최저호가·매물 수 보강 필요"],
        ["서울 플랜 중위 실거래", won_eok(seoul_median), "서울 거주 시 면적·연식 타협 필요"],
        ["세대수 미확인", f"{unknown_scale_count}/{len(final_top10) + len(seoul_top10)}", "단지 규모 데이터 보강 필요"],
    ]


def build_blocks(
    *,
    months: list[str],
    final_top10: list[dict[str, Any]],
    seoul_top10: list[dict[str, Any]],
    region_tops: dict[str, list[dict[str, Any]]],
    older_top10: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    start_month, end_month = months[0], months[-1]
    blocks: list[dict[str, Any]] = [
        callout(
            f"랭킹 기준: 국토부 실거래 {start_month[:4]}.{start_month[4:]}~{end_month[:4]}.{end_month[4:]}, "
            "59/84형, 10.5억 이하. 역 도보는 카카오 로컬 직선거리 기반 추정, 호가는 별도 관측값 입력 시 반영.",
        ),
        heading("핵심 인사이트", 2),
        table(["항목", "값", "해석"], insight_rows(final_top10, seoul_top10)),
        divider(),
        heading("최종 TOP10", 2),
        table(
            [
                "순위",
                "지역",
                "단지",
                "평형",
                "연식",
                "세대수",
                "실거래",
                "최저호가",
                "호가갭",
                "매물",
                "가까운 역",
                "역 도보",
                "거래일",
                "거래수",
                "가격위치",
                "판단 지표",
            ],
            top_rows(final_top10),
        ),
        divider(),
        heading("서울 거주 플랜 TOP10", 2),
        paragraph("서울 거주를 우선할 때의 별도 후보군입니다. 같은 예산에서는 면적·연식·생활권 타협 가능성이 큽니다."),
        table(
            [
                "순위",
                "지역",
                "단지",
                "평형",
                "연식",
                "세대수",
                "실거래",
                "최저호가",
                "호가갭",
                "매물",
                "가까운 역",
                "역 도보",
                "거래일",
                "거래수",
                "가격위치",
                "판단 지표",
            ],
            top_rows(seoul_top10),
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
                    [
                        "순위",
                        "단지",
                        "평형",
                        "연식",
                        "세대수",
                        "실거래",
                        "최저호가",
                        "호가갭",
                        "매물",
                        "가까운 역",
                        "역 도보",
                        "거래일",
                        "예산",
                        "거래수",
                        "가격위치",
                    ],
                    regional_rows(items),
                )
            )
        else:
            blocks.append(paragraph("10.5억 이하 59/84 실거래 후보 부족."))

    blocks.extend(
        [
            divider(),
            heading("구축 포함 TOP10", 2),
            paragraph("연식 가점을 낮추고 가격·거래량·입지 우선순위를 더 반영한 후보군입니다."),
            table(
                [
                    "순위",
                    "지역",
                    "단지",
                    "평형",
                    "연식",
                    "세대수",
                    "실거래",
                    "최저호가",
                    "호가갭",
                    "매물",
                    "가까운 역",
                    "역 도보",
                    "거래일",
                    "거래수",
                    "가격위치",
                    "판단 지표",
                ],
                top_rows(older_top10),
            ),
            divider(),
            heading("보강 필요 데이터", 2),
            paragraph("최저호가, 매물 수, 세대수, 주거유형, 실제 보행 경로, 주차/수리 리스크, 생활 인프라."),
            paragraph("출처: 국토교통부 실거래가 공개시스템 API, 카카오 로컬 API. 호가·매물 수·세대수는 별도 데이터 보강 대상."),
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
    seoul_top10: list[dict[str, Any]],
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
        "seoul_living_top10": seoul_top10,
        "regional_top10": region_tops,
        "older_included_top10": older_top10,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish data-backed TOP10 rankings to Notion.")
    parser.add_argument("--months", nargs="+", help="YYYYMM values. Defaults to same month last year through current month.")
    parser.add_argument("--metadata", type=Path, default=Path("data/manual/complex_metadata.csv"))
    parser.add_argument("--observations", type=Path, default=Path("data/manual/market_observations.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/recommendation_rankings.json"))
    parser.add_argument("--skip-notion", action="store_true")
    parser.add_argument("--skip-station-access", action="store_true")
    args = parser.parse_args()

    env = read_env()
    service_key = env.get("PUBLIC_DATA_API_KEY")
    if not service_key:
        raise SystemExit("PUBLIC_DATA_API_KEY is required in .env")

    months = args.months or default_months(date.today())
    candidates = fetch_candidates(
        service_key=service_key,
        months=months,
        metadata_path=args.metadata,
        observations_path=args.observations,
    )
    if not args.skip_station_access:
        enrich_station_access(
            station_enrichment_pool(candidates),
            rest_api_key=env.get("KAKAO_REST_API_KEY"),
        )
    final_top10 = ranked(candidates)[:10]
    seoul_top10 = ranked_seoul_plan(candidates)[:10]
    region_tops = regional_top10(candidates)
    older_top10 = ranked(candidates, older_friendly=True)[:10]

    write_outputs(
        candidates=candidates,
        final_top10=final_top10,
        seoul_top10=seoul_top10,
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
                seoul_top10=seoul_top10,
                region_tops=region_tops,
                older_top10=older_top10,
            ),
        )

    print(
        json.dumps(
            {"final_top10": final_top10, "seoul_living_top10": seoul_top10, "older_top10": older_top10},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
