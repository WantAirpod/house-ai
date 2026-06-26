from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from home_decision_ai.collectors.kapt import fetch_basic_info
from home_decision_ai.collectors.kapt import fetch_complexes_by_legal_dong
from home_decision_ai.collectors.kapt import fetch_detail_info


def read_env_value(name: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch K-apt complex basic/detail information.")
    parser.add_argument("--bjd-code", help="Legal dong code. Example: 4146510100")
    parser.add_argument("--kapt-code", help="K-apt complex code.")
    parser.add_argument("--name-contains", help="Filter complex list by name substring.")
    args = parser.parse_args()

    service_key = read_env_value("PUBLIC_DATA_API_KEY")
    if not service_key:
        raise SystemExit("PUBLIC_DATA_API_KEY is required in .env")

    kapt_code = args.kapt_code
    if args.bjd_code:
        complexes = fetch_complexes_by_legal_dong(
            service_key=service_key,
            bjd_code=args.bjd_code,
        )
        if args.name_contains:
            complexes = [item for item in complexes if args.name_contains in item.name]
        if not kapt_code:
            print(json.dumps([asdict(item) for item in complexes], ensure_ascii=False, indent=2))
            return
        print(json.dumps([asdict(item) for item in complexes], ensure_ascii=False, indent=2))

    if not kapt_code:
        raise SystemExit("--kapt-code or --bjd-code is required.")

    basic = fetch_basic_info(service_key=service_key, kapt_code=kapt_code)
    detail = fetch_detail_info(service_key=service_key, kapt_code=kapt_code)
    payload = {
        "basic": asdict(basic) if basic else None,
        "detail": asdict(detail) if detail else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
