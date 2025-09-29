#!/usr/bin/env python3
"""Entrypoint for pulling rank tracking data."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

REQUIRED_ENV_VARS = [
    "RANKS_API_TOKEN",
    "RANKS_PROJECT_ID",
]


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def _validate_env() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(sorted(missing))
        )


def main() -> None:
    _configure_logging()
    logging.info("Starting ranks pull run")
    _validate_env()

    logging.info(
        "Requesting ranks for project %s", os.environ.get("RANKS_PROJECT_ID")
    )

    # NOTE: Replace the placeholder logic below with the actual pull implementation.
    logging.info("Performing placeholder ranks pull work")

    logging.info(
        "Ranks pull completed successfully at %s",
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - we want to log and exit cleanly
        logging.getLogger(__name__).exception("Ranks pull failed: %s", exc)
        raise
