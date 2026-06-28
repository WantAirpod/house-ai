# ruff: noqa: E501
from __future__ import annotations

import json
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any

from home_decision_ai.collectors.molit_rtms import fetch_apartment_trades

START_MONTH = "202107"
END_MONTH = "202606"
TARGET_NAME = "기흥역센트럴푸르지오"
REGIONS = {
    "기흥": "41463",
    "수지": "41465",
    "평촌": "41173",
    "하남": "41450",
    "강동": "11740",
}
CACHE_PATH = Path("data/processed/giheung_central_comparison_trades.json")
EXISTING_CACHE_PATH = Path("data/processed/five_year_trade_cache.json")
ANALYSIS_PATH = Path("data/processed/giheung_central_comparison_analysis.json")
CHART_PATH = Path("reports/assets/giheung_central_5y_comparison.svg")
PERIODS = ["2021H2", "2022", "2023", "2024", "2025", "2026H1"]
BASKETS = {
    "기흥 센트럴": [TARGET_NAME],
    "수지": [
        "신명스카이뷰",
        "대지마을현대홈타운3차2단지",
        "포레나 광교상현",
        "써니벨리",
        "힐스테이트광교산",
    ],
    "평촌": ["은하수청구", "한가람(두산)", "한가람(한양)", "한가람(삼성)", "무궁화효성"],
    "하남": [
        "하남힐즈파크푸르지오2단지",
        "미사강변한신휴플러스",
        "대명강변타운",
        "하남풍산아이파크(5단지)",
        "하남풍산아이파크(1단지)",
    ],
    "강동": ["현대1", "동아하이빌아파트", "암사e편한세상", "암사동한솔", "우성"],
}
COLORS = {
    "기흥 센트럴": "#176b48",
    "수지": "#2474a6",
    "평촌": "#c97912",
    "하남": "#b33b32",
    "강동": "#59636f",
}


def read_env_value(name: str) -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"{name} is required")


def month_range(start: str, end: str) -> list[str]:
    year, month = int(start[:4]), int(start[4:])
    end_pair = (int(end[:4]), int(end[4:]))
    values: list[str] = []
    while (year, month) <= end_pair:
        values.append(f"{year:04d}{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return values


def seed_cache() -> dict[str, list[dict[str, Any]]]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    seeded: dict[str, list[dict[str, Any]]] = {}
    if not EXISTING_CACHE_PATH.exists():
        return seeded
    existing = json.loads(EXISTING_CACHE_PATH.read_text())
    name_map = {"용인 기흥": "기흥", "용인 수지": "수지"}
    for key, rows in existing.items():
        old_region, lawd_cd, deal_ym = key.split("|")
        region = name_map.get(old_region)
        if region and START_MONTH <= deal_ym <= END_MONTH:
            seeded[f"{region}|{lawd_cd}|{deal_ym}"] = rows
    return seeded


def collect_trades() -> dict[str, list[dict[str, Any]]]:
    cache = seed_cache()
    service_key = read_env_value("PUBLIC_DATA_API_KEY")
    jobs = [
        (region, lawd_cd, deal_ym)
        for region, lawd_cd in REGIONS.items()
        for deal_ym in month_range(START_MONTH, END_MONTH)
        if f"{region}|{lawd_cd}|{deal_ym}" not in cache
    ]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                fetch_apartment_trades,
                service_key=service_key,
                lawd_cd=lawd_cd,
                deal_ym=deal_ym,
                rows=2000,
            ): (region, lawd_cd, deal_ym)
            for region, lawd_cd, deal_ym in jobs
        }
        for future in as_completed(futures):
            region, lawd_cd, deal_ym = futures[future]
            rows = [asdict(item) for item in future.result()]
            cache[f"{region}|{lawd_cd}|{deal_ym}"] = rows
            print(f"fetched {region} {deal_ym}: {len(rows)}")
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False))
    return cache


