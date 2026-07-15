from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from home_decision_ai.config import load_project_config
from home_decision_ai.db import session as db_session
from home_decision_ai.db.base import Base
from home_decision_ai.db.models import FinancingCalculatorShare
from home_decision_ai.models.financing import FinancingScenarioInput, calculate_financing_scenario
from home_decision_ai.settings import get_settings


class FinancingCalculatorRequest(BaseModel):
    purchase_price_krw: int = Field(default=1_017_000_000, ge=0)
    cash_krw: int = Field(default=290_000_000, ge=0)
    lease_deposit_krw: int = Field(default=0, ge=0)
    lease_loan_krw: int = Field(default=0, ge=0)
    lease_equity_included_in_cash: bool = True
    combined_gross_income_krw: int = Field(default=145_400_000, gt=0)
    borrower_gross_income_krw: int = Field(default=97_400_000, ge=0)
    spouse_gross_income_krw: int = Field(default=48_000_000, ge=0)
    borrower_mortgage_share_percent: float = Field(default=100.0, ge=0, le=100)
    mortgage_amount_krw: int = Field(default=600_000_000, ge=0)
    collateral_value_krw: int = Field(default=0, ge=0)
    ltv_ratio_percent: float = Field(default=70.0, ge=0, le=100)
    mortgage_policy_cap_krw: int = Field(default=600_000_000, ge=0)
    room_deduction_enabled: bool = False
    room_deduction_amount_krw: int = Field(default=48_000_000, ge=0)
    mortgage_rate_percent: float = Field(default=4.7, ge=0)
    mortgage_term_years: int = Field(default=40, gt=0)
    mortgage_stress_rate_percent: float = Field(default=2.31, ge=0)
    mortgage_stress_ratio_percent: float = Field(default=100.0, ge=0, le=100)
    credit_rate_percent: float = Field(default=6.5, ge=0)
    credit_term_years: int = Field(default=5, gt=0)
    credit_income_limit_ratio_percent: float = Field(default=100.0, ge=0)
    borrower_credit_income_limit_ratio_percent: float = Field(default=100.0, ge=0)
    spouse_credit_income_limit_ratio_percent: float = Field(default=80.0, ge=0)
    credit_stress_rate_percent: float = Field(default=1.5, ge=0)
    credit_stress_threshold_krw: int = Field(default=100_000_000, ge=0)
    family_loan_amount_krw: int = Field(default=65_000_000, ge=0)
    family_loan_rate_percent: float = Field(default=4.6, ge=0)
    family_loan_term_years: int = Field(default=10, gt=0)
    family_loan_repayment_type: Literal["bullet", "amortizing"] = "bullet"
    family_principal_reserve_enabled: bool = False
    acquisition_tax_rate_percent: float = Field(default=3.3, ge=0)
    first_time_homebuyer_eligible: bool = True
    first_time_homebuyer_price_limit_krw: int = Field(default=1_200_000_000, ge=0)
    first_time_acquisition_tax_discount_limit_krw: int = Field(default=2_000_000, ge=0)
    local_education_tax_discount_ratio_percent: float = Field(default=10.0, ge=0)
    brokerage_rate_percent: float = Field(default=0.55, ge=0)
    legal_cost_krw: int = Field(default=2_000_000, ge=0)
    card_acquisition_tax: bool = True
    card_brokerage: bool = False
    card_legal_cost: bool = False
    card_payment_ratio_percent: float = Field(default=100.0, ge=0, le=100)
    card_installment_months: int = Field(default=12, gt=0)
    card_installment_rate_percent: float = Field(default=0.0, ge=0)
    dsr_warning_percent: float = Field(default=39.0, ge=0)
    dsr_limit_percent: float = Field(default=40.0, gt=0)

    def to_domain(self) -> FinancingScenarioInput:
        return FinancingScenarioInput(**self.model_dump())


class FinancingCalculatorShareRequest(BaseModel):
    state: dict[str, Any]


