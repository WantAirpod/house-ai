from __future__ import annotations

import argparse
import json

from home_decision_ai.collectors.molit_rtms import fetch_apartment_trades
from home_decision_ai.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch MOLIT apartment trades.")
    parser.add_argument("--lawd-cd", required=True, help="법정동 시군구 코드 앞 5자리")
    parser.add_argument("--deal-ym", required=True, help="거래월 YYYYMM")
    parser.add_argument("--name-contains", default=None, help="단지명 부분 검색어")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.public_data_api_key:
        raise SystemExit("PUBLIC_DATA_API_KEY is required.")

    trades = fetch_apartment_trades(
        service_key=settings.public_data_api_key,
        lawd_cd=args.lawd_cd,
        deal_ym=args.deal_ym,
    )
    if args.name_contains:
        trades = [trade for trade in trades if args.name_contains in trade.apartment_name]

    print(
        json.dumps(
            [trade.__dict__ for trade in trades],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
