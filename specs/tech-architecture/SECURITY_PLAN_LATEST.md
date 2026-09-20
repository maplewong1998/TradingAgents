# Security Plan — TradingAgents

**Status:** NOT YET PRODUCED — scaffolded by `bigpowers init` on 2026-09-20.
**Produced by:** `security-review` (verify-work Phase 5) or `harden-vps`.
**Threat model per epic:** `specs/security/epics/<id>/THREAT_MODEL.md` (created by `build-epic` step 0) — a HIGH/CRITICAL risk finding adds +2 to that epic's WSJF numerator.

## Known surface (from map-codebase, to be validated)

- **Secrets.** API keys for 14 providers arrive via environment/dotenv, resolved in `tradingagents/llm_clients/api_key_env.py` and `cli/utils.py` (`ensure_api_key`). `.env` is gitignored; `.env.example` and `.env.enterprise.example` ship as templates. Confirm no key is ever logged or written into `results_dir` report trees.
- **Third-party egress.** Vendor modules (`y_finance`, `alpha_vantage_*`, `fred`, `sec_edgar`, `polymarket`, `reddit`, `stocktwits`) make outbound HTTP. `sec_edgar` sets a `User-Agent`; confirm every vendor has a timeout and that redirects/response size are bounded.
- **Prompt injection via retrieved content.** News headlines, Reddit/StockTwits posts, and SEC filing text are injected into agent prompts. This is the highest-risk untrusted-input path in the project and is currently unmitigated by design — it needs an explicit decision, not an assumption.
- **Filesystem writes.** Reports and caches are written under `~/.tradingagents/`. `safe_ticker_component` sanitizes ticker-derived path segments (`dataflows/utils.py`) — verify it covers every path construction site.
- **No network-facing service.** No HTTP server, auth layer, or session handling exists; there is no remote attack surface beyond the CLI itself.
