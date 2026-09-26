"""Run with `uv run opspilot-api` (or `python -m opspilot.api`)."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "opspilot.api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
