#!/usr/bin/env python3
"""Entrypoint for pulling Google Search Console data."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

REQUIRED_ENV_VARS = [
    "GSC_SERVICE_ACCOUNT_JSON",
    "GSC_PROPERTY_IDS",
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
    logging.info("Starting Google Search Console pull run")
    _validate_env()

    logging.info("Using properties: %s", os.environ.get("GSC_PROPERTY_IDS"))

    # NOTE: Replace the placeholder logic below with the actual pull implementation.
    logging.info("Performing placeholder GSC pull work")

    logging.info(
        "GSC pull completed successfully at %s",
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - we want to log and exit cleanly
        logging.getLogger(__name__).exception("GSC pull failed: %s", exc)
        raise
