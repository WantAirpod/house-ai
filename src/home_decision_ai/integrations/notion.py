from __future__ import annotations

from dataclasses import dataclass

from home_decision_ai.settings import Settings


@dataclass(frozen=True)
class NotionPublishResult:
    enabled: bool
    page_id: str | None
    message: str


class NotionClient:
    """Thin boundary for Notion publishing.

    TODO: Implement actual Notion API calls after the target page/database is created.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def publish_markdown(self, title: str, markdown: str) -> NotionPublishResult:
        if not self.settings.is_notion_enabled:
            return NotionPublishResult(
                enabled=False,
                page_id=None,
                message=f"Notion is not configured. Draft kept locally: {title}",
            )

        return NotionPublishResult(
            enabled=True,
            page_id=None,
            message="TODO: Publish markdown to Notion API.",
        )
