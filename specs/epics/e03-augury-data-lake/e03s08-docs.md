# Story e03s08: Docs + knowledge refresh (CHANGELOG, .env.example, README, tech-stack, glossary)

<!-- story: e03s08 -->

**type:** docs
**risk:** P3 (documentation only, zero behavioral change)
**context:** domain
**bcps:** 2
**status:** planned (e45s06 ledger — tasks start `failing`, flip only on green verify)

**Context:** The augury integration is opt-in by design (D3), which makes the
docs the feature's front door: if the config snippet and the honest-degradation
contract aren't written down, the capability is undiscoverable. This story
ships the user-facing surface (CHANGELOG, .env.example, README config section)
and refreshes the knowledge base (tech-stack vendor-seam section with
re-measured counts per the house re-measure rule, glossary terms). Mirrors the
e02s03 docs-story precedent.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `CHANGELOG.md`, `.env.example`, `README.md` | User-facing config story | users | Documents only what shipped in e03s01–s07; env var named exactly `AUGURY_BASE_URL` |
| `specs/tech-architecture/tech-stack.md` | Derived architecture truth | all skills | Vendor counts/lists re-measured with grep on the merged tree, never adjusted by hand (house refresh rule) |
| `specs/product/GLOSSARY_LATEST.yaml` | Domain language | specs | New terms: data lake, PIT vintage, signal family, binding gate |

## Requirements (delta tags, e45s29)

#### ADDED: CHANGELOG entry
`feat(dataflows)`: augury vendor (six mapped methods) + four opt-in tool
categories; names the `AUGURY_BASE_URL` surface and the defaults-unchanged
guarantee.

#### ADDED: Configuration docs
`.env.example` gains `AUGURY_BASE_URL` with the localhost:8765 default and the
empty-disables semantics; README config section shows the opt-in
`data_vendors`/`tool_vendors` snippets (e.g. `"core_stock_apis":
"augury,yfinance"`, `"ai_forecast": "augury"`), states that the lake must be
running and backfilled (`POST /data/*` jobs are augury-side), and documents the
NO_DATA / DATA_UNAVAILABLE sentinel contract.

#### ADDED: Knowledge refresh
tech-stack.md vendor seam section lists `augury` and the four new categories
with re-measured counts; glossary gains the four terms above.

## Discovery Mandate (external API, verified)

No external API surface in this story. Documentation targets verified against
the merged code: env-override precedent `TRADINGAGENTS_DEBATE_GATE`
(`default_config.py`), sentinel strings in `dataflows/interface.py`
(`NO_DATA_AVAILABLE`, `DATA_UNAVAILABLE`).

## Slopcheck

No external packages involved.

## Steps

1. CHANGELOG entry → verify: `grep -q "augury" CHANGELOG.md`
2. `.env.example` + README config section (opt-in snippets, lake prerequisite,
   sentinel contract) → verify: `grep -q "AUGURY_BASE_URL" .env.example && grep -q "augury" README.md`
3. tech-stack.md vendor-seam refresh (counts re-measured via grep, cited in the
   story header comment) + GLOSSARY_LATEST.yaml terms → verify: `grep -q "augury" specs/tech-architecture/tech-stack.md && grep -q "signal family" specs/product/GLOSSARY_LATEST.yaml`
4. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s08-P3-01
Given a user with a running lake
When they follow only the README config section
Then they can enable an augury chain and learn the base-URL variable, the backfill prerequisite, and the sentinel contract without reading source

# scenario: SC-e03s08-P3-02
Given the merged tree
When tech-stack.md is re-derived by map-codebase
Then the vendor lists and counts match what the story wrote (no hand-adjusted numbers)
```

## Verification Script (Step-by-Step, UAT)

1. Read the README section end-to-end and follow it cold — an augury chain activates.
2. Run `.venv/bin/python -m pytest -q` and `ruff check .` — green.
3. Diff tech-stack.md vendor counts against `grep -c` on the tree — they match.

## Out of scope

- augury-side documentation; a CLI vendor picker (declined, SCOPE out_of_scope);
  migrating the docs to a wiki (maintain-wiki runs its own ceremony).

## Risks

- **Documenting aspiration instead of shipped behavior** — every snippet is
  written against the merged e03s01–s07 code; the UAT follows the README cold.
- **Count drift in tech-stack.md** — the re-measure rule (grep on the tree) is
  the mitigation, per the e02s03 header-comment precedent.
