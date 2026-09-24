"""News, macro-calendar, and prediction-market functions for Augury."""

from __future__ import annotations

import re
from datetime import date

from .augury_core import _date_value, _format_value, _request
from .errors import NoMarketDataError
from .symbol_utils import normalize_symbol
from .utils import get_current_date


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
