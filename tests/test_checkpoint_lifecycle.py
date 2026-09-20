"""The checkpoint lifecycle is reusable so --checkpoint works on the CLI path (#1249).

Checkpoint setup previously lived only inside ``propagate``; the CLI streamed the
checkpointer-less graph, so ``--checkpoint`` neither saved nor resumed. The
lifecycle is now ``begin_checkpoint`` / ``end_checkpoint`` /
``clear_checkpoint_on_success`` on TradingAgentsGraph, used by both paths. These
tests drive that lifecycle exactly as the CLI does (begin -> stream self.graph ->
clear/end) and prove state is saved and resumed.
"""
from __future__ import annotations

import tempfile
from typing import TypedDict

import pytest
from langgraph.graph import END, StateGraph

from tradingagents.graph.checkpointer import checkpoint_step
from tradingagents.graph.trading_graph import TradingAgentsGraph

_should_crash = False


class _State(TypedDict):
    count: int


def _node_a(state: _State) -> dict:
    return {"count": state["count"] + 1}


def _node_b(state: _State) -> dict:
    if _should_crash:
        raise RuntimeError("simulated mid-stream crash")
    return {"count": state["count"] + 10}


def _workflow() -> StateGraph:
    b = StateGraph(_State)
    b.add_node("analyst", _node_a)
    b.add_node("trader", _node_b)
    b.set_entry_point("analyst")
    b.add_edge("analyst", "trader")
    b.add_edge("trader", END)
    return b


def _bare_graph(tmpdir, *, enabled=True, gate="auto"):
    g = object.__new__(TradingAgentsGraph)
    g.config = {
        "checkpoint_enabled": enabled, "data_cache_dir": tmpdir,
        "max_debate_rounds": 1, "max_risk_discuss_rounds": 1,
        "debate_gate": gate,
    }
    g.selected_analysts = ("market",)
    g.workflow = _workflow()
    g.graph = g.workflow.compile()
    g._checkpointer_ctx = None
    return g




@pytest.mark.unit
def test_disabled_is_a_noop():
    with tempfile.TemporaryDirectory() as tmp:
        g = _bare_graph(tmp, enabled=False)
        plain = g.graph
        assert g.begin_checkpoint("AAPL", "2026-05-08", "stock") is None
        assert g.graph is plain  # graph not recompiled
        g.end_checkpoint()  # safe no-op


@pytest.mark.unit
def test_begin_returns_thread_id_and_recompiles():
    with tempfile.TemporaryDirectory() as tmp:
        g = _bare_graph(tmp)
        plain = g.graph
        tid = g.begin_checkpoint("AAPL", "2026-05-08", "stock")
        try:
            assert tid  # a real thread_id
            assert g.graph is not plain  # recompiled with a checkpointer
        finally:
            g.end_checkpoint()
        assert g._checkpointer_ctx is None  # restored


@pytest.mark.unit
def test_checkpoint_input_is_none_only_when_resuming():
    global _should_crash
    with tempfile.TemporaryDirectory() as tmp:
        init = {"count": 0}
        args = ("AAPL", "2026-05-08", "stock")
        # Fresh run: no checkpoint yet -> stream the initial state, then crash.
        g1 = _bare_graph(tmp)
        tid = g1.begin_checkpoint(*args)
        try:
            assert g1._resuming is False
            assert g1.checkpoint_input(init) is init  # not resuming -> initial state
            _should_crash = True
            with pytest.raises(RuntimeError):
                for _ in g1.graph.stream(init, config={"configurable": {"thread_id": tid}}):
                    pass
        finally:
            g1.end_checkpoint()
        assert g1.checkpoint_input(init) is init  # reset after teardown

        # A later run finds the checkpoint -> resume by feeding None, not the
        # initial state (re-passing it would duplicate messages, #1249).
        _should_crash = False
        g2 = _bare_graph(tmp)
        g2.begin_checkpoint(*args)
        try:
            assert g2._resuming is True
            assert g2.checkpoint_input(init) is None
        finally:
            g2.end_checkpoint()


@pytest.mark.unit
def test_cli_style_usage_saves_then_resumes():
    global _should_crash
    with tempfile.TemporaryDirectory() as tmp:
        cfg_args = ("AAPL", "2026-05-08", "stock")

        # Run 1 (the CLI path): begin -> stream self.graph -> crash at 'trader'.
        _should_crash = True
        g1 = _bare_graph(tmp)
        tid = g1.begin_checkpoint(*cfg_args)
        args = {"config": {"configurable": {"thread_id": tid}}}
        try:
            with pytest.raises(RuntimeError):
                for _ in g1.graph.stream({"count": 0}, **args):
                    pass
        finally:
            g1.end_checkpoint()

        # A checkpoint was saved for this run signature (so --checkpoint works).

        sig = g1._run_signature("stock")
        assert checkpoint_step(tmp, "AAPL", "2026-05-08", sig) is not None

        # Run 2 (fresh graph, as a new CLI invocation): resume and finish.
        _should_crash = False
        g2 = _bare_graph(tmp)
        tid2 = g2.begin_checkpoint(*cfg_args)
        assert tid2 == tid  # stable id -> same thread resumes
        try:
            result = g2.graph.invoke(None, config={"configurable": {"thread_id": tid2}})
            assert result["count"] == 11  # analyst(+1) resumed into trader(+10)
            g2.clear_checkpoint_on_success(*cfg_args)
        finally:
            g2.end_checkpoint()

        # Cleared on success -> a later run starts fresh.
        assert checkpoint_step(tmp, "AAPL", "2026-05-08", sig) is None


