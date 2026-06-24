from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NAVER_SEARCH_BASE_URL = "https://openapi.naver.com/v1/search"


@dataclass(frozen=True)
class NaverSearchResult:
    title: str
    link: str
    description: str
    pub_date: str | None = None


def clean_html_text(value: str | None) -> str:
    if not value:
        return ""
    no_tags = re.sub(r"<[^>]+>", "", value)
    return unescape(no_tags).strip()


def parse_search_results(data: dict) -> list[NaverSearchResult]:
    results: list[NaverSearchResult] = []
    for item in data.get("items", []):
        results.append(
            NaverSearchResult(
                title=clean_html_text(item.get("title")),
                link=item.get("originallink") or item.get("link") or "",
                description=clean_html_text(item.get("description")),
                pub_date=item.get("pubDate") or item.get("postdate"),
            )
        )
    return results


def search_naver(
    *,
    client_id: str,
    client_secret: str,
    service: str,
    query: str,
    display: int = 10,
    sort: str = "date",
) -> list[NaverSearchResult]:
    """Search Naver OpenAPI.

    Supported services include `news`, `blog`, and other Naver Search API
    endpoints. This is not a Naver Real Estate listing API.
    """
    params = urlencode(
        {
            "query": query,
            "display": display,
            "sort": sort,
        }
    )
    request = Request(
        f"{NAVER_SEARCH_BASE_URL}/{service}.json?{params}",
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
    )
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return parse_search_results(data)
