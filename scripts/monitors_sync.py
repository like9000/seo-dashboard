#!/usr/bin/env python3
"""Synchronise monitor definitions from an external service."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

REQUIRED_ENV_VARS = [
    "MONITORS_API_TOKEN",
    "MONITORS_BASE_URL",
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
    logging.info("Starting monitors synchronisation run")
    _validate_env()

    logging.info(
        "Syncing monitors from %s", os.environ.get("MONITORS_BASE_URL", "<undefined>")
    )

    # NOTE: Replace the placeholder logic below with the actual sync implementation.
    logging.info("Performing placeholder monitors sync work")

    logging.info(
        "Monitors sync completed successfully at %s",
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - we want to log and exit cleanly
        logging.getLogger(__name__).exception("Monitors sync failed: %s", exc)
        raise