@pytest.mark.unit
def test_clearing_removes_the_database_sidecars(tmp_path):
    """SQLite writes -wal and -shm next to the database; leaving them behind
    means a cleared checkpoint still has committed state on disk."""
    from tradingagents.graph.checkpointer import clear_all_checkpoints

    cp = tmp_path / "checkpoints"
    cp.mkdir(parents=True)
    for suffix in (".db", ".db-wal", ".db-shm"):
        (cp / f"NVDA{suffix}").write_text("x")

    cleared = clear_all_checkpoints(str(tmp_path))

    assert cleared == 1
    assert list(cp.iterdir()) == []


# --- the gate policy is part of the checkpoint key (e02s02, SC-e02s02-P1-01) ---


@pytest.mark.unit
def test_the_run_signature_carries_the_gate_mode():
    """The gate changes the graph's route, so it changes the graph's shape.

    A signature that ignores the policy lets a thread checkpointed under `auto`
    resume under `always`: the debate would then be skipped (or held) by a
    decision the resumed graph never took (#1089 class, story e02s02).
    """
    with tempfile.TemporaryDirectory() as tmp:
        auto = _bare_graph(tmp, gate="auto")._run_signature("stock")
        always = _bare_graph(tmp, gate="always")._run_signature("stock")
        never = _bare_graph(tmp, gate="never")._run_signature("stock")

        assert "gate=auto" in auto
        assert len({auto, always, never}) == 3  # one signature per policy
        assert auto == _bare_graph(tmp, gate="auto")._run_signature("stock")


@pytest.mark.unit
def test_a_resume_under_a_changed_gate_mode_starts_fresh():
    """Same ticker+date, different policy: the checkpoint must not be reused."""
    global _should_crash
    with tempfile.TemporaryDirectory() as tmp:
        args = ("AAPL", "2026-05-08", "stock")

        _should_crash = True
        g1 = _bare_graph(tmp, gate="auto")
        tid = g1.begin_checkpoint(*args)
        try:
            with pytest.raises(RuntimeError):
                for _ in g1.graph.stream(
                    {"count": 0}, config={"configurable": {"thread_id": tid}}
                ):
                    pass
        finally:
            g1.end_checkpoint()
        auto_signature = g1._run_signature("stock")
        assert checkpoint_step(tmp, "AAPL", "2026-05-08", auto_signature) is not None

        # The same run, now under `always`: nothing to resume, so both nodes run.
        _should_crash = False
        g2 = _bare_graph(tmp, gate="always")
        tid2 = g2.begin_checkpoint(*args)
        try:
            assert tid2 != tid
            assert g2._resuming is False
            assert g2.checkpoint_input({"count": 0}) == {"count": 0}
            result = g2.graph.invoke(
                {"count": 0}, config={"configurable": {"thread_id": tid2}}
            )
            assert result["count"] == 11  # analyst(+1) then trader(+10), from scratch
        finally:
            g2.end_checkpoint()

        # The other policy's checkpoint is untouched, not consumed by this run.
        assert checkpoint_step(tmp, "AAPL", "2026-05-08", auto_signature) is not None


@pytest.mark.unit
def test_the_same_gate_mode_still_resumes():
    """The extra key must not break resume: the same policy is the same thread."""
    global _should_crash
    with tempfile.TemporaryDirectory() as tmp:
        args = ("AAPL", "2026-05-08", "stock")

        _should_crash = True
        g1 = _bare_graph(tmp, gate="auto")
        tid = g1.begin_checkpoint(*args)
        try:
            with pytest.raises(RuntimeError):
                for _ in g1.graph.stream(
                    {"count": 0}, config={"configurable": {"thread_id": tid}}
                ):
                    pass
        finally:
            g1.end_checkpoint()

        _should_crash = False
        g2 = _bare_graph(tmp, gate="auto")
        tid2 = g2.begin_checkpoint(*args)
        try:
            assert tid2 == tid  # stable id -> the saved run resumes
            assert g2._resuming is True
            assert g2.checkpoint_input({"count": 0}) is None  # resume, don't re-add
            result = g2.graph.invoke(None, config={"configurable": {"thread_id": tid2}})
            assert result["count"] == 11
        finally:
            g2.end_checkpoint()
