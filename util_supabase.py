"""Helpers for interacting with Supabase's REST endpoint.

The Supabase Python SDK adds a hefty dependency footprint; these utilities
implement the small portion that the data pipelines need: upserting batches of
rows and reading configuration from environment variables.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

import requests

logger = logging.getLogger(__name__)


class SupabaseConfigurationError(RuntimeError):
    """Raised when the Supabase configuration is missing."""


def _chunked(iterable: Iterable[Mapping[str, Any]], chunk_size: int) -> Iterable[List[Mapping[str, Any]]]:
    chunk: List[Mapping[str, Any]] = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


class SupabaseWriter:
    """Thin REST client aware of Supabase specific headers and retry logic."""

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.url = (url or os.getenv("SUPABASE_URL"))
        self.api_key = api_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()

        if not self.url or not self.api_key:
            raise SupabaseConfigurationError(
                "Supabase configuration missing. Provide SUPABASE_URL and either "
                "SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY."
            )

    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[MutableMapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> requests.Response:
        url = f"{self.url.rstrip('/')}/rest/v1/{path.lstrip('/')}"
        headers = headers or {}
        headers.setdefault("apikey", self.api_key)
        headers.setdefault("Authorization", f"Bearer {self.api_key}")

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    timeout=30,
                )
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "Supabase request to %s failed (attempt %s/%s): %s", url, attempt, self.max_retries, exc
                )
                time.sleep(sleep_seconds)
                continue

            if response.status_code >= 500 and attempt < self.max_retries:
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                logger.info(
                    "Supabase server error %s on %s (attempt %s/%s), retrying in %.1fs", 
                    response.status_code,
                    url,
                    attempt,
                    self.max_retries,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue

            return response

        return response  # pragma: no cover - loop always returns earlier or raises

    # ------------------------------------------------------------------
    def upsert_rows(
        self,
        table: str,
        rows: Iterable[Mapping[str, Any]],
        *,
        on_conflict: Optional[str] = None,
        chunk_size: int = 500,
        ignore_duplicates: bool = False,
    ) -> None:
        """Upsert ``rows`` into ``table`` using Supabase's REST endpoint."""

        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        prefer_directives = ["resolution=merge-duplicates"]
        if ignore_duplicates:
            prefer_directives.append("ignore-duplicates")
        headers["Prefer"] = ",".join(prefer_directives)

        params: Dict[str, Any] = {}
        if on_conflict:
            params["on_conflict"] = on_conflict

        for chunk in _chunked(rows, chunk_size):
            payload = [dict(item) for item in chunk]
            response = self._request(
                "POST",
                table,
                headers=headers,
                params=params,
                json_body=payload,
            )
            if response.status_code not in {200, 201, 204}:
                raise RuntimeError(
                    f"Supabase upsert failed with status {response.status_code}: {response.text}"
                )
            logger.info("Upserted %s rows into %s", len(payload), table)

    # ------------------------------------------------------------------
    def fetch_rows(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Optional[Mapping[str, str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"select": select}
        if filters:
            params.update(filters)
        if limit is not None:
            params["limit"] = str(limit)

        response = self._request("GET", table, params=params)
        if response.status_code not in {200, 206}:
            raise RuntimeError(
                f"Supabase fetch failed with status {response.status_code}: {response.text}"
            )
        if not response.text:
            return []
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Supabase returned invalid JSON for table {table}: {response.text}"
            ) from exc
        if not isinstance(data, list):
            raise RuntimeError(
                f"Expected Supabase to return a list, received: {type(data).__name__}"
            )
        return data


__all__ = ["SupabaseWriter", "SupabaseConfigurationError"]
