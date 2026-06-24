from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Start the HTTP server in Railway and local environments."""
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "home_decision_ai.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
