"""Golden-set evaluation scorer for VinChatbot.

Loads golden cases from data/eval/golden/*.json (plus the legacy
data/eval/calendar_golden_qa.json), runs each through the live VinUniAgentService, and
scores: required/forbidden facts, citation presence + expected source, and correct
refusal for adversarial cases. Writes a timestamped report to data/eval/results/.

Requires OPENROUTER_API_KEY (+ Qdrant config) since it exercises the real agent.

Usage:
    py scripts/run_eval.py [--golden-dir data/eval/golden] [--min-pass 0.0] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from vinchatbot.app.agents.guardrails import normalize_for_matching
from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.core.observability import get_rerank_count, get_stage_ledger, ledger_totals
from vinchatbot.app.schemas.chat import ChatRequest

REFUSAL_ACTIONS = {
    "prompt_injection",
    "restricted_data",
    "abusive_language",
    "out_of_scope",
    "out_of_scope_task",
    "graceful_degradation",
}


def _load_cases(golden_dir: Path, legacy_calendar: Path) -> list[dict]:
    sources: list[Path] = []
    if golden_dir.exists():
        sources.extend(sorted(golden_dir.glob("*.json")))
    if legacy_calendar.exists() and legacy_calendar not in sources:
        sources.append(legacy_calendar)

    cases: list[dict] = []
    for path in sources:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_cases = payload.get("cases", payload) if isinstance(payload, dict) else payload
        category = path.stem.replace("_golden_qa", "")
        for case in raw_cases:
            case.setdefault("category", category)
            cases.append(case)
    return cases


# Numeral↔word equivalence (accent-less, as `normalize_for_matching` strips diacritics). Lets a fact token
# "một"/"one" match the answer's numeral "1" and vice-versa — a genuine matcher-bug fix (the bot answering
# "1 tháng" satisfies the required "một tháng|one month"), NOT score-padding: it equates the SAME number
# across formats only, never different numbers. VI homonyms are EXCLUDED on purpose — "năm" (5) collides with
# "năm" (year) and "tư" (4) with "thứ tư" (Thursday) — so they keep plain substring behaviour.
_NUM_WORD_TO_DIGIT = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
    "mot": "1", "hai": "2", "ba": "3", "bon": "4", "sau": "6", "bay": "7", "tam": "8", "chin": "9", "muoi": "10",
}
_DIGIT_TO_WORDS: dict[str, set[str]] = {}
for _w, _d in _NUM_WORD_TO_DIGIT.items():
    _DIGIT_TO_WORDS.setdefault(_d, set()).add(_w)


def _number_match(token: str, answer_norm: str) -> bool | None:
    """If `token` is a number (digit or known number-word), return whether ANY equivalent form (the digit
    or its EN/VI words) appears in the answer as a STANDALONE number/word (boundary-checked, so a fact "two"
    is NOT satisfied by the "2" inside "2027"). Returns None when `token` is not a number → caller falls back
    to substring matching."""
    if token.isdigit():
        digit = token
    elif token in _NUM_WORD_TO_DIGIT:
        digit = _NUM_WORD_TO_DIGIT[token]
    else:
        return None
    for form in {digit} | _DIGIT_TO_WORDS.get(digit, set()):
        boundary = rf"(?<!\d){re.escape(form)}(?!\d)" if form.isdigit() else rf"(?<!\w){re.escape(form)}(?!\w)"
        if re.search(boundary, answer_norm):
            return True
    return False


def _fact_matches(answer_norm: str, fact: str, strict: bool) -> bool:
    # OR-synonyms: a required fact may list interchangeable wordings as "a|b|c" — satisfied if ANY
    # alternative matches. Loosens brittle single-word facts (e.g. "form|application" — the policy's
    # "application form" answered as either "form" or "application" is correct). Also bridges VI/EN
    # terms ("liêm chính|academic integrity") for bilingual cases.
    fact = str(fact)
    if "|" in fact:
        return any(_fact_matches(answer_norm, alt, strict) for alt in fact.split("|") if alt.strip())
    fact_norm = normalize_for_matching(fact)
    if strict:
        return fact_norm in answer_norm
    # Token-subset: every alphanumeric token of the fact appears in the answer. Stripping
    # punctuation tolerates range/format phrasing, e.g. "January 11 to January 22, 2027"
    # satisfies "January 11, 2027" and "23 đến 27 tháng 8 năm 2027" satisfies "23 tháng 8 năm 2027".
    # Number tokens additionally match across numeral/word forms (1 ↔ one ↔ một) via _number_match.
    tokens = re.findall(r"\w+", fact_norm)
    if not tokens:
        return fact_norm in answer_norm
    for tok in tokens:
        num = _number_match(tok, answer_norm)
        matched = num if num is not None else (tok in answer_norm)
        if not matched:
            return False
    return True


def _contains_all(answer_norm: str, facts: list[str], strict: bool = False) -> bool:
    return all(_fact_matches(answer_norm, fact, strict) for fact in facts)


def _contains_any(answer_norm: str, facts: list[str]) -> bool:
    # Forbidden facts always use exact substring matching (no token-subset over-flagging).
    return any(normalize_for_matching(str(fact)) in answer_norm for fact in facts)


def _is_refusal(response) -> bool:
    actions = {entry.get("action") for entry in response.tool_trace if isinstance(entry, dict)}
    if actions & REFUSAL_ACTIONS:
        return True
    return not response.citations and response.needs_human_review


def confidently_wrong(
    *, expects_refusal: bool, facts_ok: bool, declined: bool, has_citations: bool
) -> bool:
    """A turn that SERVED a factually wrong/unsupported answer without declining.

    This is the failure mode a future output-audit critic (Phase B) would convert into a safe
    graceful-degradation — the metric whose drop proves the critic's worth (the critic does NOT lift
    `passed`, it moves answers from confidently-wrong to safely-declined). Excludes refusal cases and
    any turn that already declined (graceful-degradation).
    """
    if expects_refusal:
        return False
    return has_citations and not declined and not facts_ok


def _capture_telemetry(latency_ms: int) -> dict:
    """Snapshot this turn's per-stage cost/latency ledger (the contextvars hold the last turn's data
    until the next chat() resets them). Read immediately after the turn(s) for a case."""
    ledger = {name: dict(entry) for name, entry in get_stage_ledger().items()}
    totals = ledger_totals(ledger)
    return {
        "latency_ms": latency_ms,
        "tokens_in": totals["tokens_in"],
        "tokens_out": totals["tokens_out"],
        "est_cost_usd": totals["est_cost_usd"],
        "model_calls": totals["model_calls"],
        "rerank_calls": get_rerank_count(),
        "stages": {
            name: {
                "calls": int(entry.get("calls") or 0),
                "latency_ms": round(float(entry.get("latency_ms") or 0.0), 1),
                "est_cost_usd": round(float(entry.get("est_cost_usd") or 0.0), 8),
            }
            for name, entry in ledger.items()
        },
    }


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolated percentile (pct in [0,1]); 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return float(ordered[low] + (ordered[high] - ordered[low]) * (rank - low))


def _score_case(case: dict, response, strict: bool = False) -> dict:
    answer_norm = normalize_for_matching(response.answer)
    expects_refusal = bool(case.get("expects_refusal"))

    if expects_refusal:
        passed = _is_refusal(response)
        return {"facts_ok": passed, "citation_ok": True, "refusal_ok": passed, "passed": passed}

    required = case.get("required_facts", [])
    forbidden = case.get("forbidden_facts", [])
    facts_ok = (not required or _contains_all(answer_norm, required, strict)) and not (
        forbidden and _contains_any(answer_norm, forbidden)
    )

    # expected_source may be a single slug or a LIST of acceptable slugs (e.g. the same document in
    # EN + VI: the EN policy page and the VI tariff PDF are one authoritative source — a VI query that
    # cites the VI PDF must not be scored as a citation failure).
    expected_source = case.get("expected_source")
    has_citation = bool(response.citations)
    if expected_source is None:
        source_ok = True
    else:
        expected_list = expected_source if isinstance(expected_source, list) else [expected_source]
        source_ok = any(
            str(es).lower() in (c.source_url or "").lower()
            for es in expected_list
            for c in response.citations
        )
    citation_ok = has_citation and source_ok

    return {
        "facts_ok": facts_ok,
        "citation_ok": citation_ok,
        "refusal_ok": True,
        "passed": facts_ok and citation_ok,
    }


async def _run(cases: list[dict], strict: bool = False) -> list[dict]:
    service = VinUniAgentService()
    rows: list[dict] = []
    for index, case in enumerate(cases, start=1):
        case_id = case.get("id", f"case-{index}")
        try:
            # Multi-turn cases send a `turns` list on one conversation (exercises in-session
            # memory); the final answer is scored. Single-turn cases use `question`.
            turns = case.get("turns") or [case["question"]]
            response = None
            started = time.perf_counter()
            for turn in turns:
                response = await service.chat(
                    ChatRequest(message=turn, conversation_id=f"eval-{case_id}")
                )
            latency_ms = int((time.perf_counter() - started) * 1000)
            score = _score_case(case, response, strict)
            telemetry = _capture_telemetry(latency_ms)
            expects_refusal = bool(case.get("expects_refusal"))
            rows.append(
                {
                    "id": case_id,
                    "category": case.get("category", "unknown"),
                    "question": turns[-1],
                    "expects_refusal": expects_refusal,
                    **score,
                    "confidently_wrong": confidently_wrong(
                        expects_refusal=expects_refusal,
                        facts_ok=bool(score.get("facts_ok")),
                        declined=_is_refusal(response),
                        has_citations=bool(response.citations),
                    ),
                    **telemetry,
                    "answer": response.answer,
                    "citations": [c.source_url for c in response.citations],
                }
            )
        except Exception as exc:  # keep scoring the rest of the set
            rows.append(
                {
                    "id": case_id,
                    "category": case.get("category", "unknown"),
                    "question": case.get("question", ""),
                    "expects_refusal": bool(case.get("expects_refusal")),
                    "facts_ok": False,
                    "citation_ok": False,
                    "refusal_ok": False,
                    "passed": False,
                    "confidently_wrong": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return rows


def _summarize(rows: list[dict]) -> dict:
    def rate(subset: list[dict], key: str) -> float:
        return round(sum(1 for r in subset if r.get(key)) / len(subset), 3) if subset else 0.0

    by_category: dict[str, dict] = {}
    for category in sorted({r["category"] for r in rows}):
        subset = [r for r in rows if r["category"] == category]
        by_category[category] = {
            "n": len(subset),
            "passed": rate(subset, "passed"),
            "facts_ok": rate(subset, "facts_ok"),
            "citation_ok": rate(subset, "citation_ok"),
        }
    return {
        "n": len(rows),
        "passed": rate(rows, "passed"),
        "facts_ok": rate(rows, "facts_ok"),
        "citation_ok": rate(rows, "citation_ok"),
        "by_category": by_category,
        "ledger": _summarize_ledger(rows),
    }


def _summarize_ledger(rows: list[dict]) -> dict:
    """Cost/latency/model-call aggregates + the confidently-wrong rate (Phase C ledger).

    Additive to the report — existing pass/facts/citation keys are untouched so baseline diffing is
    unaffected. confidently_wrong_rate is over ANSWERABLE cases (refusal cases can't be "wrong served").
    """
    def num(row: dict, key: str) -> float:
        return float(row.get(key) or 0.0)

    costs = [num(r, "est_cost_usd") for r in rows]
    latencies = [num(r, "latency_ms") for r in rows]
    model_calls = [num(r, "model_calls") for r in rows]
    n = len(rows) or 1

    answerable = [r for r in rows if not r.get("expects_refusal")]
    cw = sum(1 for r in answerable if r.get("confidently_wrong"))

    by_stage: dict[str, dict] = {}
    for row in rows:
        for name, entry in (row.get("stages") or {}).items():
            agg = by_stage.setdefault(name, {"turns": 0, "calls": 0, "latency_ms": 0.0, "est_cost_usd": 0.0})
            agg["turns"] += 1
            agg["calls"] += int(entry.get("calls") or 0)
            agg["latency_ms"] += float(entry.get("latency_ms") or 0.0)
            agg["est_cost_usd"] += float(entry.get("est_cost_usd") or 0.0)
    for agg in by_stage.values():
        turns = agg["turns"] or 1
        agg["latency_ms_mean"] = round(agg["latency_ms"] / turns, 1)
        agg["est_cost_usd_total"] = round(agg["est_cost_usd"], 8)
        agg.pop("latency_ms")
        agg.pop("est_cost_usd")

    return {
        "confidently_wrong": cw,
        "confidently_wrong_rate": round(cw / len(answerable), 3) if answerable else 0.0,
        "est_cost_usd_total": round(sum(costs), 6),
        "est_cost_usd_mean": round(sum(costs) / n, 8),
        "tokens_in_total": int(sum(num(r, "tokens_in") for r in rows)),
        "tokens_out_total": int(sum(num(r, "tokens_out") for r in rows)),
        "model_calls_mean": round(sum(model_calls) / n, 2),
        "rerank_calls_total": int(sum(num(r, "rerank_calls") for r in rows)),
        "latency_ms_mean": round(sum(latencies) / n, 1),
        "latency_ms_p95": round(_percentile(latencies, 0.95), 1),
        "by_stage": by_stage,
    }


def _compute_diff(
    rows: list[dict], summary: dict, base_rows: list[dict], base_summary: dict
) -> dict:
    """Compare a new run (rows/summary) against a baseline report's cases/summary.

    Returns per-case flips for the cases present in BOTH runs (so an expanded eval set doesn't
    show every new case as a 'flip'), plus added/removed ids and the overall pass rates.
    """
    base_pass = {c["id"]: bool(c.get("passed")) for c in base_rows if "id" in c}
    cur_pass = {r["id"]: bool(r.get("passed")) for r in rows if "id" in r}
    shared = [i for i in cur_pass if i in base_pass]
    return {
        "lost": sorted(i for i in shared if base_pass[i] and not cur_pass[i]),
        "gained": sorted(i for i in shared if not base_pass[i] and cur_pass[i]),
        "added": sorted(i for i in cur_pass if i not in base_pass),
        "removed": sorted(i for i in base_pass if i not in cur_pass),
        "overall_base": base_summary.get("passed"),
        "overall_cur": summary.get("passed"),
    }


def _print_diff(rows: list[dict], summary: dict, baseline_path: Path) -> None:
    """Print per-case flips (pass<->fail) + per-category pass-rate deltas vs a prior report."""
    if not baseline_path.exists():
        print(f"\n[diff] baseline not found: {baseline_path}")
        return
    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    diff = _compute_diff(rows, summary, base.get("cases", []), base.get("summary", {}))
    category = {r["id"]: r.get("category", "unknown") for r in rows if "id" in r}

    print(f"\n===== DIFF vs {baseline_path.name} =====")
    print(
        f"overall: {diff['overall_base']} -> {diff['overall_cur']}  "
        f"(+{len(diff['gained'])} / -{len(diff['lost'])}; "
        f"new={len(diff['added'])}, removed={len(diff['removed'])})"
    )
    print("LOST (pass -> fail):" if diff["lost"] else "LOST: none")
    for case_id in diff["lost"]:
        print(f"  - [{category.get(case_id, '?')}] {case_id}")
    print("GAINED (fail -> pass):" if diff["gained"] else "GAINED: none")
    for case_id in diff["gained"]:
        print(f"  + [{category.get(case_id, '?')}] {case_id}")

    base_cat = base.get("summary", {}).get("by_category", {})
    cur_cat = summary.get("by_category", {})
    print("per-category passed (baseline -> current):")
    for cat in sorted(set(base_cat) | set(cur_cat)):
        print(f"  {cat}: {base_cat.get(cat, {}).get('passed')} -> {cur_cat.get(cat, {}).get('passed')}")
    if diff["added"]:
        print("new cases (not in baseline):", ", ".join(diff["added"]))
    if diff["removed"]:
        print("removed cases (only in baseline):", ", ".join(diff["removed"]))


def _mean(values: list, ndigits: int | None = None) -> float:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return 0.0
    avg = sum(nums) / len(nums)
    return round(avg, ndigits) if ndigits is not None else avg


def _aggregate_runs(all_run_rows: list[list[dict]]) -> tuple[dict, list[dict]]:
    """Aggregate N independent eval runs into a de-noised summary + per-case stability (Phase 1.22a).

    Each case gets a `passed_rate` over the N runs and a `stable` class: "pass" (passed every run),
    "fail" (failed every run), or "noisy" (flipped). The summary `passed` is the MEAN over runs. This
    is the promotion-gate signal: a regression only counts if it is STABLE, never a noisy flip (the
    ~2-case run-to-run nondeterminism that muddied single-run A/Bs)."""
    runs = len(all_run_rows)
    per_run = [_summarize(rows) for rows in all_run_rows]
    by_id = [{r["id"]: r for r in rows if "id" in r} for rows in all_run_rows]

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for rows in all_run_rows:
        for r in rows:
            cid = r.get("id")
            if cid and cid not in seen:
                seen.add(cid)
                ordered_ids.append(cid)

    cases: list[dict] = []
    for cid in ordered_ids:
        present = [d[cid] for d in by_id if cid in d]
        passes = [bool(x.get("passed")) for x in present]
        facts = [bool(x.get("facts_ok")) for x in present]
        cits = [bool(x.get("citation_ok")) for x in present]
        rep = present[0]
        stable = "pass" if (passes and all(passes) and len(passes) == runs) else (
            "fail" if not any(passes) else "noisy"
        )
        cases.append({
            "id": cid,
            "category": rep.get("category", "unknown"),
            "question": rep.get("question", ""),
            "expects_refusal": rep.get("expects_refusal", False),
            "passed": _mean(passes) >= 0.5,  # majority bool (keeps single-run diff against this report valid)
            "passed_rate": _mean(passes, 3),
            "facts_ok": _mean(facts) >= 0.5,
            "facts_rate": _mean(facts, 3),
            "citation_ok": _mean(cits) >= 0.5,
            "citation_rate": _mean(cits, 3),
            "runs_passed": passes,
            "stable": stable,
            "confidently_wrong": rep.get("confidently_wrong", False),
            "latency_ms": _mean([x.get("latency_ms") for x in present]),
            "tokens_in": _mean([x.get("tokens_in") for x in present]),
            "tokens_out": _mean([x.get("tokens_out") for x in present]),
            "est_cost_usd": _mean([x.get("est_cost_usd") for x in present]),
            "model_calls": _mean([x.get("model_calls") for x in present]),
            "rerank_calls": _mean([x.get("rerank_calls") for x in present]),
            "stages": rep.get("stages"),
            "answer": rep.get("answer", ""),
            "citations": rep.get("citations", []),
        })

    by_cat: dict[str, dict] = {}
    for cat in sorted({c["category"] for c in cases}):
        by_cat[cat] = {
            "n": sum(1 for c in cases if c["category"] == cat),
            "passed": _mean([s["by_category"].get(cat, {}).get("passed", 0.0) for s in per_run], 3),
            "facts_ok": _mean([s["by_category"].get(cat, {}).get("facts_ok", 0.0) for s in per_run], 3),
            "citation_ok": _mean([s["by_category"].get(cat, {}).get("citation_ok", 0.0) for s in per_run], 3),
        }
    stability = {
        "runs": runs,
        "stable_pass": sum(1 for c in cases if c["stable"] == "pass"),
        "stable_fail": sum(1 for c in cases if c["stable"] == "fail"),
        "noisy": sum(1 for c in cases if c["stable"] == "noisy"),
        "noisy_ids": sorted(c["id"] for c in cases if c["stable"] == "noisy"),
    }
    summary = {
        "n": len(cases),
        "runs": runs,
        "passed": _mean([s["passed"] for s in per_run], 3),
        "facts_ok": _mean([s["facts_ok"] for s in per_run], 3),
        "citation_ok": _mean([s["citation_ok"] for s in per_run], 3),
        "passed_per_run": [s["passed"] for s in per_run],
        "by_category": by_cat,
        "stability": stability,
        "ledger": _summarize_ledger(cases),
    }
    return summary, cases


def _print_multi_diff(cases: list[dict], summary: dict, baseline_path: Path) -> None:
    """Multi-run diff: only STABLE flips count; noisy cases are listed but excluded from the gate."""
    if not baseline_path.exists():
        print(f"\n[diff] baseline not found: {baseline_path}")
        return
    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    base_rows = base.get("cases", [])
    # baseline may be single-run (bool passed) or multi-run (passed_rate)
    base_rate = {
        c["id"]: c.get("passed_rate", 1.0 if c.get("passed") else 0.0)
        for c in base_rows if "id" in c
    }
    cat = {c["id"]: c.get("category", "?") for c in cases}
    gained, lost, noisy = [], [], []
    for c in cases:
        cid = c["id"]
        if cid not in base_rate:
            continue
        if c["stable"] == "noisy":
            noisy.append(cid)
            continue
        base_passed = base_rate[cid] >= 0.5
        cur_passed = c["stable"] == "pass"
        if not base_passed and cur_passed:
            gained.append(cid)
        elif base_passed and not cur_passed:
            lost.append(cid)

    runs = summary.get("stability", {}).get("runs")
    print(f"\n===== MULTI-RUN DIFF vs {baseline_path.name} ({runs} runs) =====")
    print(f"overall mean: {base.get('summary', {}).get('passed')} -> {summary['passed']}  "
          f"(per-run: {summary.get('passed_per_run')})")
    print(f"STABLE GAINED (+{len(sorted(gained))}):" if gained else "STABLE GAINED: none")
    for cid in sorted(gained):
        print(f"  + [{cat.get(cid, '?')}] {cid}")
    print(f"STABLE LOST — regressions (-{len(lost)}):" if lost else "STABLE LOST: none")
    for cid in sorted(lost):
        print(f"  - [{cat.get(cid, '?')}] {cid}")
    print(f"NOISY (flip within {runs} runs — EXCLUDED from gate) ({len(noisy)}): {sorted(noisy)}")
    base_cat = base.get("summary", {}).get("by_category", {})
    cur_cat = summary.get("by_category", {})
    print("per-category passed mean (baseline -> current):")
    for c in sorted(set(base_cat) | set(cur_cat)):
        print(f"  {c}: {base_cat.get(c, {}).get('passed')} -> {cur_cat.get(c, {}).get('passed')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score VinChatbot against golden sets.")
    parser.add_argument("--golden-dir", default="data/eval/golden")
    parser.add_argument("--legacy-calendar", default="data/eval/calendar_golden_qa.json")
    parser.add_argument("--min-pass", type=float, default=0.0, help="Exit non-zero below this overall pass rate.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases (quick smoke).")
    parser.add_argument("--strict", action="store_true", help="Exact-substring fact matching (default: token-subset).")
    parser.add_argument("--diff", default=None, help="Path to a prior report JSON; print per-case flips + per-category deltas vs it.")
    parser.add_argument("--runs", type=int, default=1, help="Run the suite N times; report MEAN + per-case stability (pass/fail/noisy). Use for promotion gates to de-noise the ~2-case run-to-run flips. Default 1 = byte-identical to before.")
    args = parser.parse_args()

    cases = _load_cases(Path(args.golden_dir), Path(args.legacy_calendar))
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("No golden cases found. Add files under", args.golden_dir)
        sys.exit(1)

    runs = max(1, args.runs)
    all_run_rows: list[list[dict]] = []
    for index in range(runs):
        if runs > 1:
            print(f"[run {index + 1}/{runs}]")
        all_run_rows.append(asyncio.run(_run(cases, strict=args.strict)))

    if runs == 1:
        rows = all_run_rows[0]
        summary = _summarize(rows)
        report = {"summary": summary, "cases": rows}
    else:
        summary, rows = _aggregate_runs(all_run_rows)
        report = {"summary": summary, "cases": rows}

    results_dir = Path("data/eval/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = results_dir / f"eval_{timestamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")
    led = summary.get("ledger", {})
    print(
        f"ledger: cost≈${led.get('est_cost_usd_total', 0):.4f} "
        f"(mean ${led.get('est_cost_usd_mean', 0):.6f}/turn), "
        f"latency mean {led.get('latency_ms_mean', 0):.0f}ms / p95 {led.get('latency_ms_p95', 0):.0f}ms, "
        f"model_calls/turn {led.get('model_calls_mean', 0)}, "
        f"confidently_wrong {led.get('confidently_wrong', 0)} "
        f"({led.get('confidently_wrong_rate', 0):.1%} of answerable)"
    )
    if runs > 1:
        st = summary.get("stability", {})
        print(
            f"stability over {runs} runs: stable_pass={st.get('stable_pass')} "
            f"stable_fail={st.get('stable_fail')} noisy={st.get('noisy')} -> {st.get('noisy_ids')}"
        )
    if args.diff:
        (_print_multi_diff if runs > 1 else _print_diff)(rows, summary, Path(args.diff))
    if summary["passed"] < args.min_pass:
        print(f"FAIL: overall pass {summary['passed']} < min-pass {args.min_pass}")
        sys.exit(1)


if __name__ == "__main__":
    main()
