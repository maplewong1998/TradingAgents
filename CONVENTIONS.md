# Conventions

Project-wide rules for every AI agent and human working in TradingAgents.
Read this before any git or GitHub operation.

> Sections marked **§ bigpowers doctrine** are the standard lifecycle rules and MUST NOT be
> weakened. Sections marked **§ TradingAgents** are derived from this codebase as it exists
> today (see `specs/tech-architecture/tech-stack.md`). Where a rule below is not yet
> mechanically enforced, it says so.

---

## Conventional Commits & Semantic Versioning

All changes MUST follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
Versions follow [SemVer 2.0.0](https://semver.org/).

### Commit message format

`<type>(<scope>): <description>` — the space after the colon is MANDATORY.

### Types & version bumps

| Type | Bump |
|------|------|
| `feat` | Minor (`x.Y.z`) |
| `fix`, `perf` | Patch (`x.y.Z`) |
| `docs`, `chore`, `style`, `refactor`, `test` | None (unless breaking) |
| `BREAKING CHANGE:` or `!` after type | Major (`X.y.z`) |

**The real version is never hand-tracked.** Semantic-release decides it at merge.
`specs/release-plan.yaml` → `release.version` is a non-authoritative mirror; `git tag` is the authority.

**Scope vocabulary for this repo:** `cli`, `graph`, `agents`, `dataflows`, `llm_clients`, `portfolio`, `reporting`, `tests`, `specs`.

```bash
# Good
feat(dataflows): add tiingo as a core_stock_apis vendor
fix(agents): treat an unparseable decision as REVIEW, not Hold

# Bad — missing space, no scope, vague
fix:stuff
```

**Git attribution:** NEVER add `Co-authored-by` or any trailer attributing code to an AI agent. Commits MUST appear authored solely by the human user.

---

## GitHub & Git Operations

- **No direct work on `main`.** Every task starts on a feature branch or worktree via `kickoff-branch`.
- **Integrate (team default):** `gh pr create` + `gh pr merge --squash` via `release-branch`.
- **Integrate (solo):** with `workflow_mode: solo-git` in `specs/state.yaml`, ship via `bash scripts/land-branch.sh <branch> "<conventional message>"` after release gates.
- Use `gh run view` / `gh run watch` for CI status. Verify with `gh auth status` first.
- **NEVER** call the GitHub REST API directly (curl/fetch) — use `gh`.
- **NEVER** create GitHub issues from an automated workflow. Write a local `.md` file in `specs/` instead.
- Pushing a feature branch for backup/CI is allowed. Never push directly to `main`.

### Pre-merge verification gates

```bash
bash scripts/run-verification-gates.sh    # blocks merge on failure
```

---

## Agent Workflow Mandates — § bigpowers doctrine

**AGENTS MUST NEVER BYPASS THE BIGPOWERS WORKFLOW.**

- **No direct coding.** A directive like "build feature X" or "fix the bug" MUST NOT be executed by writing code directly. Route through the skills.
- **Required routing.**
  - No context → `survey-context`.
  - Before feature code → `plan-work` (tasks with `verify:` in `specs/epics/`). The planning spine is `scope-work` → `slice-tasks` → `plan-work`.
  - Implement via `develop-tdd` or `execute-plan`.
  - Bug reports → `investigate-bug` before any fix.
- **Verification mandate.** Every story ends with a step-by-step manual verification script handed to the user. Wait for behavioral confirmation (UAT) before declaring a story done.
- **No plan, no code.** Code generation without a corresponding plan in `specs/` is forbidden.
- **Traceability mandate.** Every story MUST have ≥1 `story: eNNsNN` tag in its implementing code or test file. Enforced by `bash scripts/trace-stories.sh --strict` in CI.
- **Scenario IDs.** When `specs/tech-architecture/eNN-TEST_PLAN_LATEST.md` exists, critical-path scenarios use `SC-eNNsYY-P{0|1|2|3}-NN` and are referenced in tests as `# scenario: SC-eNNsYY-P0-NN` alongside the `# story:` tag.
- **Stream continuity.** When writing large files, output continuously in ~200-line chunks. Do not go silent.

---

## Always Green / Shift Left — § bigpowers doctrine

**Always Green** means Preflight and CI are green before any forward work — not "green enough for this task."

**Shift Left (1-10-100):** a defect costs ~1× to fix in development, 10× in integration, 100× in production. Fixing a red gate now is cheaper than debugging it in production.

- **Preflight** — this project's full local verification stack:
  ```bash
  pytest -q && ruff check .
  ```
  Preflight MUST be green before kickoff, develop, or verify advances.
  Runs inside the project virtualenv (`.venv/`). Provision it once with
  `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"`;
  `pytest` is a dev extra and is not on the system Python.
- **CI green** — when a PR is open, `gh pr checks` MUST pass before merge. CI runs `pytest -q` on Python 3.10–3.13, a clean-install import smoke test, and `ruff check .`.

### Test commands

```bash
pytest -q                       # full suite
pytest -q -m unit               # fast isolated tests only
pytest -q tests/test_rating_integrity.py    # one file
```

Markers are strict (`--strict-markers`): `unit`, `integration`, `smoke`. Only apply `integration` to tests that genuinely need an external service.

---

## Discovered Defects — § bigpowers doctrine

Any **reproducible gate failure** hit during unrelated work is a discovered defect, not background noise.

**fix-or-log ladder (mandatory):**

1. **`quick-fix`** — trivial, data-only, or single-file fixes inside guardrails.
2. **`fix-bug`** — when quick-fix aborts, or the failure needs investigation (`specs/bugs/BUG-*.md` + TDD).
3. **Log** — only when reproduction is genuinely blocked; write a BUG spec and stop forward work until triaged.

Discovered fixes ship in the **same PR** as the original work but as **separate commits**. Never narrate a failure and continue.

**Hard block:** red Preflight or red CI blocks `kickoff-branch`, `develop-tdd`, and `verify-work` until fix-or-log produces green.

---

## Risk Tiers (Effective Rule Matrix) — § bigpowers doctrine

### P0 — Critical (never violate)

- **[always-green]** Preflight and CI green before forward work.
- **[no-direct-coding]** Feature work routed through bigpowers skills with a plan in `specs/`.
- **[traceability]** Every story has ≥1 `story: eNNsNN` tag in code or tests.
- **[no-generated-edits]** Never edit generated artifacts directly.

### P1 — High (fix before merge)

- **[conventional-commits]** Conventional Commits; semantic-release owns version bumps.
- **[verify-per-story]** Every story/task has runnable `verify:` commands.
- **[test-on-change]** New functions and bug fixes include tests; regressions get regression tests.
- **[branch-protection]** No direct work on `main`.

### P2 — Medium (same epic or next)

- **[file-size-cap]** Source files under 300 lines unless listed in § File-Size Exceptions.
- **[handoff-signaling]** Critical-path skills write `handoff.next_skill` to `specs/state.yaml`.
- **[plan-tests-waiver]** P2/P3-dominant epics may set `test_plan: waived` in `specs/state.yaml`.

### P3 — Low (best effort)

- **[boy-scout]** Leave touched files at least as clean as found.
- **[terse-when-heavy]** Switch to `terse-mode` past ~20 turns of context.

### Banned dismissive phrases

Agents MUST NOT use these (or close paraphrases) to ignore a reproducible failure:

| Banned phrase | Required behavior instead |
|---------------|---------------------------|
| "pre-existing" | Run fix-or-log; if truly unrelated, prove it with a passing repro after revert |
| "unrelated to this session" | Session boundaries do not waive green gates |
| "not introduced by my changes" | Bisect or fix anyway — solo-default owns the whole tree |
| "out of scope" (to ignore a red gate) | Invoke `quick-fix` or `fix-bug`; scope never overrides Always Green |

---

## Code Style — § TradingAgents

Ruff config lives in `pyproject.toml` and is the authority:

- `select = ["E", "W", "F", "I", "B", "UP", "C4", "SIM"]`, `ignore = ["E501"]`, line length 100, `target-version = "py310"`.
- `"**/__init__.py" = ["F401"]` — re-exports are intentional.
- `combine-as-imports = true` for isort.
- **`ruff format` is deliberately NOT adopted yet** — the config comment defers it until the open-PR backlog clears, to avoid mass merge conflicts. Do NOT run repo-wide formatting.
- CI lints the **whole repo** with strict select. Keep `ruff check .` clean.

Python style observed throughout:

- `from __future__ import annotations` and PEP 604 unions (`str | None`).
- Module-level `logger = logging.getLogger(__name__)`.
- Pydantic `BaseModel` at every LLM boundary (`agents/schemas.py`, `portfolio.py`).
- Agent nodes are closures returned by `create_*` factories, not classes. Match that shape.
- Prefer the existing seam: a new data vendor raises the `VendorError` taxonomy and adds a `VENDOR_METHODS` entry — it does **not** add a new `except` clause in `route_to_vendor`.

## Comments — § TradingAgents

This is the codebase's strongest convention. Preserve it.

- **Comments explain WHY, not what.** Cite the issue number that motivated the decision: `# a decision nobody can read is not a Hold (#1170)`.
- Docstrings state the contract **and the failure mode** — especially for anything that can return a sentinel, fall back, or fail open.
- A comment that restates the code MUST be deleted. A comment that records a rejected alternative MUST be kept.

## Tests (F.I.R.S.T) — § TradingAgents

- **Autouse fixtures in `tests/conftest.py` are load-bearing. Do not remove or weaken them:**
  - `_dummy_api_keys` injects placeholder keys for 14 providers so keyless CI cannot hang.
  - `_isolate_config` deep-copies `DEFAULT_CONFIG` around every test because `set_config` **merges** and would otherwise leak vendor routing between tests.
- Tests are named behaviorally and reference the issue number: `test_unparseable_signal_is_review_not_silent_hold`.
- Mock at the boundary (`requests`, provider clients), never mock the thing under test.
- **No coverage tool is configured.** Any large refactor MUST establish a coverage baseline first (see `specs/tech-architecture/TEST_PLAN_LATEST.md`).

## Defensive Code — § TradingAgents

Categories that apply to this project (confirmed against the code):

| Category | Where it applies | Existing mechanism |
|----------|------------------|--------------------|
| **Retry** | LLM calls | `llm_max_retries` config, forwarded per provider (default stays provider's 2, #1091) |
| **Timeout** | Vendor HTTP | Per-vendor request timeouts in `dataflows/*` |
| **Graceful degradation** | Structured output, identity resolution | `invoke_structured_or_freetext` falls back to free text; identity lookup is fail-open |
| **Fail-safe sentinel** | Vendor data, rating parse | `NoMarketDataError` → NO_DATA sentinel; unparseable rating → `REVIEW`, never a fabricated `Hold` |
| **Circuit breaker** | *not implemented* | Not present. Do not claim otherwise. |
| **Rate limit** | *handled by reaction, not prevention* | `VendorRateLimitError` causes skip-to-next-vendor; there is no backoff/throttle |

**Rule:** never claim a defensive category the code does not have. If a plan needs one of the missing categories, that is a design decision requiring an ADR.

## Dependencies — § TradingAgents

- Runtime deps are pinned with floors in `pyproject.toml`. Adding one requires a `research-first` pass and a note on why an existing dep cannot do it.
- Optional integrations MUST be extras (`[project.optional-dependencies]`), with a helpful error when the extra is absent — follow the `bedrock` pattern (`langchain-aws`) and its `test_helpful_error_when_langchain_aws_absent` test.
- CI's clean-install smoke job catches undeclared runtime imports (e.g. #994 `python-dotenv`). A new top-level import without a declared dep will fail CI.

## Structure — § TradingAgents

- `tradingagents/` is the library; `cli/` is presentation. **The library MUST NOT import from `cli/`** (check with `bash scripts/check-import-boundaries.sh`).
- Business logic belongs in agents/prompts; **all external I/O goes through `dataflows/interface.route_to_vendor`**. No agent node calls a vendor SDK directly.
- `specs/` holds all planning output. `results/` is generated and gitignored.
- Never edit `scripts/` — it is a symlink to the global bigpowers install.

## Logging — § TradingAgents

- Stdlib `logging` with a module-level logger. No print statements in library code (`cli/` uses Rich for user output).
- **Never log API keys or full request payloads.** Vendors log failures, not credentials.
- Log warnings on every fallback path — a silent fallback is a bug (#989). Include the vendor/agent name and the reason.

## File-Size Exceptions — § TradingAgents

The P2 cap is 300 lines. These files exceed it and are documented exceptions:

| File | Lines | Status |
|------|-------|--------|
| `cli/main.py` | 1460 | Exception — refactor candidate, see `specs/tech-architecture/REFACTOR_LATEST.md` |
| `cli/utils.py` | 718 | Exception |
| `tradingagents/graph/trading_graph.py` | 672 | Exception — facade |
| `tradingagents/dataflows/y_finance.py` | 527 | Exception |
| `tradingagents/agents/schemas.py` | 379 | Exception |
| `tradingagents/llm_clients/openai_client.py` | 338 | Exception |
| `tradingagents/agents/utils/memory.py` | 337 | Exception |
| `tradingagents/dataflows/stockstats_utils.py` | 330 | Exception |

**These files MUST NOT grow further.** Extract before adding. Removing an entry from this table is the goal.

## specs/ — All Planning Output Goes Here — § bigpowers doctrine

| Layer | File | Answers |
|-------|------|---------|
| Session | `specs/state.yaml` | Active flow, epic/bug, git, `handoff.next_skill`, metrics |
| Release index | `specs/release-plan.yaml` | Epic list + WSJF (**not** story status) |
| Progress | `specs/execution-status.yaml` | Flat `e01` / `e01s01` keys — sole SoT for story state |
| Cycle time | `specs/metrics/cycle-times.yaml` | Per-story BCPs, start/end, cycle minutes |
| Stack | `specs/tech-architecture/tech-stack.md` | Stack, architecture, conventions, signals |

- **Do NOT** put story status in `release-plan.yaml`.
- **Do NOT** duplicate the release plan inside `state.yaml`.
- Validate layout with `bash scripts/validate-specs-yaml.sh`.
- Patch runtime keys with `bash scripts/bp-yaml-set.sh specs/state.yaml handoff.next_skill plan-work`.

`state.yaml` carries top-level `workflow_mode` (`team-pr` | `solo-git`) — the canonical integrate-mode signal for all skills.

### BCP accounting mandate

Every story in `specs/release-plan.yaml` MUST have a `bcps:` field set before implementation begins. BCP is a **story-level** pre-build size; per-task `[BCP N]` annotations are not part of the method. After landing, `release-branch` appends `bcp_per_hour = story_bcps / cycle_minutes * 60` to `specs/metrics/cycle-times.yaml`.

### Timestamps & handoff

- `survey-context` writes `metrics.story_start` (ISO 8601) to `specs/state.yaml` at story start.
- `release-branch` writes `metrics.story_end`, `metrics.cycle_minutes`, `metrics.bcp_per_hour`.
- Every critical-path skill (survey-context, plan-tests, plan-work, kickoff-branch, develop-tdd, verify-work, audit-code, commit-message, release-branch) MUST write `handoff.next_skill` as its last action. Agents MUST read it before asking "what's next?".

Missing timestamps are a gate violation — do not advance past `release-branch` without them.
