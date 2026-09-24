"""Read-only HTTP vendor for the cache-first augury data lake.

Augury is consumed over its API boundary rather than imported as a Python
package. Reads are cache-first, so a missing ticker can mean that the matching
lake refresh job has not run yet; this module turns that condition into the
existing ``VendorError`` taxonomy instead of starting a job (#e03s01).
"""

from __future__ import annotations

import logging
import os
from datetime import date

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
    if "/fundamentals/" in path:
        return "the lake may need the matching POST /data/fundamentals refresh job first"
    if "/financials/" in path:
        return "the lake may need the matching POST /data/financials refresh job first"
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


_FUNDAMENTAL_LABELS = {
    "pe_ratio": "PE Ratio",
    "pb_ratio": "Price to Book",
    "market_cap": "Market Cap",
    "sector": "Sector",
    "dividend_yield": "Dividend Yield",
    "valid_from": "Valid From",
    "valid_to": "Valid To",
    "ingested_at": "Ingested At",
}

_FINANCIALS_FIELDS = (
    "ticker",
    "statement",
    "metric",
    "period_end",
    "report_date",
    "restatement_id",
    "value",
)
# The lake's ``statement`` vocabulary is balance/income/cashflow; keep this
# mapping at the boundary so report labels cannot drift from pit.py (#e03s02).
_STATEMENT_NAMES = {
    "balance": "Balance Sheet",
    "cashflow": "Cash Flow",
    "income": "Income Statement",
}


def get_augury_fundamentals(ticker: str, curr_date: str | None = None) -> str:
    """Return the point-in-time fundamentals snapshot from Augury.

    The lake requires ``as_of`` even when the caller leaves it unset. Passing
    it through unchanged keeps the upstream validation visible rather than
    replacing a missing date with today's live snapshot (#e03s02).
    """
    canonical = normalize_symbol(ticker)
    path = f"/api/v1/fundamentals/{canonical}"
    try:
        payload = _request(path, {"as_of": curr_date})
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc

    if not isinstance(payload, dict):
        raise NoMarketDataError(ticker, canonical, "fundamentals snapshot was not an object")

    lines = [
        f"{label}: {_format_value(payload.get(field))}"
        for field, label in _FUNDAMENTAL_LABELS.items()
        if payload.get(field) is not None
    ]
    if not lines:
        raise NoMarketDataError(ticker, canonical, "no fundamental fields returned")

    return f"# Company Fundamentals for {canonical}\n\n" + "\n".join(lines)


def _financial_rows(ticker: str, curr_date: str | None) -> tuple[str, list[dict]]:
    """Read every financial page in the lake's stable PIT order."""
    canonical = normalize_symbol(ticker)
    path = f"/api/v1/financials/{canonical}"
    rows: list[dict] = []
    page = 1

    while True:
        try:
            payload = _request(
                path,
                {
                    "as_of": curr_date,
                    "fields": ",".join(_FINANCIALS_FIELDS),
                    "page": page,
                    "page_size": 200,
                },
            )
        except NoMarketDataError as exc:
            raise NoMarketDataError(ticker, canonical, exc.detail) from exc

        page_rows = payload.get("data", []) if isinstance(payload, dict) else []
        rows.extend(row for row in page_rows if isinstance(row, dict))
        pagination = payload.get("pagination", {}) if isinstance(payload, dict) else {}
        total_pages = pagination.get("total_pages")
        if not page_rows or (total_pages is not None and page >= total_pages):
            break
        if total_pages is None and len(page_rows) < 200:
            break
        page += 1

    return canonical, rows


def _date_value(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _period_dates(rows: list[dict], freq: str) -> set[date]:
    """Infer annual versus quarterly dates from the lake period spacing.

    Augury currently serves facts without a frequency column. A repeated
    month/day roughly a year apart is the annual cadence; remaining dates with
    roughly three-month spacing are quarterly. This mirrors the endpoint's
    period-based contract while keeping the inference visible to callers
    (#e03s02).
    """
    dates = sorted({period for row in rows if (period := _date_value(row.get("period_end")))})
    if not dates:
        return set()
    if len(dates) == 1:
        return set(dates)

    annual: set[date] = set()
    quarterly: set[date] = set()
    for period in dates:
        for other in dates:
            if period == other:
                continue
            delta_days = abs((period - other).days)
            month_delta = abs((period.year - other.year) * 12 + period.month - other.month)
            day_delta = abs(period.day - other.day)
            if 300 <= delta_days <= 400 and month_delta % 12 == 0 and day_delta <= 31:
                annual.add(period)
            if 70 <= delta_days <= 120 and month_delta in (2, 3, 4):
                quarterly.add(period)

    return annual if freq == "annual" else quarterly - annual


def _get_augury_statement(
    ticker: str,
    statement: str,
    freq: str = "quarterly",
    curr_date: str | None = None,
) -> str:
    normalized_freq = freq.lower()
    if normalized_freq not in {"annual", "quarterly"}:
        raise ValueError("freq must be 'annual' or 'quarterly'")

    canonical, rows = _financial_rows(ticker, curr_date)
    matching = [row for row in rows if row.get("statement") == statement]
    wanted_periods = _period_dates(matching, normalized_freq)
    filtered = [
        row
        for row in matching
        if _date_value(row.get("period_end")) in wanted_periods
    ]
    if not filtered:
        label = _STATEMENT_NAMES[statement]
        raise NoMarketDataError(
            ticker,
            canonical,
            f"no {label.lower()} rows for {normalized_freq} frequency; "
            f"{_job_hint('/api/v1/financials/')}",
        )

    label = _STATEMENT_NAMES[statement]
    lines = [
        f"# {label} data for {canonical} ({normalized_freq})",
        "# Augury PIT facts are ordered newest period first; frequency is inferred from period spacing.",
        "",
        "| Metric | Period End | Report Date | Restatement | Value |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in filtered:
        lines.append(
            "| "
            + " | ".join(
                _format_value(row.get(field))
                for field in ("metric", "period_end", "report_date", "restatement_id", "value")
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def get_augury_balance_sheet(
    ticker: str, freq: str = "quarterly", curr_date: str | None = None
) -> str:
    """Return Augury point-in-time balance-sheet facts."""
    return _get_augury_statement(ticker, "balance", freq, curr_date)


def get_augury_cashflow(
    ticker: str, freq: str = "quarterly", curr_date: str | None = None
) -> str:
    """Return Augury point-in-time cash-flow facts."""
    return _get_augury_statement(ticker, "cashflow", freq, curr_date)


def get_augury_income_statement(
    ticker: str, freq: str = "quarterly", curr_date: str | None = None
) -> str:
    """Return Augury point-in-time income-statement facts."""
    return _get_augury_statement(ticker, "income", freq, curr_date)


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
            # the canonical ticker used on the wire (#e03s01).
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
