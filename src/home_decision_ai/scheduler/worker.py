from __future__ import annotations

from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler

from home_decision_ai.integrations.notion import NotionClient
from home_decision_ai.services.reporting import build_daily_report_stub
from home_decision_ai.settings import get_settings


def run_daily_job() -> None:
    settings = get_settings()
    report = build_daily_report_stub(date.today())
    result = NotionClient(settings).publish_markdown(report.title, report.body_markdown)
    print(result.message)


def main() -> None:
    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(run_daily_job, "cron", hour=8, minute=0)
    print("home-decision-ai worker started")
    scheduler.start()


if __name__ == "__main__":
    main()
