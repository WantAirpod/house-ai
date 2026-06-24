from home_decision_ai.integrations.openai_responses import extract_output_text


def test_extract_output_text() -> None:
    data = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "hello"},
                    {"type": "refusal", "refusal": "no"},
                ]
            },
            {"content": [{"type": "output_text", "text": " world"}]},
        ]
    }

    assert extract_output_text(data) == "hello world"
