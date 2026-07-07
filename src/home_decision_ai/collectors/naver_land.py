from __future__ import annotations

import json
import os
import re
from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


NAVER_LAND_BASE_URL = "https://fin.land.naver.com/front-api/v1"
NAVER_LAND_REFERER = "https://fin.land.naver.com/map"


class NaverLandError(RuntimeError):
    """Base error for Naver Pay Real Estate observation requests."""


class NaverLandRateLimitError(NaverLandError):
    """Raised when Naver Pay Real Estate returns 429."""


@dataclass(frozen=True)
class NaverLandPyeong:
    pyeong_type_number: str
    name: str | None
    exclusive_area_m2: float | None
    supply_area_m2: float | None


@dataclass(frozen=True)
class NaverLandObservation:
    complex_number: str
    pyeong_type_number: str | None
    real_estate_type: str
    trade_type: str
    observed_at: str
    lowest_asking_price_krw: int | None
    highest_asking_price_krw: int | None
    inventory_count: int | None
    source_url: str
    raw_status: str


def observation_source_url(complex_number: str) -> str:
    return f"https://fin.land.naver.com/complexes/{complex_number}"


def extract_complex_number_from_url(url: str) -> str | None:
    """Extract a Naver complex number from common Naver Pay Real Estate URLs."""
    parsed = urlparse(url)
    path_match = re.search(r"/complexes/(\d+)", parsed.path)
    if path_match:
        return path_match.group(1)
    query = parse_qs(parsed.query)
    for key in ("complexNumber", "complexNo", "complexId"):
        values = query.get(key)
        if values and values[0].isdigit():
            return values[0]
    return None


