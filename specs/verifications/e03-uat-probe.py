# verify-work phase 6 — UAT probes for e03 (deterministic, no network, no live lake).
# Usage: .venv/bin/python specs/verifications/e03-uat-probe.py <probe>
# Probes: default | optin | sentinel-core | sentinel-optional | not-configured
import copy
import os
import sys

for k in ["ALPHA_VANTAGE_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_API_KEY",
          "DASHSCOPE_API_KEY", "DASHSCOPE_CN_API_KEY", "DEEPSEEK_API_KEY",
          "GOOGLE_API_KEY", "MINIMAX_API_KEY", "MINIMAX_CN_API_KEY",
          "OPENAI_API_KEY", "OPENROUTER_API_KEY", "XAI_API_KEY",
          "ZHIPU_API_KEY", "ZHIPU_CN_API_KEY"]:
    os.environ.setdefault(k, "test-placeholder")

probe = sys.argv[1]

AUGURY_TOOLS = {"get_ai_forecast", "get_valuation", "get_signal_states",
                "get_liquidity", "get_feature_vector", "get_universe_membership"}

if probe in ("default", "optin"):
    from tradingagents.dataflows.config import set_config
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if probe == "optin":
        cfg["data_vendors"] = dict(cfg["data_vendors"], ai_forecast="augury",
                                   valuation="augury", signal_states="augury",
                                   cross_sectional="augury")
        set_config({"data_vendors": cfg["data_vendors"]})
    g = TradingAgentsGraph(config=cfg)
    names = {k: sorted(getattr(node, "tools_by_name", {}).keys())
             for k, node in g.tool_nodes.items()}
    for node, tools in names.items():
        flagged = sorted(AUGURY_TOOLS & set(tools))
        print(f"{probe}: node={node} tools={tools} augury_bound={flagged}")
    if probe == "default":
        assert all(not (AUGURY_TOOLS & set(v)) for v in names.values()), "default must bind no augury tools"
        print("U1 PASS: default config binds zero augury tools")
    else:
        assert "get_ai_forecast" in names["market"], "market must gain get_ai_forecast"
        assert "get_valuation" in names["fundamentals"], "fundamentals must gain get_valuation"
        assert "get_signal_states" in names["market"] and "get_signal_states" in names["fundamentals"]
        assert "get_liquidity" in names["market"] and "get_feature_vector" in names["market"]
        assert "get_universe_membership" in names["fundamentals"]
        assert not (AUGURY_TOOLS & set(names["news"])), "news node untouched"
        print("U2 PASS: opt-in binds augury tools exactly per D2/D5")

elif probe == "sentinel-core":
    from tradingagents.dataflows.config import set_config
    from tradingagents.dataflows.interface import route_to_vendor
    set_config({"data_vendors": {"core_stock_apis": "augury"}})
    try:
        route_to_vendor("get_stock_data", "AAPL", "2026-09-01", "2026-09-20")
        print("U3 FAIL: expected an exception with the lake down")
        sys.exit(1)
    except Exception as e:
        print(f"U3 PASS: fail-closed core category raised {type(e).__name__}: {str(e)[:120]}")

elif probe == "sentinel-optional":
    from tradingagents.dataflows.config import set_config
    from tradingagents.dataflows.interface import route_to_vendor
    set_config({"data_vendors": {"macro_data": "augury"}})
    out = route_to_vendor("get_macro_indicators", "cpi", "2026-09-20")
    assert "DATA_UNAVAILABLE" in str(out), f"expected DATA_UNAVAILABLE sentinel, got: {str(out)[:120]}"
    print(f"U4 PASS: fail-open optional category returned sentinel: {str(out)[:120]}")

elif probe == "not-configured":
    from tradingagents.dataflows.config import set_config
    from tradingagents.dataflows.errors import VendorNotConfiguredError
    from tradingagents.dataflows.interface import route_to_vendor
    set_config({"augury_base_url": "", "data_vendors": {"core_stock_apis": "augury"}})
    try:
        route_to_vendor("get_stock_data", "AAPL", "2026-09-01", "2026-09-20")
        print("U5 FAIL: expected VendorNotConfiguredError")
        sys.exit(1)
    except VendorNotConfiguredError as e:
        print(f"U5 PASS: empty base URL surfaced as VendorNotConfiguredError: {str(e)[:100]}")
