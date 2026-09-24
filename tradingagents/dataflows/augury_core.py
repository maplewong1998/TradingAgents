"""Shared HTTP machinery for the cache-first Augury vendor family.

Augury is consumed over its API boundary rather than imported as a Python
package. Reads are cache-first, so a missing ticker can mean that the matching
lake refresh job has not run yet; this module turns that condition into the
existing ``VendorError`` taxonomy instead of starting a job (#e03s01).
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime

import requests

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8765"
REQUEST_TIMEOUT = 30

def get_base_url() -> str:
    """Resolve the augury endpoint, with an empty env value disabling the vendor."""
    if "AUGURY_BASE_URL" in os.environ:
        base_url = os.environ["AUGURY_BASE_URL"]
    else:
        base_url = get_config().get("augury_base_url", DEFAULT_BASE_URL)
    if not base_url:
        raise VendorNotConfiguredError(
            "Augury is not configured: set AUGURY_BASE_URL or augury_base_url."
        )
    return base_url.rstrip("/")

def _job_hint(path: str) -> str:
    """Return the refresh job that can populate the read endpoint."""
    if "/bars/" in path:
        return "the lake may need the matching POST /data/ohlcv refresh job first"
    if "/fundamentals/" in path:
        return "the lake may need the matching POST /data/fundamentals refresh job first"
    if "/financials/" in path:
        return "the lake may need the matching POST /data/financials refresh job first"
    if "/valuation/" in path or "/kronos" in path:
        return "the lake may need the matching POST /data/kronos or fundamentals refresh job first"
    return "the lake may need the matching POST /data/* refresh job first"

def _response_payload(path: str, response) -> dict:
    """Validate an Augury response and map its frozen ErrorResponse envelope."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        error_response = exc.response or response
        status_code = getattr(error_response, "status_code", response.status_code)
        try:
            body = error_response.json()
        except (TypeError, ValueError):
            body = {}
        code = body.get("code")
        detail = body.get("detail") or getattr(error_response, "text", "")
        logger.warning("Augury request failed with status %s (code=%s)", status_code, code)
        symbol = path.rstrip("/").rsplit("/", 1)[-1]
        if status_code == 404 or code == "not_found":
            raise NoMarketDataError(
                symbol,
                detail=f"{detail}; {_job_hint(path)}",
            ) from exc
        if status_code == 429 or code == "rate_limited":
            raise VendorRateLimitError(detail or "Augury rate limit reached") from exc
        raise
    return response.json()

def _request(path: str, params: dict) -> dict:
    """GET an augury endpoint and map its frozen ErrorResponse envelope.

    Connection and timeout exceptions intentionally remain untouched. The
    routing seam logs those failures loudly and can continue to the next
    configured vendor (#989).
    """
    response = requests.get(
        f"{get_base_url()}/{path.lstrip('/')}",
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    return _response_payload(path, response)

def _request_post(path: str, payload: dict) -> dict:
    """POST a synchronous Augury read endpoint through the same error seam."""
    response = requests.post(
        f"{get_base_url()}/{path.lstrip('/')}",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    return _response_payload(path, response)

def _format_value(value) -> str:
    if value is None:
        return ""
    return str(value)

def _date_value(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None

def _as_of_date(value: str | None) -> date:
    """Parse an API date or timestamp for the forecast vintage guard."""
    parsed = _date_value(value)
    return parsed or date.today()