def extract_pyeong_type_number_from_url(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    for key in ("pyeongTypeNumber", "pyeongTypeNo", "ptpNo"):
        values = query.get(key)
        if values and values[0]:
            return values[0]
    return None


def load_har_json_responses(path: str) -> list[tuple[str, dict[str, Any]]]:
    """Load JSON responses from a browser HAR export."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    responses: list[tuple[str, dict[str, Any]]] = []
    for entry in data.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        response = entry.get("response", {})
        content = response.get("content", {})
        url = request.get("url") or ""
        text_value = content.get("text")
        if not url or not text_value:
            continue
        if content.get("encoding") == "base64":
            try:
                text_value = b64decode(text_value).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                continue
        try:
            responses.append((url, json.loads(text_value)))
        except json.JSONDecodeError:
            continue
    return responses


def parse_asking_price_har(path: str) -> list[NaverLandObservation]:
    observations: list[NaverLandObservation] = []
    for url, data in load_har_json_responses(path):
        if "/front-api/v1/complex/askingPrice" not in url:
            continue
        complex_number = extract_complex_number_from_url(url)
        if not complex_number:
            continue
        query = parse_qs(urlparse(url).query)
        observation = parse_observation_response(
            data,
            complex_number=complex_number,
            pyeong_type_number=extract_pyeong_type_number_from_url(url),
            real_estate_type=(query.get("realEstateType") or ["APT"])[0],
            trade_type=(query.get("tradeType") or ["A1"])[0],
        )
        observations.append(observation)
    return observations


def parse_korean_price_to_krw(value: Any) -> int | None:
    """Parse Naver-style prices into KRW.

    Naver responses can expose prices as integers, strings with won units, or
    display strings such as "10억 5,000". This parser keeps the collector
    tolerant because the internal API schema is not public.
    """
    if value is None:
        return None
    if isinstance(value, int):
        # Most real-estate API payloads use 만원. Very large values are already KRW.
        return value if value >= 10_000_000 else value * 10_000
    if isinstance(value, float):
        return parse_korean_price_to_krw(int(value))

    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if text.isdigit():
        return parse_korean_price_to_krw(int(text))

    eok = 0
    man = 0
    eok_match = re.search(r"(\d+(?:\.\d+)?)\s*억", text)
    if eok_match:
        eok = int(float(eok_match.group(1)) * 100_000_000)
    after_eok = text.split("억", 1)[1] if "억" in text else text
    man_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:만)?", after_eok)
    if man_match and man_match.group(1):
        man = int(float(man_match.group(1)) * 10_000)
    return eok + man if eok or man else None


def pick_list(data: dict[str, Any], *paths: tuple[str, ...]) -> list[dict[str, Any]]:
    for path in paths:
        value: Any = data
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def parse_pyeong_list_response(data: dict[str, Any]) -> list[NaverLandPyeong]:
    items = pick_list(
        data,
        ("result", "pyeongList"),
        ("result", "list"),
        ("data", "pyeongList"),
        ("data", "list"),
        ("pyeongList",),
        ("list",),
    )
    result: list[NaverLandPyeong] = []
    for item in items:
        pyeong_type_number = first_present(
            item,
            "pyeongTypeNumber",
            "pyeongNo",
            "pyeongTypeNo",
            "ptpNo",
        )
        if pyeong_type_number is None:
            continue
        result.append(
            NaverLandPyeong(
                pyeong_type_number=str(pyeong_type_number),
                name=first_present(item, "pyeongName", "name", "pyeongNm"),
                exclusive_area_m2=_parse_float(
                    first_present(item, "exclusiveArea", "exclusiveAreaM2", "exclArea")
                ),
                supply_area_m2=_parse_float(first_present(item, "supplyArea", "supplyAreaM2")),
            )
        )
    return result


def parse_observation_response(
    data: dict[str, Any],
    *,
    complex_number: str,
    pyeong_type_number: str | None,
    real_estate_type: str,
    trade_type: str,
) -> NaverLandObservation:
    flat = _flatten_dict(data)
    low = _first_price(flat, "min", "minimum", "lowest", "low")
    high = _first_price(flat, "max", "maximum", "highest", "high")
    count = _first_int(flat, "count", "cnt", "articleCount", "inventory")
    return NaverLandObservation(
        complex_number=complex_number,
        pyeong_type_number=pyeong_type_number,
        real_estate_type=real_estate_type,
        trade_type=trade_type,
        observed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        lowest_asking_price_krw=low,
        highest_asking_price_krw=high,
        inventory_count=count,
        source_url=observation_source_url(complex_number),
        raw_status="observed",
    )


def fetch_pyeong_list(*, complex_number: str, cookie: str | None = None) -> list[NaverLandPyeong]:
    data = _request_json("GET", "/complex/pyeongList", {"complexNumber": complex_number}, cookie)
    return parse_pyeong_list_response(data)


def fetch_asking_price(
    *,
    complex_number: str,
    pyeong_type_number: str | None = None,
    real_estate_type: str = "APT",
    trade_type: str = "A1",
    cookie: str | None = None,
) -> NaverLandObservation:
    params = {
        "complexNumber": complex_number,
        "realEstateType": real_estate_type,
        "tradeType": trade_type,
    }
    if pyeong_type_number:
        params["pyeongTypeNumber"] = pyeong_type_number
    data = _request_json("GET", "/complex/askingPrice", params, cookie)
    return parse_observation_response(
        data,
        complex_number=complex_number,
        pyeong_type_number=pyeong_type_number,
        real_estate_type=real_estate_type,
        trade_type=trade_type,
    )


def _request_json(
    method: str,
    path: str,
    params: dict[str, object],
    cookie: str | None = None,
) -> dict[str, Any]:
    url = f"{NAVER_LAND_BASE_URL}{path}"
    data = None
    if method.upper() == "GET":
        url = f"{url}?{urlencode(params)}"
    else:
        data = json.dumps(params).encode("utf-8")

    request_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://fin.land.naver.com",
        "Referer": NAVER_LAND_REFERER,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": os.getenv(
            "NAVER_LAND_USER_AGENT",
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
        ),
    }
    request_cookie = cookie or os.getenv("NAVER_LAND_COOKIE")
    if request_cookie:
        request_headers["Cookie"] = request_cookie

    request = Request(
        url,
        data=data,
        method=method.upper(),
        headers=request_headers,
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            raise NaverLandRateLimitError("Naver Pay Real Estate returned 429.") from exc
        raise NaverLandError(f"Naver Pay Real Estate HTTP {exc.code}: {body[:300]}") from exc


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _flatten_dict(value: Any) -> dict[str, Any]:
    flat: dict[str, Any] = {}

    def visit(prefix: str, item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                visit(next_prefix, nested)
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                visit(f"{prefix}.{index}", nested)
        else:
            flat[prefix] = item

    visit("", value)
    return flat


def _first_price(flat: dict[str, Any], *name_parts: str) -> int | None:
    for key, value in flat.items():
        lowered = key.lower()
        if any(part in lowered for part in name_parts) and "price" in lowered:
            parsed = parse_korean_price_to_krw(value)
            if parsed is not None:
                return parsed
    return None


def _first_int(flat: dict[str, Any], *name_parts: str) -> int | None:
    for key, value in flat.items():
        lowered = key.lower()
        if not any(part.lower() in lowered for part in name_parts):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.replace(",", "").strip().isdigit():
            return int(value.replace(",", "").strip())
    return None
