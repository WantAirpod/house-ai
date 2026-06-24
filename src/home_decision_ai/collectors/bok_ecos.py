from __future__ import annotations

from dataclasses import dataclass
from urllib.request import urlopen

import json


ECOS_BASE_URL = "https://ecos.bok.or.kr/api"
BASE_RATE_STAT_CODE = "722Y001"
BASE_RATE_ITEM_CODE = "0101000"


@dataclass(frozen=True)
class BaseRateObservation:
    """One 한국은행 기준금리 observation from ECOS."""

    observed_date: str
    value_percent: float
    stat_code: str = BASE_RATE_STAT_CODE
    item_code: str = BASE_RATE_ITEM_CODE
    source: str = "한국은행 ECOS"


def parse_base_rate_rows(data: dict) -> list[BaseRateObservation]:
    rows = data.get("StatisticSearch", {}).get("row", [])
    observations: list[BaseRateObservation] = []
    for row in rows:
        observations.append(
            BaseRateObservation(
                observed_date=row["TIME"],
                value_percent=float(row["DATA_VALUE"]),
            )
        )
    return observations


def fetch_base_rate(
    *,
    api_key: str,
    start_date: str,
    end_date: str,
    rows: int = 300,
) -> list[BaseRateObservation]:
    """Fetch 한국은행 기준금리 from ECOS.

    Dates use YYYYMMDD format. The ECOS series is daily and repeats the current
    base rate until a policy change.
    """
    url = (
        f"{ECOS_BASE_URL}/StatisticSearch/{api_key}/json/kr/1/{rows}/"
        f"{BASE_RATE_STAT_CODE}/D/{start_date}/{end_date}/{BASE_RATE_ITEM_CODE}"
    )
    with urlopen(url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return parse_base_rate_rows(data)


def latest_base_rate(observations: list[BaseRateObservation]) -> BaseRateObservation | None:
    if not observations:
        return None
    return max(observations, key=lambda observation: observation.observed_date)
