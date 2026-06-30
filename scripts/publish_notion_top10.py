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
MIN_LATEST_TRADE_PRICE_KRW = 900_000_000
MAX_EXCLUDED_HOUSEHOLD_COUNT = 300
PREFERRED_MIN_HOUSEHOLD_COUNT = 500
WALKING_DISTANCE_PER_MINUTE_M = 60
STATION_SEARCH_RADIUS_M = 5000
MAX_STATION_WALK_MINUTES_EXCLUSIVE = 23
PREFERRED_MAX_AGE_YEARS = 12
STATION_CACHE_PATH = Path("data/processed/station_access_cache.json")
FIVE_YEAR_TRADE_CACHE_PATH = Path("data/processed/five_year_trade_cache.json")
MOLIT_SOURCE_URL = "https://rt.molit.go.kr/"
KAKAO_LOCAL_SOURCE_URL = "https://developers.kakao.com/docs/latest/ko/local/dev-guide"
NAVER_BLOG_SOURCE_URL = "https://developers.naver.com/docs/serviceapi/search/blog/blog.md"

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
        "memo": "9억 이상 10.5억 이하 59/84 실거래만 추림. 생활권·연식·면적 타협 가능성 확인.",
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


def trailing_months(today: date, count: int) -> list[str]:
    current_index = today.year * 12 + today.month - 1
    months: list[str] = []
    for offset in range(count - 1, -1, -1):
        index = current_index - offset
        year, month_index = divmod(index, 12)
        months.append(f"{year:04d}{month_index + 1:02d}")
    return months


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


def load_blog_review_rows(path: Path, limit: int = 20) -> list[list[str]]:
    if not path.exists():
        return []

    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if (row.get("section") or "").strip() not in {
                "new_build_top10",
                "all_age_top10",
            }:
                continue
            positive = (row.get("positive_keywords") or "-").strip()
            negative = (row.get("negative_keywords") or "-").strip()
            required = (row.get("required_keywords") or "-").strip()
            titles = (row.get("sample_titles") or "-").strip()
            if positive != "-":
                summary = f"긍정: {positive[:80]}"
            else:
                summary = "긍정 신호 부족"
            if negative != "-":
                risk = f"주의: {negative[:80]}"
            elif required != "-":
                risk = f"확인: {required[:80]}"
            else:
                risk = "본문 정독 필요"
            rows.append(
                [
                    (row.get("section") or "-").strip(),
                    (row.get("complex_name") or "-").strip(),
                    (row.get("area_bucket") or "-").strip(),
                    (row.get("reviewed_count") or "0").strip(),
                    (row.get("review_status") or "-").strip(),
                    summary,
                    risk,
                    titles[:180],
                ]
            )
            if len(rows) >= limit:
                break
    return rows


def load_blog_analysis(
    summary_path: Path, sources_path: Path
) -> tuple[dict[tuple[str, str, str], dict[str, str]], dict[tuple[str, str, str], list[dict[str, str]]]]:
    summaries: dict[tuple[str, str, str], dict[str, str]] = {}
    sources: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)

    if summary_path.exists():
        with summary_path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                key = (
                    (row.get("region") or "").strip(),
                    (row.get("complex_name") or "").strip(),
                    (row.get("area_bucket") or "").strip(),
                )
                if key[0] and key[1] and key[2] and key not in summaries:
                    summaries[key] = dict(row)

    if sources_path.exists():
        with sources_path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                key = (
                    (row.get("region") or "").strip(),
                    (row.get("complex_name") or "").strip(),
                    (row.get("area_bucket") or "").strip(),
                )
                if key[0] and key[1] and key[2]:
                    sources[key].append(dict(row))

    return summaries, sources


