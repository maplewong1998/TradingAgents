# Story e03s07: Cross-sectional context — analyst-bound (liquidity, feature vector, universe)

<!-- story: e03s07 -->

**type:** feat
**risk:** P1 (new read-only tools; per-item failure slots must never be smoothed over)
**context:** domain
**bcps:** 5
**status:** planned (e45s06 ledger — tasks start `failing`, flip only on green verify)

**Context:** The cross-sectional pack (D1), placed per D5: the Portfolio
Manager has no tool loop today and the confirmed constraint is zero graph
change, so these tools are shaped per-ticker and bound to existing analyst
ToolNodes — the context reaches the Portfolio Manager through analyst reports
as it does for every other input. Three tools: `get_liquidity` (market
analyst), `get_feature_vector` (market analyst — the single-ticker view of the
lake's batch decision vector), and `get_universe_membership` (fundamentals
analyst — is this ticker in the tradeable universe as of the analysis date,
delisted included so a delisting is *visible*).

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `dataflows/augury.py` | Augury lake HTTP vendor | `route_to_vendor` | New fns `get_augury_liquidity`, `get_augury_feature_vector`, `get_augury_universe_membership`; per-item `failed` slots rendered, never dropped |
| `dataflows/interface.py` | The only vendor seam | `@tool` wrappers | New category `cross_sectional` in `TOOLS_CATEGORIES` + `OPTIONAL_CATEGORIES`; registration-only |
| `agents/utils/cross_sectional_tools.py` (NEW) | `@tool` wrappers | analysts, `agent_utils.__all__` | `InjectedState("trade_date")` + `as_of` clamp pattern |
| `graph/trading_graph.py` `_create_tool_nodes` | Per-analyst ToolNodes | `TradingAgentsGraph.__init__` | Same binding gate as e03s05/s06; **no PM ToolNode, no new edges** (D5) |

## Requirements (delta tags, e45s29)

#### ADDED: get_liquidity tool (market analyst)
`@tool get_liquidity(ticker, curr_date)` → `GET /liquidity/{ticker}` rendered
as a short markdown block. If the endpoint proves live-vintage-only at
implementation time (no `as_of` in the served contract), the polymarket
withholding rule applies for past analysis dates — verified against
openapi.json during RED and pinned by test.

#### ADDED: get_feature_vector tool (market analyst)
`@tool get_feature_vector(ticker, curr_date)` → `POST
/api/v1/batch/feature-vector` with a one-ticker body (endpoint accepts 1–500
tickers and returns per-ticker `failed` slots). A `failed` slot for the
requested ticker renders as an explicit "not available: \<reason\>" line —
never silently omitted. Feature reads are PIT-safe (`as_of`/vintage pins per
the features contract).

#### ADDED: get_universe_membership tool (fundamentals analyst)
`@tool get_universe_membership(ticker, curr_date)` → `GET /api/v1/universe?
as_of=<clamped>&q=<ticker>`; the lake's universe is PIT and includes delisted
members, so the markdown states membership status plainly, including "present
but delisted" and "absent from the tradeable universe" as distinct outcomes.

## Discovery Mandate (external API, verified)

Verified 2026-09-24 against `~/Repo_Private/augury/openapi.json` + README:
`POST /api/v1/batch/feature-vector` — "Cross-sectional decision vectors (1–500
tickers, per-ticker `failed` slots)"; request `FeatureVectorBatchRequest`,
response `FeatureVectorResponse`/`FeatureVectorItem` + `FeatureVectorWatermark`.
`GET /api/v1/universe` — "PIT universe membership, delisted included
(`?as_of=&q=`)". `GET /liquidity/{ticker}` param `ticker*` (also
`/liquidity/batch`). All list responses are `Page[T]` envelopes
(`page`/`page_size`, max 200).

## Slopcheck

No new external packages. `requests` **[OK]** — via the e03s01 `_request` helper
(the batch POST reuses its error mapping; `requests.post` beside
`requests.get`, same boundary).

## Steps

1. RED: extend `tests/test_augury_tools.py` (`# story: e03s07`) — liquidity
   markdown + the live-vintage check result pinned; feature vector with a
   `failed` slot rendered explicitly; universe membership present / delisted /
   absent rendered as three distinct outcomes; binding-gate on/off matrix →
   verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "liquidity or feature_vector or universe" --collect-only`
2. GREEN vendor: the three functions, including the per-item `failed`-slot
   honesty and the universe status trichotomy → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "vendor and (liquidity or feature_vector or universe)"`
3. Seam: `cross_sectional` category in `TOOLS_CATEGORIES` + `VENDOR_METHODS` +
   `OPTIONAL_CATEGORIES` → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "registration or routing"`
4. GREEN tools + bindings: `cross_sectional_tools.py`; `agent_utils.__all__`
   exports; market node gains `get_liquidity` + `get_feature_vector`,
   fundamentals node gains `get_universe_membership`, all under the binding
   gate; conditional prompt paragraphs; assert no ToolNode exists for the
   Portfolio Manager → verify: `.venv/bin/python -m pytest -q tests/test_augury_tools.py -k "cross_sectional or binding or prompt"`
5. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s07-P1-01
Given cross_sectional configured as "augury" and the lake returns a failed slot for the ticker
When get_feature_vector runs
Then the markdown contains an explicit "not available" line naming the reason

# scenario: SC-e03s07-P1-02
Given the same configuration and a ticker delisted before the analysis date
When get_universe_membership runs
Then the markdown says "present but delisted" as of that date, not "absent"

# scenario: SC-e03s07-P0-01
Given any configuration
When the graph is built
Then the Portfolio Manager has no ToolNode and the graph's node/edge set is unchanged from today

# scenario: SC-e03s07-P1-03
Given a stock default_config
When the analyst ToolNodes are built
Then none of the three tools is bound and prompts are unchanged
```

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_augury_tools.py -v -k "liquidity or feature_vector or universe or cross_sectional"` — all green.
2. Run `.venv/bin/python -m pytest -q` and `ruff check .` — full Preflight green.
3. Optional live smoke: with the lake up and `cross_sectional: "augury"`, run a
   covered ticker and observe the liquidity block and universe membership line
   in the analyst reports.

## Out of scope

- A Portfolio Manager tool loop (D5 — would be a graph change); true
  multi-ticker screening UX (the batch endpoint is used one ticker at a time);
  `/api/v1/features/query` cross-sectional filters; watchlist/decision/position
  endpoints (decision storage is the lake's domain).

## Risks

- **Per-ticker shaping wastes the batch endpoint** — accepted: the run analyzes
  one ticker; the per-item `failed` slot is the contract piece that matters,
  and it is pinned by SC-e03s07-P1-01.
- **Liquidity vintage unclear until implementation** — the RED task pins the
  answer from openapi.json and applies the withholding rule if live-only.
- **"Absent from universe" misread as "invalid ticker"** — the markdown names
  the lake's universe explicitly ("not in the augury tradeable universe as of
  <date>") so agents don't conflate it with a bad symbol.
