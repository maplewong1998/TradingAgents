"""Read-only HTTP vendor for the cache-first augury data lake.

Augury is consumed over its API boundary rather than imported as a Python
package. Reads are cache-first, so a missing ticker can mean that the matching
lake refresh job has not run yet; this module turns that condition into the
existing ``VendorError`` taxonomy instead of starting a job (#e03s01).
"""

from __future__ import annotations

import logging
import os

import requests

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError
from .symbol_utils import normalize_symbol

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
    return "the lake may need the matching POST /data/* refresh job first"


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


def _format_value(value) -> str:
    if value is None:
        return ""
    return str(value)


def get_augury_stock(symbol: str, start_date: str, end_date: str) -> str:
    """Return augury daily bars as a chronological markdown table.

    Augury pages are newest-first. All pages are therefore collected before
    reversing once, preserving chronology when a requested window crosses a
    page boundary (the lake's page size is capped at 200).
    """
    canonical = normalize_symbol(symbol)
    path = f"/api/v1/bars/{canonical}"
    rows: list[dict] = []
    page = 1

    while True:
        try:
            payload = _request(
                path,
                {
                    "start": start_date,
                    "end": end_date,
                    "page": page,
                    "page_size": 200,
                },
            )
        except NoMarketDataError as exc:
            # Preserve the user's symbol for the router sentinel while retaining
            # the canonical ticker used on the wire.
            raise NoMarketDataError(symbol, canonical, exc.detail) from exc
        page_rows = payload.get("data", []) if isinstance(payload, dict) else []
        rows.extend(page_rows)
        pagination = payload.get("pagination", {}) if isinstance(payload, dict) else {}
        total_pages = pagination.get("total_pages")
        if not page_rows or (total_pages is not None and page >= total_pages):
            break
        if total_pages is None and len(page_rows) < 200:
            break
        page += 1

    if not rows:
        raise NoMarketDataError(
            symbol,
            canonical,
            f"rows between {start_date} and {end_date}",
        )

    rows.reverse()
    lines = [
        f"# Stock data for {canonical} from {start_date} to {end_date}",
        f"# Total records: {len(rows)}",
        "",
        "| Date | Open | High | Low | Close | Volume | Adj Close |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                _format_value(row.get(field))
                for field in (
                    "trade_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "adj_close",
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
