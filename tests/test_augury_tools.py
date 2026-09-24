# story: e03s05
"""TDD contracts for Augury's optional AI forecast and valuation pack."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
import requests

from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.interface import route_to_vendor

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


def _augury():
    return importlib.import_module("tradingagents.dataflows.augury")


def _error_response(detail: str = "not cached") -> dict:
    return {"detail": detail, "code": "not_found", "request_id": "r1", "errors": []}


# scenario: SC-e03s05-P1-01

def test_kronos_vendor_renders_flags_and_forecast_fields(monkeypatch):
    payload = {
        "ticker": "AAPL",
        "data_available": True,
        "torch_available": True,
        "hint": "cached prediction",
        "model_name": "kronos-base",
        "predicted_at": "2026-01-14T18:00:00Z",
        "forecast_window": 20,
        "predicted_return_pct": 12.5,
        "forecast_volatility": 0.21,
        "bull_signal": True,
        "bear_signal": False,
        "neutral_signal": False,
        "upside_probability": 0.74,
        "data_asof": "2026-01-14",
        "stale_days": 1,
        "degraded": True,
    }
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload)

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_ai_forecast("aapl", "2026-01-15")

    assert calls[0][0].endswith("/signals/AAPL/kronos")
    assert report.startswith("## Augury Kronos AI forecast for AAPL")
    for field, value in (
        ("predicted_return_pct", "12.5"),
        ("forecast_window", "20"),
        ("bull_signal", "True"),
        ("bear_signal", "False"),
        ("neutral_signal", "False"),
        ("upside_probability", "0.74"),
        ("model_name", "kronos-base"),
        ("data_available", "True"),
        ("degraded", "True"),
        ("stale_days", "1"),
        ("data_asof", "2026-01-14"),
    ):
        assert f"{field}: {value}" in report


# scenario: SC-e03s05-P0-01

def test_kronos_vendor_withholds_a_live_vintage_from_historical_analysis(monkeypatch):
    payload = {
        "ticker": "AAPL",
        "data_available": True,
        "torch_available": True,
        "model_name": "kronos-base",
        "forecast_window": 20,
        "predicted_return_pct": 99.0,
        "bull_signal": True,
        "bear_signal": False,
        "neutral_signal": False,
        "upside_probability": 0.99,
        "data_asof": "2026-09-20",
        "stale_days": 0,
        "degraded": False,
    }
    monkeypatch.setattr(_augury().requests, "get", lambda *a, **k: FakeResponse(payload))

    report = _augury().get_augury_ai_forecast("AAPL", "2026-01-15")

    assert "withheld" in report.lower()
    assert "2026-09-20" in report and "2026-01-15" in report
    assert "99.0" not in report
    assert "upside_probability" not in report
    assert "bull_signal" not in report


def test_kronos_unavailable_data_raises_typed_no_data(monkeypatch):
    payload = {
        "ticker": "AAPL",
        "data_available": False,
        "torch_available": False,
        "hint": "run POST /data/kronos",
        "data_asof": None,
        "stale_days": None,
        "degraded": True,
    }
    monkeypatch.setattr(_augury().requests, "get", lambda *a, **k: FakeResponse(payload))

    with pytest.raises(NoMarketDataError, match="POST /data/kronos"):
        _augury().get_augury_ai_forecast("AAPL", "2026-01-15")


# scenario: SC-e03s05-P1-02

def test_valuation_vendor_renders_methods_and_summary_table(monkeypatch):
    payload = {
        "ticker": "AAPL",
        "sector": "Technology",
        "run_date": "2026-01-15",
        "methods": [
            {
                "method": "pe_relative",
                "fair_value": 210.0,
                "current_price": 180.0,
                "premium_discount": 0.1667,
                "assessment": "undervalued",
                "confidence": "high",
                "is_reliable": True,
            }
        ],
        "summary": {
            "average_value": 210.0,
            "median_value": 205.0,
            "min_value": 190.0,
            "max_value": 230.0,
            "undervalued_count": 2,
            "overvalued_count": 0,
            "fair_count": 1,
            "reliable_count": 2,
            "total_methods": 3,
            "current_price": 180.0,
            "average_premium_discount": 0.1667,
            "margin_of_safety": 0.1429,
        },
    }
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload)

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_valuation("aapl", "2026-01-15")

    assert calls[0][0].endswith("/valuation/AAPL")
    assert "| Method | Fair Value | Current Price | Premium/Discount | Assessment | Confidence | Reliable |" in report
    assert "| pe_relative | 210.0 | 180.0 | 0.1667 | undervalued | high | True |" in report
    assert "average_value" in report and "210.0" in report
    assert "median_value" in report and "205.0" in report
    assert "margin_of_safety" in report and "0.1429" in report


def test_valuation_vendor_marks_live_vintage_for_past_analysis(monkeypatch):
    payload = {"ticker": "AAPL", "methods": [], "summary": {"average_value": 1}}
    monkeypatch.setattr(_augury().requests, "get", lambda *a, **k: FakeResponse(payload))

    report = _augury().get_augury_valuation("AAPL", "2026-01-15")

    assert "live-vintage" in report.lower()
    assert "2026-01-15" in report


def test_valuation_404_raises_typed_no_data(monkeypatch):
    monkeypatch.setattr(
        _augury().requests,
        "get",
        lambda *a, **k: FakeResponse(_error_response("fundamentals are not cached"), 404),
    )

    with pytest.raises(NoMarketDataError, match="fundamentals are not cached"):
        _augury().get_augury_valuation("AAPL", "2026-01-15")


# scenario: SC-e03s05-P1-02

def test_optional_valuation_routing_returns_unavailable_sentinel(monkeypatch):
    monkeypatch.setattr(
        _augury().requests,
        "get",
        lambda *a, **k: FakeResponse(_error_response(), 404),
    )
    set_config({"data_vendors": {"valuation": "augury"}})

    result = route_to_vendor("get_valuation", "AAPL", "2026-01-15")

    assert result.startswith("NO_DATA_AVAILABLE:")
    assert "do not" in result.lower() and "fabricate" in result.lower()


def test_forecast_and_valuation_registration_and_optional_categories():
    interface = importlib.import_module("tradingagents.dataflows.interface")
    assert interface.TOOLS_CATEGORIES["ai_forecast"]["tools"] == ["get_ai_forecast"]
    assert interface.TOOLS_CATEGORIES["valuation"]["tools"] == ["get_valuation"]
    assert "ai_forecast" in interface.OPTIONAL_CATEGORIES
    assert "valuation" in interface.OPTIONAL_CATEGORIES
    assert interface.VENDOR_METHODS["get_ai_forecast"]["augury"] is _augury().get_augury_ai_forecast
    assert interface.VENDOR_METHODS["get_valuation"]["augury"] is _augury().get_augury_valuation


def test_tool_wrappers_clamp_requested_dates_to_trade_date(monkeypatch):
    tools = importlib.import_module("tradingagents.agents.utils.ai_forecast_tools")
    calls = []
    monkeypatch.setattr(
        tools,
        "route_to_vendor",
        lambda method, *args: calls.append((method, args)) or "report",
    )

    tools.get_ai_forecast.func("AAPL", "2026-09-20", "2026-01-15")
    tools.get_valuation.func("AAPL", "2026-09-20", "2026-01-15")

    assert calls == [
        ("get_ai_forecast", ("AAPL", "2026-01-15")),
        ("get_valuation", ("AAPL", "2026-01-15")),
    ]
    assert "get_ai_forecast" in importlib.import_module(
        "tradingagents.agents.utils.agent_utils"
    ).__all__


class _CapturingRunnable:
    def __init__(self, owner):
        self.owner = owner

    def invoke(self, prompt):
        self.owner.prompt = prompt
        return SimpleNamespace(tool_calls=[], content="report")

    __call__ = invoke


class _CapturingLlm:
    def __init__(self):
        self.bound_tools = []
        self.prompt = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return _CapturingRunnable(self)


def _run_analyst(factory_path, config):
    set_config(config)
    module_name, factory_name = factory_path.rsplit(":", 1)
    module = importlib.import_module(module_name)
    llm = _CapturingLlm()
    factory = getattr(module, factory_name)
    factory(llm)({
        "trade_date": "2026-01-15",
        "messages": [],
        "asset_type": "stock",
        "company_of_interest": "AAPL",
    })
    text = "\n".join(message.content for message in llm.prompt.messages)
    return llm, text


def test_default_config_does_not_bind_augury_tools_or_prompt_text():
    market, market_text = _run_analyst(
        "tradingagents.agents.analysts.market_analyst:create_market_analyst",
        {"data_vendors": {"technical_indicators": "yfinance", "ai_forecast": "yfinance"}},
    )
    fundamentals, fundamentals_text = _run_analyst(
        "tradingagents.agents.analysts.fundamentals_analyst:create_fundamentals_analyst",
        {"data_vendors": {"fundamental_data": "yfinance", "valuation": "yfinance"}},
    )
    assert "get_ai_forecast" not in {tool.name for tool in market.bound_tools}
    assert "get_valuation" not in {tool.name for tool in fundamentals.bound_tools}
    assert "Kronos" not in market_text
    assert "Augury valuation" not in fundamentals_text


def test_configured_augury_binds_matching_tools_and_prompt_paragraphs():
    market, market_text = _run_analyst(
        "tradingagents.agents.analysts.market_analyst:create_market_analyst",
        {"data_vendors": {"ai_forecast": "augury"}},
    )
    fundamentals, fundamentals_text = _run_analyst(
        "tradingagents.agents.analysts.fundamentals_analyst:create_fundamentals_analyst",
        {"data_vendors": {"valuation": "augury"}},
    )
    assert "get_ai_forecast" in {tool.name for tool in market.bound_tools}
    assert "get_valuation" in {tool.name for tool in fundamentals.bound_tools}
    assert "Kronos" in market_text
    assert "multi-method valuation" in fundamentals_text


def test_graph_tool_nodes_honor_category_and_tool_vendor_overrides():
    graph = importlib.import_module("tradingagents.graph.trading_graph")
    set_config({"data_vendors": {"ai_forecast": "augury", "valuation": "augury"}})
    nodes = graph.TradingAgentsGraph._create_tool_nodes(None)
    assert "get_ai_forecast" in nodes["market"].tools_by_name
    assert "get_valuation" in nodes["fundamentals"].tools_by_name

    set_config(
        {
            "data_vendors": {"ai_forecast": "yfinance", "valuation": "yfinance"},
            "tool_vendors": {"get_ai_forecast": "augury", "get_valuation": "augury"},
        }
    )
    nodes = graph.TradingAgentsGraph._create_tool_nodes(None)
    assert "get_ai_forecast" in nodes["market"].tools_by_name
    assert "get_valuation" in nodes["fundamentals"].tools_by_name


def test_graph_default_tool_nodes_have_no_augury_tools():
    graph = importlib.import_module("tradingagents.graph.trading_graph")
    set_config({"data_vendors": {"ai_forecast": "yfinance", "valuation": "yfinance"}})
    nodes = graph.TradingAgentsGraph._create_tool_nodes(None)
    assert "get_ai_forecast" not in nodes["market"].tools_by_name
    assert "get_valuation" not in nodes["fundamentals"].tools_by_name


# story: e03s06
# scenario: SC-e03s06-P1-01

def test_signal_states_vendor_renders_trigger_detail_date_and_version(monkeypatch):
    payload = {
        "data": [
            {
                "ticker": "AAPL",
                "family": "rsi_cross",
                "signal_date": "2026-01-14",
                "value": 29.4,
                "direction": "bull",
                "triggered": True,
                "definition_id": 7,
                "formula_version": 2,
            }
        ],
        "pagination": {"page": 1, "total_pages": 1},
    }
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(payload)

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_signal_states("aapl", "rsi_cross", "2026-01-15")

    assert calls == [
        (
            "http://localhost:8765/api/v1/signals/AAPL",
            {"params": {"family": "rsi_cross", "as_of": "2026-01-15"}, "timeout": 30},
        )
    ]
    assert "rsi_cross" in report
    assert "True" in report
    assert "bull" in report and "29.4" in report
    assert "2026-01-14" in report
    assert "2" in report


# scenario: SC-e03s06-P1-02

def test_signal_states_unknown_family_returns_valid_set_without_abort(monkeypatch):
    monkeypatch.setattr(
        _augury().requests,
        "get",
        lambda *a, **k: FakeResponse(
            {"detail": "unknown family 'momentum_magic'", "code": "validation_error"},
            422,
        ),
    )

    report = _augury().get_augury_signal_states("AAPL", "momentum_magic", "2026-01-15")

    assert "momentum_magic" in report
    for family in (
        "sma_streak", "sma_cross", "rsi_cross", "macd_cross", "bb_cross",
        "adx_breakout", "psar_flip", "hurst", "regime", "sentiment", "insider",
        "earnings_surprise", "quality",
    ):
        assert family in report
    assert "Traceback" not in report


def test_signal_states_tool_clamps_requested_date_to_trade_date(monkeypatch):
    tools = importlib.import_module("tradingagents.agents.utils.signal_states_tools")
    calls = []
    monkeypatch.setattr(
        tools,
        "route_to_vendor",
        lambda method, *args: calls.append((method, args)) or "report",
    )

    tools.get_signal_states.func("AAPL", "rsi_cross", "2026-09-20", "2026-01-15")

    assert calls == [("get_signal_states", ("AAPL", "rsi_cross", "2026-01-15"))]
    assert "get_signal_states" in importlib.import_module(
        "tradingagents.agents.utils.agent_utils"
    ).__all__


def test_signal_states_registration_and_optional_routing(monkeypatch):
    interface = importlib.import_module("tradingagents.dataflows.interface")
    assert interface.TOOLS_CATEGORIES["signal_states"]["tools"] == ["get_signal_states"]
    assert "signal_states" in interface.OPTIONAL_CATEGORIES
    assert interface.VENDOR_METHODS["get_signal_states"]["augury"] is (
        _augury().get_augury_signal_states
    )

    monkeypatch.setattr(
        _augury().requests,
        "get",
        lambda *a, **k: FakeResponse({"detail": "bad family"}, 422),
    )
    set_config({"data_vendors": {"signal_states": "augury"}})
    result = route_to_vendor("get_signal_states", "AAPL", "rsi_cross", "2026-01-15")
    assert "valid families" in result.lower()


def test_signal_states_binding_gate_binds_both_analyst_nodes_only_when_opted_in():
    graph = importlib.import_module("tradingagents.graph.trading_graph")

    set_config({"data_vendors": {"signal_states": "yfinance"}})
    nodes = graph.TradingAgentsGraph._create_tool_nodes(None)
    assert "get_signal_states" not in nodes["market"].tools_by_name
    assert "get_signal_states" not in nodes["fundamentals"].tools_by_name

    set_config({"data_vendors": {"signal_states": "augury"}})
    nodes = graph.TradingAgentsGraph._create_tool_nodes(None)
    assert "get_signal_states" in nodes["market"].tools_by_name
    assert "get_signal_states" in nodes["fundamentals"].tools_by_name


def test_signal_states_prompt_paragraphs_are_conditional_and_family_specific():
    default_market, default_market_text = _run_analyst(
        "tradingagents.agents.analysts.market_analyst:create_market_analyst",
        {"data_vendors": {"signal_states": "yfinance"}},
    )
    default_fundamentals, default_fundamentals_text = _run_analyst(
        "tradingagents.agents.analysts.fundamentals_analyst:create_fundamentals_analyst",
        {"data_vendors": {"signal_states": "yfinance"}},
    )
    assert "get_signal_states" not in {tool.name for tool in default_market.bound_tools}
    assert "get_signal_states" not in {tool.name for tool in default_fundamentals.bound_tools}
    assert "sma_streak" not in default_market_text
    assert "earnings_surprise" not in default_fundamentals_text

    market, market_text = _run_analyst(
        "tradingagents.agents.analysts.market_analyst:create_market_analyst",
        {"data_vendors": {"signal_states": "augury"}},
    )
    fundamentals, fundamentals_text = _run_analyst(
        "tradingagents.agents.analysts.fundamentals_analyst:create_fundamentals_analyst",
        {"data_vendors": {"signal_states": "augury"}},
    )
    assert "get_signal_states" in {tool.name for tool in market.bound_tools}
    assert "get_signal_states" in {tool.name for tool in fundamentals.bound_tools}
    assert "sma_streak" in market_text and "psar_flip" in market_text
    assert "hurst" in fundamentals_text and "quality" in fundamentals_text


# story: e03s07
# scenario: SC-e03s07-P1-03

def test_liquidity_vendor_pins_live_only_contract_and_withholds_historical_reads(monkeypatch):
    """The OpenAPI contract has no as_of/vintage, so past liquidity is withheld."""
    augury = _augury()
    monkeypatch.setattr(augury, "get_current_date", lambda: "2026-09-24")
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"ticker": "AAPL", "latest_price": 200.0, "adv_dollar_vol": 1_000_000})

    monkeypatch.setattr(augury.requests, "get", fake_get)

    historical = augury.get_augury_liquidity("aapl", "2026-01-15")
    assert "withheld" in historical.lower()
    assert "2026-01-15" in historical
    assert calls == []

    current = augury.get_augury_liquidity("aapl", "2026-09-24")
    assert calls[0] == (
        "http://localhost:8765/liquidity/AAPL",
        {"params": {"window_days": 90}, "timeout": 30},
    )
    assert "adv_dollar_vol: 1000000" in current


# scenario: SC-e03s07-P1-01

def test_feature_vector_vendor_sends_one_ticker_and_renders_failed_slot(monkeypatch):
    augury = _augury()
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            {
                "as_of": "2026-01-15",
                "data_vintage": "v20260115",
                "items": [],
                "failed": ["AAPL: daily features are not cached"],
            }
        )

    monkeypatch.setattr(augury.requests, "post", fake_post)

    report = augury.get_augury_feature_vector("aapl", "2026-01-15")

    assert calls == [
        (
            "http://localhost:8765/api/v1/batch/feature-vector",
            {
                "json": {
                    "tickers": ["AAPL"],
                    "as_of": "2026-01-15",
                    "vintage": "current",
                },
                "timeout": 30,
            },
        )
    ]
    assert "not available: daily features are not cached" in report


def test_feature_vector_vendor_renders_success_item_and_missing_item_explicitly(monkeypatch):
    augury = _augury()
    monkeypatch.setattr(
        augury.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "as_of": "2026-01-15",
                "data_vintage": "v20260115",
                "items": [
                    {
                        "ticker": "AAPL",
                        "features": {"rsi_14": 55.5},
                        "fundamentals": {"market_cap": 1_000_000},
                        "ground_truth": {},
                        "watermark": {"bars_healthy": True},
                    }
                ],
                "failed": [],
            }
        ),
    )

    report = augury.get_augury_feature_vector("AAPL", "2026-01-15")

    assert "rsi_14" in report and "55.5" in report
    assert "market_cap" in report and "1000000" in report
    assert "data_vintage: v20260115" in report


# scenario: SC-e03s07-P1-02

@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"data": [{"ticker": "AAPL", "source": "futu", "valid_from": "2025-01-01"}]},
            "member of the Augury tradeable universe",
        ),
        (
            {
                "data": [
                    {
                        "ticker": "AAPL",
                        "source": "futu",
                        "valid_from": "2025-01-01",
                        "delisted": True,
                    }
                ]
            },
            "present but delisted",
        ),
        ({"data": []}, ""),
    ],
)
def test_universe_membership_vendor_renders_member_delisted_and_absent(payload, expected, monkeypatch):
    augury = _augury()
    monkeypatch.setattr(
        augury.requests,
        "get",
        lambda url, **kwargs: FakeResponse(payload),
    )

    report = augury.get_augury_universe_membership("aapl", "2026-01-15")

    if expected:
        assert expected in report
    else:
        assert "absent from the Augury tradeable universe" in report
    assert "2026-01-15" in report


def test_universe_membership_vendor_forwards_pit_query(monkeypatch):
    augury = _augury()
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            {
                "data": [
                    {
                        "ticker": "AAPL",
                        "source": "futu",
                        "valid_from": "2025-01-01",
                    }
                ]
            }
        )

    monkeypatch.setattr(augury.requests, "get", fake_get)
    augury.get_augury_universe_membership("aapl", "2026-01-15")

    assert calls == [
        (
            "http://localhost:8765/api/v1/universe",
            {"params": {"as_of": "2026-01-15", "q": "AAPL"}, "timeout": 30},
        )
    ]


def test_cross_sectional_registration_and_optional_routing():
    interface = importlib.import_module("tradingagents.dataflows.interface")
    assert interface.TOOLS_CATEGORIES["cross_sectional"]["tools"] == [
        "get_liquidity",
        "get_feature_vector",
        "get_universe_membership",
    ]
    assert "cross_sectional" in interface.OPTIONAL_CATEGORIES
    assert interface.VENDOR_METHODS["get_liquidity"]["augury"] is (
        _augury().get_augury_liquidity
    )
    assert interface.VENDOR_METHODS["get_feature_vector"]["augury"] is (
        _augury().get_augury_feature_vector
    )
    assert interface.VENDOR_METHODS["get_universe_membership"]["augury"] is (
        _augury().get_augury_universe_membership
    )


def test_cross_sectional_tool_wrappers_clamp_requested_dates_to_trade_date(monkeypatch):
    tools = importlib.import_module("tradingagents.agents.utils.cross_sectional_tools")
    calls = []
    monkeypatch.setattr(
        tools,
        "route_to_vendor",
        lambda method, *args: calls.append((method, args)) or "report",
    )

    tools.get_liquidity.func("AAPL", "2026-09-20", "2026-01-15")
    tools.get_feature_vector.func("AAPL", "2026-09-20", "2026-01-15")
    tools.get_universe_membership.func("AAPL", "2026-09-20", "2026-01-15")

    assert calls == [
        ("get_liquidity", ("AAPL", "2026-01-15")),
        ("get_feature_vector", ("AAPL", "2026-01-15")),
        ("get_universe_membership", ("AAPL", "2026-01-15")),
    ]
    agent_utils = importlib.import_module("tradingagents.agents.utils.agent_utils")
    assert {"get_liquidity", "get_feature_vector", "get_universe_membership"} <= set(
        agent_utils.__all__
    )


def test_cross_sectional_binding_gate_and_portfolio_manager_graph_integrity():
    graph = importlib.import_module("tradingagents.graph.trading_graph")

    set_config({"data_vendors": {"cross_sectional": "yfinance"}})
    default_nodes = graph.TradingAgentsGraph._create_tool_nodes(None)
    assert set(default_nodes) == {"market", "social", "news", "fundamentals"}
    assert "get_liquidity" not in default_nodes["market"].tools_by_name
    assert "get_feature_vector" not in default_nodes["market"].tools_by_name
    assert "get_universe_membership" not in default_nodes["fundamentals"].tools_by_name

    set_config({"data_vendors": {"cross_sectional": "augury"}})
    configured_nodes = graph.TradingAgentsGraph._create_tool_nodes(None)
    assert {"get_liquidity", "get_feature_vector"} <= set(
        configured_nodes["market"].tools_by_name
    )
    assert "get_universe_membership" in configured_nodes["fundamentals"].tools_by_name
    assert "portfolio_manager" not in configured_nodes


def test_cross_sectional_prompt_paragraphs_are_conditional_and_analyst_bound():
    default_market, default_market_text = _run_analyst(
        "tradingagents.agents.analysts.market_analyst:create_market_analyst",
        {"data_vendors": {"cross_sectional": "yfinance"}},
    )
    default_fundamentals, default_fundamentals_text = _run_analyst(
        "tradingagents.agents.analysts.fundamentals_analyst:create_fundamentals_analyst",
        {"data_vendors": {"cross_sectional": "yfinance"}},
    )
    assert "get_liquidity" not in {tool.name for tool in default_market.bound_tools}
    assert "get_feature_vector" not in {tool.name for tool in default_market.bound_tools}
    assert "get_universe_membership" not in {
        tool.name for tool in default_fundamentals.bound_tools
    }
    assert "cross-sectional" not in default_market_text
    assert "tradeable universe" not in default_fundamentals_text

    market, market_text = _run_analyst(
        "tradingagents.agents.analysts.market_analyst:create_market_analyst",
        {"data_vendors": {"cross_sectional": "augury"}},
    )
    fundamentals, fundamentals_text = _run_analyst(
        "tradingagents.agents.analysts.fundamentals_analyst:create_fundamentals_analyst",
        {"data_vendors": {"cross_sectional": "augury"}},
    )
    assert {"get_liquidity", "get_feature_vector"} <= {
        tool.name for tool in market.bound_tools
    }
    assert "get_universe_membership" in {tool.name for tool in fundamentals.bound_tools}
    assert "cross-sectional" in market_text
    assert "tradeable universe" in fundamentals_text
