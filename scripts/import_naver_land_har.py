from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from home_decision_ai.collectors.naver_land import NaverLandObservation
from home_decision_ai.collectors.naver_land import parse_asking_price_har


OBSERVATION_FIELDS = [
    "observed_at",
    "complex_name",
    "region",
    "area_m2",
    "transaction_price_krw",
    "asking_price_krw",
    "inventory_count",
    "source_id",
    "source_url",
    "verification_status",
    "memo",
]

MAPPING_FIELDS = [
    "region",
    "complex_name",
    "naver_complex_number",
    "pyeong_type_number",
    "area_m2",
    "real_estate_type",
    "trade_type",
    "source_url",
    "memo",
]


def append_market_observation(
    path: Path,
    *,
    region: str,
    complex_name: str,
    area_m2: str,
    observation: NaverLandObservation,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OBSERVATION_FIELDS)
        if should_write_header:
            writer.writeheader()
        writer.writerow(
            {
                "observed_at": observation.observed_at[:10],
                "complex_name": complex_name,
                "region": region,
                "area_m2": area_m2,
                "transaction_price_krw": "",
                "asking_price_krw": observation.lowest_asking_price_krw or "",
                "inventory_count": observation.inventory_count or "",
                "source_id": "naverpay_realestate_har",
                "source_url": observation.source_url,
                "verification_status": "needs_verification",
                "memo": "브라우저 HAR에서 추출한 네이버페이 부동산 관측값. 화면 재확인 후 확정.",
            }
        )


def upsert_naver_mapping(
    path: Path,
    *,
    region: str,
    complex_name: str,
    area_m2: str,
    observation: NaverLandObservation,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))

    key = (region, complex_name, area_m2)
    next_row = {
        "region": region,
        "complex_name": complex_name,
        "naver_complex_number": observation.complex_number,
        "pyeong_type_number": observation.pyeong_type_number or "",
        "area_m2": area_m2,
        "real_estate_type": observation.real_estate_type,
        "trade_type": observation.trade_type,
        "source_url": observation.source_url,
        "memo": "브라우저 HAR에서 매핑",
    }

    replaced = False
    for index, row in enumerate(rows):
        if ((row.get("region") or ""), (row.get("complex_name") or ""), (row.get("area_m2") or "")) == key:
            rows[index] = {**row, **next_row}
            replaced = True
            break
    if not replaced:
        rows.append(next_row)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MAPPING_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def choose_observation(
    observations: list[NaverLandObservation],
    *,
    complex_number: str | None,
    pyeong_type_number: str | None,
) -> NaverLandObservation:
    if not observations:
        raise SystemExit("No /complex/askingPrice JSON response found in HAR.")

    filtered = observations
    if complex_number:
        filtered = [item for item in filtered if item.complex_number == complex_number]
    if pyeong_type_number:
        filtered = [item for item in filtered if item.pyeong_type_number == pyeong_type_number]
    if not filtered:
        raise SystemExit("No HAR observation matched the requested complex/pyeong number.")
    return filtered[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Naver Pay Real Estate asking price from a HAR file.")
    parser.add_argument("--har", type=Path, required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--complex-name", required=True)
    parser.add_argument("--area-m2", required=True)
    parser.add_argument("--complex-number")
    parser.add_argument("--pyeong-type-number")
    parser.add_argument("--observations", type=Path, default=Path("data/manual/market_observations.csv"))
    parser.add_argument("--naver-land", type=Path, default=Path("data/manual/naver_land_complexes.csv"))
    args = parser.parse_args()

    observations = parse_asking_price_har(str(args.har))
    selected = choose_observation(
        observations,
        complex_number=args.complex_number,
        pyeong_type_number=args.pyeong_type_number,
    )
    append_market_observation(
        args.observations,
        region=args.region,
        complex_name=args.complex_name,
        area_m2=args.area_m2,
        observation=selected,
    )
    upsert_naver_mapping(
        args.naver_land,
        region=args.region,
        complex_name=args.complex_name,
        area_m2=args.area_m2,
        observation=selected,
    )
    print(json.dumps(asdict(selected), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
