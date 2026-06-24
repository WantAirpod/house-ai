from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from home_decision_ai.config import load_project_config
from home_decision_ai.settings import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


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
        project_config = load_project_config(Path(settings.config_dir))
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "regions": project_config.regions,
                "watchlist": project_config.watchlist,
                "database_configured": settings.is_database_enabled,
                "notion_configured": settings.is_notion_enabled,
            },
        )

    @app.get("/api/briefing/daily")
    def daily_briefing_preview() -> dict[str, object]:
        project_config = load_project_config(Path(settings.config_dir))
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