def load_naver_land_mappings(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    if not path.exists():
        return {}

    mappings: dict[tuple[str, str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            region = (row.get("region") or "").strip()
            name = (row.get("complex_name") or "").strip()
            area_value = parse_float(row.get("area_m2"))
            bucket = area_bucket(area_value)
            complex_number = (row.get("naver_complex_number") or "").strip()
            pyeong_type_number = (row.get("pyeong_type_number") or "").strip()
            if not region or not name or bucket is None:
                continue
            if complex_number.upper() == "TODO":
                complex_number = ""
            if pyeong_type_number.upper() == "TODO":
                pyeong_type_number = ""
            mappings[(region, name, bucket)] = {
                "naver_complex_number": complex_number or None,
                "naver_pyeong_type_number": pyeong_type_number or None,
                "naver_real_estate_type": (row.get("real_estate_type") or "APT").strip(),
                "naver_trade_type": (row.get("trade_type") or "A1").strip(),
                "naver_source_url": (row.get("source_url") or "").strip() or None,
                "naver_memo": (row.get("memo") or "").strip() or None,
            }
    return mappings


def exclusion_reasons(metadata: dict[str, Any] | None) -> list[str]:
    if not metadata or metadata.get("exclude_override"):
        return []

    reasons: list[str] = []
    household_count = metadata.get("household_count")
    if household_count is not None and household_count <= MAX_EXCLUDED_HOUSEHOLD_COUNT:
        reasons.append(f"{MAX_EXCLUDED_HOUSEHOLD_COUNT}세대 이하")

    property_type = metadata.get("property_type")
    if property_type in EXCLUDED_PROPERTY_TYPES:
        reasons.append(f"제외 주거유형: {property_type}")
    if property_type == "mixed_use_apartment" and household_count is not None:
        if household_count < PREFERRED_MIN_HOUSEHOLD_COUNT:
            reasons.append(f"{PREFERRED_MIN_HOUSEHOLD_COUNT}세대 미만 주상복합")
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


def percentile(values: list[int], ratio: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def fetch_five_year_histories(
    *,
    service_key: str,
    candidates: list[dict[str, Any]],
    months: list[str],
    cache_path: Path = FIVE_YEAR_TRADE_CACHE_PATH,
) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    target_keys = {candidate_key(item) for item in candidates}
    target_regions = {item["region"] for item in candidates}
    histories: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    cache = load_json_cache(cache_path)
    refresh_months = set(months[-2:])

    for region_name in target_regions:
        region = REGIONS[region_name]
        for subregion, lawd_cd in region["lawd_codes"].items():
            for month in months:
                cache_key = f"{subregion}|{lawd_cd}|{month}"
                if cache_key not in cache or month in refresh_months:
                    cache[cache_key] = [
                        asdict(trade)
                        for trade in fetch_trades_with_retry(
                            service_key=service_key,
                            lawd_cd=lawd_cd,
                            deal_ym=month,
                        )
                    ]
                for trade in cache[cache_key]:
                    bucket = area_bucket(trade.get("area_m2"))
                    if bucket is None:
                        continue
                    key = (region_name, subregion, trade.get("apartment_name") or "", bucket)
                    if key in target_keys and trade.get("price_krw"):
                        histories[key].append(trade)

    save_json_cache(cache_path, cache)
    return histories


def summarize_price_history(
    trades: list[dict[str, Any]], *, recent_months: set[str]
) -> dict[str, Any]:
    prices = [int(item["price_krw"]) for item in trades if item.get("price_krw")]
    recent_prices = [
        int(item["price_krw"])
        for item in trades
        if item.get("price_krw") and item.get("deal_ym") in recent_months
    ]
    yearly: list[dict[str, Any]] = []
    years = sorted({str(item.get("deal_ym") or "")[:4] for item in trades if item.get("deal_ym")})
    for year in years:
        year_prices = sorted(
            int(item["price_krw"])
            for item in trades
            if item.get("price_krw") and str(item.get("deal_ym") or "").startswith(year)
        )
        if not year_prices:
            continue
        yearly.append(
            {
                "year": year,
                "count": len(year_prices),
                "min_price_krw": year_prices[0],
                "median_price_krw": int(median(year_prices)),
                "max_price_krw": year_prices[-1],
            }
        )

    q25 = percentile(recent_prices, 0.25)
    q50 = percentile(recent_prices, 0.50)
    q75 = percentile(recent_prices, 0.75)
    return {
        "trade_count": len(prices),
        "five_year_min_krw": min(prices) if prices else None,
        "five_year_max_krw": max(prices) if prices else None,
        "recent_12m_count": len(recent_prices),
        "recent_12m_q25_krw": q25,
        "recent_12m_median_krw": q50,
        "recent_12m_q75_krw": q75,
        "fair_price_low_krw": q25,
        "fair_price_high_krw": q50,
        "yearly": yearly,
    }


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
    naver_land_path: Path,
) -> list[dict[str, Any]]:
    trades_by_complex: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    metadata_by_complex = load_complex_metadata(metadata_path)
    observations_by_complex = load_market_observations(observations_path)
    naver_mappings_by_complex = load_naver_land_mappings(naver_land_path)

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
        naver_mapping = (
            naver_mappings_by_complex.get((subregion, name, bucket))
            or naver_mappings_by_complex.get((region_name, name, bucket))
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
                "naver_complex_number": naver_mapping.get("naver_complex_number") if naver_mapping else None,
                "naver_pyeong_type_number": (
                    naver_mapping.get("naver_pyeong_type_number") if naver_mapping else None
                ),
                "naver_real_estate_type": (
                    naver_mapping.get("naver_real_estate_type") if naver_mapping else "APT"
                ),
                "naver_trade_type": naver_mapping.get("naver_trade_type") if naver_mapping else "A1",
                "naver_source_url": naver_mapping.get("naver_source_url") if naver_mapping else None,
                "household_count": metadata.get("household_count") if metadata else None,
                "property_type": metadata.get("property_type") if metadata else "unknown",
                "metadata_source_url": metadata.get("source_url") if metadata else None,
                "metadata_memo": metadata.get("memo") if metadata else None,
                "excluded": bool(reasons),
                "exclusion_reasons": reasons,
            }
        )
    return candidates


def station_walk_is_eligible(item: dict[str, Any], *, require_verified: bool) -> bool:
    walk_minutes = item.get("station_walk_minutes")
    if walk_minutes is None:
        return not require_verified
    return walk_minutes < MAX_STATION_WALK_MINUTES_EXCLUSIVE


def new_build_is_eligible(item: dict[str, Any]) -> bool:
    age_years = item.get("age_years")
    return age_years is not None and age_years <= PREFERRED_MAX_AGE_YEARS


def latest_trade_price_is_eligible(item: dict[str, Any]) -> bool:
    latest_price = item.get("latest_price_krw")
    return bool(latest_price and MIN_LATEST_TRADE_PRICE_KRW <= latest_price <= BUDGET_MAX_KRW)


def score_candidate(
    item: dict[str, Any],
    *,
    older_friendly: bool = False,
    require_verified_station: bool = False,
) -> float:
    latest_price = item["latest_price_krw"]
    if item["excluded"] or not latest_trade_price_is_eligible(item):
        return -1_000
    if item["household_count"] is None:
        return -1_000
    if not station_walk_is_eligible(item, require_verified=require_verified_station):
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
        elif walk_minutes < MAX_STATION_WALK_MINUTES_EXCLUSIVE:
            score -= 14
        else:
            score -= 45

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


def score_seoul_plan(item: dict[str, Any], *, require_verified_station: bool = False) -> float:
    latest_price = item["latest_price_krw"]
    if (
        item["region"] != "서울 판교 출퇴근권"
        or item["excluded"]
        or not latest_trade_price_is_eligible(item)
    ):
        return -1_000
    if not station_walk_is_eligible(item, require_verified=require_verified_station):
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
        score -= 10

    if item["price_position_pct"] >= 85:
        score -= 2
    walk_minutes = item.get("station_walk_minutes")
    if walk_minutes is not None:
        if walk_minutes <= 10:
            score += 4
        elif walk_minutes <= 15:
            score += 2
        elif walk_minutes < MAX_STATION_WALK_MINUTES_EXCLUSIVE:
            score -= 14
        else:
            score -= 45

    hoga_gap = asking_gap_pct(item)
    if hoga_gap is not None:
        if hoga_gap <= 5:
            score += 1
        elif hoga_gap <= 10:
            score -= 4
        else:
            score -= 8
    return round(score, 2)


def score_small_household_candidate(
    item: dict[str, Any], *, require_verified_station: bool = False
) -> float:
    latest_price = item["latest_price_krw"]
    household_count = item.get("household_count")
    if household_count is None or household_count > MAX_EXCLUDED_HOUSEHOLD_COUNT:
        return -1_000
    if not latest_trade_price_is_eligible(item):
        return -1_000
    if not station_walk_is_eligible(item, require_verified=require_verified_station):
        return -1_000

    region_priority = REGIONS[item["region"]]["priority"]
    score = 0.0
    score += {1: 28, 2: 16, 3: 8, 4: 5}.get(region_priority, 0)
    score += 14 if latest_price <= BUDGET_REALISTIC_KRW else 6
    score += 8 if item["area_bucket"] == "84" else 7
    score += min(item["trade_count"], 20) * 0.35

    built_year = item["built_year"] or 0
    if built_year >= 2019:
        score += 10
    elif built_year >= 2014:
        score += 8
    elif built_year >= 2006:
        score += 4

    if item["price_position_pct"] >= 85:
        score -= 2
    walk_minutes = item.get("station_walk_minutes")
    if walk_minutes is not None:
        if walk_minutes <= 10:
            score += 4
        elif walk_minutes <= 15:
            score += 2
        elif walk_minutes < MAX_STATION_WALK_MINUTES_EXCLUSIVE:
            score -= 14
        else:
            score -= 40

    # This list is a watchlist, not a buy recommendation.
    score -= 12
    return round(score, 2)


def ranked(
    candidates: list[dict[str, Any]],
    *,
    older_friendly: bool = False,
    require_verified_station: bool = False,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for item in candidates:
        copy = dict(item)
        copy["score"] = score_candidate(
            copy,
            older_friendly=older_friendly,
            require_verified_station=require_verified_station,
        )
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


def dedupe_by_complex(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in items:
        key = (item["region"], item["subregion"], item["name"])
        if key not in selected:
            selected[key] = item
    return list(selected.values())


def ranked_small_household(
    candidates: list[dict[str, Any]], *, require_verified_station: bool = False
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for item in candidates:
        copy = dict(item)
        copy["score"] = score_small_household_candidate(
            copy, require_verified_station=require_verified_station
        )
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


def ranked_seoul_plan(
    candidates: list[dict[str, Any]], *, require_verified_station: bool = False
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for item in candidates:
        copy = dict(item)
        copy["score"] = score_seoul_plan(copy, require_verified_station=require_verified_station)
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
        output[region_name] = dedupe_by_complex(
            ranked(region_candidates, require_verified_station=True)
        )[:10]
    return output


def station_enrichment_pool(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {candidate_key(item): item for item in candidates}
    selected: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    for item in ranked(candidates)[:120]:
        selected[candidate_key(item)] = by_key[candidate_key(item)]
    for item in ranked(candidates, older_friendly=True)[:120]:
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


def naver_land_status_label(item: dict[str, Any]) -> str:
    complex_number = item.get("naver_complex_number")
    pyeong_type_number = item.get("naver_pyeong_type_number")
    if complex_number and pyeong_type_number:
        return "관측 가능"
    if complex_number:
        return "평형번호 미매핑"
    return "단지번호 미매핑"


def asking_price_label(item: dict[str, Any]) -> str:
    asking_price = item.get("asking_price_krw")
    if asking_price is None:
        return "호가 미관측"
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
        return "매물수 미관측"
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
    if walk_minutes < MAX_STATION_WALK_MINUTES_EXCLUSIVE:
        return "역 도보권"
    return "순위 제외"


def asking_preference_label(item: dict[str, Any]) -> str:
    gap = asking_gap_pct(item)
    if gap is None:
        return "호가 미관측"
    if gap <= 0:
        return "호가 우호"
    if gap <= 5:
        return "호가 보통"
    if gap <= 10:
        return "호가 부담"
    return "호가 과열"


def text(content: str, *, bold: bool = False, href: str | None = None) -> dict[str, Any]:
    text_payload: dict[str, Any] = {"content": content[:2000]}
    if href:
        text_payload["link"] = {"url": href}
    return {"type": "text", "text": text_payload, "annotations": {"bold": bold}}


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


def table_cell(value: str | tuple[str, str], *, bold: bool = False) -> list[dict[str, Any]]:
    if isinstance(value, tuple):
        label, href = value
        return [text(label, bold=bold, href=href)]
    return [text(value, bold=bold)]


def table(headers: list[str], rows: list[list[str | tuple[str, str]]]) -> dict[str, Any]:
    children = [
        {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [table_cell(cell, bold=True) for cell in headers]},
        }
    ]
    for row in rows:
        children.append(
            {
                "object": "block",
                "type": "table_row",
                "table_row": {"cells": [table_cell(cell) for cell in row]},
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


def top_rows(
    items: list[dict[str, Any]],
    *,
    analysis_urls: dict[tuple[str, str, str, str], str] | None = None,
) -> list[list[str | tuple[str, str]]]:
    rows: list[list[str | tuple[str, str]]] = []
    for idx, item in enumerate(items, 1):
        row: list[str | tuple[str, str]] = [
                str(idx),
                display_region(item),
                item["name"],
                item["area_bucket"],
                str(item["built_year"] or "-"),
                household_label(item),
                won_eok(item["latest_price_krw"]),
                station_label(item),
                station_walk_label(item),
                deal_date(item),
                str(item["trade_count"]),
                f"{item['price_position_pct']}%",
                key_reason(item),
            ]
        if analysis_urls is not None:
            analysis_url = analysis_urls.get(candidate_key(item))
            row.append(("전체 보기", analysis_url) if analysis_url else "미생성")
        rows.append(row)
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
                station_label(item),
                station_walk_label(item),
                deal_date(item),
                item["budget_status"],
                str(item["trade_count"]),
                price_position_label(item),
            ]
        )
    return rows


def small_household_rows(items: list[dict[str, Any]]) -> list[list[str]]:
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
                station_label(item),
                station_walk_label(item),
                deal_date(item),
                str(item["trade_count"]),
                price_position_label(item),
                " · ".join(item.get("exclusion_reasons") or [f"{MAX_EXCLUDED_HOUSEHOLD_COUNT}세대 이하"]),
            ]
        )
    return rows


def count_price_high(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if item.get("price_position_pct", 0) >= 85)


def count_unknown_households(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if item.get("household_count") is None)


def count_station_ineligible(items: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in items
        if item.get("station_walk_minutes") is None
        or item["station_walk_minutes"] >= MAX_STATION_WALK_MINUTES_EXCLUSIVE
    )


def insight_rows(
    new_build_top10: list[dict[str, Any]], all_age_top10: list[dict[str, Any]]
) -> list[list[str]]:
    return [
        ["신축 후보", str(len(new_build_top10)), "준공 12년 이하만 표시"],
        ["구축 포함 후보", str(len(all_age_top10)), "연식 제한 없이 동일 기준 적용"],
        [
            "신축 84형 비중",
            f"{sum(1 for item in new_build_top10 if item['area_bucket'] == '84')}/{len(new_build_top10)}",
            "실거주 면적 안정성 확인",
        ],
        [
            "최근 고점권 후보",
            f"{count_price_high(all_age_top10)}/{len(all_age_top10)}",
            "호가 추격 주의",
        ],
        [
            "도보·세대수 하드필터 위반",
            str(count_station_ineligible(new_build_top10 + all_age_top10)),
            "도보 23분 이상·300세대 이하 제외",
        ],
    ]


def build_blocks(
    *,
    months: list[str],
    new_build_top10: list[dict[str, Any]],
    all_age_top10: list[dict[str, Any]],
    blog_review_rows: list[list[str]] | None = None,
    analysis_urls: dict[tuple[str, str, str, str], str] | None = None,
) -> list[dict[str, Any]]:
    start_month, end_month = months[0], months[-1]
    blocks: list[dict[str, Any]] = [
        callout(
            f"랭킹 기준: 국토부 실거래 {start_month[:4]}.{start_month[4:]}~{end_month[:4]}.{end_month[4:]}, "
            "59/84형, 최근 실거래 9억 이상 10.5억 이하. 역 도보는 카카오 로컬 직선거리 기반 추정. "
            "동일 단지는 대표 평형 1개만 표시. 도보시간 미확인 또는 23분 이상, 300세대 이하는 제외. "
            "호가와 매물 수는 네이버페이 부동산 관측 안정화 전까지 표와 순위 설명에서 제외.",
        ),
        heading("핵심 인사이트", 2),
        table(["항목", "값", "해석"], insight_rows(new_build_top10, all_age_top10)),
        divider(),
        heading("최종 TOP10 · 신축만", 2),
        paragraph("준공 12년 이하 단지만 대상으로 한 최종 후보입니다."),
        table(
            [
                "순위",
                "지역",
                "단지",
                "평형",
                "연식",
                "세대수",
                "실거래",
                "가까운 역",
                "역 도보",
                "거래일",
                "거래수",
                "가격위치",
                "판단 지표",
                "상세 분석",
            ],
            top_rows(new_build_top10, analysis_urls=analysis_urls or {}),
        ),
        divider(),
        heading("최종 TOP10 · 구축 포함", 2),
        paragraph("연식 제한 없이 가격·거래량·입지·단지 규모를 함께 반영한 최종 후보입니다."),
        table(
            [
                "순위",
                "지역",
                "단지",
                "평형",
                "연식",
                "세대수",
                "실거래",
                "가까운 역",
                "역 도보",
                "거래일",
                "거래수",
                "가격위치",
                "판단 지표",
                "상세 분석",
            ],
            top_rows(all_age_top10, analysis_urls=analysis_urls or {}),
        ),
        divider(),
        heading("블로그 검토 현황", 2),
        paragraph(
            "네이버 블로그 검색 결과를 후보별 최소 10개 기준으로 수집하고, "
            "제목/요약에서 긍정 신호와 리스크 신호를 추출합니다."
        ),
        table(
            ["구분", "단지", "평형", "검토수", "상태", "블로그 요약", "리스크/확인", "근거 제목"],
            blog_review_rows
            or [["미생성", "블로그 검토 리포트 실행 필요", "-", "0", "미완료", "-", "-", "-"]],
        ),
        divider(),
        heading("보강 필요 데이터", 2),
        paragraph("실제 보행 경로, 주차/수리 리스크, 생활 인프라, 블로그/커뮤니티 근거."),
        paragraph(
            "출처: 국토교통부 실거래가 공개시스템 API, 카카오 로컬 API. "
            "호가·매물 수는 네이버페이 부동산 관측 안정화 전까지 별도 수동 확인 대상으로 분리."
        ),
    ]
    return blocks


def blog_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (item["region"], item["name"], item["area_bucket"])


def price_assessment(item: dict[str, Any], analysis: dict[str, Any]) -> str:
    latest = item["latest_price_krw"]
    q25 = analysis.get("recent_12m_q25_krw")
    q50 = analysis.get("recent_12m_median_krw")
    q75 = analysis.get("recent_12m_q75_krw")
    if not q25 or not q50 or not q75:
        return "최근 12개월 비교 거래 부족"
    if latest <= q25:
        return "최근 거래 분포 하단: 가격 우호"
    if latest <= q50:
        return "최근 거래 중앙값 이하: 적정 검토"
    if latest <= q75:
        return "최근 거래 상단: 협상 필요"
    return "최근 거래 75백분위 초과: 추격 주의"


def detail_analysis_blocks(
    *,
    rank: int,
    item: dict[str, Any],
    price_analysis: dict[str, Any],
    blog_summary: dict[str, str] | None,
    blog_sources: list[dict[str, str]],
    history_months: list[str],
) -> list[dict[str, Any]]:
    fair_low = price_analysis.get("fair_price_low_krw")
    fair_high = price_analysis.get("fair_price_high_krw")
    fair_range = (
        f"{won_eok(fair_low)} ~ {won_eok(fair_high)}"
        if fair_low is not None and fair_high is not None
        else "비교 거래 부족"
    )
    basic_rows: list[list[str | tuple[str, str]]] = [
        ["통합 순위", str(rank)],
        ["지역 / 단지", f"{display_region(item)} / {item['name']}"],
        ["대표 전용면적", f"{item['area_bucket']}㎡군 (최근 거래 {item['latest_area_m2']}㎡)"],
        ["준공 / 연식", f"{item['built_year']}년 / {item['age_years']}년차"],
        ["세대수 / 유형", f"{household_label(item)} / {item['property_type']}"],
        ["최근 실거래", f"{won_eok(item['latest_price_krw'])} · {deal_date(item)} · {item['latest_floor']}층"],
        ["최근 13개월", f"{item['trade_count']}건 · {won_eok(item['min_price_krw'])}~{won_eok(item['max_price_krw'])}"],
        ["가격 위치", f"기간 내 {item['price_position_pct']}% · 저점 대비 {item['price_change_from_min_pct']}%"],
        ["역 접근성", f"{station_label(item)} · {item['station_distance_m']}m · {station_walk_label(item)}"],
        ["예산 / 금융 판단", f"{item['budget_status']} · {item['financing_recommendation']}"],
        ["랭킹 점수", str(item["score"])],
        ["메타데이터 메모", item.get("metadata_memo") or "-"],
    ]

    yearly_rows: list[list[str]] = [
        [
            row["year"],
            str(row["count"]),
            won_eok(row["min_price_krw"]),
            won_eok(row["median_price_krw"]),
            won_eok(row["max_price_krw"]),
        ]
        for row in price_analysis.get("yearly", [])
    ] or [["-", "0", "-", "-", "-"]]

    price_rows = [
        ["5년 전체 거래", str(price_analysis.get("trade_count") or 0), "동일 단지·동일 면적군"],
        ["5년 저가~고가", f"{won_eok(price_analysis.get('five_year_min_krw'))} ~ {won_eok(price_analysis.get('five_year_max_krw'))}", "장기 변동 범위"],
        ["최근 12개월 거래", str(price_analysis.get("recent_12m_count") or 0), "적정 가격선 표본"],
        ["최근 12개월 25백분위", won_eok(price_analysis.get("recent_12m_q25_krw")), "협상 목표선"],
        ["최근 12개월 중앙값", won_eok(price_analysis.get("recent_12m_median_krw")), "적정 상단"],
        ["최근 12개월 75백분위", won_eok(price_analysis.get("recent_12m_q75_krw")), "추격 주의 기준"],
        ["적정 매수가 구간", fair_range, "최근 12개월 25백분위~중앙값"],
        ["현재 평가", price_assessment(item, price_analysis), "층·향·수리 상태는 별도 조정"],
    ]

    summary = blog_summary or {}
    blog_summary_rows = [
        ["검토 문서", summary.get("reviewed_count") or str(len(blog_sources))],
        ["긍정 신호", summary.get("positive_keywords") or "유의미한 반복 신호 부족"],
        ["단점·리스크", summary.get("negative_keywords") or "유의미한 반복 신호 부족"],
        ["추가 확인", summary.get("required_keywords") or "본문 정독 및 임장 확인"],
        ["검색어", summary.get("search_query") or f"{item['name']} 아파트 장점 단점"],
    ]
    blog_source_rows: list[list[str | tuple[str, str]]] = []
    for source in blog_sources[:10]:
        blog_source_rows.append(
            [
                source.get("rank") or "-",
                (source.get("title") or "원문", source.get("url") or NAVER_BLOG_SOURCE_URL),
                source.get("pub_date") or "-",
                (source.get("description") or "-")[:350],
                source.get("positive_keywords") or "-",
                source.get("negative_keywords") or "-",
            ]
        )
    if not blog_source_rows:
        blog_source_rows = [["-", "수집 자료 없음", "-", "-", "-", "-"]]

    source_rows: list[list[str | tuple[str, str]]] = [
        ["실거래", ("국토교통부 실거래가 공개시스템", MOLIT_SOURCE_URL)],
        ["세대수·단지유형", ("단지 메타데이터 원문", item.get("metadata_source_url") or MOLIT_SOURCE_URL)],
        ["역 위치·거리", ("카카오 로컬 API", KAKAO_LOCAL_SOURCE_URL)],
        ["블로그 검색", ("네이버 검색 API", NAVER_BLOG_SOURCE_URL)],
    ]

    return [
        callout(
            f"최종 후보 {rank}위 · {item['name']} · 최근 실거래 {won_eok(item['latest_price_krw'])} · "
            f"적정 매수가 {fair_range}"
        ),
        heading("단지·거래 전체 데이터", 2),
        table(["항목", "값"], basic_rows),
        divider(),
        heading("최근 5년 가격 분석", 2),
        paragraph(
            f"분석기간 {history_months[0][:4]}.{history_months[0][4:]}~{history_months[-1][:4]}.{history_months[-1][4:]}. "
            "동일 단지·동일 전용면적군 실거래를 사용합니다. 적정 매수가는 최근 12개월 25백분위~중앙값이며 감정평가액이 아닙니다."
        ),
        table(["연도", "거래수", "최저", "중앙값", "최고"], yearly_rows),
        table(["가격 지표", "값", "해석"], price_rows),
        divider(),
        heading("블로그 장단점 검토", 2),
        table(["항목", "내용"], blog_summary_rows),
        table(["순번", "원문", "작성일", "핵심 내용", "긍정", "부정"], blog_source_rows),
        divider(),
        heading("출처와 미수집 항목", 2),
        table(["데이터", "출처"], source_rows),
        paragraph(
            "현재 자동화에서 호가·매물 수·실제 보행 경로·주차 체감·수리 상태는 확정 데이터가 아닙니다. "
            "블로그 신호는 홍보성 글이 섞일 수 있어 임장 질문을 만드는 보조 근거로만 사용합니다."
        ),
    ]


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
        for attempt in range(1, 4):
            try:
                with urlopen(req, timeout=60) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Notion API failed: {exc.code} {detail}") from exc
            except TimeoutError:
                if attempt == 3:
                    raise
                time.sleep(2 * attempt)
        raise RuntimeError("Notion API request failed.")

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
        preserved_child_pages = {
            "입력 정보 아카이브",
            "자금·대출 시나리오",
            "기흥역센트럴푸르지오 심층 분석",
            "입지 선택 결론 | 기흥역 역세권 vs 수지 준역세권",
            "갈아타기 전략 | 기흥역 84㎡에서 성복역 84㎡로",
            "정책 분석 | 2026 기흥 토허·규제지역 지정",
        }
        for block in self.children(page_id):
            block_type = block["type"]
            # Keep manually managed reference pages alive. Everything else is regenerated.
            if (
                block_type == "child_page"
                and block[block_type].get("title") in preserved_child_pages
            ):
                continue
            endpoint = "pages" if block_type == "child_page" else "blocks"
            self.request("PATCH", f"{endpoint}/{block['id']}", {"archived": True})

    def append_children(self, page_id: str, blocks: list[dict[str, Any]]) -> None:
        for start in range(0, len(blocks), 80):
            self.request("PATCH", f"blocks/{page_id}/children", {"children": blocks[start : start + 80]})

    def create_child_page(
        self, *, parent_page_id: str, title: str, blocks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        page = self.request(
            "POST",
            "pages",
            {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "properties": {"title": {"type": "title", "title": rich_text(title)}},
                "children": blocks[:80],
            },
        )
        if len(blocks) > 80:
            self.append_children(page["id"], blocks[80:])
        return page


def publish_detail_analysis_pages(
    *,
    notion: Notion,
    parent_page_id: str,
    candidates: list[dict[str, Any]],
    price_analyses: dict[tuple[str, str, str, str], dict[str, Any]],
    blog_summaries: dict[tuple[str, str, str], dict[str, str]],
    blog_sources: dict[tuple[str, str, str], list[dict[str, str]]],
    history_months: list[str],
) -> dict[tuple[str, str, str, str], str]:
    urls: dict[tuple[str, str, str, str], str] = {}
    index_page = notion.create_child_page(
        parent_page_id=parent_page_id,
        title="TOP10 후보 상세 분석",
        blocks=[
            callout(
                "신축·구축 포함 TOP10 후보별 전체 데이터, 최근 5년 가격선, "
                "블로그 10건 장단점과 원문 출처를 보관합니다."
            )
        ],
    )
    for rank, item in enumerate(candidates, 1):
        key = candidate_key(item)
        page = notion.create_child_page(
            parent_page_id=index_page["id"],
            title=f"{rank}. {item['name']} {item['area_bucket']}㎡ 전체 분석",
            blocks=detail_analysis_blocks(
                rank=rank,
                item=item,
                price_analysis=price_analyses.get(key, {}),
                blog_summary=blog_summaries.get(blog_key(item)),
                blog_sources=blog_sources.get(blog_key(item), []),
                history_months=history_months,
            ),
        )
        if page.get("url"):
            urls[key] = page["url"]
    return urls


def write_outputs(
    *,
    candidates: list[dict[str, Any]],
    new_build_top10: list[dict[str, Any]],
    all_age_top10: list[dict[str, Any]],
    price_analyses: dict[tuple[str, str, str, str], dict[str, Any]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_date": date.today().isoformat(),
        "source": "MOLIT RTMS apartment trade API",
        "candidate_count": len(candidates),
        "new_build_top10": new_build_top10,
        "all_age_top10": all_age_top10,
        "five_year_price_analyses": {
            "|".join(key): value for key, value in price_analyses.items()
        },
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish data-backed TOP10 rankings to Notion.")
    parser.add_argument("--months", nargs="+", help="YYYYMM values. Defaults to same month last year through current month.")
    parser.add_argument("--metadata", type=Path, default=Path("data/manual/complex_metadata.csv"))
    parser.add_argument("--observations", type=Path, default=Path("data/manual/market_observations.csv"))
    parser.add_argument("--naver-land", type=Path, default=Path("data/manual/naver_land_complexes.csv"))
    parser.add_argument("--blog-review", type=Path, default=Path("data/processed/blog_review_summary.csv"))
    parser.add_argument("--blog-sources", type=Path, default=Path("data/processed/blog_review_sources.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/recommendation_rankings.json"))
    parser.add_argument("--skip-notion", action="store_true")
    parser.add_argument("--skip-station-access", action="store_true")
    parser.add_argument("--skip-five-year-analysis", action="store_true")
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
        naver_land_path=args.naver_land,
    )
    if not args.skip_station_access:
        enrich_station_access(
            station_enrichment_pool(candidates),
            rest_api_key=env.get("KAKAO_REST_API_KEY"),
        )
    new_build_candidates = [item for item in candidates if new_build_is_eligible(item)]
    new_build_top10 = dedupe_by_complex(
        ranked(new_build_candidates, require_verified_station=True)
    )[:10]
    all_age_top10 = dedupe_by_complex(
        ranked(candidates, older_friendly=True, require_verified_station=True)
    )[:10]
    detail_candidates = dedupe_by_complex(new_build_top10 + all_age_top10)
    blog_review_rows = load_blog_review_rows(args.blog_review)
    blog_summaries, blog_sources = load_blog_analysis(args.blog_review, args.blog_sources)
    history_months = trailing_months(date.today(), 60)
    histories: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    if not args.skip_five_year_analysis:
        histories = fetch_five_year_histories(
            service_key=service_key,
            candidates=detail_candidates,
            months=history_months,
        )
    recent_months = set(history_months[-12:])
    price_analyses = {
        candidate_key(item): summarize_price_history(
            histories.get(candidate_key(item), []), recent_months=recent_months
        )
        for item in detail_candidates
    }

    write_outputs(
        candidates=candidates,
        new_build_top10=new_build_top10,
        all_age_top10=all_age_top10,
        price_analyses=price_analyses,
        output_path=args.output,
    )

    if not args.skip_notion:
        notion_key = env.get("NOTION_API_KEY")
        page_id = env.get("NOTION_PARENT_PAGE_ID")
        if not notion_key or not page_id:
            raise SystemExit("NOTION_API_KEY and NOTION_PARENT_PAGE_ID are required in .env")
        notion = Notion(notion_key)
        notion.archive_dashboard_blocks(page_id)
        analysis_urls = publish_detail_analysis_pages(
            notion=notion,
            parent_page_id=page_id,
            candidates=detail_candidates,
            price_analyses=price_analyses,
            blog_summaries=blog_summaries,
            blog_sources=blog_sources,
            history_months=history_months,
        )
        notion.append_children(
            page_id,
            build_blocks(
                months=months,
                new_build_top10=new_build_top10,
                all_age_top10=all_age_top10,
                blog_review_rows=blog_review_rows,
                analysis_urls=analysis_urls,
            ),
        )

    print(
        json.dumps(
            {
                "new_build_top10": new_build_top10,
                "all_age_top10": all_age_top10,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
