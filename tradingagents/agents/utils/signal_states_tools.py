"""Optional Augury signal-family trigger-state tool (#e03s06)."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tradingagents.dataflows.augury import AUGURY_SIGNAL_FAMILIES
from tradingagents.dataflows.date_window import as_of
from tradingagents.dataflows.interface import route_to_vendor

_SIGNAL_FAMILY_DESCRIPTION = (
    "Signal family. Valid families: " + ", ".join(AUGURY_SIGNAL_FAMILIES)
)


@tool
def get_signal_states(
    ticker: Annotated[str, "Ticker symbol to inspect"],
    family: Annotated[str, _SIGNAL_FAMILY_DESCRIPTION],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Retrieve Augury's versioned point-in-time trigger states for one family.

    The requested date is clamped to the run's trade date so a historical run
    cannot read a future signal state. Invalid families return a helpful
    vendor message and do not abort the optional analyst enrichment (#e03s06).
    """
    return route_to_vendor(
        "get_signal_states",
        ticker,
        family,
        as_of(curr_date, trade_date),
    )
