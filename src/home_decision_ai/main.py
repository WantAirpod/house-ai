from __future__ import annotations

from pathlib import Path

from home_decision_ai.config import load_project_config


def main() -> None:
    """Run the project configuration CLI."""
    project_root = Path.cwd()
    config = load_project_config(project_root / "config")

    print("home-decision-ai")
    print(f"- regions: {len(config.regions)}")
    print(f"- watchlist items: {len(config.watchlist)}")
    print("- status: configuration loaded")
    print("- TODO: run web app, scheduled jobs, and report publishing")


if __name__ == "__main__":
    main()
