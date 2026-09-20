"""Init-time coercion/validation for run-configuration values.

These helpers used to live in ``graph/trading_graph.py``. That module is listed
in CONVENTIONS § File-Size Exceptions ("MUST NOT grow further"), and the frozen
baseline is exactly at its 672-line cap, so every line the facade adds has to be
paid for elsewhere in the same file. Extracting the coercers keeps the facade's
validation contract (fail at graph init, before any spend) while leaving room
for new config keys.

The facade re-imports these names, so ``from
tradingagents.graph.trading_graph import _coerce_max_tokens`` keeps working for
existing callers and tests.
"""

from __future__ import annotations


def _coerce_max_retries(value):
    """Validate an ``llm_max_retries`` value to a non-negative int.

    Accepts an int or a numeric string (env vars arrive as strings). Rejects
    booleans and negatives loudly so a misconfiguration fails at startup rather
    than silently disabling retries.
    """
    if isinstance(value, bool):
        raise ValueError(f"llm_max_retries must be an integer, not a boolean: {value!r}")
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"llm_max_retries must be an integer, got {value!r}") from exc
    if n < 0:
        raise ValueError(f"llm_max_retries must be >= 0, got {n}")
    return n


def _coerce_max_tokens(value):
    """Validate a ``max_tokens`` value to a positive int (env vars are strings)."""
    if isinstance(value, bool):
        raise ValueError(f"max_tokens must be an integer, not a boolean: {value!r}")
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"max_tokens must be an integer, got {value!r}") from exc
    if n <= 0:
        raise ValueError(f"max_tokens must be > 0, got {n}")
    return n
