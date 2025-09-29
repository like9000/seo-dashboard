"""Pull keyword ranks from the Check Position API and upsert them into Supabase."""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from util_checkpos import CheckPositionClient
from util_supabase import SupabaseWriter

logger = logging.getLogger(__name__)


def _group_monitors(monitors: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str, str, str, str], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[str, str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    default_engine = os.getenv("MONITORS_DEFAULT_ENGINE", "google")
    default_device = os.getenv("MONITORS_DEFAULT_DEVICE", "desktop")
    for monitor in monitors:
        keyword = monitor.get("keyword")
        if not keyword:
            logger.debug("Skipping monitor without keyword: %s", monitor)
            continue
        engine = monitor.get("engine") or default_engine
        device = monitor.get("device") or default_device
        location = monitor.get("location") or os.getenv("MONITORS_DEFAULT_LOCATION")
        language = monitor.get("language") or os.getenv("MONITORS_DEFAULT_LANGUAGE")
        target_url = monitor.get("target_url") or monitor.get("url")
        key = (engine, device, location or "", language or "", target_url or "")
        grouped[key].append(monitor)
    return grouped


def _build_records(
    monitors: Iterable[Dict[str, Any]],
    responses: List[Dict[str, Any]],
    *,
    engine: str,
    device: str,
    location: str,
    language: str,
    target_url: str,
    checked_at: datetime,
) -> List[Dict[str, Any]]:
    monitor_by_keyword = {str(m["keyword"]).lower(): m for m in monitors if m.get("keyword")}
    records: List[Dict[str, Any]] = []

    for item in responses:
        keyword = str(item.get("keyword") or item.get("query") or "").strip()
        if not keyword:
            continue
        monitor = monitor_by_keyword.get(keyword.lower())
        if not monitor:
            logger.debug("Received rank for unexpected keyword %s", keyword)
            continue
        record = {
            "monitor_id": monitor.get("id"),
            "keyword": monitor.get("keyword"),
            "engine": engine,
            "device": device,
            "location": location or None,
            "language": language or None,
            "target_url": target_url or monitor.get("target_url"),
            "rank": item.get("rank") or item.get("position"),
            "url_found": item.get("url") or item.get("result_url"),
            "checked_at": checked_at.isoformat(),
            "raw_response": json.dumps(item),
        }
        records.append(record)
    return records


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    supabase = SupabaseWriter()
    client = CheckPositionClient()

    monitors_table = os.getenv("MONITORS_TABLE", "monitor_keywords")
    monitor_filters = json.loads(os.getenv("RANKS_MONITOR_FILTERS", "{}"))
    select = os.getenv(
        "RANKS_MONITOR_SELECT",
        "id,keyword,target_url,engine,device,location,language",
    )
    monitors = supabase.fetch_rows(monitors_table, select=select, filters=monitor_filters)
    if not monitors:
        logger.info("No monitors found, skipping rank pull")
        return

    grouped = _group_monitors(monitors)
    ranks_table = os.getenv("RANKS_TABLE", "search_ranks")
    on_conflict = os.getenv("RANKS_CONFLICT_COLUMNS", "monitor_id,checked_at")
    checked_at = datetime.utcnow()

    all_records: List[Dict[str, Any]] = []
    for (engine, device, location, language, target_url), items in grouped.items():
        keywords = [item["keyword"] for item in items if item.get("keyword")]
        if not keywords:
            continue
        logger.info(
            "Fetching ranks for %s keywords (engine=%s device=%s location=%s language=%s)",
            len(keywords),
            engine,
            device,
            location or "-",
            language or "-",
        )
        responses = client.fetch_positions(
            keywords,
            engine=engine,
            device=device,
            location=location or None,
            language=language or None,
            url=target_url or None,
            depth=int(os.getenv("RANKS_DEPTH", "50")),
        )
        records = _build_records(
            items,
            responses,
            engine=engine,
            device=device,
            location=location,
            language=language,
            target_url=target_url,
            checked_at=checked_at,
        )
        all_records.extend(records)

    if not all_records:
        logger.info("No rank records produced")
        return

    supabase.upsert_rows(
        ranks_table,
        all_records,
        on_conflict=on_conflict,
        chunk_size=int(os.getenv("RANKS_UPSERT_CHUNK", "200")),
    )


def main() -> None:
    try:
        run()
    except Exception:  # pragma: no cover
        logger.exception("Rank pull failed")
        raise


if __name__ == "__main__":
    main()
