"""Pipeline extracting the top Search Console queries for each property."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from gsc_pull import _parse_date, _parse_properties, fetch_search_console_rows
from util_gsc_oauth import GSCAuthenticator
from util_supabase import SupabaseWriter

logger = logging.getLogger(__name__)


def _build_payload(
    site_url: str,
    dimensions: List[str],
    row: Dict[str, Any],
    *,
    period_start: str,
    period_end: str,
    requested_at: datetime,
    rank: int,
) -> Dict[str, Any]:
    dimension_values = dict(zip(dimensions, row.get("keys", [])))
    payload: Dict[str, Any] = {
        "property_url": site_url,
        "period_start": period_start,
        "period_end": period_end,
        "rank": rank,
        "requested_at": requested_at.isoformat(),
        "clicks": row.get("clicks", 0.0),
        "impressions": row.get("impressions", 0.0),
        "ctr": row.get("ctr", 0.0),
        "position": row.get("position", 0.0),
    }
    payload.update(dimension_values)
    return payload


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    properties_raw = os.getenv("GSC_PROPERTIES")
    if not properties_raw:
        raise RuntimeError("GSC_PROPERTIES environment variable is required")
    properties = _parse_properties(properties_raw)

    days = int(os.getenv("GSC_TOP_QUERIES_LOOKBACK", "7"))
    end_date = _parse_date(os.getenv("GSC_TOP_QUERIES_END"), date.today())
    start_date = (date.fromisoformat(end_date) - timedelta(days=days - 1)).isoformat()

    dimensions_env = os.getenv("GSC_TOP_QUERIES_DIMENSIONS", "query")
    dimensions = [item.strip() for item in dimensions_env.split(",") if item.strip()]
    row_limit = int(os.getenv("GSC_TOP_QUERIES_LIMIT", "250"))

    sort_metric = os.getenv("GSC_TOP_QUERIES_SORT", "clicks")
    supabase_table = os.getenv("GSC_TOP_QUERIES_TABLE", "gsc_top_queries")
    on_conflict = os.getenv(
        "GSC_TOP_QUERIES_CONFLICT",
        "property_url,period_start,period_end,rank",
    )

    authenticator = GSCAuthenticator()
    supabase = SupabaseWriter()
    requested_at = datetime.utcnow()

    for site_url in properties:
        rows = fetch_search_console_rows(
            authenticator,
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions,
            row_limit=row_limit,
            dimension_filters=None,
            search_type=os.getenv("GSC_SEARCH_TYPE", "web"),
        )
        rows.sort(key=lambda item: item.get(sort_metric, 0.0), reverse=True)
        top_rows = rows[:row_limit]
        payload = [
            _build_payload(
                site_url,
                dimensions,
                row,
                period_start=start_date,
                period_end=end_date,
                requested_at=requested_at,
                rank=index,
            )
            for index, row in enumerate(top_rows, start=1)
        ]
        if not payload:
            logger.info("No top queries found for %s", site_url)
            continue
        supabase.upsert_rows(supabase_table, payload, on_conflict=on_conflict)


def main() -> None:
    try:
        run()
    except Exception:  # pragma: no cover
        logger.exception("GSC top queries pipeline failed")
        raise


if __name__ == "__main__":
    main()