def period_label(deal_ym: str) -> str:
    year = int(deal_ym[:4])
    if year == 2021:
        return "2021H2"
    if year == 2026:
        return "2026H1"
    return str(year)


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("values are required")
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def basket_series(
    by_region: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, float | int | None]], dict[str, dict[str, int]]]:
    region_lookup = {
        "기흥 센트럴": "기흥",
        "수지": "수지",
        "평촌": "평촌",
        "하남": "하남",
        "강동": "강동",
    }
    series: dict[str, dict[str, float | int | None]] = {}
    counts: dict[str, dict[str, int]] = {}
    for basket_name, complex_names in BASKETS.items():
        rows = [
            row
            for row in by_region[region_lookup[basket_name]]
            if row["apartment_name"] in complex_names
        ]
        basket_values: dict[str, float | int | None] = {}
        basket_counts: dict[str, int] = {}
        for period in PERIODS:
            complex_medians = []
            count = 0
            for complex_name in complex_names:
                prices = [
                    int(row["price_krw"])
                    for row in rows
                    if row["apartment_name"] == complex_name
                    and period_label(row["deal_ym"]) == period
                ]
                if prices:
                    complex_medians.append(median(prices))
                    count += len(prices)
            basket_values[period] = median(complex_medians) if complex_medians else None
            basket_counts[period] = count
        series[basket_name] = basket_values
        counts[basket_name] = basket_counts
    return series, counts


