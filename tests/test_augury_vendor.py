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
