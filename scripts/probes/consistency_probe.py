"""Consistency probe (Phase 1.11).

Runs a small set of representative questions N times each (fresh conversation per run) and measures how
much the answer + citations vary run-to-run. Cheap alternative to an N× full-130 eval — it directly
targets the inconsistency root (same question -> different answer). Use it to compare BEFORE vs AFTER a
determinism change.

Usage:
    py scripts/consistency_probe.py [--runs 3] [--limit N]

Reports per question: distinct_answers (1=stable), avg pairwise token-Jaccard (1.0=identical wording),
distinct citation-sets (1=stable); plus aggregates.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import re
from pathlib import Path

from vinchatbot.app.agents.vinuni_agent import VinUniAgentService
from vinchatbot.app.schemas.chat import ChatRequest

# Harder, student-phrased questions: vague, colloquial, code-switching, multi-part, comparison,
# emotional — the messy real inputs that stress retrieval + expansion + generation.
PROBE_QUESTIONS = [
    "Tui muốn nghỉ học một kỳ rồi quay lại thì cần làm thủ tục gì vậy ạ?",
    "Học phí một tín chỉ ngành Khoa học Máy tính là bao nhiêu, một kỳ đóng tổng cộng bao nhiêu tiền?",
    "Deadline nào sắp tới mà em cần để ý không ạ?",
    "Cho em hỏi add/drop deadline kỳ này là ngày nào ạ?",
    "Đóng học phí trễ hạn thì có bị phạt không, phạt bao nhiêu vậy?",
    "Em bị áp lực học tập quá, trường mình có dịch vụ hỗ trợ tâm lý nào không ạ?",
    "Ngành nào ở VinUni có học phí thấp nhất vậy?",
    "I think I might fail a course this semester — can I retake it later and will it cost extra?",
    "What do I actually need to prepare before I graduate?",
]


_REFUSAL_MARKERS = (
    "chưa tìm thấy",
    "không tìm thấy",
    "could not find",
    "couldn't find",
    "i could not find",
    "không có thông tin",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_refusal(text: str) -> bool:
    low = _norm(text)
    return any(m in low for m in _REFUSAL_MARKERS)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", _norm(text)))


def _avg_pairwise_jaccard(answers: list[str]) -> float:
    token_sets = [_tokens(a) for a in answers]
    pairs = list(itertools.combinations(token_sets, 2))
    if not pairs:
        return 1.0
    scores = []
    for a, b in pairs:
        union = a | b
        scores.append(len(a & b) / len(union) if union else 1.0)
    return sum(scores) / len(scores)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Measure run-to-run answer/citation stability.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="Only probe the first N questions.")
    parser.add_argument(
        "--questions-file",
        default=None,
        help="Text file, one question per line (# comments and blank lines ignored).",
    )
    args = parser.parse_args()

    if args.questions_file:
        lines = Path(args.questions_file).read_text(encoding="utf-8").splitlines()
        questions = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    else:
        questions = PROBE_QUESTIONS
    if args.limit:
        questions = questions[: args.limit]
    service = VinUniAgentService()

    distinct_answer_counts: list[int] = []
    jaccards: list[float] = []
    stable_citation_flags: list[bool] = []
    refusal_consistent_flags: list[bool] = []

    print(f"Consistency probe — {len(questions)} questions x {args.runs} runs\n" + "=" * 74)
    for qi, question in enumerate(questions):
        answers: list[str] = []
        citation_sets: list[tuple[str, ...]] = []
        for run in range(args.runs):
            try:
                resp = await service.chat(
                    ChatRequest(message=question, conversation_id=f"probe-{qi}-r{run}")
                )
                answers.append(resp.answer)
                citation_sets.append(tuple(sorted((c.source_url or "") for c in resp.citations)))
            except Exception as exc:  # one failing turn must not abort the whole probe
                answers.append(f"[ERROR: {type(exc).__name__}]")
                citation_sets.append(("[error]",))

        distinct_answers = len({_norm(a) for a in answers})
        jac = _avg_pairwise_jaccard(answers)
        stable_citations = len(set(citation_sets)) == 1
        refusal_consistent = len({_is_refusal(a) for a in answers}) == 1  # all answer or all refuse
        distinct_answer_counts.append(distinct_answers)
        jaccards.append(jac)
        stable_citation_flags.append(stable_citations)
        refusal_consistent_flags.append(refusal_consistent)

        print(f"\nQ{qi}: {question}")
        print(
            f"   distinct_answers={distinct_answers}/{args.runs}  avg_jaccard={jac:.2f}  "
            f"citations_stable={stable_citations}  refuse/answer_consistent={refusal_consistent}"
        )
        for run, a in enumerate(answers):
            print(f"     r{run}: {_norm(a)[:160]}")

    n = len(questions)
    print("\n" + "=" * 74)
    print("AGGREGATE")
    print(f"  mean distinct_answers : {sum(distinct_answer_counts)/n:.2f} (1.00 = perfectly stable)")
    print(f"  mean avg_jaccard      : {sum(jaccards)/n:.2f} (1.00 = identical wording)")
    print(f"  fully-stable answers  : {sum(1 for c in distinct_answer_counts if c == 1)}/{n}")
    print(f"  stable-citation Qs    : {sum(stable_citation_flags)}/{n} (substance proxy)")
    print(f"  refuse/answer-consistent : {sum(refusal_consistent_flags)}/{n} (no answer<->refuse flips)")


if __name__ == "__main__":
    asyncio.run(main())
