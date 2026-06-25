from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from home_decision_ai.collectors.molit_rtms import fetch_apartment_trades


DEFAULT_REGIONS = {
    "용인 수지": "41465",
    "용인 기흥": "41463",
    "용인 처인": "41461",
}

EXCLUDED_PROPERTY_TYPES = {
    "officetel",
    "officetel_apartment",
    "urban_living_housing",
    "non_apartment",
}


def read_env_value(name: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1]
    return None


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


def load_complex_metadata(path: Path | None) -> dict[tuple[str, str], dict]:
    if path is None or not path.exists():
        return {}

    metadata: dict[tuple[str, str], dict] = {}
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


def exclusion_reasons(
    metadata: dict | None,
    *,
    min_household_count: int,
    excluded_property_types: set[str],
) -> list[str]:
    if not metadata or metadata.get("exclude_override"):
        return []

    reasons: list[str] = []
    household_count = metadata.get("household_count")
    if household_count is not None and household_count < min_household_count:
        reasons.append(f"{min_household_count}세대 미만")

    property_type = metadata.get("property_type")
    if property_type in excluded_property_types:
        reasons.append(f"제외 주거유형: {property_type}")

    return reasons


def review_candidates(
    *,
    service_key: str,
    months: list[str],
    budget_upper_krw: int,
    metadata_path: Path | None = None,
    min_household_count: int = 300,
    excluded_property_types: set[str] | None = None,
    include_excluded: bool = False,
) -> list[dict]:
    trades_by_complex: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    metadata_by_complex = load_complex_metadata(metadata_path)
    excluded_types = excluded_property_types or EXCLUDED_PROPERTY_TYPES

    for region_name, lawd_cd in DEFAULT_REGIONS.items():
        for month in months:
            trades = fetch_apartment_trades(
                service_key=service_key,
                lawd_cd=lawd_cd,
                deal_ym=month,
            )
            for trade in trades:
                bucket = area_bucket(trade.area_m2)
                if not bucket:
                    continue
                item = asdict(trade)
                item["region"] = region_name
                item["bucket"] = bucket
                trades_by_complex[(region_name, trade.apartment_name, bucket)].append(item)

    summaries: list[dict] = []
    for (region, name, bucket), trades in trades_by_complex.items():
        prices = [trade["price_krw"] for trade in trades if trade["price_krw"]]
        if not prices:
            continue
        trades_sorted = sorted(trades, key=lambda t: (t["deal_ym"], int(t["deal_day"] or 0)))
        latest = trades_sorted[-1]
        built_years = [trade["built_year"] for trade in trades if trade["built_year"]]
        built_year = max(set(built_years), key=built_years.count) if built_years else None
        min_price = min(prices)
        max_price = max(prices)
        if max_price <= budget_upper_krw:
            budget_status = "적합"
        elif min_price <= budget_upper_krw:
            budget_status = "경계"
        else:
            budget_status = "초과"
        metadata = metadata_by_complex.get((region, name))
        reasons = exclusion_reasons(
            metadata,
            min_household_count=min_household_count,
            excluded_property_types=excluded_types,
        )
        if reasons and not include_excluded:
            continue
        summaries.append(
            {
                "region": region,
                "name": name,
                "area_bucket": bucket,
                "built_year": built_year,
                "trade_count": len(prices),
                "min_price_krw": min_price,
                "max_price_krw": max_price,
                "latest_price_krw": latest["price_krw"],
                "latest_deal_ym": latest["deal_ym"],
                "latest_deal_day": latest["deal_day"],
                "latest_area_m2": latest["area_m2"],
                "latest_floor": latest["floor"],
                "budget_status": budget_status,
                "household_count": metadata.get("household_count") if metadata else None,
                "property_type": metadata.get("property_type") if metadata else "unknown",
                "excluded": bool(reasons),
                "exclusion_reasons": reasons,
            }
        )

    region_score = {"용인 수지": 3, "용인 기흥": 2, "용인 처인": 1}
    status_score = {"적합": 3, "경계": 2, "초과": 1}
    return sorted(
        summaries,
        key=lambda item: (
            status_score.get(item["budget_status"], 0),
            1 if (item["built_year"] or 0) >= 2014 else 0,
            region_score.get(item["region"], 0),
            item["trade_count"],
            -(item["latest_price_krw"] or 0),
        ),
        reverse=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Review apartment candidates using MOLIT RTMS.")
    parser.add_argument("--months", nargs="+", required=True, help="YYYYMM values")
    parser.add_argument("--budget-upper-krw", type=int, default=1_050_000_000)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("data/manual/complex_metadata.csv"),
        help="CSV with region, complex_name, household_count, property_type, exclude_override.",
    )
    parser.add_argument("--min-household-count", type=int, default=300)
    parser.add_argument("--include-excluded", action="store_true")
    args = parser.parse_args()

    service_key = read_env_value("PUBLIC_DATA_API_KEY")
    if not service_key:
        raise SystemExit("PUBLIC_DATA_API_KEY is required.")

    summaries = review_candidates(
        service_key=service_key,
        months=args.months,
        budget_upper_krw=args.budget_upper_krw,
        metadata_path=args.metadata,
        min_household_count=args.min_household_count,
        include_excluded=args.include_excluded,
    )
    print(json.dumps(summaries[: args.limit], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
