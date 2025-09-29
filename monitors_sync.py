"""Synchronise monitor definitions with Supabase."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from util_supabase import SupabaseWriter

logger = logging.getLogger(__name__)


def _load_definitions() -> List[Dict[str, Any]]:
    file_path = os.getenv("MONITORS_FILE")
    if file_path:
        logger.info("Loading monitor definitions from %s", file_path)
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
    else:
        content = os.getenv("MONITORS_JSON")
        if not content:
            raise RuntimeError("Either MONITORS_FILE or MONITORS_JSON must be provided")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Monitor definitions must be valid JSON") from exc
    if isinstance(data, dict):
        data = data.get("monitors") or []
    if not isinstance(data, list):
        raise RuntimeError("Monitor definitions must be a list")
    return data


def _normalise(definition: Dict[str, Any]) -> Dict[str, Any]:
    keyword = definition.get("keyword")
    if not keyword:
        raise RuntimeError("Monitor definition missing keyword")

    default_engine = os.getenv("MONITORS_DEFAULT_ENGINE", "google")
    default_device = os.getenv("MONITORS_DEFAULT_DEVICE", "desktop")

    payload: Dict[str, Any] = {
        "keyword": keyword,
        "target_url": definition.get("url") or definition.get("target_url"),
        "engine": definition.get("engine") or default_engine,
        "device": definition.get("device") or default_device,
        "location": definition.get("location") or os.getenv("MONITORS_DEFAULT_LOCATION"),
        "language": definition.get("language") or os.getenv("MONITORS_DEFAULT_LANGUAGE"),
        "tags": definition.get("tags"),
        "active": definition.get("active", True),
        "metadata": definition.get("metadata"),
        "updated_at": datetime.utcnow().isoformat(),
    }

    if isinstance(payload["tags"], (list, tuple)):
        payload["tags"] = ",".join(str(tag) for tag in payload["tags"])

    return payload


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    supabase_table = os.getenv("MONITORS_TABLE", "monitor_keywords")
    on_conflict = os.getenv(
        "MONITORS_CONFLICT_COLUMNS",
        "keyword,engine,device,location,language",
    )

    definitions = [_normalise(defn) for defn in _load_definitions()]
    if not definitions:
        logger.info("No monitor definitions supplied")
        return

    supabase = SupabaseWriter()
    supabase.upsert_rows(supabase_table, definitions, on_conflict=on_conflict)


def main() -> None:
    try:
        run()
    except Exception:  # pragma: no cover
        logger.exception("Monitor sync failed")
        raise


if __name__ == "__main__":
    main()
