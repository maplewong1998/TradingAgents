"""Structured verdict for the conditional debate gate (story e02s01).

Lives beside the gate node rather than in ``agents/schemas.py`` because that
module is at the size cap (see CONVENTIONS.md § File-Size Exceptions: "these
files MUST NOT grow further"); the names are re-exported from
``tradingagents.agents.schemas`` so the public import path is unchanged.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DebateGateVerdict(BaseModel):
    """The gate judge's answer to one question: is this evidence contested?

    Contract: a structured call, so the routing decision is a typed value rather
    than prose a weaker model could phrase into a skip. Failure mode: any
    exception, ``None``, or unparseable payload is caught by the gate node,
    which then routes into the debate exactly as the unconditional graph did.
    Skipping a debate is only ever allowed from a valid instance of this model.
    """

    evidence_aligned: bool = Field(
        description=(
            "True only when the four analyst reports point to the same "
            "directional conclusion with shared evidence. False when they "
            "disagree, hedge, or rest on different evidence."
        ),
    )
    confidence: Literal["low", "medium", "high"] = Field(
        description=(
            "Confidence in this alignment judgement, driven by how complete and "
            "agreement-consistent the four reports are. Use 'low' whenever any "
            "report is missing or thin: low confidence never skips the debate."
        ),
    )
    aligned_direction: Literal["bullish", "bearish", "mixed", "unclear"] | None = Field(
        default=None,
        description=(
            "The shared direction when evidence_aligned is True: bullish, "
            "bearish, mixed or unclear. Omit it when the reports are not aligned."
        ),
    )
    rationale: str = Field(
        description=(
            "One to three sentences naming the specific agreement or tension "
            "between the reports. This text is shown to the Research Manager "
            "when the debate is skipped, so state the evidence, not a verdict."
        ),
    )


def render_debate_gate_marker(verdict: DebateGateVerdict) -> str:
    """Render a verdict to the marker the Research Manager reads as debate history.

    On a skip the research manager receives this string instead of a debate
    transcript. It is deliberately explicit that no debate was held: an empty
    transcript reads as "the debate found nothing", which invites the manager to
    invent the conflict it expects to weigh (#1176 fabrication class).
    """
    direction = verdict.aligned_direction or "unclear"
    return "\n".join([
        "**Debate skipped by the Debate Gate.** The four analyst reports are "
        f"aligned ({direction}) at {verdict.confidence} confidence, so the Bull/Bear "
        "debate was not run: no conflicting arguments were presented, and none "
        "should be assumed.",
        "",
        f"**Gate rationale**: {verdict.rationale}",
    ])
