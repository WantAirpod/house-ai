from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from home_decision_ai.config import load_project_config
from home_decision_ai.models.financing import FinancingScenarioInput, calculate_financing_scenario
from home_decision_ai.settings import get_settings


class FinancingCalculatorRequest(BaseModel):
    purchase_price_krw: int = Field(default=990_000_000, ge=0)
    cash_krw: int = Field(default=280_000_000, ge=0)
    lease_deposit_krw: int = Field(default=400_000_000, ge=0)
    lease_loan_krw: int = Field(default=300_000_000, ge=0)
    lease_equity_included_in_cash: bool = True
    combined_gross_income_krw: int = Field(default=150_000_000, gt=0)
    mortgage_amount_krw: int = Field(default=600_000_000, ge=0)
    mortgage_rate_percent: float = Field(default=5.0, ge=0)
    mortgage_term_years: int = Field(default=30, gt=0)
    mortgage_stress_rate_percent: float = Field(default=3.0, ge=0)
    mortgage_stress_ratio_percent: float = Field(default=40.0, ge=0, le=100)
    credit_rate_percent: float = Field(default=6.0, ge=0)
    credit_term_years: int = Field(default=7, gt=0)
    credit_stress_rate_percent: float = Field(default=1.5, ge=0)
    credit_stress_threshold_krw: int = Field(default=100_000_000, ge=0)
    family_loan_amount_krw: int = Field(default=70_000_000, ge=0)
    family_loan_rate_percent: float = Field(default=4.6, ge=0)
    family_loan_term_years: int = Field(default=10, gt=0)
    acquisition_tax_rate_percent: float = Field(default=3.3, ge=0)
    first_time_homebuyer_eligible: bool = False
    first_time_homebuyer_price_limit_krw: int = Field(default=1_200_000_000, ge=0)
    first_time_acquisition_tax_discount_limit_krw: int = Field(default=2_000_000, ge=0)
    local_education_tax_discount_ratio_percent: float = Field(default=10.0, ge=0)
    brokerage_rate_percent: float = Field(default=0.55, ge=0)
    legal_cost_krw: int = Field(default=2_000_000, ge=0)
    card_acquisition_tax: bool = True
    card_brokerage: bool = True
    card_legal_cost: bool = True
    card_installment_months: int = Field(default=12, gt=0)
    card_installment_rate_percent: float = Field(default=0.0, ge=0)
    dsr_warning_percent: float = Field(default=39.0, ge=0)
    dsr_limit_percent: float = Field(default=40.0, gt=0)

    def to_domain(self) -> FinancingScenarioInput:
        return FinancingScenarioInput(**self.model_dump())


def resolve_config_dir(config_dir: str) -> Path:
    path = Path(config_dir)
    if path.is_absolute() or path.exists():
        return path

    project_root = Path(__file__).resolve().parents[3]
    return project_root / config_dir


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.environment,
            "database_configured": settings.is_database_enabled,
            "notion_configured": settings.is_notion_enabled,
        }

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        del request
        regions: list[dict[str, Any]] = []
        watchlist: list[dict[str, Any]] = []
        dashboard_error: str | None = None

        try:
            project_config = load_project_config(resolve_config_dir(settings.config_dir))
            regions = project_config.regions
            watchlist = project_config.watchlist
        except Exception as exc:  # pragma: no cover - defensive dashboard rendering
            dashboard_error = str(exc)

        rows = "\n".join(
            f"<tr><td>{region.get('priority', '-')}</td>"
            f"<td>{region.get('name', '-')}</td>"
            f"<td>{region.get('commute_notes', '-')}</td></tr>"
            for region in regions
        )
        watchlist_rows = "\n".join(
            f"<tr><td>{item.get('status', '-')}</td>"
            f"<td>{item.get('name', '-')}</td>"
            f"<td>{', '.join(str(size) for size in item.get('target_sizes', []))}</td>"
            f"<td>{item.get('max_price_krw', '-')}</td></tr>"
            for item in watchlist
        )
        error_html = (
            f"<section><h2>설정 로딩 오류</h2><p>{dashboard_error}</p></section>"
            if dashboard_error
            else ""
        )
        database_status = "configured" if settings.is_database_enabled else "not configured"
        notion_status = "configured" if settings.is_notion_enabled else "not configured"

        html = f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>home-decision-ai</title>
    <style>
      body {{
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #f7f7f4;
        color: #202124;
      }}
      main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px; }}
      table {{
        width: 100%;
        border-collapse: collapse;
        background: #fff;
        border: 1px solid #deded8;
      }}
      th, td {{
        padding: 12px;
        border-bottom: 1px solid #e9e9e3;
        text-align: left;
        font-size: 14px;
      }}
      th {{ background: #efefe8; }}
      .status {{ display: flex; gap: 12px; flex-wrap: wrap; }}
      .pill {{
        padding: 8px 10px;
        border: 1px solid #d5d5cd;
        background: #fff;
        border-radius: 6px;
        font-size: 14px;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>home-decision-ai</h1>
      <p>실거주 아파트 매수를 위한 부동산 인텔리전스 플랫폼</p>
      <p><a href="/financing-calculator">자금·대출 계산기 열기</a></p>
      <section class="status">
        <div class="pill">Database: {database_status}</div>
        <div class="pill">Notion: {notion_status}</div>
        <div class="pill">Watchlist: {len(watchlist)}</div>
      </section>
      {error_html}
      <section>
        <h2>관심 지역</h2>
        <table>
          <thead><tr><th>우선순위</th><th>지역</th><th>출퇴근 메모</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
      <section>
        <h2>관심 단지 후보</h2>
        <table>
          <thead><tr><th>상태</th><th>이름</th><th>평형</th><th>상한가</th></tr></thead>
          <tbody>{watchlist_rows}</tbody>
        </table>
      </section>
    </main>
  </body>
</html>"""
        return HTMLResponse(html)

    @app.get("/api/briefing/daily")
    def daily_briefing_preview() -> dict[str, object]:
        project_config = load_project_config(resolve_config_dir(settings.config_dir))
        return {
            "status": "draft",
            "message": "Daily briefing generation pipeline is ready for implementation.",
            "sections": [
                "policy_and_rates",
                "watchlist_changes",
                "transactions",
                "asking_prices",
                "ai_opinion",
            ],
            "watchlist_count": len(project_config.watchlist),
        }

    @app.get("/financing-calculator", response_class=HTMLResponse)
    def financing_calculator() -> HTMLResponse:
        template_path = (
            Path(__file__).resolve().parents[1] / "templates" / "financing_calculator.html"
        )
        return HTMLResponse(template_path.read_text(encoding="utf-8"))

    @app.get("/api/financing/defaults")
    def financing_defaults() -> dict[str, object]:
        return FinancingCalculatorRequest().model_dump()

    @app.post("/api/financing/calculate")
    def calculate_financing(values: FinancingCalculatorRequest) -> dict[str, object]:
        return calculate_financing_scenario(values.to_domain())

    return app
