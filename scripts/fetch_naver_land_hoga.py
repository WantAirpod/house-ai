from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from home_decision_ai.collectors.naver_land import NaverLandRateLimitError
from home_decision_ai.collectors.naver_land import extract_complex_number_from_url
from home_decision_ai.collectors.naver_land import fetch_asking_price
from home_decision_ai.collectors.naver_land import fetch_pyeong_list


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


def append_market_observation(
    path: Path,
    *,
    region: str,
    complex_name: str,
    area_m2: str | None,
    observation: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OBSERVATION_FIELDS)
        if should_write_header:
            writer.writeheader()
        writer.writerow(
            {
                "observed_at": str(observation["observed_at"])[:10],
                "complex_name": complex_name,
                "region": region,
                "area_m2": area_m2 or "",
                "transaction_price_krw": "",
                "asking_price_krw": observation.get("lowest_asking_price_krw") or "",
                "inventory_count": observation.get("inventory_count") or "",
                "source_id": "naverpay_realestate",
                "source_url": observation.get("source_url") or "",
                "verification_status": "needs_verification",
                "memo": "네이버페이 부동산 내부 관측 API 기준. 화면/중개사 확인 후 확정.",
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Naver Pay Real Estate asking price observations.")
    parser.add_argument("--complex-number", help="Naver Pay Real Estate complex number.")
    parser.add_argument("--source-url", help="Naver Pay Real Estate complex URL containing complex number.")
    parser.add_argument("--pyeong-type-number", help="Naver pyeong type number. Omit to query all/summary.")
    parser.add_argument("--real-estate-type", default="APT", help="APT, OPST, etc. Default: APT")
    parser.add_argument("--trade-type", default="A1", help="Naver trade type. A1 is sale in current UI.")
    parser.add_argument("--pyeong-list", action="store_true", help="Fetch pyeong list instead of asking price.")
    parser.add_argument("--cookie", help="Optional Cookie header copied from your own browser session.")
    parser.add_argument("--region", help="Region name for CSV append. Example: 용인 수지")
    parser.add_argument("--complex-name", help="Complex name for CSV append.")
    parser.add_argument("--area-m2", help="Exclusive area for CSV append. Example: 84")
    parser.add_argument(
        "--append-observation",
        type=Path,
        help="Append successful asking-price observation to this CSV path.",
    )
    args = parser.parse_args()

    complex_number = args.complex_number
    if not complex_number and args.source_url:
        complex_number = extract_complex_number_from_url(args.source_url)
    if not complex_number:
        raise SystemExit("--complex-number or --source-url with a complex number is required.")

    try:
        if args.pyeong_list:
            payload = [
                asdict(item)
                for item in fetch_pyeong_list(complex_number=complex_number, cookie=args.cookie)
            ]
        else:
            payload = asdict(
                fetch_asking_price(
                    complex_number=complex_number,
                    pyeong_type_number=args.pyeong_type_number,
                    real_estate_type=args.real_estate_type,
                    trade_type=args.trade_type,
                    cookie=args.cookie,
                )
            )
            if args.append_observation:
                if not args.region or not args.complex_name:
                    raise SystemExit("--region and --complex-name are required with --append-observation.")
                append_market_observation(
                    args.append_observation,
                    region=args.region,
                    complex_name=args.complex_name,
                    area_m2=args.area_m2,
                    observation=payload,
                )
    except NaverLandRateLimitError as exc:
        raise SystemExit(
            "Naver Pay Real Estate returned 429. It has no official public asking-price API. "
            "Retry at low frequency with your own browser Cookie header if permitted, "
            "or enter the observation manually in data/manual/market_observations.csv."
        ) from exc

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
