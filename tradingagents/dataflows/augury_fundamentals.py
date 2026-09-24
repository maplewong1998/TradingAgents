"""Fundamental statements, valuation, and universe functions for Augury."""

from __future__ import annotations

from datetime import date

from .augury_core import _date_value, _format_value, _job_hint, _request
from .errors import NoMarketDataError
from .symbol_utils import normalize_symbol
from .utils import get_current_date

_FUNDAMENTAL_LABELS = {"pe_ratio": "PE Ratio", "pb_ratio": "Price to Book", "market_cap": "Market Cap", "sector": "Sector", "dividend_yield": "Dividend Yield", "valid_from": "Valid From", "valid_to": "Valid To", "ingested_at": "Ingested At"}

_FINANCIALS_FIELDS = ("ticker", "statement", "metric", "period_end", "report_date", "restatement_id", "value")
# The lake's ``statement`` vocabulary is balance/income/cashflow; keep this
# mapping at the boundary so report labels cannot drift from pit.py (#e03s02).
_STATEMENT_NAMES = {"balance": "Balance Sheet", "cashflow": "Cash Flow", "income": "Income Statement"}

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

_VALUATION_SUMMARY_FIELDS = ("average_value", "median_value", "min_value", "max_value", "current_price", "average_premium_discount", "margin_of_safety", "undervalued_count", "overvalued_count", "fair_count", "reliable_count", "total_methods")


def get_augury_valuation(ticker: str, curr_date: str | None) -> str:
    """Return Augury's cached multi-method valuation as markdown.

    Valuation has no historical-vintage parameter. The report therefore names
    that live-vintage limitation for past analysis dates, while a 404 is raised
    as typed no-data so the optional category can fail open (#e03s05).
    """
    canonical = normalize_symbol(ticker)
    path = f"/valuation/{canonical}"
    try:
        payload = _request(path, {})
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc

    if not isinstance(payload, dict):
        raise NoMarketDataError(ticker, canonical, "valuation response was not an object")

    lines = [f"## Augury valuation for {canonical}", ""]
    if curr_date and curr_date < get_current_date():
        lines.extend(
            [
                f"> Live-vintage caveat: Augury valuation is served from the current "
                f"cache and has no historical vintage for {curr_date}.",
                "",
            ]
        )

    methods = payload.get("methods") or []
    lines.extend(
        [
            "### Valuation methods",
            "",
            "| Method | Fair Value | Current Price | Premium/Discount | Assessment | Confidence | Reliable |",
            "| --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for method in methods:
        if not isinstance(method, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                _format_value(method.get(field))
                for field in (
                    "method",
                    "fair_value",
                    "current_price",
                    "premium_discount",
                    "assessment",
                    "confidence",
                    "is_reliable",
                )
            )
            + " |"
        )

    summary = payload.get("summary")
    if isinstance(summary, dict):
        lines.extend(
            [
                "",
                "### Valuation summary",
                "",
                "| Measure | Value |",
                "| --- | ---: |",
            ]
        )
        for field in _VALUATION_SUMMARY_FIELDS:
            lines.append(f"| {field} | {_format_value(summary.get(field))} |")

    return "\n".join(lines) + "\n"

def _universe_row_is_delisted(row: dict) -> bool:
    """Recognize explicit lifecycle markers without treating absence as delisting."""
    if row.get("delisted") is True:
        return True
    for field in ("lifecycle_status", "status"):
        if str(row.get(field, "")).casefold() == "delisted":
            return True
    return row.get("valid_to") is not None


def get_augury_universe_membership(ticker: str, curr_date: str | None) -> str:
    """Render Augury's PIT universe membership, including delisted evidence."""
    canonical = normalize_symbol(ticker)
    as_of = curr_date or get_current_date()
    path = "/api/v1/universe"
    try:
        payload = _request(path, {"as_of": as_of, "q": canonical})
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    matching = [
        row for row in rows if normalize_symbol(str(row.get("ticker", ""))) == canonical
    ]

    if not matching:
        status = "absent from the Augury tradeable universe"
    elif any(_universe_row_is_delisted(row) for row in matching):
        status = "present but delisted in the Augury tradeable universe"
    else:
        status = "member of the Augury tradeable universe"

    lines = [
        f"## Augury universe membership for {canonical} as of {as_of}",
        "",
        f"- status: {status}",
    ]
    if matching:
        row = matching[0]
        for field in ("source", "valid_from", "valid_to", "sector"):
            if row.get(field) is not None:
                lines.append(f"- {field}: {_format_value(row.get(field))}")
    return "\n".join(lines) + "\n"
