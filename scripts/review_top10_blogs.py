from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from home_decision_ai.collectors.naver_search import NaverSearchResult
from home_decision_ai.collectors.naver_search import search_naver


POSITIVE_KEYWORDS = [
    "역세권",
    "신분당선",
    "도보",
    "출퇴근",
    "신축",
    "커뮤니티",
    "대단지",
    "브랜드",
    "조용",
    "산책",
    "공원",
    "조망",
    "일조",
    "학군",
    "초등학교",
    "어린이집",
    "상권",
    "마트",
    "병원",
]

NEGATIVE_KEYWORDS = [
    "역 멂",
    "언덕",
    "버스",
    "정체",
    "주차난",
    "소음",
    "층간소음",
    "벌레",
    "냄새",
    "하자",
    "누수",
    "관리비",
    "노후",
    "수리비",
    "상권 부족",
    "학교 거리",
    "공급",
    "고점",
]

REQUIRED_KEYWORDS = [
    "주차",
    "관리비",
    "하자",
    "누수",
    "소음",
    "층간소음",
    "초등학교",
    "학군",
    "병원",
    "마트",
    "상권",
    "역",
    "도보",
    "버스",
    "자차",
    "신분당선",
    "커뮤니티",
    "조경",
    "동간거리",
    "일조",
    "조망",
]

SUMMARY_FIELDS = [
    "generated_date",
    "section",
    "region",
    "subregion",
    "complex_name",
    "area_bucket",
    "reviewed_count",
    "review_status",
    "positive_keywords",
    "negative_keywords",
    "required_keywords",
    "search_query",
    "sample_titles",
    "sample_urls",
]

SOURCE_FIELDS = [
    "generated_date",
    "section",
    "region",
    "subregion",
    "complex_name",
    "area_bucket",
    "rank",
    "title",
    "url",
    "description",
    "pub_date",
    "positive_keywords",
    "negative_keywords",
    "required_keywords",
]


def read_env_value(name: str) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def candidate_identity(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        item.get("subregion") or item.get("region") or "",
        item.get("name") or "",
        str(item.get("built_year") or ""),
        str(item.get("household_count") or ""),
    )


def collect_candidates(rankings: dict[str, Any], *, include_regional: bool) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for section in ("new_build_top10", "all_age_top10"):
        for item in rankings.get(section, []):
            candidates.append((section, item))
    del include_regional

    seen: set[tuple[str, str, str, str]] = set()
    unique: list[tuple[str, dict[str, Any]]] = []
    for section, item in candidates:
        identity = candidate_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append((section, item))
    return unique


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return (
        value.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )


