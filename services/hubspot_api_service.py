"""
HubSpot CRM API v3 client for Deals extraction.

Responsibilities:
    * Bearer-token authentication with HubSpot private app access tokens
    * Cursor-based pagination over GET /crm/v3/objects/deals
    * Client-side rate limiting (sliding window, default 150 requests / 10 s)
      plus adaptive back-off driven by HubSpot's X-HubSpot-RateLimit-* headers
    * Retry with exponential back-off for 429 and transient 5xx / network errors
    * Typed exceptions for the HubSpot error categories callers care about
    * Credential validation and deal-property discovery

The access token is never logged; it is passed per call (it arrives with each
scan request and is stored encrypted in the jobs table, never in env/config).
"""

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

import requests

from loki_logger import get_logger, log_api_call

# Core deal properties requested when the caller does not ask for specific ones.
# These are the default HubSpot deal properties that exist in every portal.
DEFAULT_DEAL_PROPERTIES: List[str] = [
    "dealname",
    "amount",
    "dealstage",
    "pipeline",
    "closedate",
    "createdate",
    "hs_lastmodifieddate",
    "dealtype",
    "description",
    "hubspot_owner_id",
    "hs_priority",
    "deal_currency_code",
    "amount_in_home_currency",
    "hs_deal_stage_probability",
    "hs_forecast_amount",
    "hs_forecast_probability",
    "hs_projected_amount",
    "hs_closed_amount",
    "hs_is_closed",
    "hs_is_closed_won",
    "days_to_close",
    "hs_next_step",
    "closed_lost_reason",
    "closed_won_reason",
    "hs_analytics_source",
    "num_associated_contacts",
    "num_contacted_notes",
    "num_notes",
    "notes_last_updated",
    "hs_object_id",
]


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class HubSpotAPIError(Exception):
    """Base error for HubSpot API failures."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        category: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.category = category
        self.correlation_id = correlation_id
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"status={self.status_code}")
        if self.category:
            parts.append(f"category={self.category}")
        if self.correlation_id:
            parts.append(f"correlationId={self.correlation_id}")
        return " | ".join(parts)


class HubSpotAuthenticationError(HubSpotAPIError):
    """401 - token missing, malformed, expired or revoked."""


class HubSpotPermissionError(HubSpotAPIError):
    """403 - token valid but missing a required scope (e.g. crm.objects.deals.read)."""


class HubSpotNotFoundError(HubSpotAPIError):
    """404 - object or endpoint not found."""


class HubSpotValidationError(HubSpotAPIError):
    """400 - bad request parameters."""


class HubSpotRateLimitError(HubSpotAPIError):
    """429 - still rate limited after exhausting retries."""


class HubSpotServerError(HubSpotAPIError):
    """5xx - HubSpot side failure after exhausting retries."""


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #
class SlidingWindowRateLimiter:
    """
    Thread-safe sliding-window limiter: at most `max_requests` per
    `window_seconds`. HubSpot private apps are limited per 10-second window
    (100/10 s on Free/Starter, 190/10 s on Pro/Enterprise; this test spec uses
    150/10 s), so the window is configurable.
    """

    def __init__(self, max_requests: int = 150, window_seconds: float = 10.0):
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = float(window_seconds)
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Block until a request slot is free. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self.window_seconds:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return waited
                sleep_for = self.window_seconds - (now - self._timestamps[0]) + 0.01
            time.sleep(sleep_for)
            waited += sleep_for


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
class HubSpotAPIService:
    """Client for the HubSpot CRM v3 Deals API."""

    DEALS_ENDPOINT = "/crm/v3/objects/deals"
    DEAL_PROPERTIES_ENDPOINT = "/crm/v3/properties/deals"
    DEAL_PIPELINES_ENDPOINT = "/crm/v3/pipelines/deals"
    ACCOUNT_INFO_ENDPOINT = "/account-info/v3/details"
    MAX_PAGE_SIZE = 100  # HubSpot hard limit for the list endpoint

    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url: str = "https://api.hubapi.com",
        timeout: int = 30,
        rate_limit_requests: int = 150,
        rate_limit_window_seconds: float = 10.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        test_delay_seconds: float = 0.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        # Artificial per-request delay; only used to make pause/cancel testable
        # against a tiny dataset. Keep 0 in real environments.
        self.test_delay_seconds = test_delay_seconds
        self.rate_limiter = SlidingWindowRateLimiter(rate_limit_requests, rate_limit_window_seconds)
        self.last_rate_limit_info: Dict[str, Any] = {}
        self.request_count = 0
        self.logger = get_logger(__name__)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "hubspot-deals-etl/1.0",
            }
        )

        self.logger.debug(
            "HubSpot API service initialized",
            extra={
                "operation": "hubspot_api_init",
                "base_url": self.base_url,
                "timeout": timeout,
                "rate_limit": f"{rate_limit_requests}/{rate_limit_window_seconds}s",
                "max_retries": max_retries,
            },
        )

    # ------------------------------------------------------------------ #
    # Authentication
    # ------------------------------------------------------------------ #
    @staticmethod
    def _auth_headers(access_token: str) -> Dict[str, str]:
        if not access_token or not isinstance(access_token, str):
            raise HubSpotAuthenticationError("HubSpot access token is missing", status_code=401)
        return {"Authorization": f"Bearer {access_token.strip()}"}

    # ------------------------------------------------------------------ #
    # Low-level request with rate limiting, retries and error mapping
    # ------------------------------------------------------------------ #
    def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        operation: str = "hubspot_request",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers(access_token)
        attempt = 0

        while True:
            attempt += 1
            waited = self.rate_limiter.acquire()
            if waited > 0:
                self.logger.debug(
                    "Client-side rate limiter delayed request",
                    extra={"operation": operation, "waited_seconds": round(waited, 2)},
                )
            if self.test_delay_seconds > 0:
                time.sleep(self.test_delay_seconds)

            start = time.monotonic()
            try:
                response = self.session.request(
                    method, url, params=params, json=json_body, headers=headers, timeout=self.timeout
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                if attempt <= self.max_retries:
                    delay = self.retry_backoff_seconds * (2 ** (attempt - 1))
                    self.logger.warning(
                        "Network error calling HubSpot, retrying",
                        extra={
                            "operation": operation,
                            "attempt": attempt,
                            "retry_in_seconds": delay,
                            "error": str(exc),
                            "duration_ms": duration_ms,
                        },
                    )
                    time.sleep(delay)
                    continue
                self.logger.error(
                    "Network error calling HubSpot, retries exhausted",
                    extra={"operation": operation, "attempts": attempt, "error": str(exc)},
                )
                raise HubSpotServerError(f"Network error contacting HubSpot: {exc}") from exc

            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self.request_count += 1
            self._capture_rate_limit_headers(response)
            log_api_call(
                self.logger,
                operation,
                method=method,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            if response.status_code < 400:
                self._adaptive_throttle(operation)
                if response.status_code == 204 or not response.content:
                    return {}
                return response.json()

            # ---- error handling ----
            if response.status_code in self.RETRYABLE_STATUS and attempt <= self.max_retries:
                delay = self._retry_delay(response, attempt)
                self.logger.warning(
                    "Retryable HubSpot error",
                    extra={
                        "operation": operation,
                        "status_code": response.status_code,
                        "attempt": attempt,
                        "retry_in_seconds": round(delay, 2),
                        "policy": response.headers.get("X-HubSpot-RateLimit-Policy")
                        or self._error_body(response).get("policyName"),
                    },
                )
                time.sleep(delay)
                continue

            raise self._map_error(response, operation)

    def _retry_delay(self, response: requests.Response, attempt: int) -> float:
        """Honour Retry-After when present, otherwise exponential back-off."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 0.5)
            except ValueError:
                pass
        if response.status_code == 429:
            # Wait out the rest of HubSpot's 10 s window if we know it
            interval_ms = self.last_rate_limit_info.get("interval_ms")
            if interval_ms:
                return min(interval_ms / 1000.0, 10.0)
        return self.retry_backoff_seconds * (2 ** (attempt - 1))

    @staticmethod
    def _error_body(response: requests.Response) -> Dict[str, Any]:
        try:
            body = response.json()
            return body if isinstance(body, dict) else {}
        except ValueError:
            return {}

    def _map_error(self, response: requests.Response, operation: str) -> HubSpotAPIError:
        body = self._error_body(response)
        message = body.get("message") or response.text[:300] or response.reason
        category = body.get("category")
        correlation_id = body.get("correlationId")
        status = response.status_code

        self.logger.error(
            "HubSpot API error",
            extra={
                "operation": operation,
                "status_code": status,
                "category": category,
                "correlation_id": correlation_id,
                "hubspot_message": message,
            },
        )

        if status == 401:
            cls = HubSpotAuthenticationError
        elif status == 403:
            cls = HubSpotPermissionError
        elif status == 404:
            cls = HubSpotNotFoundError
        elif status == 429:
            cls = HubSpotRateLimitError
        elif status in (400, 422):
            cls = HubSpotValidationError
        elif status >= 500:
            cls = HubSpotServerError
        else:
            cls = HubSpotAPIError
        return cls(message, status_code=status, category=category, correlation_id=correlation_id)

    def _capture_rate_limit_headers(self, response: requests.Response) -> None:
        h = response.headers

        def _int(name: str) -> Optional[int]:
            value = h.get(name)
            try:
                return int(value) if value is not None else None
            except ValueError:
                return None

        info = {
            "daily_limit": _int("X-HubSpot-RateLimit-Daily"),
            "daily_remaining": _int("X-HubSpot-RateLimit-Daily-Remaining"),
            "interval_ms": _int("X-HubSpot-RateLimit-Interval-Milliseconds"),
            "interval_max": _int("X-HubSpot-RateLimit-Max"),
            "interval_remaining": _int("X-HubSpot-RateLimit-Remaining"),
        }
        info = {k: v for k, v in info.items() if v is not None}
        if info:
            info["captured_at"] = datetime.now(timezone.utc).isoformat()
            self.last_rate_limit_info = info

    def _adaptive_throttle(self, operation: str) -> None:
        """
        Back off pre-emptively when HubSpot says the current window is almost
        used up (protects against other apps sharing the same portal quota).
        """
        remaining = self.last_rate_limit_info.get("interval_remaining")
        interval_ms = self.last_rate_limit_info.get("interval_ms") or 10000
        if remaining is not None and remaining <= 5:
            pause = interval_ms / 1000.0 / 2
            self.logger.warning(
                "HubSpot rate-limit window nearly exhausted, pausing",
                extra={"operation": operation, "remaining": remaining, "pause_seconds": pause},
            )
            time.sleep(pause)

    # ------------------------------------------------------------------ #
    # Deals
    # ------------------------------------------------------------------ #
    def get_deals(
        self,
        access_token: str,
        limit: int = 100,
        after: Optional[str] = None,
        properties: Optional[List[str]] = None,
        archived: bool = False,
        associations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch one page of deals.

        GET /crm/v3/objects/deals?limit=&after=&properties=&archived=

        Returns the raw HubSpot response:
            {"results": [...], "paging": {"next": {"after": "...", "link": "..."}}}
        `paging` is absent on the last page.
        """
        params: Dict[str, Any] = {
            "limit": max(1, min(int(limit), self.MAX_PAGE_SIZE)),
            "archived": str(bool(archived)).lower(),
        }
        if after:
            params["after"] = after
        props = properties or DEFAULT_DEAL_PROPERTIES
        params["properties"] = ",".join(props)
        if associations:
            params["associations"] = ",".join(associations)

        self.logger.debug(
            "Fetching deals page",
            extra={
                "operation": "get_deals",
                "limit": params["limit"],
                "has_cursor": bool(after),
                "property_count": len(props),
                "archived": archived,
            },
        )
        data = self._request("GET", self.DEALS_ENDPOINT, access_token, params=params, operation="get_deals")
        self.logger.info(
            "Deals page retrieved",
            extra={
                "operation": "get_deals",
                "result_count": len(data.get("results", [])),
                "has_more": bool(self.next_cursor(data)),
            },
        )
        return data

    def iter_deals(
        self,
        access_token: str,
        page_size: int = 100,
        properties: Optional[List[str]] = None,
        archived: bool = False,
        after: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Convenience generator yielding every deal across all pages."""
        pages = 0
        while True:
            page = self.get_deals(access_token, page_size, after, properties, archived)
            yield from page.get("results", [])
            pages += 1
            after = self.next_cursor(page)
            if not after or (max_pages and pages >= max_pages):
                return

    def get_deal(self, access_token: str, deal_id: str, properties: Optional[List[str]] = None) -> Dict[str, Any]:
        """GET /crm/v3/objects/deals/{dealId}"""
        params = {"properties": ",".join(properties or DEFAULT_DEAL_PROPERTIES)}
        return self._request(
            "GET", f"{self.DEALS_ENDPOINT}/{deal_id}", access_token, params=params, operation="get_deal"
        )

    @staticmethod
    def next_cursor(page: Dict[str, Any]) -> Optional[str]:
        """Extract the `after` cursor for the next page, or None on the last page."""
        return ((page.get("paging") or {}).get("next") or {}).get("after")

    def get_deal_properties(self, access_token: str) -> List[Dict[str, Any]]:
        """
        GET /crm/v3/properties/deals - every deal property defined in the portal
        (name, label, type, fieldType, groupName, ...). Used to drive type
        conversion and to request all properties when filters ask for "*".
        """
        data = self._request(
            "GET", self.DEAL_PROPERTIES_ENDPOINT, access_token, operation="get_deal_properties"
        )
        return data.get("results", [])

    def get_deal_pipelines(self, access_token: str) -> List[Dict[str, Any]]:
        """GET /crm/v3/pipelines/deals - pipelines and their stage IDs/labels."""
        data = self._request(
            "GET", self.DEAL_PIPELINES_ENDPOINT, access_token, operation="get_deal_pipelines"
        )
        return data.get("results", [])

    # ------------------------------------------------------------------ #
    # Credentials / diagnostics
    # ------------------------------------------------------------------ #
    def validate_credentials(self, access_token: str) -> Dict[str, Any]:
        """
        Validate a token by performing the cheapest call that needs the
        crm.objects.deals.read scope. Never raises; returns a result dict.
        """
        result: Dict[str, Any] = {"valid": False, "has_deals_scope": False, "error": None}
        try:
            self._request(
                "GET",
                self.DEALS_ENDPOINT,
                access_token,
                params={"limit": 1, "properties": "dealname"},
                operation="validate_credentials",
            )
            result.update(valid=True, has_deals_scope=True)
            self.logger.info("HubSpot credentials validated", extra={"operation": "validate_credentials"})
        except HubSpotPermissionError as exc:
            # Token authenticates but lacks the deals scope
            result.update(valid=True, has_deals_scope=False, error=str(exc))
        except HubSpotAPIError as exc:
            result["error"] = str(exc)
        except Exception as exc:  # pragma: no cover - defensive
            result["error"] = f"Unexpected error: {exc}"
        if result["error"]:
            self.logger.warning(
                "HubSpot credential validation failed",
                extra={"operation": "validate_credentials", "error": result["error"]},
            )
        return result

    def validate_token(self, access_token: str) -> bool:
        """Backward-compatible boolean wrapper used by the generated template."""
        r = self.validate_credentials(access_token)
        return r["valid"] and r["has_deals_scope"]

    def get_account_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """GET /account-info/v3/details - portalId, timeZone, companyCurrency, ..."""
        try:
            return self._request(
                "GET", self.ACCOUNT_INFO_ENDPOINT, access_token, operation="get_account_info"
            )
        except HubSpotAPIError as exc:
            self.logger.debug("Account info unavailable", extra={"operation": "get_account_info", "error": str(exc)})
            return None

    def get_api_usage(self) -> Dict[str, Any]:
        """Last rate-limit headers seen plus the number of requests made."""
        return {**self.last_rate_limit_info, "requests_made": self.request_count}

    def test_connection(self, access_token: str) -> Dict[str, Any]:
        """Full connectivity diagnostic used by tooling/tests."""
        creds = self.validate_credentials(access_token)
        return {
            "token_valid": creds["valid"],
            "has_deals_scope": creds["has_deals_scope"],
            "account_info": self.get_account_info(access_token) if creds["valid"] else None,
            "usage_info": self.get_api_usage(),
            "error": creds["error"],
        }
