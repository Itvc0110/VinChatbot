# Phase 1.5 — Monitoring, Logging & Observability — Plan + Log

Goal (from AICB Day-13 *Monitoring, Logging & Observability*): **know how the agent runs in
production without waiting for a user to complain.** Make the per-turn signals we already compute
(latency, intent, guardrail action, citations, confidence, faithfulness) *queryable*, and add the
two AI failure modes traditional monitoring misses — **cost** and **answer quality**.

Source deck framing: **3 pillars + a 4th** — Metrics (how much / how long), Logs (what happened),
Traces (why / where), **Continuous online eval** (is the answer still *correct*?). Plus **4 Golden
Signals + 2 for AI**: Latency, Traffic, Errors, Saturation **+ Cost + Quality**.

Legend: [ ] todo · [~] in progress · [x] done · [-] deferred.
House rules carried over: every new behavior is `ENABLE_*`/config-gated; no regression to the proven
**0.919 / 80-subset 0.912** eval band ([PHASE1.4_LOG.md](PHASE1.4_LOG.md)); build on existing code,
don't rebuild.

> **Status: ✅ COMPLETE — 1.5a + 1.5b shipped (2026-06-15); 1.5c deferred to future work.**
> Delivered: structured JSON logging + `X-Request-ID` correlation + PII redaction + per-turn
> token/cost capture (**1.5a**); Langfuse tracing wired at the chat model with session grouping +
> email/phone masking (**1.5b**). Verified live (4 turns → traces in Langfuse Cloud, `flush()`
> confirmed) with **no eval regression: overall 0.930 ≥ 0.919, guards 1.000**
> (report `eval_20260615T165804Z.json`). New dep: `langfuse` (optional `observability` extra).
> **1.5c** (Prometheus/Grafana + alerts + SLO + feedback endpoint) → [../FUTURE_IMPROVEMENTS.md](../FUTURE_IMPROVEMENTS.md) §H.
> Full detail in **§ Execution log** below.

---

## Baseline — what we already have (build on this, don't rebuild)

