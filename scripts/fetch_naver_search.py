from __future__ import annotations

import argparse
import json
from pathlib import Path

from home_decision_ai.collectors.naver_search import search_naver


def read_env_value(name: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Naver Search API results.")
    parser.add_argument("--service", default="news", help="news, blog, cafearticle, etc.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--display", type=int, default=5)
    parser.add_argument("--sort", default="date")
    args = parser.parse_args()

    client_id = read_env_value("NAVER_CLIENT_ID")
    client_secret = read_env_value("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required.")

    results = search_naver(
        client_id=client_id,
        client_secret=client_secret,
        service=args.service,
        query=args.query,
        display=args.display,
        sort=args.sort,
    )
    print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
