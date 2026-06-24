from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


KAKAO_LOCAL_BASE_URL = "https://dapi.kakao.com/v2/local"


@dataclass(frozen=True)
class KakaoPlace:
    place_name: str
    address_name: str
    road_address_name: str
    longitude: float
    latitude: float
    phone: str | None = None
    place_url: str | None = None


def parse_places(data: dict) -> list[KakaoPlace]:
    places: list[KakaoPlace] = []
    for item in data.get("documents", []):
        places.append(
            KakaoPlace(
                place_name=item.get("place_name") or "",
                address_name=item.get("address_name") or "",
                road_address_name=item.get("road_address_name") or "",
                longitude=float(item["x"]),
                latitude=float(item["y"]),
                phone=item.get("phone") or None,
                place_url=item.get("place_url") or None,
            )
        )
    return places


def search_keyword(
    *,
    rest_api_key: str,
    query: str,
    size: int = 5,
) -> list[KakaoPlace]:
    params = urlencode({"query": query, "size": size})
    request = Request(
        f"{KAKAO_LOCAL_BASE_URL}/search/keyword.json?{params}",
        headers={"Authorization": f"KakaoAK {rest_api_key}"},
    )
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return parse_places(data)
