from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ReportDraft:
    title: str
    body_markdown: str


def build_daily_report_stub(report_date: date) -> ReportDraft:
    """Build a deterministic placeholder until real analyzers are implemented."""
    return ReportDraft(
        title=f"{report_date.isoformat()} Daily Briefing",
        body_markdown=(
            "# Daily Briefing\n\n"
            "## 오늘의 핵심\n\n"
            "- TODO: 정책, 관심 단지, 실거래, 호가 데이터를 수집한 뒤 요약합니다.\n\n"
            "## AI 의견\n\n"
            "- TODO: 실거주 관점에서 매수 적기와 리스크를 판단합니다.\n"
        ),
    )
