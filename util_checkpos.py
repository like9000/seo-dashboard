"""Helper functions for interacting with the Check Position API."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional

import requests

logger = logging.getLogger(__name__)


def _ensure(value: Optional[str], name: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required configuration value: {name}")
    return value


class CheckPositionClient:
    """Lightweight wrapper around the Check Position HTTP API."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("CHECKPOS_API_URL") or "https://api.checkposition.com").rstrip("/")
        self.api_key = _ensure(api_key or os.getenv("CHECKPOS_API_KEY"), "CHECKPOS_API_KEY")
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

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
                    "Check Position request to %s failed (attempt %s/%s): %s", url, attempt, self.max_retries, exc
                )
                time.sleep(sleep_seconds)
                continue

            if response.status_code >= 500 and attempt < self.max_retries:
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                logger.info(
                    "Check Position server error %s on %s (attempt %s/%s), retrying in %.1fs",
                    response.status_code,
                    url,
                    attempt,
                    self.max_retries,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Check Position request failed with status {response.status_code}: {response.text}"
                )

            try:
                return response.json()
            except ValueError as exc:
                raise RuntimeError(
                    f"Check Position returned invalid JSON for {url}: {response.text}"
                ) from exc

        # The loop either returns or raises, keep mypy happy.
        raise RuntimeError("Failed to communicate with Check Position API")

    # ------------------------------------------------------------------
    def fetch_positions(
        self,
        keywords: Iterable[str],
        *,
        engine: str = "google",
        device: str = "desktop",
        location: Optional[str] = None,
        language: Optional[str] = None,
        url: Optional[str] = None,
        depth: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch ranking information for a collection of ``keywords``."""

        payload: Dict[str, Any] = {
            "engine": engine,
            "device": device,
            "depth": depth,
            "keywords": list(keywords),
        }
        if location:
            payload["location"] = location
        if language:
            payload["language"] = language
        if url:
            payload["url"] = url

        response = self._request("POST", "/v1/ranks", json_body=payload)
        data = response.get("data") or response.get("results") or response
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if not isinstance(data, list):
            raise RuntimeError(
                "Unexpected Check Position response shape. Expected list under 'data' or 'results'."
            )
        return data


__all__ = ["CheckPositionClient"]
