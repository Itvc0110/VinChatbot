"""Golden-set evaluation for the Phase 5 PERSONAL tools (authenticated student).

Unlike run_eval.py (anonymous, RAG), this binds a verified student identity (via the same
set_student_identity contextvar the chat route uses) and runs each case through the live
VinUniAgentService, then reports — per case — the DISPATCHER ROUTE (did it go to the personal
specialist?), WHICH TOOLS fired (is the tool-calling well designed?), and answer FACTS.

Requires the app DB (Neon) + OPENROUTER + Qdrant config. Read-only: only reads student data.

Usage:
    py scripts/run_eval_personal.py [--email student.cs.demo@vinuni.edu.vn] [--limit N] [--id <case-id>]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":  # psycopg async needs the selector loop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # The report prints Vietnamese; the default Windows console codec (cp1252) cannot encode it and
    # crashes mid-run. Force UTF-8 stdout so the eval completes.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from vinchatbot.app.agents.guardrails import normalize_for_matching  # noqa: E402
from vinchatbot.app.agents.vinuni_agent import VinUniAgentService  # noqa: E402
from vinchatbot.app.core.config import get_settings  # noqa: E402
from vinchatbot.app.core.observability import (  # noqa: E402
    reset_student_identity,
    set_student_identity,
)
from vinchatbot.app.db.connection import (  # noqa: E402
    close_app_db_pool,
    get_app_db_pool,
    open_app_db_pool,
    open_readonly_app_db_pool,
)
from vinchatbot.app.schemas.chat import ChatRequest  # noqa: E402

PERSONAL_TOOLS = {
    "get_my_profile", "get_my_academic_standing", "get_my_schedule", "get_my_courses",
    "get_my_transcript", "get_my_deadlines", "get_my_curriculum_progress",
    "get_my_course_eligibility", "project_gpa_for_target",
}

_REFUSAL_ACTIONS = {
    "prompt_injection", "restricted_data", "abusive_language", "out_of_scope", "out_of_scope_task",
    "graceful_degradation",
}
_DECLINE_MARKERS = (
    "outside the scope", "out of scope", "ngoai pham vi", "khong the giup", "cannot help",
    "can't help", "i cannot", "i can't", "i am unable", "i'm unable", "chua tim thay",
    "khong ho tro", "khong nam trong pham vi",
)


def _is_declined(response) -> bool:
    """True if the turn was refused/declined (guardrail refusal, graceful-degradation, or a decline
    phrase in the answer) — used to score out-of-scope-task cases (expect_route='refuse')."""
    for entry in response.tool_trace:
        if isinstance(entry, dict) and entry.get("action") in _REFUSAL_ACTIONS:
            return True
    norm = normalize_for_matching(response.answer)
    return any(m in norm for m in _DECLINE_MARKERS)


def _fact_ok(answer_norm: str, fact: str) -> bool:
    if "|" in fact:
        return any(_fact_ok(answer_norm, a) for a in fact.split("|") if a.strip())
    tokens = re.findall(r"\w+", normalize_for_matching(fact))
    return all(t in answer_norm for t in tokens) if tokens else normalize_for_matching(fact) in answer_norm


def _tools_from_trace(response) -> tuple[list[str], list[dict]]:
    """Return (ordered tool names called, [{name,args}] from tool_calls) extracted from the trace."""
    names: list[str] = []
    calls: list[dict] = []
    for entry in response.tool_trace:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "tool_calls":
            for call in entry.get("calls") or []:
                nm = call.get("name") if isinstance(call, dict) else None
                if nm:
                    calls.append({"name": nm, "args": call.get("args")})
        if entry.get("type") == "tool_result" and entry.get("name"):
            names.append(entry["name"])
    # union of result names + call names, order-preserving
    for c in calls:
        if c["name"] not in names:
            names.append(c["name"])
    return names, calls


async def _lookup_identity(email: str):
    pool = get_app_db_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "select sp.id as profile_id, sp.user_id from student_profiles sp "
            "join users u on u.id = sp.user_id where lower(u.email) = lower(%s)",
            (email,),
        )
        row = await cur.fetchone()
    if row is None:
        raise SystemExit(f"No student profile for {email}")
    return row["profile_id"], row["user_id"]


async def _run(cases: list[dict], email: str) -> list[dict]:
    settings = get_settings()
    await open_app_db_pool(settings)
    await open_readonly_app_db_pool(settings)
    profile_id, user_id = await _lookup_identity(email)
    service = VinUniAgentService()  # built AFTER pools open -> personal specialist wired

    rows: list[dict] = []
    for case in cases:
        cid = case["id"]
        set_student_identity(student_profile_id=profile_id, user_id=user_id)
        try:
            response = await service.chat(
                ChatRequest(message=case["question"], conversation_id=f"eval-personal-{cid}")
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"id": cid, "error": f"{type(exc).__name__}: {exc}"})
            reset_student_identity()
            continue
        finally:
            reset_student_identity()

        names, calls = _tools_from_trace(response)
        routed_personal = any(n in PERSONAL_TOOLS for n in names)
        answer_norm = normalize_for_matching(response.answer)

        expect_route = case.get("expect_route", "personal")
        declined = _is_declined(response)
        if expect_route == "refuse":
            route_ok = (not routed_personal) and declined
        elif expect_route == "personal":
            route_ok = routed_personal
        else:  # general
            route_ok = not routed_personal

        required = case.get("required_facts", [])
        facts_ok = all(_fact_ok(answer_norm, f) for f in required) if required else None
        forbidden_hit = any(_fact_ok(answer_norm, f) for f in case.get("forbidden_facts", []))
        expect_tool = case.get("expect_tool")
        tool_ok = (any(expect_tool in n for n in names)) if expect_tool else None
        cite_ok = (bool(response.citations)) if case.get("expect_citation") else None
        loose = bool(case.get("loose"))

        passed = route_ok and not forbidden_hit
        if not loose and facts_ok is not None:
            passed = passed and facts_ok
        if cite_ok is not None:
            passed = passed and cite_ok

        rows.append({
            "id": cid,
            "lang": case.get("language"),
            "question": case["question"],
            "expect_route": expect_route,
            "routed_personal": routed_personal,
            "declined": declined,
            "route_ok": route_ok,
            "tools": names,
            "tool_calls": calls,
            "expect_tool": expect_tool,
            "tool_ok": tool_ok,
            "required": required,
            "facts_ok": facts_ok,
            "forbidden_hit": forbidden_hit,
            "loose": loose,
            "citations": [c.source_url for c in response.citations],
            "cite_ok": cite_ok,
            "passed": passed,
            "answer": response.answer,
        })
    await close_app_db_pool()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Score VinChatbot personal tools (authenticated).")
    parser.add_argument("--golden", default="data/eval/golden_personal.json")
    parser.add_argument("--email", default=None, help="Override the student account.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--id", default=None, help="Run only the case with this id.")
    args = parser.parse_args()

    payload = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    cases = payload["cases"]
    email = args.email or payload.get("student", "student.cs.demo@vinuni.edu.vn")
    if args.id:
        cases = [c for c in cases if c["id"] == args.id]
    if args.limit:
        cases = cases[: args.limit]

    rows = asyncio.run(_run(cases, email))

    print(f"\n===== PERSONAL EVAL ({email}) — {len(rows)} cases =====\n")
    for r in rows:
        if "error" in r:
            print(f"[{r['id']}] ERROR: {r['error']}\n")
            continue
        mark = "PASS" if r["passed"] else "FAIL"
        route_label = "OK" if r["route_ok"] else f"MISFIRE(expected {r['expect_route']})"
        print(f"[{mark}] {r['id']} ({r['lang']}) route={route_label} "
              f"facts={r['facts_ok']} tool_ok={r['tool_ok']}")
        print(f"   Q: {r['question']}")
        print(f"   tools: {r['tools']}")
        proj = [c for c in r["tool_calls"] if c["name"] == "project_gpa_for_target"]
        if proj:
            print(f"   projection args: {[c['args'] for c in proj]}")
        if r["required"]:
            print(f"   required: {r['required']} -> facts_ok={r['facts_ok']}")
        if r["cite_ok"] is not None:
            print(f"   citations: {r['citations']}")
        if r["expect_route"] == "refuse":
            print(f"   declined={r['declined']} (expect a refusal of this out-of-scope task)")
        print(f"   A: {r['answer'][:320].replace(chr(10), ' ')}\n")

    scored = [r for r in rows if "error" not in r]
    print("===== SUMMARY =====")
    print(f"passed:      {sum(1 for r in scored if r['passed'])}/{len(scored)}")
    print(f"route_ok:    {sum(1 for r in scored if r['route_ok'])}/{len(scored)}")
    print(f"tool_ok:     {sum(1 for r in scored if r.get('tool_ok'))}/{sum(1 for r in scored if r.get('expect_tool'))}")
    facts_cases = [r for r in scored if r['facts_ok'] is not None and not r['loose']]
    print(f"facts_ok:    {sum(1 for r in facts_cases if r['facts_ok'])}/{len(facts_cases)} (strict cases)")
    misfires = [r['id'] for r in scored if not r['route_ok']]
    print(f"route misfires: {misfires or 'none'}")
    errs = [r['id'] for r in rows if 'error' in r]
    print(f"errors: {errs or 'none'}")


if __name__ == "__main__":
    main()
