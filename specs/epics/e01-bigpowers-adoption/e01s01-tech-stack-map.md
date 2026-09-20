# e01s01 — Derive the tech-stack doc from the codebase

<!-- story: e01s01 -->

**Status:** done — 2026-09-20
**Epic:** e01 Bigpowers Adoption

## Intent

TradingAgents had no `specs/` tree, so every agent session started cold and had to
re-derive the stack, the data flow, and the house conventions by reading source.
This story produced `specs/tech-architecture/tech-stack.md` — the project's
long-term architectural memory — from a cold scan of the code, not from
assumptions.

## Method

`map-codebase` over the existing `.codegraph` index plus targeted reads of
manifests, entry points, and the gray-area modules (error taxonomy, LLM client
factory, structured output, vendor routing, test harness).

## Acceptance

- `specs/tech-architecture/tech-stack.md` exists and states stack, architecture,
  observed conventions, and active signals.
- Every claim traces to a real file in the repo.
- Known gaps are recorded as signals, not smoothed over.

## Verify

```bash
test -s specs/tech-architecture/tech-stack.md && grep -q '^## Signals' specs/tech-architecture/tech-stack.md
```

## Outcome

Delivered. The scan surfaced one structural gap worth an early follow-up: agents
are coupled to analyst factories in `GraphSetup.setup_graph`, and the graph-shape
signature is assembled in three places (`trading_graph._run_signature`,
`checkpointer`, `GraphSetup`). Recorded under § Signals rather than fixed here —
fixing it is product work, not bootstrap.
