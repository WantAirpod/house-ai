from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from home_decision_ai.config import load_project_config
from home_decision_ai.settings import get_settings


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
        error_html = f"<section><h2>설정 로딩 오류</h2><p>{dashboard_error}</p></section>" if dashboard_error else ""

        html = f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>home-decision-ai</title>
    <style>
      body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f7f4; color: #202124; }}
      main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px; }}
      table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #deded8; }}
      th, td {{ padding: 12px; border-bottom: 1px solid #e9e9e3; text-align: left; font-size: 14px; }}
      th {{ background: #efefe8; }}
      .status {{ display: flex; gap: 12px; flex-wrap: wrap; }}
      .pill {{ padding: 8px 10px; border: 1px solid #d5d5cd; background: #fff; border-radius: 6px; font-size: 14px; }}
    </style>
  </head>
  <body>
    <main>
      <h1>home-decision-ai</h1>
      <p>실거주 아파트 매수를 위한 부동산 인텔리전스 플랫폼</p>
      <section class="status">
        <div class="pill">Database: {"configured" if settings.is_database_enabled else "not configured"}</div>
        <div class="pill">Notion: {"configured" if settings.is_notion_enabled else "not configured"}</div>
        <div class="pill">Watchlist: {len(watchlist)}</div>
      </section>
      {error_html}
      <section>
        <h2>관심 지역</h2>
        <table><thead><tr><th>우선순위</th><th>지역</th><th>출퇴근 메모</th></tr></thead><tbody>{rows}</tbody></table>
      </section>
      <section>
        <h2>관심 단지 후보</h2>
        <table><thead><tr><th>상태</th><th>이름</th><th>평형</th><th>상한가</th></tr></thead><tbody>{watchlist_rows}</tbody></table>
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

    return app