def dedupe_results(results: list[NaverSearchResult]) -> list[NaverSearchResult]:
    seen: set[str] = set()
    deduped: list[NaverSearchResult] = []
    for result in results:
        key = result.link or clean_text(result.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def search_candidate_blogs(
    *,
    client_id: str,
    client_secret: str,
    item: dict[str, Any],
    target_count: int,
    sleep_seconds: float,
) -> tuple[str, list[NaverSearchResult]]:
    name = item["name"]
    subregion = item.get("subregion") or item.get("region") or ""
    queries = [
        f"{name} 아파트 장점 단점",
        f"{name} {subregion} 실거주 후기",
        f"{name} 주차 관리비 소음",
    ]
    all_results: list[NaverSearchResult] = []
    used_query = queries[0]
    for query in queries:
        try:
            results = search_naver(
                client_id=client_id,
                client_secret=client_secret,
                service="blog",
                query=query,
                display=10,
                sort="sim",
            )
        except HTTPError as exc:
            if exc.code == 429 and all_results:
                break
            raise
        all_results = dedupe_results([*all_results, *results])
        if len(all_results) >= target_count:
            used_query = query
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return used_query, all_results[:target_count]


def keyword_summary(results: list[NaverSearchResult], keywords: list[str]) -> str:
    counter: Counter[str] = Counter()
    for result in results:
        text = clean_text(f"{result.title} {result.description}")
        counter.update(match_keywords(text, keywords))
    if not counter:
        return "-"
    return ", ".join(keyword for keyword, _ in counter.most_common(8))


def sample_titles(results: list[NaverSearchResult], limit: int = 3) -> str:
    return " / ".join(clean_text(result.title) for result in results[:limit])


def status_for_count(count: int, target: int) -> str:
    if count >= target:
        return "충족"
    if count > 0:
        return "부족"
    return "없음"


def write_markdown(path: Path, summary_rows: list[dict[str, str]], source_rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# TOP10 블로그 검토 리포트",
        "",
        f"- 생성일: {date.today().isoformat()}",
        "- 기준: 후보별 네이버 블로그 검색 결과 최소 10개",
        "- 해석: 제목/요약 키워드 기반 1차 검토이며 본문 확인 전 확정 판단 금지",
        "",
        "## 요약",
        "",
        "|구분|단지|평형|검토수|상태|장점 키워드|단점 키워드|필수확인 키워드|",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for row in summary_rows:
        lines.append(
            "|{section}|{complex_name}|{area_bucket}|{reviewed_count}|{review_status}|"
            "{positive_keywords}|{negative_keywords}|{required_keywords}|".format(**row)
        )

    lines.extend(["", "## 출처", ""])
    current = None
    for row in source_rows:
        title = f"{row['section']} / {row['complex_name']} {row['area_bucket']}"
        if title != current:
            current = title
            lines.extend(["", f"### {title}", ""])
        lines.append(f"- {row['title']} - {row['url']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review TOP10 candidates with Naver Blog search results.")
    parser.add_argument("--rankings", type=Path, default=Path("data/processed/recommendation_rankings.json"))
    parser.add_argument("--summary-output", type=Path, default=Path("data/processed/blog_review_summary.csv"))
    parser.add_argument("--sources-output", type=Path, default=Path("data/processed/blog_review_sources.csv"))
    parser.add_argument("--markdown-output", type=Path, default=Path("reports/research/top10_blog_review.md"))
    parser.add_argument("--target-count", type=int, default=10)
    parser.add_argument("--include-regional", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.35)
    args = parser.parse_args()

    client_id = read_env_value("NAVER_CLIENT_ID")
    client_secret = read_env_value("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required in .env")

    rankings = json.loads(args.rankings.read_text(encoding="utf-8"))
    candidates = collect_candidates(rankings, include_regional=args.include_regional)
    generated = date.today().isoformat()
    summary_rows: list[dict[str, str]] = []
    source_rows: list[dict[str, str]] = []

    for section, item in candidates:
        query, results = search_candidate_blogs(
            client_id=client_id,
            client_secret=client_secret,
            item=item,
            target_count=args.target_count,
            sleep_seconds=args.sleep_seconds,
        )
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
        positive = keyword_summary(results, POSITIVE_KEYWORDS)
        negative = keyword_summary(results, NEGATIVE_KEYWORDS)
        required = keyword_summary(results, REQUIRED_KEYWORDS)
        summary_rows.append(
            {
                "generated_date": generated,
                "section": section,
                "region": item.get("region") or "",
                "subregion": item.get("subregion") or "",
                "complex_name": item.get("name") or "",
                "area_bucket": item.get("area_bucket") or "",
                "reviewed_count": str(len(results)),
                "review_status": status_for_count(len(results), args.target_count),
                "positive_keywords": positive,
                "negative_keywords": negative,
                "required_keywords": required,
                "search_query": query,
                "sample_titles": sample_titles(results),
                "sample_urls": " / ".join(result.link for result in results[:3]),
            }
        )
        for rank, result in enumerate(results, 1):
            title = clean_text(result.title)
            description = clean_text(result.description)
            text = f"{title} {description}"
            source_rows.append(
                {
                    "generated_date": generated,
                    "section": section,
                    "region": item.get("region") or "",
                    "subregion": item.get("subregion") or "",
                    "complex_name": item.get("name") or "",
                    "area_bucket": item.get("area_bucket") or "",
                    "rank": str(rank),
                    "title": title,
                    "url": result.link,
                    "description": description,
                    "pub_date": result.pub_date or "",
                    "positive_keywords": ", ".join(match_keywords(text, POSITIVE_KEYWORDS)) or "-",
                    "negative_keywords": ", ".join(match_keywords(text, NEGATIVE_KEYWORDS)) or "-",
                    "required_keywords": ", ".join(match_keywords(text, REQUIRED_KEYWORDS)) or "-",
                }
            )

    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)
    with args.sources_output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=SOURCE_FIELDS)
        writer.writeheader()
        writer.writerows(source_rows)
    write_markdown(args.markdown_output, summary_rows, source_rows)
    print(json.dumps({"candidates": len(summary_rows), "sources": len(source_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