class FinancingCalculatorShareResponse(BaseModel):
    id: str
    url: str


class FinancingCalculatorSharedStateResponse(BaseModel):
    id: str
    state: dict[str, Any]


def resolve_config_dir(config_dir: str) -> Path:
    path = Path(config_dir)
    if path.is_absolute() or path.exists():
        return path

    project_root = Path(__file__).resolve().parents[3]
    return project_root / config_dir


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    @app.on_event("startup")
    def startup() -> None:
        if not settings.is_database_enabled:
            return
        db_session.configure_database()
        assert db_session.engine is not None
        Base.metadata.create_all(bind=db_session.engine)

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
    def dashboard() -> HTMLResponse:
        template_path = Path(__file__).resolve().parents[1] / "templates" / "dashboard.html"
        return HTMLResponse(template_path.read_text(encoding="utf-8"))

    @app.get("/research", response_class=HTMLResponse)
    def research_overview(request: Request) -> HTMLResponse:
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
    <title>후보 단지 리서치 | home-decision-ai</title>
    <style>
      body {{
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #f7f7f4;
        color: #202124;
      }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 52px; }}
      a {{ color: #176b48; }}
      .back {{ display: inline-block; margin-bottom: 20px; font-size: 14px; }}
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
      <a class="back" href="/">홈으로 돌아가기</a>
      <h1>후보 단지 리서치</h1>
      <p>관심 지역과 검토 중인 단지의 원본 목록입니다.</p>
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

    @app.post("/api/financing-calculator/share")
    def create_financing_calculator_share(
        payload: FinancingCalculatorShareRequest,
        request: Request,
    ) -> FinancingCalculatorShareResponse:
        if not settings.is_database_enabled:
            raise HTTPException(status_code=503, detail="Database is not configured.")

        state_json = json.dumps(payload.state, ensure_ascii=False, separators=(",", ":"))
        if db_session.SessionLocal is None:
            db_session.configure_database()
        assert db_session.SessionLocal is not None
        session = db_session.SessionLocal()
        try:
            for _ in range(8):
                share_id = secrets.token_hex(4)
                if not session.get(FinancingCalculatorShare, share_id):
                    session.add(FinancingCalculatorShare(id=share_id, state_json=state_json))
                    session.commit()
                    url = str(request.url_for("financing_calculator")).split("?")[0]
                    return FinancingCalculatorShareResponse(id=share_id, url=f"{url}?s={share_id}")
        finally:
            session.close()
        raise HTTPException(status_code=500, detail="Could not create share id.")

    @app.get("/api/financing-calculator/share/{share_id}")
    def get_financing_calculator_share(share_id: str) -> FinancingCalculatorSharedStateResponse:
        if not settings.is_database_enabled:
            raise HTTPException(status_code=503, detail="Database is not configured.")
        if len(share_id) > 16:
            raise HTTPException(status_code=404, detail="Share not found.")

        if db_session.SessionLocal is None:
            db_session.configure_database()
        assert db_session.SessionLocal is not None
        session = db_session.SessionLocal()
        try:
            share = session.get(FinancingCalculatorShare, share_id)
            if not share:
                raise HTTPException(status_code=404, detail="Share not found.")
            return FinancingCalculatorSharedStateResponse(
                id=share.id,
                state=json.loads(share.state_json),
            )
        finally:
            session.close()

    @app.get("/financing-plan", response_class=HTMLResponse)
    def financing_plan() -> HTMLResponse:
        template_path = Path(__file__).resolve().parents[1] / "templates" / "financing_plan.html"
        return HTMLResponse(template_path.read_text(encoding="utf-8"))

    @app.get("/api/financing/defaults")
    def financing_defaults() -> dict[str, object]:
        return FinancingCalculatorRequest().model_dump()

    @app.post("/api/financing/calculate")
    def calculate_financing(values: FinancingCalculatorRequest) -> dict[str, object]:
        return calculate_financing_scenario(values.to_domain())

    return app
