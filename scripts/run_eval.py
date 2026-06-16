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
from datetime import UTC, datetime
from pathlib import Path

from vinchatbot.app.agents.guardrails import normalize_for_matching
from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.schemas.chat import ChatRequest

REFUSAL_ACTIONS = {
    "prompt_injection",
    "restricted_data",
    "abusive_language",
    "out_of_scope",
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


def _fact_matches(answer_norm: str, fact: str, strict: bool) -> bool:
    fact_norm = normalize_for_matching(str(fact))
    if strict:
        return fact_norm in answer_norm
    # Token-subset: every alphanumeric token of the fact appears in the answer. Stripping
    # punctuation tolerates range/format phrasing, e.g. "January 11 to January 22, 2027"
    # satisfies "January 11, 2027" and "23 đến 27 tháng 8 năm 2027" satisfies "23 tháng 8 năm 2027".
    tokens = re.findall(r"\w+", fact_norm)
    return all(tok in answer_norm for tok in tokens) if tokens else fact_norm in answer_norm


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

    expected_source = case.get("expected_source")
    has_citation = bool(response.citations)
    source_ok = expected_source is None or any(
        str(expected_source).lower() in (c.source_url or "").lower() for c in response.citations
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
            for turn in turns:
                response = await service.chat(
                    ChatRequest(message=turn, conversation_id=f"eval-{case_id}")
                )
            score = _score_case(case, response, strict)
            rows.append(
                {
                    "id": case_id,
                    "category": case.get("category", "unknown"),
                    "question": turns[-1],
                    **score,
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
                    "facts_ok": False,
                    "citation_ok": False,
                    "refusal_ok": False,
                    "passed": False,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Score VinChatbot against golden sets.")
    parser.add_argument("--golden-dir", default="data/eval/golden")
    parser.add_argument("--legacy-calendar", default="data/eval/calendar_golden_qa.json")
    parser.add_argument("--min-pass", type=float, default=0.0, help="Exit non-zero below this overall pass rate.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases (quick smoke).")
    parser.add_argument("--strict", action="store_true", help="Exact-substring fact matching (default: token-subset).")
    parser.add_argument("--diff", default=None, help="Path to a prior report JSON; print per-case flips + per-category deltas vs it.")
    args = parser.parse_args()

    cases = _load_cases(Path(args.golden_dir), Path(args.legacy_calendar))
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("No golden cases found. Add files under", args.golden_dir)
        sys.exit(1)

    rows = asyncio.run(_run(cases, strict=args.strict))
    summary = _summarize(rows)

    results_dir = Path("data/eval/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = results_dir / f"eval_{timestamp}.json"
    report_path.write_text(
        json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")
    if args.diff:
        _print_diff(rows, summary, Path(args.diff))
    if summary["passed"] < args.min_pass:
        print(f"FAIL: overall pass {summary['passed']} < min-pass {args.min_pass}")
        sys.exit(1)


if __name__ == "__main__":
    main()
