"""Optional Augury cross-sectional context tools for analyst nodes (#e03s07)."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tradingagents.dataflows.date_window import as_of
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_liquidity(
    ticker: Annotated[str, "Ticker symbol whose liquidity to inspect"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Retrieve Augury liquidity context for one ticker.

    The requested date is clamped to the run's trade date. Augury's endpoint is
    live-vintage-only, so historical requests return an explicit withholding
    notice instead of leaking current liquidity into a backtest.
    """
    return route_to_vendor("get_liquidity", ticker, as_of(curr_date, trade_date))


@tool
def get_feature_vector(
    ticker: Annotated[str, "Ticker symbol whose feature vector to inspect"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Retrieve Augury's point-in-time cross-sectional feature vector."""
    return route_to_vendor("get_feature_vector", ticker, as_of(curr_date, trade_date))


@tool
def get_universe_membership(
    ticker: Annotated[str, "Ticker symbol whose universe membership to inspect"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Retrieve PIT tradeable-universe membership, keeping delisting visible."""
    return route_to_vendor("get_universe_membership", ticker, as_of(curr_date, trade_date))
