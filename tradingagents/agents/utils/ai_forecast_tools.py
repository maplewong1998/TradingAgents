"""Optional Augury forecast and valuation tools for analyst nodes (#e03s05)."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.date_window import as_of
from tradingagents.dataflows.interface import route_to_vendor


def is_augury_enabled(category: str, method: str) -> bool:
    """Return whether an explicit Augury chain enables one optional tool.

    ``default`` deliberately does not count as opt-in: the forecast and
    valuation are live-vintage enrichment and must be absent from a stock
    configuration unless the operator names Augury (#e03s05, D3).
    """
    config = get_config()
    tool_vendors = config.get("tool_vendors", {})
    chain = tool_vendors.get(method, config.get("data_vendors", {}).get(category, "default"))
    vendors = chain if isinstance(chain, (list, tuple)) else str(chain).split(",")
    return any(str(vendor).strip().casefold() == "augury" for vendor in vendors)


@tool
def get_ai_forecast(
    ticker: Annotated[str, "Ticker symbol to forecast"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Retrieve Augury's cached Kronos AI forecast for a ticker.

    The requested date is clamped to the run's trade date, and a live-vintage
    forecast newer than that date is withheld rather than leaking future data.
    """
    return route_to_vendor("get_ai_forecast", ticker, as_of(curr_date, trade_date))


@tool
def get_valuation(
    ticker: Annotated[str, "Ticker symbol to value"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Retrieve Augury's cached multi-method valuation for a ticker.

    The requested date is clamped to the run's trade date. A missing cached
    fundamentals snapshot returns the optional-category unavailable sentinel.
    """
    return route_to_vendor("get_valuation", ticker, as_of(curr_date, trade_date))