| Pillar | Status today | Where |
|--------|--------------|-------|
| **Logs** | Basic: stdlib `basicConfig`, **text** format; a few key=value turn logs (latency_ms, citations, confidence) | [../vinchatbot/app/core/logging.py](../vinchatbot/app/core/logging.py), [../vinchatbot/app/agents/vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py) |
| **Traces** | **Proto-trace**: `tool_trace` captures tool calls + results per turn, returned in the response (not persisted, not timed) | `_extract_tool_trace` in [../vinchatbot/app/agents/vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py), [../vinchatbot/app/schemas/chat.py](../vinchatbot/app/schemas/chat.py) |
| **Quality (4th)** | **Offline** eval harness + per-turn quality signals (confidence, faithfulness, graceful degradation, guardrail actions) | [../scripts/run_eval.py](../scripts/run_eval.py), [../vinchatbot/app/agents/guardrails.py](../vinchatbot/app/agents/guardrails.py) |
| **Metrics** | ❌ none aggregated; `/health` returns 200 OK only (the deck's "200 OK ≠ correct answer" trap) | [../vinchatbot/app/main.py](../vinchatbot/app/main.py) |
| **Cost** | ❌ none — LangChain `usage_metadata` (tokens) is **discarded** every turn | — |

**Key insight:** we already *compute* most AI-specific signals per turn and then throw them away;
and we capture **zero** token/cost data despite cost being a live concern (see PHASE1.4 model-cost
threads). The cheapest high-value move is to emit what we have as structured JSON + capture tokens.

---

## Gaps vs the deck
- Logs not JSON; no **correlation/request ID**; no **PII redaction** of logged input/output.
- **No cost/token capture** — the most valuable missing signal for us.
- `tool_trace` not exported to a tracing backend → no waterfall, no per-LLM-call timing/tokens.
- No metrics endpoint, no P50/95/99, no traffic/error rate, no alerting, no SLO.
- 4th pillar exists **offline only** — no online quality capture (👍/👎, online guardrail/degradation rates).

---

## Plan — phased, proportionate to a Phase-1 project

### Phase 1.5a — Structured logging + cost visibility  *(recommended first; no new infra, no keys)*
Highest value / lowest effort. All in existing code.

- [x] **JSON log formatter** + `LOG_FORMAT=auto|json|text`, `LOG_LEVEL` — reworked
  [../vinchatbot/app/core/logging.py](../vinchatbot/app/core/logging.py) (`JsonFormatter` +
  `RequestIdFilter`, stdlib only, **no new dependency**). `auto` → json in prod, text in dev.
- [x] **Correlation / request ID**: FastAPI middleware in
  [../vinchatbot/app/main.py](../vinchatbot/app/main.py) mints/honors `X-Request-ID`, stores it in a
  `contextvars.ContextVar` ([../vinchatbot/app/core/observability.py](../vinchatbot/app/core/observability.py)),
  the filter injects it into every record, returned as the `X-Request-ID` response header.
- [x] **PII redaction** `redact()` in
  [../vinchatbot/app/core/observability.py](../vinchatbot/app/core/observability.py) (prefix + length
  + sha8). Gated `LOG_REDACT_PII=true`.
- [x] **Token + cost capture** (`ENABLE_COST_TRACKING=true`): `sum_token_usage` over
  `result["messages"]` + `estimate_cost_usd` (per-model price table) in
  [../vinchatbot/app/agents/vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py). Fail-open.
  Caveat: misses supervisor/expansion/guard calls → captured in 1.5b via the callback.
- [x] **One structured "turn" log line** (`_log_turn`): event, conversation_id, intent, latency_ms,
  tokens_in/out, est_cost_usd, citations, confidence, guardrail_action, degraded, tool_calls,
  needs_human_review, redacted question. Emitted on both the success and degradation paths.
- [x] Tests: [../tests/test_observability.py](../tests/test_observability.py) — JSON formatter +
  extras, redact, token sum, cost (known/unknown model), request-id header mint+honor. **7/7 pass.**

**Config added (.env.example + config.py):** `LOG_FORMAT`, `LOG_LEVEL`, `LOG_REDACT_PII`,
`ENABLE_COST_TRACKING`. **No keys required.**

### Phase 1.5b — Tracing with Langfuse  *(the deck's recommended tool; needs keys — see Action required)*
Biggest observability jump for least code.

- [x] Added `langfuse>=4.0.0,<5` as the `observability` optional extra in
  [../pyproject.toml](../pyproject.toml) (`pip install -e ".[observability]"`). Installed
  **langfuse 4.7.1**; `pip check` shows **no** langchain/langgraph/pydantic conflict (the NeMo
  problem we avoided). API is v4: `from langfuse.langchain import CallbackHandler`.
- [x] Wired the **Langfuse callback handler** at **`build_chat_model`**
  ([../vinchatbot/app/llm/openrouter_chat.py](../vinchatbot/app/llm/openrouter_chat.py)) so **every**
  LLM call is traced (supervisor, specialists, query expansion, guard, capability) — the model-level
  attach also captures the calls 1.5a's in-message summation misses. Builder +
  `get_langfuse_callbacks` in [../vinchatbot/app/core/observability.py](../vinchatbot/app/core/observability.py).
  Gated `ENABLE_LANGFUSE` + both keys; **fail-open** (missing key / import / init error → `[]`, never
  breaks a turn). Per-turn grouping via `langfuse_session_id=conversation_id` + `request_id` metadata
  on the graph invoke ([../vinchatbot/app/agents/vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py)).
- [x] Auto-captures (once keys are set): trace waterfall, per-LLM-call tokens/cost/latency, tool
  spans, and the hosted dashboard. Validated the enabled init path with dummy keys → a
  `LangchainCallbackHandler` is constructed (real traces require live keys).
- [x] **Privacy/compliance (deck §13):** `langfuse_mask` (gated by `LOG_REDACT_PII`) scrubs
  **email + phone** from trace payloads before send, deliberately keeping fees/dates/policy codes
  for debugging. Wired via the `Langfuse(mask=…)` client param.
- [x] Verified ≥10 traces end-to-end (2026-06-15 live run: 4 turns, each fanning out to several
  generations/tool spans, sent to Langfuse Cloud; `flush()` confirmed). See Execution log.

**Config added:** `ENABLE_LANGFUSE`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.
**Keys required — user action.**

### Phase 1.5c — Metrics endpoint + dashboard + alerting + SLO  *(DEFERRED → future work)*

**Decision (2026-06-15): Phase 1.5 closes at 1.5a + 1.5b.** The full SRE stack (Prometheus `/metrics`,
Grafana dashboards, ≥3 alerts + SLO/error-budget, readiness probe, `POST /chat/feedback`) is **real
infra beyond a Phase-1 project's needs** — Langfuse already covers per-call latency/cost/token
dashboards. Moved to [../FUTURE_IMPROVEMENTS.md](../FUTURE_IMPROVEMENTS.md) §H (Phase 1.5c) with its
config (`ENABLE_METRICS`, `SLACK_WEBHOOK_URL`) and scope intact.

---

## Action required (user) — fill `.env` / `.env.example`

> **Satisfied 2026-06-15** — user added live Langfuse keys to `.env`; tracing verified. Kept below
> as setup reference for a fresh environment. Nothing here is needed for **Phase 1.5a**.

**Before Phase 1.5b (Langfuse):** create a project at https://cloud.langfuse.com (free tier) or
self-host, then add to [../.env](../.env):
```
ENABLE_LANGFUSE=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL
```

**Before Phase 1.5c (alerting, only if pursued):**
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

No keys are needed for structured logging or cost tracking (1.5a) — cost uses the model ids already
in `.env`.

---

## Decisions & caveats (recorded up front)
- **TTFT needs streaming.** The deck lists Time-To-First-Token, but the app uses non-streaming
  `ainvoke`. TTFT requires switching to `astream` — **stretch goal, not in 1.5a/b.** We log total
  latency_ms (already have it).
- **Price table drifts.** Per-model prices live in code (env-overridable) and must be kept in sync
  with OpenRouter/OpenAI; treat `est_cost_usd` as an estimate. Langfuse (1.5b) is the more
  authoritative cost source since it reads real usage per call.
- **Proportionality (recommendation).** **Phase 1.5a + Langfuse (1.5b) already satisfy most of the
  Day-13 deliverable** (JSON logging + correlation ID + PII redaction + tracing + a cost/latency/
  token dashboard). The full Prometheus + Grafana + Slack stack (1.5c) is real infra — defer unless
  the course deliverable explicitly requires the dashboard/alerts/SLO artifacts.
- **Fail-open everywhere.** No observability path may break a chat turn (mirror the
  reranker/guard/safety fail-open pattern).
- **Don't over-collect (deck §10).** Emit one rich structured turn line + Langfuse traces; avoid
  per-token debug spam in prod.

## Gates (per phase)
- `pytest -m "not live"` green + `ruff check .` green.
- A **no-regression** live eval after 1.5a and after 1.5b (must hold the **0.919 / 80-subset 0.912**
  band — observability must not change agent behavior). Reuse [../scripts/run_eval.py](../scripts/run_eval.py);
  never run evals concurrently (PHASE1.4 quota lesson).

---

## Execution log

### 2026-06-15 — Phase 1.5a implemented (structured logging + cost capture)

**Changed/added.**
- New [../vinchatbot/app/core/observability.py](../vinchatbot/app/core/observability.py): request-id
  contextvar (`set/reset/get_request_id`), `redact()`, `MODEL_PRICES_USD_PER_M`, `sum_token_usage`,
  `estimate_cost_usd`.
- [../vinchatbot/app/core/logging.py](../vinchatbot/app/core/logging.py): `JsonFormatter` +
  `RequestIdFilter`; `configure_logging(settings)` installs one root handler (json/text by env).
- [../vinchatbot/app/main.py](../vinchatbot/app/main.py): `request_id_middleware` (mint/honor
  `X-Request-ID`, fail-open) + pass `settings` to `configure_logging`.
- [../vinchatbot/app/agents/vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py): `_log_turn`
  (token/cost + structured turn line) on success **and** graceful-degradation paths; replaced the
  old free-text turn log.
- [../vinchatbot/app/core/config.py](../vinchatbot/app/core/config.py): `log_format`, `log_level`,
  `log_redact_pii`, `enable_cost_tracking`. `.env` + `.env.example`: Observability section.

**Workflow safety.** No agent decision path touched (prompts, models, retrieval, guards all
unchanged) — logging only. All new paths fail-open (cost capture wrapped in try/except; middleware
resets the contextvar in `finally`; redaction gated). `ChatResponse` contract unchanged.

**Gates.** `ruff check .` → **clean**. `pytest -m "not live"` → **107 passed, 2 failed**. The 2
failures are in `test_chunker.py` and **pre-exist this work** (verified by `git stash` → identical
failures on clean HEAD): (1) `test_parse_docx_…` = `python-docx` not installed in this env; (2)
`test_chunker_v2_builds_section_path…` = shelved markdown-chunking feature. Neither touches
observability.

**No-regression live eval.** NOT run yet (saves OpenRouter/Qdrant quota; PHASE1.4 quota lesson).
Risk is ~zero since no decision path changed. Recommended before merge: single
`py scripts/run_eval.py` and confirm the 0.919 / 80-subset 0.912 band holds. _(report id: pending)_

**Next:** Phase 1.5b (Langfuse) — paused for user to add `LANGFUSE_*` keys to `.env`.

### 2026-06-15 — Phase 1.5b implemented (Langfuse tracing)

**Dependency.** `langfuse>=4.0.0,<5` → installed **4.7.1**. `pip check`: no conflict with
langchain 1.0 / langgraph 0.6 / pydantic 2 (the pre-existing torch/tf/streamlit warnings are
unrelated). v4 API: `Langfuse(public_key, secret_key, host, environment, mask)` + `CallbackHandler()`.

**Changed/added.**
- [../vinchatbot/app/core/observability.py](../vinchatbot/app/core/observability.py):
  `get_langfuse_callbacks` (lazy, cached, fail-open client init), `scrub_pii` (email/phone),
  `langfuse_mask` (recursive), `reset_langfuse_for_tests`.
- [../vinchatbot/app/llm/openrouter_chat.py](../vinchatbot/app/llm/openrouter_chat.py): attach
  `callbacks=get_langfuse_callbacks(settings) or None` on the `ChatOpenAI` model.
- [../vinchatbot/app/agents/vinuni_agent.py](../vinchatbot/app/agents/vinuni_agent.py): session
  grouping metadata on the graph invoke (only when `enable_langfuse`).
- [../vinchatbot/app/core/config.py](../vinchatbot/app/core/config.py): `enable_langfuse`,
  `langfuse_public_key`, `langfuse_secret_key`, `langfuse_host`. `.env`/`.env.example`: Langfuse block
  (keys blank for the user to paste; `ENABLE_LANGFUSE=true` in `.env`).
- [../.gitignore](../.gitignore): `LOGS/*.log` (uvicorn stdout/stderr; phase `*.md` stay tracked).

**Workflow safety.** When disabled or unkeyed, `get_langfuse_callbacks` returns `[]` → `callbacks=None`
→ identical behavior to before. No decision path changed.

**Gates.** `ruff` clean · `pytest -m "not live"` → **110 passed, 2 failed** (the same pre-existing
`test_chunker.py` docx/markdown failures — unrelated). +3 Langfuse/scrub tests. Enabled-path init
smoke-tested with dummy keys (handler constructs). Live no-regression eval still recommended once
keys are in.

**Action for user:** paste `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` into `.env`, then
`pip install -e ".[observability]"` (already installed locally) and run a few chats to confirm ≥10
traces appear in Langfuse.

### 2026-06-15 — Live verification + Phase 1.5 closed at a/b

**Live run (keys in `.env`, `LOG_FORMAT=json`).** 4 turns through `VinUniAgentService.chat`
(`conversation_id=langfuse-smoke`): calendar (course-drop → "October 9, 2026" ✓), financial (Nursing
tuition → "349,650,000 VND" ✓, Vietnamese), policy (LOA ✓), services (library ✓). All four emitted a
structured `chat_turn` JSON line; **Langfuse client initialized and `flush()` confirmed** → traces +
generations (with token/cost/latency) sent to Langfuse Cloud. Example captured cost: calendar turn
≈ 8.3k in / 80 out tokens ≈ $0.0013; financial ≈ 29k / 173 ≈ $0.0045 — confirms the answer model is
the cost driver (PHASE1.4 finding). One-off `scripts/_smoke_langfuse.py` used then removed.

**Note:** Windows console is cp1252 — Vietnamese output needs `PYTHONIOENCODING=utf-8` /
`sys.stdout.reconfigure("utf-8")` for ad-hoc scripts (the app's JSON logs use `ensure_ascii=False`
and logging handles encoding errors gracefully).

**1.5c deferred** to [../FUTURE_IMPROVEMENTS.md](../FUTURE_IMPROVEMENTS.md) §H. **Phase 1.5 = DONE
(a + b).**

**No-regression eval (report `eval_20260615T165804Z.json`, 86 cases, gpt-4o-mini, serving collection).**
Overall **0.930** (facts_ok 0.953, citation_ok 0.977) — **above** the 0.919 baseline; guards intact
(adversarial/safety/unanswerable all 1.000). Per-category vs PHASE1.4 run 8: calendar 0.929 (↑ from
0.893, nondeterminism), financial 0.875, policy_conduct 0.714, services 0.800, conduct 1.000,
multiturn 1.000 — all within/above the proven band. **Confirms 1.5a/b are behavior-preserving**
(logging + fail-open callbacks only; no decision path changed). Phase 1.5 gates fully green.