def summarize_series(series: dict[str, dict[str, float | int | None]]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for name, values in series.items():
        first = values["2021H2"]
        latest = values["2026H1"]
        valid = [float(value) for value in values.values() if value is not None]
        if first is None or latest is None:
            continue
        trough = min(valid)
        peak = max(valid)
        summaries[name] = {
            "change_2021h2_to_2026h1_percent": round((latest / first - 1) * 100, 1),
            "recovery_from_trough_percent": round((latest / trough - 1) * 100, 1),
            "distance_from_peak_percent": round((latest / peak - 1) * 100, 1),
            "latest_median_krw": round(latest),
            "index": {
                period: round(float(value) / float(first) * 100, 1) if value is not None else None
                for period, value in values.items()
            },
        }
    return summaries


def chart_svg(series: dict[str, dict[str, float | int | None]]) -> str:
    width, height = 1200, 700
    left_panel = (70, 130, 500, 450)
    right_panel = (650, 130, 500, 450)
    all_values = [
        float(value) / 100_000_000
        for values in series.values()
        for value in values.values()
        if value is not None
    ]
    absolute_min = math.floor((min(all_values) - 0.5) * 2) / 2
    absolute_max = math.ceil((max(all_values) + 0.5) * 2) / 2

    def points(
        values: list[float], panel: tuple[int, int, int, int], low: float, high: float
    ) -> str:
        x, y, panel_width, panel_height = panel
        coords = []
        for idx, value in enumerate(values):
            px = x + idx * panel_width / (len(values) - 1)
            py = y + panel_height - (value - low) / (high - low) * panel_height
            coords.append(f"{px:.1f},{py:.1f}")
        return " ".join(coords)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="1200" height="700" fill="#ffffff"/>',
        '<text x="70" y="48" font-family="sans-serif" font-size="26" font-weight="700" fill="#17201b">기흥역센트럴푸르지오 vs 유사 가격대 84㎡ 바스켓</text>',
        '<text x="70" y="78" font-family="sans-serif" font-size="14" fill="#667068">국토교통부 실거래 · 지역 바스켓은 단지별 중앙값의 중앙값 · 2021H2~2026H1</text>',
        '<text x="70" y="112" font-family="sans-serif" font-size="16" font-weight="700" fill="#17201b">연도별 중앙가격 (억원)</text>',
        '<text x="650" y="112" font-family="sans-serif" font-size="16" font-weight="700" fill="#17201b">2021H2=100 가격지수</text>',
    ]
    for panel, low, high in ((left_panel, absolute_min, absolute_max), (right_panel, 65, 125)):
        x, y, panel_width, panel_height = panel
        for step in range(6):
            value = low + (high - low) * step / 5
            py = y + panel_height - step * panel_height / 5
            svg.append(
                f'<line x1="{x}" y1="{py:.1f}" x2="{x + panel_width}" y2="{py:.1f}" stroke="#e1e5e1" stroke-width="1"/>'
            )
            svg.append(
                f'<text x="{x - 10}" y="{py + 5:.1f}" text-anchor="end" font-family="sans-serif" font-size="12" fill="#667068">{value:.1f}</text>'
            )
        for idx, period in enumerate(PERIODS):
            px = x + idx * panel_width / (len(PERIODS) - 1)
            svg.append(
                f'<text x="{px:.1f}" y="{y + panel_height + 25}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#667068">{period}</text>'
            )

    for name, values in series.items():
        absolute = [float(values[period]) / 100_000_000 for period in PERIODS]
        base = absolute[0]
        indexed = [value / base * 100 for value in absolute]
        color = COLORS[name]
        stroke_width = 4 if name == "기흥 센트럴" else 2.5
        svg.append(
            f'<polyline points="{points(absolute, left_panel, absolute_min, absolute_max)}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
        svg.append(
            f'<polyline points="{points(indexed, right_panel, 65, 125)}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
        for panel, chart_values, low, high in (
            (left_panel, absolute, absolute_min, absolute_max),
            (right_panel, indexed, 65, 125),
        ):
            x, y, panel_width, panel_height = panel
            for idx, value in enumerate(chart_values):
                px = x + idx * panel_width / (len(chart_values) - 1)
                py = y + panel_height - (value - low) / (high - low) * panel_height
                svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{color}"/>')

    legend_x = 70
    for name, color in COLORS.items():
        svg.append(
            f'<line x1="{legend_x}" y1="650" x2="{legend_x + 28}" y2="650" stroke="{color}" stroke-width="4"/>'
        )
        svg.append(
            f'<text x="{legend_x + 36}" y="655" font-family="sans-serif" font-size="13" fill="#17201b">{name}</text>'
        )
        legend_x += 205
    svg.append("</svg>")
    return "\n".join(svg)


def main() -> None:
    cache = collect_trades()
    by_region: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, rows in cache.items():
        region = key.split("|")[0]
        by_region[region].extend(
            row
            for row in rows
            if row.get("area_m2") and 82 <= float(row["area_m2"]) <= 86 and row.get("price_krw")
        )

    target_rows = [row for row in by_region["기흥"] if row["apartment_name"] == TARGET_NAME]
    recent_start = "202507"
    target_recent = [row["price_krw"] for row in target_rows if row["deal_ym"] >= recent_start]
    target_median = median(target_recent)
    print(f"target recent median={target_median / 100_000_000:.2f}억 n={len(target_recent)}")

    output: dict[str, Any] = {
        "generated_at": date.today().isoformat(),
        "target_recent_median_krw": target_median,
        "regions": {},
    }
    for region, rows in by_region.items():
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["apartment_name"]].append(row)
        candidates = []
        for name, complex_rows in grouped.items():
            recent = [row["price_krw"] for row in complex_rows if row["deal_ym"] >= recent_start]
            if len(recent) < 4 or len(complex_rows) < 15:
                continue
            recent_median = median(recent)
            gap = abs(recent_median - target_median) / target_median
            if gap > 0.25:
                continue
            candidates.append(
                {
                    "name": name,
                    "recent_median_krw": recent_median,
                    "recent_count": len(recent),
                    "five_year_count": len(complex_rows),
                    "built_year": int(
                        median([r["built_year"] for r in complex_rows if r["built_year"]])
                    ),
                    "gap_percent": round(gap * 100, 1),
                }
            )
        candidates.sort(key=lambda item: (item["gap_percent"], -item["recent_count"]))
        output["regions"][region] = candidates[:15]
        print(f"\n[{region}]")
        for item in candidates[:15]:
            print(item)

    Path("data/processed/giheung_central_comparison_candidates.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2)
    )

    series, counts = basket_series(by_region)
    target_recent_prices = [
        int(row["price_krw"]) for row in target_rows if row["deal_ym"] >= recent_start
    ]
    analysis = {
        "generated_at": date.today().isoformat(),
        "period": {"start": START_MONTH, "end": END_MONTH},
        "area_filter_m2": {"min": 82, "max": 86},
        "basket_members": BASKETS,
        "series_krw": series,
        "trade_counts": counts,
        "summaries": summarize_series(series),
        "target_recent_distribution": {
            "count": len(target_recent_prices),
            "min_krw": min(target_recent_prices),
            "q25_krw": round(percentile(target_recent_prices, 0.25)),
            "median_krw": round(percentile(target_recent_prices, 0.5)),
            "q75_krw": round(percentile(target_recent_prices, 0.75)),
            "max_krw": max(target_recent_prices),
            "price_990m_percentile": round(
                sum(value <= 990_000_000 for value in target_recent_prices)
                / len(target_recent_prices)
                * 100,
                1,
            ),
            "price_1030m_percentile": round(
                sum(value <= 1_030_000_000 for value in target_recent_prices)
                / len(target_recent_prices)
                * 100,
                1,
            ),
        },
    }
    ANALYSIS_PATH.write_text(json.dumps(analysis, ensure_ascii=False, indent=2))
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHART_PATH.write_text(chart_svg(series))
    print(f"\nwrote {ANALYSIS_PATH}")
    print(f"wrote {CHART_PATH}")


if __name__ == "__main__":
    main()
