"""What the live display shows, and what the run log keeps.

The display drops a message it judges empty, and the state log is written for a
person to read afterwards. Both got that wrong in ways that hide real content.
"""

from __future__ import annotations

import json

import pytest

from cli.main import extract_content_string


@pytest.mark.unit
@pytest.mark.parametrize("text", ["0", "False", "None", "[]", "{}", "0.0"])
def test_a_message_that_reads_like_a_python_value_is_still_text(text):
    """These were parsed as Python and judged empty, so the message vanished."""
    assert extract_content_string(text) == text


@pytest.mark.unit
@pytest.mark.parametrize("value, expected", [
    ("  Hold  ", "Hold"),
    ("", None),
    ("   ", None),
    (None, None),
    ([], None),
    ({}, None),
    ({"text": "from a dict"}, "from a dict"),
    ([{"type": "text", "text": "part one"}, {"type": "text", "text": "part two"}], "part one part two"),
])
def test_the_other_shapes_are_unchanged(value, expected):
    assert extract_content_string(value) == expected


@pytest.mark.unit
def test_the_state_log_keeps_non_ascii_readable(tmp_path):
    """Reports can be in any language; the log is read by a person."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    graph = object.__new__(TradingAgentsGraph)
    graph.config = {"results_dir": str(tmp_path)}
    graph.ticker = "600519.SS"
    graph.log_states_dict = {}

    graph._log_state("2026-09-01", {
        "company_of_interest": "600519.SS", "trade_date": "2026-09-01",
        "market_report": "市场", "sentiment_report": "情绪", "news_report": "新闻",
        "fundamentals_report": "基本面", "investment_plan": "计划",
        "trader_investment_plan": "交易计划", "final_trade_decision": "评级: 买入",
        "investment_debate_state": {"bull_history": "", "bear_history": "", "history": "",
                                    "current_response": "", "judge_decision": "", "count": 0},
        "risk_debate_state": {"aggressive_history": "", "conservative_history": "",
                              "neutral_history": "", "history": "", "judge_decision": "",
                              "latest_speaker": "", "current_aggressive_response": "",
                              "current_conservative_response": "", "current_neutral_response": "",
                              "count": 0},
    })

    written = next(tmp_path.rglob("full_states_log*.json")).read_text(encoding="utf-8")
    assert "买入" in written
    assert "\\u" not in written
    assert json.loads(written)  # still valid JSON


@pytest.mark.unit
def test_the_live_display_does_not_scroll_the_terminal():
    """A layout taller than the window makes rich redraw by scrolling, which
    reads as flicker; the alternate screen holds it in place (#784). The final
    report prints after the live view ends, so nothing is lost when it closes."""
    import inspect

    import cli.main as m

    assert "screen=True" in inspect.getsource(m.run_analysis)


# --- a skipped debate is shown as skipped (e02s02, SC-e02s02-P2-01) ----------

REPORTS = {"market_report": "MKT: trend up, volume confirms."}

RESEARCH_TEAM = ("Bull Researcher", "Bear Researcher", "Research Manager")


def _chunk(**state):
    return {**REPORTS, **state}


def _buffer():
    """A buffer initialized exactly as run_analysis does, on a fresh instance."""
    import cli.main as m

    buffer = m.MessageBuffer()
    buffer.init_for_analysis(["market"])
    return buffer


@pytest.mark.unit
def test_a_skipped_debate_leaves_no_research_agent_pending():
    """SC-e02s02-P2-01 — the gate routes past the debaters, so the live view must
    say so: 'skipped' for Bull/Bear, never 'pending' (a stalled-looking run) or
    'completed' (work that never happened)."""
    from cli.stream_handler import apply_value_chunk

    buffer = _buffer()
    apply_value_chunk(buffer, _chunk())  # analyst phase done
    assert buffer.agent_status["Market Analyst"] == "completed"

    marker = "**Debate skipped by the Debate Gate.**"
    apply_value_chunk(buffer, _chunk(investment_debate_state={
        "bull_history": "", "bear_history": "", "history": marker,
        "current_response": marker, "judge_decision": "", "count": 0,
    }, debate_gate_verdict=marker))

    assert buffer.agent_status["Bull Researcher"] == "skipped"
    assert buffer.agent_status["Bear Researcher"] == "skipped"
    assert [a for a in RESEARCH_TEAM if buffer.agent_status[a] == "pending"] == []


@pytest.mark.unit
def test_skipped_survives_the_research_manager_decision():
    """The judge's chunk used to mark the whole research team 'completed', which
    would rewrite the two agents the gate never ran."""
    from cli.stream_handler import apply_value_chunk

    buffer = _buffer()
    marker = "**Debate skipped by the Debate Gate.**"
    apply_value_chunk(buffer, _chunk(investment_debate_state={
        "bull_history": "", "bear_history": "", "history": marker,
        "current_response": marker, "judge_decision": "", "count": 0,
    }, debate_gate_verdict=marker))
    apply_value_chunk(buffer, _chunk(investment_debate_state={
        "bull_history": "", "bear_history": "", "history": marker,
        "current_response": marker, "judge_decision": "**Recommendation**: Buy", "count": 0,
    }, debate_gate_verdict=marker, investment_plan="PLAN"))

    assert buffer.agent_status["Research Manager"] == "completed"
    assert buffer.agent_status["Bull Researcher"] == "skipped"
    assert buffer.agent_status["Bear Researcher"] == "skipped"
    assert buffer.agent_status["Trader"] == "in_progress"


@pytest.mark.unit
def test_a_held_debate_is_not_read_as_skipped():
    """The held path writes the same `debate_gate_verdict` key (that is the whole
    trap), so the status must come from the transcript, not from that key."""
    from cli.stream_handler import apply_value_chunk

    held_marker = "**Debate skipped by the Debate Gate.**"  # held runs carry it too
    buffer = _buffer()
    apply_value_chunk(buffer, _chunk(investment_debate_state={
        "bull_history": "", "bear_history": "", "history": "", "current_response": "",
        "judge_decision": "", "count": 0,
    }, debate_gate_verdict=held_marker))
    assert buffer.agent_status["Bull Researcher"] != "skipped"

    apply_value_chunk(buffer, _chunk(investment_debate_state={
        "bull_history": "BULL ARGUMENT", "bear_history": "", "history": "BULL ARGUMENT",
        "current_response": "BULL ARGUMENT", "judge_decision": "", "count": 1,
    }, debate_gate_verdict=held_marker))
    assert buffer.agent_status["Bull Researcher"] == "in_progress"
    assert buffer.agent_status["Bear Researcher"] != "skipped"

    apply_value_chunk(buffer, _chunk(investment_debate_state={
        "bull_history": "BULL ARGUMENT", "bear_history": "BEAR ARGUMENT",
        "history": "BULL ARGUMENT BEAR ARGUMENT", "current_response": "BEAR ARGUMENT",
        "judge_decision": "**Recommendation**: Buy", "count": 2,
    }, debate_gate_verdict=held_marker, investment_plan="PLAN"))

    assert buffer.agent_status["Bull Researcher"] == "completed"
    assert buffer.agent_status["Bear Researcher"] == "completed"
    assert buffer.agent_status["Research Manager"] == "completed"


@pytest.mark.unit
def test_the_progress_panel_renders_the_skipped_status(monkeypatch):
    """The status must reach the screen: it is a known state now, next to
    pending / completed / error, not an unmapped fall-through."""
    from io import StringIO

    from rich.console import Console

    import cli.main as m

    buffer = _buffer()
    buffer.update_agent_status("Bull Researcher", "skipped")
    buffer.update_agent_status("Bear Researcher", "skipped")
    monkeypatch.setattr(m, "message_buffer", buffer)

    layout = m.create_layout()
    m.update_display(layout, stats_handler=None, start_time=None)
    rendered = StringIO()
    Console(file=rendered, width=120).print(layout)
    assert "skipped" in rendered.getvalue()
