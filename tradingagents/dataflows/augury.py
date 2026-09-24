"""Read-only HTTP vendor for the cache-first augury data lake.

Augury is consumed over its API boundary rather than imported as a Python
package. Reads are cache-first, so a missing ticker can mean that the matching
lake refresh job has not run yet; this module turns that condition into the
existing ``VendorError`` taxonomy instead of starting a job (#e03s01).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta

import requests

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError
from .symbol_utils import normalize_symbol
from .utils import get_current_date

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

# This is the exact intersection of market_analyst.py's advertised names and the
# columns assembled by augury signals/daily_features.py:121-141 (#e03s03).
_INDICATOR_MAP = {
    "close_200_sma": "sma_200",
    "macd": "macd_line",
    "macdh": "macd_histogram",
    "macds": "macd_signal",
    "mfi": "mfi_14",
    "rsi": "rsi_14",
    "atr": "atr_14",
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
    if isinstance(value, datetime):
        return value.date()
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


def get_augury_indicators(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    """Return one mapped technical indicator from Augury's feature rows.

    The technical-indicator tool clamps ``curr_date`` to the analysis date before
    this vendor is called. Unmapped stockstats vocabulary is deliberately declined
    so a configured fallback can calculate it without guessing a lake column
    (#e03s03, D4).
    """
    canonical = normalize_symbol(symbol)
    mapped = _INDICATOR_MAP.get(indicator)
    if mapped is None:
        served = ", ".join(sorted(set(_INDICATOR_MAP.values())))
        raise NoMarketDataError(
            symbol,
            canonical,
            f"augury does not serve indicator '{indicator}'; served set: {served}",
        )

    end_date = datetime.strptime(curr_date, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=look_back_days)
    path = f"/api/v1/features/{canonical}"
    try:
        payload = _request(
            path,
            {
                "start": start_date.isoformat(),
                "end": curr_date,
                "fields": mapped,
                "page": 1,
                "page_size": 200,
            },
        )
    except NoMarketDataError as exc:
        raise NoMarketDataError(symbol, canonical, exc.detail) from exc

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    if not rows:
        raise NoMarketDataError(
            symbol,
            canonical,
            f"no {mapped} rows between {start_date} and {curr_date}",
        )

    lines = [
        f"## {indicator} values from {start_date} to {curr_date}:",
        "",
        f"| Date | {mapped} |",
        "| --- | ---: |",
    ]
    for row in rows:
        lines.append(f"| {_format_value(row.get('trade_date'))} | {_format_value(row.get(mapped))} |")
    return "\n".join(lines) + "\n"


def get_augury_news(ticker: str, start_date: str, end_date: str) -> str:
    """Return Augury news filtered to the caller's point-in-time date window.

    Augury's news endpoint has no ``as_of`` parameter, so filtering its response
    locally is mandatory: future articles must not enter a backtest report
    (#e03s03, SC-e03s03-P0-01).
    """
    canonical = normalize_symbol(ticker)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    window_days = (end - start).days + 1
    if window_days < 1:
        raise NoMarketDataError(ticker, canonical, f"invalid news window {start_date} to {end_date}")

    path = f"/news/{canonical}"
    try:
        payload = _request(path, {"days": window_days + 7})
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    filtered = [
        row
        for row in rows
        if isinstance(row, dict)
        and (published := _date_value(row.get("published_at"))) is not None
        and start <= published <= end
    ]
    if not filtered:
        raise NoMarketDataError(
            ticker,
            canonical,
            f"no news between {start_date} and {end_date} after client-side PIT filtering",
        )

    lines = [f"## {canonical} News, from {start_date} to {end_date}:", ""]
    for row in filtered:
        lines.extend(
            [
                f"### {_format_value(row.get('title'))}",
                f"- URL: {_format_value(row.get('url'))}",
                f"- Tickers: {_format_value(row.get('tickers'))}",
                f"- Source: {_format_value(row.get('source'))}",
                f"- Summary: {_format_value(row.get('summary'))}",
                f"- Sentiment: {_format_value(row.get('sentiment_score'))} ({_format_value(row.get('sentiment_label'))})",
                f"- Topics: {_format_value(row.get('topics'))}",
                f"- Published At: {_format_value(row.get('published_at'))}",
                "",
            ]
        )
    return "\n".join(lines)


DEFAULT_MACRO_LOOKBACK_DAYS = 365


def get_augury_macro_data(
    indicator: str,
    curr_date: str,
    look_back_days: int | None = None,
) -> str:
    """Return Augury's calendar observations for a macro indicator.

    The lake stores release-calendar rows rather than FRED series metadata. Keep
    that distinction visible so callers do not mistake an event table for a
    revised time series (#e03s04).
    """
    if look_back_days is None:
        look_back_days = DEFAULT_MACRO_LOOKBACK_DAYS

    payload = _request("/macro", {"indicator": indicator, "days": look_back_days})
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    if not rows:
        raise NoMarketDataError(indicator, detail=f"no macro observations for '{indicator}'")

    lines = [
        f'## Augury macro observations for "{indicator}" (calendar-style observations)',
        "- Calendar-style observations; the lake does not serve series metadata.",
        "- Rows marked [PIT approximate] use an approximate point-in-time value.",
        "",
        "| Date | Actual | Forecast | Previous |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        observed_date = _format_value(row.get("date"))
        if row.get("pit_approximate"):
            observed_date += " [PIT approximate]"
        lines.append(
            "| "
            + " | ".join(
                (
                    observed_date,
                    _format_value(row.get("actual")),
                    _format_value(row.get("forecast")),
                    _format_value(row.get("previous")),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


_PREDICTION_CATEGORY_KEYWORDS = {
    "fed": ("fed", "federal reserve", "fomc", "rate cut", "rate hike"),
    "recession": ("recession",),
    "election": ("election", "president", "presidential"),
    "crypto": ("crypto", "bitcoin", "ethereum"),
    "geopolitics": ("geopolitics", "geopolitical"),
}
DEFAULT_PREDICTION_MARKET_LIMIT = 6


def _prediction_category(topic: str) -> str | None:
    normalized = topic.casefold()
    for category, keywords in _PREDICTION_CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return None


def _prediction_topic_matches(topic: str, market: dict) -> bool:
    keywords = set(re.findall(r"[a-z0-9]+", topic.casefold()))
    searchable = " ".join(
        str(market.get(field) or "").casefold() for field in ("question", "slug")
    )
    searchable = " ".join(re.findall(r"[a-z0-9]+", searchable))
    return bool(keywords & set(searchable.split()))


def _augury_market_is_forward_looking(market: dict) -> bool:
    if market.get("closed") or market.get("active") is False:
        return False
    end_date = market.get("end_date")
    if end_date:
        try:
            if date.fromisoformat(str(end_date)[:10]) < date.today():
                return False
        except ValueError:
            pass
    return bool(market.get("outcomes")) and bool(market.get("outcome_prices"))


def get_augury_prediction_markets(
    topic: str,
    limit: int | None = None,
    curr_date: str | None = None,
) -> str:
    """Return cached Augury market odds matching a topic.

    Augury has no free-text query parameter, so topic matching happens locally
    over the question and slug. Cached odds are withheld for historical runs;
    the lake does not provide a market vintage (#e03s04).
    """
    if curr_date and curr_date < get_current_date():
        return (
            f"Prediction-market odds are withheld for {curr_date}. Augury serves "
            f"only cached current odds, with no historical vintage, so serving "
            f"them would put post-decision information into a {curr_date} analysis."
        )

    if limit is None:
        limit = DEFAULT_PREDICTION_MARKET_LIMIT
    params = {"limit": limit}
    category = _prediction_category(topic)
    if category is not None:
        params["category"] = category

    payload = _request("/prediction-markets", params)
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    candidates = [
        row
        for row in rows
        if isinstance(row, dict)
        and _prediction_topic_matches(topic, row)
        and _augury_market_is_forward_looking(row)
    ]
    candidates.sort(key=lambda row: row.get("volume") or 0, reverse=True)

    header = (
        f'## Augury prediction markets: "{topic}"\n'
        "Cached, market-implied probabilities (higher volume = deeper, more reliable). "
        "A probability is the crowd's priced odds, not a forecast you should take as certain.\n\n"
    )
    if not candidates:
        return header + f"No open prediction markets matched '{topic}'.\n"

    lines = []
    for market in candidates[:limit]:
        prices = market.get("outcome_prices") or []
        outcomes = market.get("outcomes") or []
        try:
            probability = float(prices[0])
        except (IndexError, TypeError, ValueError):
            continue
        label = outcomes[0] if outcomes else "Yes"
        volume = market.get("volume") or 0
        end_date = str(market.get("end_date") or "")[:10]
        lines.append(
            f"- **{market.get('question')}** — {label} {probability:.0%} "
            f"(${volume:,.0f} volume, resolves {end_date})"
        )
    return header + "\n".join(lines) + "\n"


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
