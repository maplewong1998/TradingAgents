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
