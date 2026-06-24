from __future__ import annotations

import argparse
import json
from pathlib import Path

from home_decision_ai.collectors.kakao_local import search_keyword


def read_env_value(name: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Search places with Kakao Local API.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--size", type=int, default=5)
    args = parser.parse_args()

    api_key = read_env_value("KAKAO_REST_API_KEY")
    if not api_key:
        raise SystemExit("KAKAO_REST_API_KEY is required.")

    places = search_keyword(rest_api_key=api_key, query=args.query, size=args.size)
    print(json.dumps([place.__dict__ for place in places], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
