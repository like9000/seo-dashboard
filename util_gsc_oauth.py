"""Utilities for authenticating against the Google Search Console API.

The module exposes a :class:`GSCAuthenticator` class that performs refresh token
flows and automatically retries transient failures.  The implementation avoids
external dependencies so the utilities can be embedded into light-weight data
pipelines.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


DEFAULT_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class ConfigurationError(RuntimeError):
    """Raised when the OAuth configuration is missing."""


@dataclass
class _TokenCache:
    """Simple in-memory representation of an access token."""

    access_token: str
    expires_at: float

    def is_valid(self) -> bool:
        return bool(self.access_token) and time.time() < self.expires_at - 30


class GSCAuthenticator:
    """Small helper responsible for refreshing OAuth access tokens.

    Parameters
    ----------
    client_id:
        Google OAuth client identifier.  If omitted the value is looked up in
        the ``GSC_CLIENT_ID`` environment variable.
    client_secret:
        Google OAuth client secret or service account secret.  Defaults to the
        ``GSC_CLIENT_SECRET`` environment variable.
    refresh_token:
        Refresh token used to mint short lived access tokens.  Defaults to the
        ``GSC_REFRESH_TOKEN`` environment variable.
    token_endpoint:
        Override for the OAuth token endpoint.  This is primarily useful when
        stubbing requests in tests.
    max_retries / backoff_factor:
        Controls the exponential backoff strategy used when talking to the
        OAuth endpoint.
    session:
        Optional :class:`requests.Session` instance.  Supplying a pre-configured
        session makes it easy to provide additional retry logic or request
        hooks.
    """

    def __init__(
        self,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_endpoint: str = DEFAULT_TOKEN_ENDPOINT,
        max_retries: int = 5,
        backoff_factor: float = 1.5,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.client_id = client_id or os.getenv("GSC_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GSC_CLIENT_SECRET")
        self.refresh_token = refresh_token or os.getenv("GSC_REFRESH_TOKEN")
        self.token_endpoint = token_endpoint
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ConfigurationError(
                "GSC OAuth configuration is incomplete. Ensure GSC_CLIENT_ID, "
                "GSC_CLIENT_SECRET and GSC_REFRESH_TOKEN are provided."
            )

        self._token: Optional[_TokenCache] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def _refresh_access_token(self) -> _TokenCache:
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.post(self.token_endpoint, data=payload, timeout=30)
                if response.status_code >= 500:
                    raise RuntimeError(
                        f"OAuth token endpoint returned {response.status_code}: {response.text}"
                    )
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as exc:  # ValueError from json()
                logger.warning(
                    "Failed to refresh Google Search Console token (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt >= self.max_retries:
                    raise
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                time.sleep(sleep_seconds)
                continue

            access_token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            if not access_token:
                raise RuntimeError(
                    "Google OAuth token response did not contain an access_token. "
                    f"Payload: {json.dumps(data)}"
                )

            logger.debug("Obtained new GSC access token valid for %s seconds", expires_in)
            return _TokenCache(access_token=access_token, expires_at=time.time() + expires_in)

        # Should never reach this line due to the raise inside the loop.
        raise RuntimeError("Unable to refresh Google Search Console access token")

    # ------------------------------------------------------------------
    def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid access token, refreshing it when necessary."""

        with self._lock:
            if not force_refresh and self._token and self._token.is_valid():
                return self._token.access_token

            self._token = self._refresh_access_token()
            return self._token.access_token

    # ------------------------------------------------------------------
    def authenticated_request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        retry_on_unauthorized: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform an authenticated HTTP request against the Search Console API.

        The helper attaches the ``Authorization`` header, refreshes the token
        whenever the call returns ``401`` and retries the request automatically.
        """

        attempt = 0
        headers = dict(headers or {})

        while True:
            attempt += 1
            token = self.get_access_token(force_refresh=attempt > 1)
            headers["Authorization"] = f"Bearer {token}"
            try:
                response = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
            except requests.RequestException:
                if attempt > self.max_retries:
                    raise
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                logger.debug("Retrying request after transport failure in %ss", sleep_seconds)
                time.sleep(sleep_seconds)
                continue

            if retry_on_unauthorized and response.status_code == 401 and attempt <= self.max_retries:
                logger.info("GSC request unauthorized, refreshing token and retrying")
                self.get_access_token(force_refresh=True)
                continue

            if response.status_code >= 500 and attempt <= self.max_retries:
                sleep_seconds = self.backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "GSC request returned %s, retrying in %.1fs",
                    response.status_code,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue

            return response


__all__ = ["GSCAuthenticator", "ConfigurationError"]
