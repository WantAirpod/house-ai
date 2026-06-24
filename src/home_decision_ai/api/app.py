from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from home_decision_ai.config import load_project_config
from home_decision_ai.settings import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


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
        regions: list[dict[str, Any]] = []
        watchlist: list[dict[str, Any]] = []
        dashboard_error: str | None = None

        try:
            project_config = load_project_config(resolve_config_dir(settings.config_dir))
            regions = project_config.regions
            watchlist = project_config.watchlist
        except Exception as exc:  # pragma: no cover - defensive dashboard rendering
            dashboard_error = str(exc)

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "regions": regions,
                "watchlist": watchlist,
                "dashboard_error": dashboard_error,
                "database_configured": settings.is_database_enabled,
                "notion_configured": settings.is_notion_enabled,
            },
        )

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
