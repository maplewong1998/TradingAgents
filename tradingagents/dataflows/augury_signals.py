"""Point-in-time forecast and signal-family state functions for Augury."""

from __future__ import annotations

from .augury_core import _as_of_date, _format_value, _request, requests
from .errors import NoMarketDataError
from .symbol_utils import normalize_symbol


def get_augury_ai_forecast(ticker: str, curr_date: str | None) -> str:
    """Return a point-in-time-safe Kronos forecast report.

    Kronos is a live-vintage cache read. A prediction newer than the analysis
    date is withheld rather than exposing look-ahead information (#e03s05,
    SC-e03s05-P0-01); cache misses use the normal no-data sentinel.
    """
    canonical = normalize_symbol(ticker)
    path = f"/signals/{canonical}/kronos"
    try:
        payload = _request(path, {})
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc

    if not isinstance(payload, dict) or not payload.get("data_available", False):
        hint = payload.get("hint") if isinstance(payload, dict) else None
        raise NoMarketDataError(
            ticker,
            canonical,
            hint or "Kronos forecast is not cached; POST /data/kronos may be required",
        )

    analysis_date = _as_of_date(curr_date)
    data_asof = payload.get("data_asof")
    if data_asof and _as_of_date(data_asof) > analysis_date:
        return (
            f"## Augury Kronos AI forecast for {canonical}\n\n"
            f"Forecast withheld: its data_asof date ({data_asof}) is later than the "
            f"as-of analysis date ({curr_date or analysis_date.isoformat()}). Serving "
            "it would introduce look-ahead information into this analysis."
        )

    lines = [
        f"## Augury Kronos AI forecast for {canonical}",
        "",
        "### Forecast",
        f"- predicted_return_pct: {_format_value(payload.get('predicted_return_pct'))}",
        f"- forecast_window: {_format_value(payload.get('forecast_window'))}",
        f"- bull_signal: {_format_value(payload.get('bull_signal'))}",
        f"- bear_signal: {_format_value(payload.get('bear_signal'))}",
        f"- neutral_signal: {_format_value(payload.get('neutral_signal'))}",
        f"- upside_probability: {_format_value(payload.get('upside_probability'))}",
        f"- model_name: {_format_value(payload.get('model_name'))}",
        "",
        "### Data honesty",
        f"- data_available: {_format_value(payload.get('data_available'))}",
        f"- degraded: {_format_value(payload.get('degraded'))}",
        f"- stale_days: {_format_value(payload.get('stale_days'))}",
        f"- data_asof: {_format_value(payload.get('data_asof'))}",
    ]
    return "\n".join(lines) + "\n"


# Keep this client vocabulary pinned to the lake registry's SIGNAL_FAMILIES in
# signals/registry.py so a caller gets a useful validation message instead of
# leaking the upstream KeyError for a mistyped family (#e03s06).
AUGURY_SIGNAL_FAMILIES = (
    "sma_streak",
    "sma_cross",
    "rsi_cross",
    "macd_cross",
    "bb_cross",
    "adx_breakout",
    "psar_flip",
    "hurst",
    "regime",
    "sentiment",
    "insider",
    "earnings_surprise",
    "quality",
)

def _signal_family_error(family: str, detail: str | None = None) -> str:
    valid = ", ".join(AUGURY_SIGNAL_FAMILIES)
    reason = f" ({detail})" if detail else ""
    return f"Unknown signal family '{family}'{reason}. Valid families: {valid}."

def get_augury_signal_states(ticker: str, family: str, curr_date: str) -> str:
    """Return versioned point-in-time trigger states for one signal family.

    The lake requires both ``family`` and ``as_of``. Invalid families are a
    caller/tool-input error, so they return an instructive message rather than
    raising through the optional enrichment category (#e03s06).
    """
    canonical = normalize_symbol(ticker)
    if family not in AUGURY_SIGNAL_FAMILIES:
        return _signal_family_error(family)

    path = f"/api/v1/signals/{canonical}"
    try:
        payload = _request(path, {"family": family, "as_of": curr_date})
    except requests.HTTPError as exc:
        response = exc.response
        status_code = getattr(response, "status_code", None)
        if status_code == 422:
            try:
                body = response.json()
            except (TypeError, ValueError):
                body = {}
            detail = body.get("detail") if isinstance(body, dict) else None
            return _signal_family_error(family, detail)
        raise
    except NoMarketDataError as exc:
        raise NoMarketDataError(ticker, canonical, exc.detail) from exc

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    if not rows:
        raise NoMarketDataError(
            ticker,
            canonical,
            f"no '{family}' signal states as of {curr_date}",
        )

    lines = [
        f"## Augury {family} signal states for {canonical} as of {curr_date}",
        "",
        "| Signal Date | Triggered | Detail | Version |",
        "| --- | --- | --- | ---: |",
    ]
    for row in rows:
        detail = row.get("detail")
        if detail is None:
            direction = row.get("direction")
            value = row.get("value")
            detail = ", ".join(
                part for part in (
                    f"direction={direction}" if direction is not None else None,
                    f"value={value}" if value is not None else None,
                ) if part
            ) or "none"
        version = row.get("formula_version", row.get("version"))
        lines.append(
            "| "
            + " | ".join(
                _format_value(value)
                for value in (
                    row.get("signal_date"),
                    row.get("triggered"),
                    detail,
                    version,
                )
            )
            + " |"
        )
    return "\\n".join(lines) + "\\n"
