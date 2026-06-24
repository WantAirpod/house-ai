from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class OpenAIResponse:
    status: str | None
    model: str | None
    output_text: str


def extract_output_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "".join(parts)


def create_text_response(
    *,
    api_key: str,
    model: str,
    input_text: str,
    max_output_tokens: int = 800,
) -> OpenAIResponse:
    """Create a text response through the OpenAI Responses API."""
    body = {
        "model": model,
        "input": input_text,
        "max_output_tokens": max(max_output_tokens, 16),
    }
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    return OpenAIResponse(
        status=data.get("status"),
        model=data.get("model"),
        output_text=extract_output_text(data),
    )
