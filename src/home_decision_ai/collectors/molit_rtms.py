from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree


RTMS_APT_TRADE_URL = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
)


@dataclass(frozen=True)
class ApartmentTrade:
    """One apartment trade from MOLIT RTMS public data."""

    apartment_name: str
    lawd_cd: str
    deal_ym: str
    deal_day: str | None
    area_m2: float | None
    floor: int | None
    price_krw: int | None
    built_year: int | None


def parse_price_krw(raw_value: str | None) -> int | None:
    if not raw_value:
        return None
    normalized = raw_value.replace(",", "").strip()
    if not normalized:
        return None
    # The API returns trade amount in 만원.
    return int(normalized) * 10_000


def parse_float(raw_value: str | None) -> float | None:
    if not raw_value or not raw_value.strip():
        return None
    return float(raw_value.strip())


def parse_int(raw_value: str | None) -> int | None:
    if not raw_value or not raw_value.strip():
        return None
    return int(raw_value.strip())


def child_text(item: ElementTree.Element, *names: str) -> str | None:
    for name in names:
        found = item.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return None


def parse_rtms_xml(xml_text: str, lawd_cd: str, deal_ym: str) -> list[ApartmentTrade]:
    root = ElementTree.fromstring(xml_text)
    items = root.findall(".//item")
    trades: list[ApartmentTrade] = []

    for item in items:
        trades.append(
            ApartmentTrade(
                apartment_name=child_text(item, "아파트", "aptNm") or "",
                lawd_cd=lawd_cd,
                deal_ym=deal_ym,
                deal_day=child_text(item, "일", "dealDay"),
                area_m2=parse_float(child_text(item, "전용면적", "excluUseAr")),
                floor=parse_int(child_text(item, "층", "floor")),
                price_krw=parse_price_krw(child_text(item, "거래금액", "dealAmount")),
                built_year=parse_int(child_text(item, "건축년도", "buildYear")),
            )
        )

    return trades


def fetch_apartment_trades(
    *,
    service_key: str,
    lawd_cd: str,
    deal_ym: str,
    rows: int = 1000,
) -> list[ApartmentTrade]:
    """Fetch apartment trades from MOLIT RTMS public API.

    `lawd_cd` is the first five digits of the legal district code.
    `deal_ym` is formatted as YYYYMM.
    """
    query = urlencode(
        {
            "serviceKey": service_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ym,
            "numOfRows": rows,
        }
    )
    with urlopen(f"{RTMS_APT_TRADE_URL}?{query}", timeout=30) as response:
        xml_text = response.read().decode("utf-8")

    return parse_rtms_xml(xml_text, lawd_cd=lawd_cd, deal_ym=deal_ym)
