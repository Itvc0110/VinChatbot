# Phase 5E — Security P0 + hardening (deferred-backlog Track A)

**Trial.** Work the Track-A items from the deferred-items plan (`pre-personalization-risk-register.md`).
Audit-first: several register items turned out **already fixed** by later PRs, so only the genuinely-open
ones were changed. Hard rule kept: never make a legit student turn fail (precision > recall).

## Audit — already done (no change)
- **A1** `/ingest/run`, `/ingest/upload`, `/ingest/preview`, `GET /sources` already require
  `require_roles("global_admin","institute_admin","staff")` in `routes_ingest.py` (register pre-dated it).
- **A6-session**: `AuthRepository.get_user_by_session_token_hash` already rejects any non-`active` user on
  EVERY request (`status != "active" → None`), so suspended/inactive users can't use a lingering session.
- **PII trace masking** already existed (`langfuse_mask` recurses span input/output → `scrub_pii`, wired via
  Langfuse `mask=`); only a student-code rule was missing.

## Experiment — changes shipped
- **A2 login brute-force** (`routes_auth.py`, `ratelimit.py`): per-(email+IP) in-process sliding window;
  counts only FAILED attempts, **peeks before verifying** so a correct login is never throttled; over
  `LOGIN_MAX_ATTEMPTS` (default 8) within `LOGIN_ATTEMPT_WINDOW_SECONDS` (300) → **429 + Retry-After**, and a
  success clears the counter. New `SlidingWindowRateLimiter.peek_blocked/record/reset_key`.
- **A3 XFF anti-spoof** (`ratelimit.py`): `_client_key` trusts the first `X-Forwarded-For` hop ONLY when the
  socket peer is in `TRUSTED_PROXIES` (default empty → never trust XFF → use the socket peer). Stops a direct
  client spoofing/poisoning its rate-limit key.
- **A4 /chat auth** (`dependencies/auth.py` `get_chat_user`, `routes_chat.py`): Vinnie is auth-only, so
  `/chat` + `/chat/stream` now require a verified session server-side, gated by `REQUIRE_AUTH_FOR_CHAT`
  (default ON; flip off for a public general-RAG mode).
- **A6 dedupe guardrail** (`routes_chat._resolve_chat`): removed the route-level `resolve_guardrail_decision`
  pre-call — guardrails now run ONCE inside `VinUniAgentService.chat` (which also builds the conversational/
  guardrail responses AND logs the guard-handled turn). A blocked request still never reaches the LLM graph.
  - **Cost (measured, before→after):** guardrail evals **2→1 per turn** (confirmed via a call counter).
    Rule-tier latency ≈ 9–81 µs/eval (greeting 9, injection 16, gray 57, policy-Q 81). So every ALLOWED
    turn saves ~40–80 µs CPU; **gray allowed turns additionally drop 1 safety-guard + 1 LLM-guard REMOTE
    call** (~hundreds of ms + the per-call `$` on qwen-2.5-7b) — the expensive part, halved. Blocked turns
    unchanged (old already short-circuited at 1 eval). No behavior change.
- **A6 PII student-code** (`observability.scrub_pii`): added `_STUDENT_CODE_RE` (`D\d{4}[A-Z]{2,6}\d{3}`) →
  `[student-id]`. **Traces/logs only** — never the live model input or the answer; the student still sees
  their own email/advisor-email/student-ID/GPA in the reply. (Names left as-is per the user's choice.)

## A5 — analyzed, intentionally NOT changed
The plan proposed making the guard/audit fail-CLOSED. Case-by-case analysis: for the gray-scope path the
resolver **already** falls back to the deterministic rule verdict for blockable cases (`out_of_scope` →
refuse); the only fail-open is `needs_scope_router`/safety-guard-outage → allow, which is **deliberate** —
failing closed there would refuse legit, ambiguous VinUni questions during a provider outage, violating the
"never decline a legit question" rule (and the cheap rule tier already runs first to catch obvious bad input).
**Decision: no change** (a fail-closed scope guard would itself be the regression). Documented here.

## Progress — verification
- `ruff` clean; **full suite 715 passed** (+ new: login lockout / success-doesn't-count; XFF trust;
  `get_chat_user` auth on/off; `scrub_pii` masks email/phone/student-code but keeps course codes + amounts).
- Updated `test_chat_route.py` (guardrail now blocks inside the agent without running the LLM graph) and
  `test_chat_persistence.py` (anon-serialization test disables `REQUIRE_AUTH_FOR_CHAT`).
- `.env.example` to update (teammate): `TRUSTED_PROXIES`, `LOGIN_MAX_ATTEMPTS`,
  `LOGIN_ATTEMPT_WINDOW_SECONDS`, `REQUIRE_AUTH_FOR_CHAT`.
- Remaining backlog (data-model, forms, output-guard A/B, RAG correctness, infra, frontend, D-roadmap) is in
  the plan; Track B (personalization polish) follows next.
