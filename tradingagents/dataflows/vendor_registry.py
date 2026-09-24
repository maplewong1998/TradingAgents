"""Vendor implementations and routing tables for the dataflow seam."""

from __future__ import annotations

from .alpha_vantage import (
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_global_news as get_alpha_vantage_global_news,
    get_income_statement as get_alpha_vantage_income_statement,
    get_indicator as get_alpha_vantage_indicator,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_stock as get_alpha_vantage_stock,
)
from .augury import (
    get_augury_ai_forecast,
    get_augury_balance_sheet,
    get_augury_cashflow,
    get_augury_feature_vector,
    get_augury_fundamentals,
    get_augury_income_statement,
    get_augury_indicators,
    get_augury_liquidity,
    get_augury_macro_data,
    get_augury_news,
    get_augury_prediction_markets,
    get_augury_signal_states,
    get_augury_stock,
    get_augury_universe_membership,
    get_augury_valuation,
)
from .fred import get_macro_data as get_fred_macro_data
from .polymarket import get_prediction_markets as get_polymarket_prediction_markets
from .sec_edgar import (
    get_balance_sheet as get_sec_edgar_balance_sheet,
    get_cashflow as get_sec_edgar_cashflow,
    get_income_statement as get_sec_edgar_income_statement,
)
from .y_finance import (
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_fundamentals as get_yfinance_fundamentals,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
    get_stock_stats_indicators_window,
    get_YFin_data_online,
)
from .yfinance_news import get_global_news_yfinance, get_news_yfinance

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "macro_data": {
        "description": "Macroeconomic indicators (rates, inflation, labor, growth)",
        "tools": [
            "get_macro_indicators",
        ]
    },
    "prediction_markets": {
        "description": "Market-implied probabilities for forward-looking events",
        "tools": [
            "get_prediction_markets",
        ]
    },
    "ai_forecast": {
        "description": "Cached AI price forecasts",
        "tools": [
            "get_ai_forecast",
        ]
    },
    "valuation": {
        "description": "Cached multi-method valuations",
        "tools": [
            "get_valuation",
        ]
    },
    "signal_states": {
        "description": "Versioned signal-family trigger states",
        "tools": [
            "get_signal_states",
        ]
    },
    "cross_sectional": {
        "description": "Cross-sectional liquidity, vectors, and universe context",
        "tools": [
            "get_liquidity",
            "get_feature_vector",
            "get_universe_membership",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "sec_edgar",
    "fred",
    "polymarket",
    "alpha_vantage",
    "augury",
]

# Optional enrichment categories. These add macro/event context to the news
# analyst but are not core to a decision, so a vendor failure here degrades to a
# sentinel instead of aborting the run (a bad LLM-supplied indicator, a missing
# key, or a network blip should not crash an analysis over flavour data). Core
# categories (prices, fundamentals, news) still raise so a broken primary is loud.
# Forecasts and valuations are optional enrichment; a cache miss must not abort a run.
OPTIONAL_CATEGORIES = {
    "macro_data",
    "prediction_markets",
    "ai_forecast",
    "valuation",
    "signal_states",
    # Cross-sectional context is optional enrichment; a lake outage must not
    # abort an analyst run (#e03s07, D5).
    "cross_sectional",
}

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "augury": get_augury_stock,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "augury": get_augury_indicators,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "augury": get_augury_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "sec_edgar": get_sec_edgar_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "augury": get_augury_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "sec_edgar": get_sec_edgar_cashflow,
        "yfinance": get_yfinance_cashflow,
        "augury": get_augury_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "sec_edgar": get_sec_edgar_income_statement,
        "yfinance": get_yfinance_income_statement,
        "augury": get_augury_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
        "augury": get_augury_news,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
    # macro_data
    "get_macro_indicators": {
        "fred": get_fred_macro_data,
        "augury": get_augury_macro_data,
    },
    # prediction_markets
    "get_prediction_markets": {
        "polymarket": get_polymarket_prediction_markets,
        "augury": get_augury_prediction_markets,
    },
    # ai_forecast and valuation
    "get_ai_forecast": {
        "augury": get_augury_ai_forecast,
    },
    "get_valuation": {
        "augury": get_augury_valuation,
    },
    "get_signal_states": {
        "augury": get_augury_signal_states,
    },
    "get_liquidity": {
        "augury": get_augury_liquidity,
    },
    "get_feature_vector": {
        "augury": get_augury_feature_vector,
    },
    "get_universe_membership": {
        "augury": get_augury_universe_membership,
    },
}
