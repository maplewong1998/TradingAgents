# story: e03s01
"""Unit contract for the opt-in augury vendor tracer bullet."""

from __future__ import annotations

import importlib

import pytest
import requests

from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from tradingagents.dataflows.interface import route_to_vendor

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.raise_for_status_called = False

    def json(self):
        return self.payload

    def raise_for_status(self):
        self.raise_for_status_called = True
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


def _augury():
    return importlib.import_module("tradingagents.dataflows.augury")


def _error_response(code: str, detail: str) -> dict:
    return {
        "detail": detail,
        "code": code,
        "request_id": "request-123",
        "errors": [],
    }


def _bars(*rows: dict, total_pages: int = 1) -> dict:
    return {
        "data": list(rows),
        "pagination": {
            "page": 1,
            "page_size": 200,
            "total_items": len(rows),
            "total_pages": total_pages,
        },
    }


def _financials(*rows: dict, total_pages: int = 1) -> dict:
    return {
        "data": list(rows),
        "pagination": {
            "page": 1,
            "page_size": 200,
            "total_items": len(rows),
            "total_pages": total_pages,
        },
    }


# story: e03s02
# scenario: SC-e03s02-P1-01

def test_augury_fundamentals_forwards_as_of_and_renders_pit_snapshot(monkeypatch):
    response = FakeResponse(
        {
            "ticker": "AAPL",
            "pe_ratio": 24.5,
            "pb_ratio": 8.2,
            "market_cap": 3_000_000_000_000,
            "sector": "Technology",
            "dividend_yield": 0.005,
        }
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_fundamentals("aapl", "2024-06-30")

    assert "# Company Fundamentals for AAPL" in report
    assert "PE Ratio: 24.5" in report
    assert "Sector: Technology" in report
    assert calls == [
        (
            "http://localhost:8765/api/v1/fundamentals/AAPL",
            {"params": {"as_of": "2024-06-30"}, "timeout": 30},
        )
    ]


# scenario: SC-e03s02-P1-03

def test_augury_balance_sheet_cashflow_income_statement_split_mixed_statements(monkeypatch):
    rows = [
        {"ticker": "AAPL", "statement": "income", "metric": "Revenue", "period_end": "2024-06-30", "value": 100},
        {"ticker": "AAPL", "statement": "balance", "metric": "Assets", "period_end": "2024-06-30", "value": 200},
        {"ticker": "AAPL", "statement": "cashflow", "metric": "Operating Cash Flow", "period_end": "2024-06-30", "value": 50},
    ]
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(_financials(*rows))

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    reports = {
        "balance": _augury().get_augury_balance_sheet("AAPL", curr_date="2024-06-30"),
        "cashflow": _augury().get_augury_cashflow("AAPL", curr_date="2024-06-30"),
        "income": _augury().get_augury_income_statement("AAPL", curr_date="2024-06-30"),
    }

    assert "Assets" in reports["balance"] and "Revenue" not in reports["balance"]
    assert "Operating Cash Flow" in reports["cashflow"] and "Assets" not in reports["cashflow"]
    assert "Revenue" in reports["income"] and "Assets" not in reports["income"]
    assert all(call[1]["params"]["as_of"] == "2024-06-30" for call in calls)
    assert all("fields" in call[1]["params"] for call in calls)


# scenario: SC-e03s02-P1-01

def test_augury_income_statement_selects_annual_or_quarterly_period_spacing(monkeypatch):
    rows = [
        {"ticker": "AAPL", "statement": "income", "metric": "Revenue", "period_end": "2024-12-31", "value": 120},
        {"ticker": "AAPL", "statement": "income", "metric": "Revenue", "period_end": "2024-09-30", "value": 30},
        {"ticker": "AAPL", "statement": "income", "metric": "Revenue", "period_end": "2024-06-30", "value": 28},
        {"ticker": "AAPL", "statement": "income", "metric": "Revenue", "period_end": "2024-03-31", "value": 27},
        {"ticker": "AAPL", "statement": "income", "metric": "Revenue", "period_end": "2023-12-31", "value": 110},
    ]
    monkeypatch.setattr(
        _augury().requests,
        "get",
        lambda *args, **kwargs: FakeResponse(_financials(*rows)),
    )

    annual = _augury().get_augury_income_statement("AAPL", freq="annual", curr_date="2024-12-31")
    quarterly = _augury().get_augury_income_statement(
        "AAPL", freq="quarterly", curr_date="2024-12-31"
    )

    assert "| 2024-12-31 |" in annual and "| 2024-09-30 |" not in annual
    assert "| 2023-12-31 |" in annual
    assert "| 2024-09-30 |" in quarterly and "| 2024-06-30 |" in quarterly
    assert "| 2024-12-31 |" not in quarterly


# scenario: SC-e03s02-P1-02

def test_augury_balance_sheet_404_includes_financials_refresh_hint(monkeypatch):
    response = FakeResponse(_error_response("not_found", "AAPL financials are not cached"), 404)
    monkeypatch.setattr(_augury().requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(NoMarketDataError) as exc_info:
        _augury().get_augury_balance_sheet("AAPL", curr_date="2024-06-30")

    assert "POST /data/financials" in exc_info.value.detail


def test_augury_cashflow_empty_statement_names_statement_in_error(monkeypatch):
    monkeypatch.setattr(
        _augury().requests,
        "get",
        lambda *args, **kwargs: FakeResponse(_financials(
            {"ticker": "AAPL", "statement": "income", "metric": "Revenue", "period_end": "2024-06-30", "value": 100}
        )),
    )

    with pytest.raises(NoMarketDataError) as exc_info:
        _augury().get_augury_cashflow("AAPL", curr_date="2024-06-30")

    assert "cash flow" in exc_info.value.detail.lower()


def test_augury_base_url_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("AUGURY_BASE_URL", raising=False)
    set_config({"augury_base_url": "http://localhost:8765"})

    assert _augury().get_base_url() == "http://localhost:8765"


def test_augury_base_url_prefers_environment(monkeypatch):
    monkeypatch.setenv("AUGURY_BASE_URL", "https://lake.example.invalid")
    set_config({"augury_base_url": "http://configured.invalid"})

    assert _augury().get_base_url() == "https://lake.example.invalid"


def test_empty_augury_base_url_disables_vendor(monkeypatch):
    monkeypatch.setenv("AUGURY_BASE_URL", "")
    set_config({"augury_base_url": "http://configured.invalid"})

    with pytest.raises(VendorNotConfiguredError):
        _augury().get_base_url()


def test_augury_404_maps_to_no_data_with_refresh_job_hint(monkeypatch):
    response = FakeResponse(_error_response("not_found", "AAPL is not cached"), 404)
    monkeypatch.setattr(_augury().requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(NoMarketDataError) as exc_info:
        _augury().get_augury_stock("AAPL", "2025-01-01", "2025-01-03")

    assert "POST /data/ohlcv" in exc_info.value.detail
    assert "AAPL is not cached" in exc_info.value.detail
    assert response.raise_for_status_called


def test_augury_429_maps_to_rate_limit(monkeypatch):
    response = FakeResponse(_error_response("rate_limited", "slow down"), 429)
    monkeypatch.setattr(_augury().requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(VendorRateLimitError):
        _augury().get_augury_stock("AAPL", "2025-01-01", "2025-01-03")


def test_augury_connection_error_propagates(monkeypatch):
    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("lake unreachable")

    monkeypatch.setattr(_augury().requests, "get", raise_connection_error)

    with pytest.raises(requests.ConnectionError, match="lake unreachable"):
        _augury().get_augury_stock("AAPL", "2025-01-01", "2025-01-03")


def test_stock_data_reverses_newest_first_pages_to_chronological_markdown(monkeypatch):
    response = FakeResponse(
        _bars(
            {"trade_date": "2025-01-03", "open": 3, "high": 4, "low": 2, "close": 3.5, "volume": 30},
            {"trade_date": "2025-01-02", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 20},
            {"trade_date": "2025-01-01", "open": 1, "high": 2, "low": 0, "close": 1.5, "volume": 10},
        )
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_stock("AAPL", "2025-01-01", "2025-01-03")

    assert report.index("| 2025-01-01 |") < report.index("| 2025-01-02 |") < report.index("| 2025-01-03 |")
    assert calls == [
        (
            "http://localhost:8765/api/v1/bars/AAPL",
            {
                "params": {
                    "start": "2025-01-01",
                    "end": "2025-01-03",
                    "page": 1,
                    "page_size": 200,
                },
                "timeout": 30,
            },
        )
    ]


def test_stock_data_fetches_all_newest_first_pages(monkeypatch):
    page_one = FakeResponse(
        _bars(
            {"trade_date": "2025-01-03", "open": 3, "high": 4, "low": 2, "close": 3.5, "volume": 30},
            total_pages=2,
        )
    )
    page_two = FakeResponse(
        _bars(
            {"trade_date": "2025-01-02", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 20},
            {"trade_date": "2025-01-01", "open": 1, "high": 2, "low": 0, "close": 1.5, "volume": 10},
            total_pages=2,
        )
    )
    pages = iter([page_one, page_two])
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"])
        return next(pages)

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_stock("AAPL", "2025-01-01", "2025-01-03")

    assert calls[0]["page"] == 1
    assert calls[1]["page"] == 2
    assert report.index("| 2025-01-01 |") < report.index("| 2025-01-03 |")


def test_empty_stock_coverage_raises_no_data(monkeypatch):
    response = FakeResponse(_bars())
    monkeypatch.setattr(_augury().requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(NoMarketDataError) as exc_info:
        _augury().get_augury_stock("aapl", "2025-01-01", "2025-01-03")

    assert exc_info.value.symbol == "aapl"
    assert exc_info.value.canonical == "AAPL"


def test_augury_is_registered_for_stock_data():
    interface = importlib.import_module("tradingagents.dataflows.interface")

    assert "augury" in interface.VENDOR_LIST
    assert interface.VENDOR_METHODS["get_stock_data"]["augury"] is _augury().get_augury_stock


# story: e03s03
# scenario: SC-e03s03-P1-01


def _features(*rows: dict) -> dict:
    return {
        "data": list(rows),
        "pagination": {
            "page": 1,
            "page_size": 200,
            "total_items": len(rows),
            "total_pages": 1,
        },
    }


def _news(*rows: dict) -> dict:
    return {
        "data": list(rows),
        "pagination": {
            "page": 1,
            "page_size": 200,
            "total_items": len(rows),
            "total_pages": 1,
        },
    }


def test_augury_indicator_map_pins_only_the_served_intersection():
    assert _augury()._INDICATOR_MAP == {
        "close_200_sma": "sma_200",
        "macd": "macd_line",
        "macdh": "macd_histogram",
        "macds": "macd_signal",
        "mfi": "mfi_14",
        "rsi": "rsi_14",
        "atr": "atr_14",
    }


def test_augury_indicators_requests_mapped_field_and_renders_rows(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            _features(
                {"ticker": "AAPL", "trade_date": "2025-01-15", "rsi_14": 61.2},
                {"ticker": "AAPL", "trade_date": "2025-01-14", "rsi_14": 59.8},
            )
        )

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_indicators("aapl", "rsi", "2025-01-15", 30)

    assert "rsi_14" in report
    assert "61.2" in report
    assert calls == [
        (
            "http://localhost:8765/api/v1/features/AAPL",
            {
                "params": {
                    "start": "2024-12-16",
                    "end": "2025-01-15",
                    "fields": "rsi_14",
                    "page": 1,
                    "page_size": 200,
                },
                "timeout": 30,
            },
        )
    ]


@pytest.mark.parametrize("indicator", ["close_50_sma", "close_10_ema", "boll", "boll_ub"])
def test_augury_indicators_decline_unserved_advertised_names(indicator):
    with pytest.raises(NoMarketDataError) as exc_info:
        _augury().get_augury_indicators("AAPL", indicator, "2025-01-15", 30)

    assert indicator in exc_info.value.detail
    assert "rsi_14" in exc_info.value.detail
    assert "sma_200" in exc_info.value.detail


# scenario: SC-e03s03-P0-01

def test_augury_news_filters_to_inclusive_analysis_window_and_keeps_sentiment_label(monkeypatch):
    response = FakeResponse(
        _news(
            {
                "url": "https://example.invalid/in-window",
                "tickers": ["AAPL"],
                "title": "In window",
                "source": "Wire",
                "summary": "Summary",
                "sentiment_score": 0.8,
                "sentiment_label": "VERY_BULLISH",
                "topics": ["earnings"],
                "published_at": "2025-01-15T16:30:00Z",
            },
            {
                "url": "https://example.invalid/too-early",
                "tickers": ["AAPL"],
                "title": "Too early",
                "source": "Wire",
                "summary": "Old",
                "sentiment_score": -0.2,
                "sentiment_label": "BEARISH",
                "topics": [],
                "published_at": "2025-01-09T12:00:00Z",
            },
            {
                "url": "https://example.invalid/future",
                "tickers": ["AAPL"],
                "title": "Future",
                "source": "Wire",
                "summary": "Future",
                "sentiment_score": 0.1,
                "sentiment_label": "NEUTRAL",
                "topics": [],
                "published_at": "2025-01-16T12:00:00Z",
            },
        )
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_news("aapl", "2025-01-10", "2025-01-15")

    assert "In window" in report
    assert "VERY_BULLISH" in report
    assert "Too early" not in report
    assert "Future" not in report
    assert calls[0][0] == "http://localhost:8765/news/AAPL"
    assert calls[0][1]["params"]["days"] >= 6


def test_augury_news_all_filtered_rows_raise_no_data(monkeypatch):
    monkeypatch.setattr(
        _augury().requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            _news(
                {
                    "title": "Future",
                    "published_at": "2025-01-16T12:00:00Z",
                    "sentiment_label": "NEUTRAL",
                }
            )
        ),
    )

    with pytest.raises(NoMarketDataError) as exc_info:
        _augury().get_augury_news("AAPL", "2025-01-10", "2025-01-15")

    assert "between 2025-01-10 and 2025-01-15" in exc_info.value.detail


def test_augury_is_registered_for_indicator_and_news_methods():
    interface = importlib.import_module("tradingagents.dataflows.interface")

    assert interface.VENDOR_METHODS["get_indicators"]["augury"] is _augury().get_augury_indicators
    assert interface.VENDOR_METHODS["get_news"]["augury"] is _augury().get_augury_news


def test_routing_augury_indicator_fallback_and_mapped_hit(monkeypatch):
    interface = importlib.import_module("tradingagents.dataflows.interface")
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(_features({"trade_date": "2025-01-15", "rsi_14": 61.2}))

    monkeypatch.setattr(_augury().requests, "get", fake_get)
    def fallback(*args, **kwargs):
        return "yfinance indicator"

    monkeypatch.setitem(interface.VENDOR_METHODS["get_indicators"], "yfinance", fallback)
    set_config({"data_vendors": {"technical_indicators": "augury,yfinance"}})

    assert "rsi_14" in route_to_vendor("get_indicators", "AAPL", "rsi", "2025-01-15", 30)
    assert calls == ["http://localhost:8765/api/v1/features/AAPL"]
    assert route_to_vendor("get_indicators", "AAPL", "close_50_sma", "2025-01-15", 30) == "yfinance indicator"


# story: e03s02

def test_augury_is_registered_for_all_fundamental_methods():
    interface = importlib.import_module("tradingagents.dataflows.interface")
    expected = {
        "get_fundamentals": "get_augury_fundamentals",
        "get_balance_sheet": "get_augury_balance_sheet",
        "get_cashflow": "get_augury_cashflow",
        "get_income_statement": "get_augury_income_statement",
    }

    for method, implementation in expected.items():
        assert interface.VENDOR_METHODS[method]["augury"] is getattr(_augury(), implementation)


def test_routing_augury_fundamental_404_falls_through_to_yfinance(monkeypatch):
    response = FakeResponse(_error_response("not_found", "AAPL fundamentals are not cached"), 404)
    monkeypatch.setattr(_augury().requests, "get", lambda *args, **kwargs: response)
    interface = importlib.import_module("tradingagents.dataflows.interface")
    replacements = {
        "get_fundamentals": lambda *args, **kwargs: "yfinance fundamentals",
        "get_balance_sheet": lambda *args, **kwargs: "yfinance balance sheet",
        "get_cashflow": lambda *args, **kwargs: "yfinance cash flow",
        "get_income_statement": lambda *args, **kwargs: "yfinance income statement",
    }
    for method, fallback in replacements.items():
        original = interface.VENDOR_METHODS[method]["yfinance"]
        monkeypatch.setitem(interface.VENDOR_METHODS[method], "yfinance", fallback)
        set_config({"data_vendors": {"fundamental_data": "augury,yfinance"}})
        if method == "get_fundamentals":
            result = route_to_vendor(method, "AAPL", "2024-06-30")
        else:
            result = route_to_vendor(method, "AAPL", curr_date="2024-06-30")
        assert result == fallback()
        monkeypatch.setitem(interface.VENDOR_METHODS[method], "yfinance", original)


def test_augury_config_defaults_and_env_override(monkeypatch):
    import tradingagents.default_config as default_config

    monkeypatch.delenv("AUGURY_BASE_URL", raising=False)
    assert default_config.DEFAULT_CONFIG["augury_base_url"] == "http://localhost:8765"
    assert default_config._ENV_OVERRIDES["AUGURY_BASE_URL"] == "augury_base_url"
    assert any(
        "augury" in str(value).lower()
        for value in default_config.DEFAULT_CONFIG["data_vendors"].values()
    ) is False

    monkeypatch.setenv("AUGURY_BASE_URL", "https://env.example.invalid")
    reloaded = importlib.reload(default_config)
    assert reloaded.DEFAULT_CONFIG["augury_base_url"] == "https://env.example.invalid"
    monkeypatch.delenv("AUGURY_BASE_URL", raising=False)
    importlib.reload(default_config)


def test_routing_augury_404_falls_through_to_yfinance(monkeypatch):
    response = FakeResponse(_error_response("not_found", "AAPL is not cached"), 404)
    monkeypatch.setattr(_augury().requests, "get", lambda *args, **kwargs: response)
    interface = importlib.import_module("tradingagents.dataflows.interface")
    yfinance = interface.VENDOR_METHODS["get_stock_data"]["yfinance"]
    monkeypatch.setitem(interface.VENDOR_METHODS["get_stock_data"], "yfinance", lambda *args: "yfinance data")
    set_config({"data_vendors": {"core_stock_apis": "augury,yfinance"}})

    assert route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-03") == "yfinance data"
    monkeypatch.setitem(interface.VENDOR_METHODS["get_stock_data"], "yfinance", yfinance)


def test_routing_augury_connection_error_falls_through_and_logs(monkeypatch, caplog):
    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("lake unreachable")

    monkeypatch.setattr(_augury().requests, "get", raise_connection_error)
    interface = importlib.import_module("tradingagents.dataflows.interface")
    yfinance = interface.VENDOR_METHODS["get_stock_data"]["yfinance"]
    monkeypatch.setitem(interface.VENDOR_METHODS["get_stock_data"], "yfinance", lambda *args: "yfinance data")
    set_config({"data_vendors": {"core_stock_apis": "augury,yfinance"}})

    assert route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-03") == "yfinance data"
    assert "augury" in caplog.text
    assert "lake unreachable" in caplog.text
    monkeypatch.setitem(interface.VENDOR_METHODS["get_stock_data"], "yfinance", yfinance)


def test_routing_augury_only_404_returns_no_data_sentinel(monkeypatch):
    response = FakeResponse(_error_response("not_found", "AAPL is not cached"), 404)
    monkeypatch.setattr(_augury().requests, "get", lambda *args, **kwargs: response)
    set_config({"data_vendors": {"core_stock_apis": "augury"}})

    result = route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-03")

    assert "NO_DATA_AVAILABLE" in result
    assert "AAPL" in result
    assert "POST /data/ohlcv" in result


def test_routing_default_stock_config_never_calls_augury(monkeypatch):
    called = False

    def unexpected_call(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("default stock routing called augury")

    monkeypatch.setattr(_augury().requests, "get", unexpected_call)
    set_config({"data_vendors": {"core_stock_apis": "yfinance"}})
    interface = importlib.import_module("tradingagents.dataflows.interface")
    monkeypatch.setitem(interface.VENDOR_METHODS["get_stock_data"], "yfinance", lambda *args: "yfinance data")

    assert route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-03") == "yfinance data"
    assert called is False


# story: e03s04
# scenario: SC-e03s04-P2-01


def _macro(*rows: dict) -> dict:
    return {
        "data": list(rows),
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total_items": len(rows),
            "total_pages": 1,
        },
    }


def _prediction_markets(*rows: dict) -> dict:
    return {
        "data": list(rows),
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total_items": len(rows),
            "total_pages": 1,
        },
    }


def test_augury_macro_renders_calendar_observations_without_fred_metadata(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            _macro(
                {
                    "indicator": "cpi",
                    "date": "2025-01-15",
                    "country": "US",
                    "actual": 3.0,
                    "forecast": 2.9,
                    "previous": 2.8,
                    "pit_approximate": True,
                }
            )
        )

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_macro_data("cpi", "2025-01-15", look_back_days=30)

    assert "calendar-style observations" in report.lower()
    assert "| Date | Actual | Forecast | Previous |" in report
    assert "| 2025-01-15 [PIT approximate] | 3.0 | 2.9 | 2.8 |" in report
    assert "Units:" not in report
    assert "Frequency:" not in report
    assert "FRED" not in report
    assert calls == [
        (
            "http://localhost:8765/macro",
            {"params": {"indicator": "cpi", "days": 30}, "timeout": 30},
        )
    ]


# scenario: SC-e03s04-P1-01


def test_augury_prediction_markets_filters_topic_keywords_and_renders_odds(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            _prediction_markets(
                {
                    "market_id": "fed-1",
                    "question": "Will the Fed cut rates in 2026?",
                    "slug": "fed-rate-cut-2026",
                    "outcomes": ["Yes", "No"],
                    "outcome_prices": [0.72, 0.28],
                    "category": "fed",
                    "end_date": "2099-01-01",
                    "volume": 12000,
                    "active": True,
                    "closed": False,
                },
                {
                    "market_id": "slug-1",
                    "question": "Central bank policy decision",
                    "slug": "rate-cut-by-june",
                    "outcomes": ["Yes", "No"],
                    "outcome_prices": [0.55, 0.45],
                    "category": "fed",
                    "end_date": "2099-01-01",
                    "volume": 8000,
                    "active": True,
                    "closed": False,
                },
                {
                    "market_id": "other-1",
                    "question": "Will Bitcoin reach a new high?",
                    "slug": "bitcoin-high",
                    "outcomes": ["Yes", "No"],
                    "outcome_prices": [0.40, 0.60],
                    "category": "crypto",
                    "end_date": "2099-01-01",
                    "volume": 99999,
                    "active": True,
                    "closed": False,
                },
            )
        )

    monkeypatch.setattr(_augury().requests, "get", fake_get)

    report = _augury().get_augury_prediction_markets("Fed rate cut", limit=2)

    assert "Augury prediction markets" in report
    assert "Will the Fed cut rates in 2026?" in report
    assert "Central bank policy decision" in report
    assert "Bitcoin" not in report
    assert "72%" in report
    assert "$12,000" in report
    assert "2099-01-01" in report
    assert calls == [
        (
            "http://localhost:8765/prediction-markets",
            {"params": {"category": "fed", "limit": 2}, "timeout": 30},
        )
    ]


def test_augury_prediction_markets_withholds_past_analysis_without_fetch(monkeypatch):
    called = False

    def unexpected_get(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("past analysis date must not fetch cached odds")

    monkeypatch.setattr(_augury().requests, "get", unexpected_get)

    report = _augury().get_augury_prediction_markets("Fed rate cut", curr_date="2020-01-01")

    assert "withheld" in report.lower()
    assert "2020-01-01" in report
    assert called is False


# scenario: SC-e03s04-P1-02


def test_augury_optional_categories_fail_open_when_lake_is_unreachable(monkeypatch):
    def raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("lake unreachable")

    monkeypatch.setattr(_augury().requests, "get", raise_connection_error)
    interface = importlib.import_module("tradingagents.dataflows.interface")
    set_config(
        {
            "data_vendors": {
                "macro_data": "augury",
                "prediction_markets": "augury",
            }
        }
    )

    macro = route_to_vendor("get_macro_indicators", "cpi", "2025-01-15")
    prediction = route_to_vendor("get_prediction_markets", "Fed rate cut", curr_date=None)

    assert "DATA_UNAVAILABLE" in macro
    assert "DATA_UNAVAILABLE" in prediction
    assert "optional" in macro
    assert "optional" in prediction


def test_augury_is_registered_for_optional_macro_and_prediction_methods():
    interface = importlib.import_module("tradingagents.dataflows.interface")

    assert interface.OPTIONAL_CATEGORIES == {"macro_data", "prediction_markets"}
    assert interface.VENDOR_METHODS["get_macro_indicators"]["augury"] is _augury().get_augury_macro_data
    assert (
        interface.VENDOR_METHODS["get_prediction_markets"]["augury"]
        is _augury().get_augury_prediction_markets
    )
