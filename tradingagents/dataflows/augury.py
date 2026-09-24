"""Compatibility umbrella for the cache-first Augury vendor family.

The former monolith is split at the house 300-line file-size cap, following the
``alpha_vantage_*.py`` family precedent. This module preserves the established
import path while re-exporting the family surface, as ``schemas.py`` does for
its extracted public models.
"""

from __future__ import annotations

from .augury_core import (
    DEFAULT_BASE_URL,
    REQUEST_TIMEOUT,
    get_base_url,
    requests,  # noqa: F401  # Keep the historical test mock handle at this path.
)
from .augury_fundamentals import (
    get_augury_balance_sheet,
    get_augury_cashflow,
    get_augury_fundamentals,
    get_augury_income_statement,
    get_augury_universe_membership,
    get_augury_valuation,
)
from .augury_market import (
    _INDICATOR_MAP,  # noqa: F401  # Preserve the historical indicator-map inspection path.
    get_augury_feature_vector,
    get_augury_indicators,
    get_augury_liquidity,
    get_augury_stock,
)
from .augury_news import (
    DEFAULT_MACRO_LOOKBACK_DAYS,
    DEFAULT_PREDICTION_MARKET_LIMIT,
    get_augury_macro_data,
    get_augury_news,
    get_augury_prediction_markets,
)
from .augury_signals import AUGURY_SIGNAL_FAMILIES, get_augury_ai_forecast, get_augury_signal_states
from .utils import get_current_date

__all__ = [
    "DEFAULT_BASE_URL",
    "REQUEST_TIMEOUT",
    "get_base_url",
    "get_current_date",
    "get_augury_ai_forecast",
    "get_augury_balance_sheet",
    "get_augury_cashflow",
    "get_augury_feature_vector",
    "get_augury_fundamentals",
    "get_augury_income_statement",
    "get_augury_indicators",
    "get_augury_liquidity",
    "get_augury_macro_data",
    "get_augury_news",
    "get_augury_prediction_markets",
    "get_augury_signal_states",
    "get_augury_stock",
    "get_augury_universe_membership",
    "get_augury_valuation",
    "AUGURY_SIGNAL_FAMILIES",
    "DEFAULT_MACRO_LOOKBACK_DAYS",
    "DEFAULT_PREDICTION_MARKET_LIMIT",
    "requests",
]
