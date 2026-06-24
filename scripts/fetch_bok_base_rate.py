from __future__ import annotations

import argparse
import json
from pathlib import Path

from home_decision_ai.collectors.bok_ecos import fetch_base_rate, latest_base_rate


def read_env_value(name: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch 한국은행 기준금리 from ECOS.")
    parser.add_argument("--start-date", required=True, help="YYYYMMDD")
    parser.add_argument("--end-date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    bok_ecos_api_key = read_env_value("BOK_ECOS_API_KEY")
    if not bok_ecos_api_key:
        raise SystemExit("BOK_ECOS_API_KEY is required.")

    observations = fetch_base_rate(
        api_key=bok_ecos_api_key,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    latest = latest_base_rate(observations)
    print(
        json.dumps(
            {
                "latest": latest.__dict__ if latest else None,
                "count": len(observations),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
