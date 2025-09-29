"""Pipeline that pulls Search Console performance data and stores it in Supabase."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

from util_gsc_oauth import GSCAuthenticator
from util_supabase import SupabaseWriter

logger = logging.getLogger(__name__)

SEARCH_ANALYTICS_ENDPOINT = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"


def _parse_properties(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_date(value: Optional[str], default: date) -> str:
    if not value:
        return default.isoformat()
    value = value.strip()
    if value.lower() == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    if value.lower() == "today":
        return date.today().isoformat()
    return date.fromisoformat(value).isoformat()


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _build_row(
    site_url: str,
    dimensions: List[str],
    row: Dict[str, Any],
    requested_at: datetime,
) -> Dict[str, Any]:
    keys = row.get("keys", [])
    metrics = {
        "clicks": row.get("clicks", 0.0),
        "impressions": row.get("impressions", 0.0),
        "ctr": row.get("ctr", 0.0),
        "position": row.get("position", 0.0),
    }
    dimension_values = dict(zip(dimensions, keys))
    payload = {
        "property_url": site_url,
        "requested_at": requested_at.isoformat(),
        **dimension_values,
        **metrics,
    }
    return payload


def fetch_search_console_rows(
    authenticator: GSCAuthenticator,
    *,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: List[str],
    row_limit: int,
    dimension_filters: Optional[List[Dict[str, Any]]] = None,
    search_type: str = "web",
) -> List[Dict[str, Any]]:
    url = SEARCH_ANALYTICS_ENDPOINT.format(site_url=quote(site_url, safe=""))
    body: Dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "type": search_type,
    }
    if dimension_filters:
        body["dimensionFilterGroups"] = dimension_filters

    logger.info(
        "Requesting GSC Search Analytics for %s (%s -> %s) dimensions=%s",
        site_url,
        start_date,
        end_date,
        dimensions,
    )
    response = authenticator.authenticated_request("POST", url, json=body)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch GSC data for {site_url}: {response.status_code} {response.text}"
        )
    payload = response.json()
    rows = payload.get("rows", [])
    logger.info("Received %s rows for %s", len(rows), site_url)
    return rows


def filter_rows(rows: Iterable[Dict[str, Any]], *, min_impressions: float) -> List[Dict[str, Any]]:
    filtered = []
    for row in rows:
        impressions = _coerce_float(row.get("impressions"), 0.0)
        if impressions < min_impressions:
            continue
        filtered.append(row)
    return filtered


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    properties_raw = os.getenv("GSC_PROPERTIES")
    if not properties_raw:
        raise RuntimeError("GSC_PROPERTIES environment variable is required")
    properties = _parse_properties(properties_raw)

    lookback_days = int(os.getenv("GSC_LOOKBACK_DAYS", "3"))
    end_date = _parse_date(os.getenv("GSC_END_DATE"), date.today())
    start_date = _parse_date(
        os.getenv("GSC_START_DATE"),
        date.fromisoformat(end_date) - timedelta(days=lookback_days),
    )

    dimensions_env = os.getenv("GSC_DIMENSIONS", "date,query,page")
    dimensions = [item.strip() for item in dimensions_env.split(",") if item.strip()]

    row_limit = int(os.getenv("GSC_ROW_LIMIT", "25000"))
    min_impressions = float(os.getenv("GSC_MIN_IMPRESSIONS", "0"))
    search_type = os.getenv("GSC_SEARCH_TYPE", "web")

    dimension_filters_json = os.getenv("GSC_DIMENSION_FILTERS")
    dimension_filters = json.loads(dimension_filters_json) if dimension_filters_json else None

    supabase_table = os.getenv("GSC_SUPABASE_TABLE", "gsc_search_analytics")
    on_conflict = os.getenv("GSC_SUPABASE_CONFLICT", "property_url,date,query,page")

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
            dimension_filters=dimension_filters,
            search_type=search_type,
        )
        if min_impressions > 0:
            rows = filter_rows(rows, min_impressions=min_impressions)
        payload = [_build_row(site_url, dimensions, row, requested_at) for row in rows]
        if not payload:
            logger.info("No rows to upsert for %s", site_url)
            continue
        supabase.upsert_rows(supabase_table, payload, on_conflict=on_conflict)


def main() -> None:
    try:
        run()
    except Exception:  # pragma: no cover - runtime guard
        logger.exception("GSC pipeline failed")
        raise


if __name__ == "__main__":
    main()
