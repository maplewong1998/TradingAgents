# Story e03s02: PIT fundamentals pack — fundamentals + three statements

<!-- story: e03s02 -->

**type:** feat
**risk:** P1 (core feature logic over the proven e03s01 client)
**context:** domain
**bcps:** 3
**status:** passing (e45s06 ledger — all 5 task verifies green)

**Context:** With the vendor core proven by e03s01, this story maps the four
fundamental-data methods onto augury's PIT endpoints — the lake's strongest
advantage over yfinance, whose `Ticker.info` is a present-day snapshot.
`get_fundamentals` reads `/api/v1/fundamentals/{ticker}?as_of=` and the three
statement methods read `/api/v1/financials/{ticker}?as_of=`, splitting rows by
the served `statement` field. Because augury gates reads on
`report_date/period_end/ingested_at <= as_of` (newest restatement per metric),
a backtested run sees exactly what was knowable on the trade date — no
look-ahead, no restatement bleed.

## Zoom-Out Check

| Module touched | Purpose | Callers | Contracts to preserve |
|---|---|---|---|
| `dataflows/augury.py` | Augury lake HTTP vendor | `route_to_vendor` | Method signatures identical to the yfinance impls: `(ticker, curr_date=None)` and `(ticker, freq="quarterly", curr_date=None)` |
| `dataflows/interface.py` | The only vendor seam | `@tool` wrappers | Registration-only: four new `"augury"` keys; no router change |

## Requirements (delta tags, e45s29)

#### ADDED: get_fundamentals via the lake
`get_augury_fundamentals(ticker, curr_date=None)` → `GET
/api/v1/fundamentals/{ticker}` with `as_of=curr_date` (required param). 404 →
`NoMarketDataError` (detail carries the job hint from the e03s01 mapper).
Rendered as the same markdown overview shape agents already consume.

#### ADDED: Statement methods via the lake
`get_augury_balance_sheet / get_augury_cashflow / get_augury_income_statement`
→ `GET /api/v1/financials/{ticker}` with `as_of` and a `fields` whitelist;
rows filtered by `statement` (balance sheet / income / cash flow) and rendered
newest-period-first (the endpoint's stable order: `period_end` descending, then
`statement` ascending, newest restatement per metric — `pit.py:128-156`).
`freq="annual"|"quarterly"` selects rows by period spacing; an empty filtered
result is `NoMarketDataError` with the statement named in `detail`.

## Discovery Mandate (external API, verified)

Verified 2026-09-24 against `~/Repo_Private/augury/openapi.json` +
`src/augury_record/api/routers/v1/pit.py`: `GET /api/v1/fundamentals/{ticker}`
params `ticker*`, `as_of*`; `GET /api/v1/financials/{ticker}` params `ticker*`,
`as_of*`, `fields`, `page`, `page_size` (max 200). `pit.py:4-5`: "financials:
report_date <= as_of AND period_end <= as_of AND ingested_at <= as_of, newest
restatement per metric — no look-ahead past the" [as_of date]. `?fields=` is a
whitelist projection; unknown fields → 422 (validation_error).

## Slopcheck

No new external packages. `requests` **[OK]** — via the e03s01 `_request` helper.

## Steps

1. RED: extend `tests/test_augury_vendor.py` (`# story: e03s02`) — fundamentals
   markdown from a mocked PIT snapshot (as_of forwarded verbatim), statement
   filtering per method (a mixed-statement fixture yields three disjoint
   reports), `freq` annual/quarterly selection by period spacing, 404 →
   `NoMarketDataError` with job-hint detail → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "fundamentals or balance_sheet or cashflow or income_statement" --collect-only`
2. GREEN `get_augury_fundamentals` → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k fundamentals`
3. GREEN the three statement methods with the `statement` filter → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "balance_sheet or cashflow or income_statement"`
4. Register all four methods under `"augury"` in `VENDOR_METHODS`; chain test:
   `"augury,yfinance"` on a 404 falls through per method → verify: `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -k "registration or routing"`
5. Full Preflight → verify: `.venv/bin/python -m pytest -q && ruff check .`

## §17 Acceptance Criteria (Gherkin)

```gherkin
# scenario: SC-e03s02-P1-01
Given chain "augury" for fundamental_data and a lake holding restated financials
When get_income_statement is called with a past curr_date
Then only rows with report_date/period_end/ingested_at <= as_of are rendered and the newest restatement wins per metric

# scenario: SC-e03s02-P1-02
Given chain "augury,yfinance" and augury 404s the ticker
When get_balance_sheet runs
Then yfinance serves and the augury error detail names the POST /data/financials job hint

# scenario: SC-e03s02-P1-03
Given an augury financials page whose statement set excludes cash-flow rows
When get_cashflow runs
Then NoMarketDataError is raised with "cash flow" named in the detail
```

## Verification Script (Step-by-Step, UAT)

1. Run `.venv/bin/python -m pytest -q tests/test_augury_vendor.py -v -k "fundamentals or balance_sheet or cashflow or income_statement"` — all green.
2. Run `.venv/bin/python -m pytest -q` and `ruff check .` — full Preflight green.
3. Optional live smoke (lake up): opt `fundamental_data` into `"augury"` and print a past-dated income statement for a backfilled ticker — values match the lake's PIT read.

## Out of scope

- Indicators/news (e03s03); macro/prediction markets (e03s04); any augury-side
  statement-coverage extension.

## Risks

- **Statement vocabulary mismatch** (lake `statement` labels vs the three TA
  methods) — detected by the mixed-statement fixture test; mapping table lives
  in one place in `augury.py` with a comment citing the lake's field.
- **freq inferred from period spacing misclassifies** an irregular filer —
  detected by the annual/quarterly fixture test; the detail text states the
  inference so agents can see the caveat.
- **Lake coverage gaps read as "no data"** — intended: the sentinel's detail
  names the refresh job rather than fabricating (#1170-class honesty).
