from __future__ import annotations

from typing import Any


HUB_TITLE = "리서치 포스팅"


def ensure_posting_hub(notion: Any, root_page_id: str) -> str:
    for block in notion.children(root_page_id):
        if block["type"] == "child_page" and block["child_page"].get("title") == HUB_TITLE:
            return block["id"]
    page = notion.create_child_page(parent_page_id=root_page_id, title=HUB_TITLE, blocks=[])
    return page["id"]


def move_page(notion: Any, page_id: str, parent_page_id: str) -> None:
    notion.request(
        "POST",
        f"pages/{page_id}/move",
        {"parent": {"type": "page_id", "page_id": parent_page_id}},
        notion_version="2026-03-11",
    )
