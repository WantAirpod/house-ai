from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import uvicorn  # noqa: E402


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "home_decision_ai.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
