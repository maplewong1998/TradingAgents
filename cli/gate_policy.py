"""The Bull/Bear debate policy as an interactive choice (story e02s02).

The gate runs in one of three modes, and the mode changes what a run does rather
than how it looks, so the CLI offers it once, next to Research Depth, and
remembers the answer. The valid set lives beside the gate node
(``tradingagents.agents.gate.debate_gate.DEBATE_GATE_MODES``) — one source of
truth for the graph, the env overlay and this menu.

This module exists because ``cli/main.py`` is at its file-size cap
(CONVENTIONS § File-Size Exceptions: "MUST NOT grow further"); new CLI code goes
into its own module instead, as ``cli/prefs.py`` and ``cli/stats_handler.py`` do.
"""

from __future__ import annotations

import os

import questionary
from rich.console import Console

from cli.utils import _matching_choice

console = Console()

# Auto leads: it is the default and the recommended policy — the debate is held
# only when the analysts actually disagree.
GATE_POLICY_OPTIONS = [
    ("Auto - judge each run; skip the debate when the analysts already agree (recommended)", "auto"),
    ("Always - always hold the Bull/Bear debate (no judge call)", "always"),
    ("Never - never hold the debate (no judge call, no arbitration)", "never"),
]


def ask_debate_gate(default=None) -> str:
    """Ask which debate policy this run should use, offering the last answer back.

    ``default`` is a prefill only: the prompt always appears, and a remembered
    value the menu no longer offers is dropped rather than handed to questionary
    as a default it cannot find.
    """
    choice = questionary.select(
        "Select Your [Debate Gate Policy]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in GATE_POLICY_OPTIONS
        ],
        default=_matching_choice(GATE_POLICY_OPTIONS, default),
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        # No answer is not "auto": a run whose policy nobody chose must not
        # silently buy (or skip) a debate it was never told to run.
        console.print("\n[red]No debate gate policy selected. Exiting...[/red]")
        raise SystemExit(1)

    return choice


def select_debate_gate(prefs: dict, config_policy: str, console, question_box) -> str:
    """Step 5b: the policy for this run, from the environment or from the menu.

    ``TRADINGAGENTS_DEBATE_GATE`` is the non-interactive path: the env overlay has
    already put the value on the config, so the prompt is skipped and the value
    used — the same precedence rule the round counts follow (#977,
    SC-e02s02-P1-02). ``console`` and ``question_box`` are the caller's, so the
    step prints like every other prompt instead of owning a second console.
    """
    if os.environ.get("TRADINGAGENTS_DEBATE_GATE"):
        console.print(
            "[green]✓ Debate gate policy from environment:[/green] "
            f"{config_policy} (set by TRADINGAGENTS_DEBATE_GATE)"
        )
        return config_policy

    console.print(
        question_box(
            "Step 5b: Debate Gate Policy",
            "Select whether the Bull/Bear debate is judged, always held, or never held",
        )
    )
    return ask_debate_gate(prefs.get("debate_gate"))


def resolve_debate_gate(config_policy: str, selections: dict, console) -> str:
    """The policy the run will use: an explicit env var wins over the menu pick.

    Mirrors the round-count rule (#977, SC-e02s02-P1-02). When the env var is set,
    the value already on the config is the one that applies, and the user is told
    which of the two answers won instead of silently discarding one of them.
    """
    if os.environ.get("TRADINGAGENTS_DEBATE_GATE"):
        console.print(
            f"[green]✓ debate_gate from environment:[/green] {config_policy} "
            "(set by TRADINGAGENTS_DEBATE_GATE, so the policy you chose does not apply)"
        )
        return config_policy
    return selections.get("debate_gate") or config_policy
