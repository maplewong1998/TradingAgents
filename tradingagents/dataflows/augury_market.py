"""Market, technical-indicator, and cross-sectional Augury functions."""

from __future__ import annotations

from datetime import datetime, timedelta

from .augury_core import _format_value, _request, _request_post
from .errors import NoMarketDataError
from .symbol_utils import normalize_symbol
from .utils import get_current_date

_LIQUIDITY_FIELDS = (
    "last_date",
    "last_trade_date",
    "data_age_days",
    "warning",
    "window_days",
    "trading_days",
    "zero_volume_days",
    "stale",
    "suspended",
    "adv_shares",
    "adv_dollar_vol",
    "median_dollar_vol",
    "amihud_illiq",
    "amivest",
    "roll_spread",
    "cs_spread",
    "vol_hhi",
    "rvol",
    "latest_price",
    "avg_close",
    "currency",
    "data_missing",
    "halt_status",
    "halt_detected_at",
)

def get_augury_liquidity(ticker: str, curr_date: str | None) -> str:
    """Return Augury's liquidity facts, withholding its live-vintage read in PIT runs.

    The OpenAPI contract exposes only ``window_days`` for this endpoint, with no
    ``as_of`` or ``vintage`` pin. A historical report must therefore not consume
    today's computed liquidity (#e03s07, SC-e03s07-P1-03).
    """
    canonical = normalize_symbol(ticker)
    if curr_date and curr_date < get_current_date():
        return (
            f"## Augury liquidity for {canonical}\n\n"
            f"Liquidity withheld for {curr_date}: the Augury liquidity endpoint is "
            "live-vintage-only and has no as_of or vintage parameter."
        )

    path = f"/liquidity/{canonical}"
    try:
        payload = _request(path, {"window_days": 90})
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc
    if not isinstance(payload, dict):
        raise NoMarketDataError(ticker, canonical, "liquidity response was not an object")

    lines = [f"## Augury liquidity for {canonical}", ""]
    for field in _LIQUIDITY_FIELDS:
        if field in payload:
            lines.append(f"- {field}: {_format_value(payload.get(field))}")
    return "\n".join(lines) + "\n"

def _feature_vector_failure(failed: list, canonical: str) -> str | None:
    """Find the requested ticker's failure reason in a batch response."""
    for failure in failed:
        if isinstance(failure, dict):
            failure_ticker = normalize_symbol(str(failure.get("ticker", "")))
            if failure_ticker != canonical:
                continue
            return str(failure.get("reason") or failure.get("detail") or "request failed")
        text = str(failure)
        if text.upper() == canonical or text.upper().startswith(f"{canonical}:"):
            reason = text[len(canonical):].lstrip(" :")
            return reason or "request failed"
    return None

def get_augury_feature_vector(ticker: str, curr_date: str | None) -> str:
    """Return one PIT-pinned item from Augury's cross-sectional batch endpoint.

    Although the lake accepts 1--500 tickers, this analyst-bound wrapper sends
    one ticker so a per-ticker failure remains explicit rather than being
    mistaken for a batch-level absence (#e03s07, SC-e03s07-P1-01).
    """
    canonical = normalize_symbol(ticker)
    path = "/api/v1/batch/feature-vector"
    try:
        payload = _request_post(
            path,
            {"tickers": [canonical], "as_of": curr_date, "vintage": "current"},
        )
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc
    if not isinstance(payload, dict):
        raise NoMarketDataError(ticker, canonical, "feature-vector response was not an object")

    failed = payload.get("failed") or []
    reason = _feature_vector_failure(failed, canonical)
    if reason is not None:
        return (
            f"## Augury feature vector for {canonical}\n\n"
            f"- status: not available: {reason}\n"
        )

    items = payload.get("items") or []
    item = next(
        (
            candidate
            for candidate in items
            if isinstance(candidate, dict)
            and normalize_symbol(str(candidate.get("ticker", ""))) == canonical
        ),
        None,
    )
    if item is None:
        return (
            f"## Augury feature vector for {canonical}\n\n"
            "- status: not available: the lake omitted this ticker from the response"
            "\n"
        )

    lines = [f"## Augury feature vector for {canonical}", ""]
    for field in ("as_of", "data_vintage"):
        if field in payload:
            lines.append(f"- {field}: {_format_value(payload.get(field))}")
    for section in ("features", "fundamentals", "ground_truth", "watermark"):
        values = item.get(section)
        if not isinstance(values, dict):
            continue
        lines.extend(["", f"### {section}"])
        lines.extend(f"- {key}: {_format_value(value)}" for key, value in values.items())
    return "\n".join(lines) + "\n"

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
