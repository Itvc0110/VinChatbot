"""VN-input robustness analyzer (teencode / no-diacritics / mistyped / CAPSLOCK).

Reads data/eval/vn_robustness.json (each case = a CLEAN baseline + a CORRUPTED variant) and reports where
the corrupted variant DIVERGES from its clean baseline through the deterministic gates (scope classifier +
full guardrail) — divergence = a robustness failure. Run: `python scripts/run_vn_robustness.py`.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import Counter
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from vinchatbot.app.agents.guardrails import (  # noqa: E402
    answer_language,
    resolve_guardrail_decision,
)
from vinchatbot.app.agents.question_scope import classify_question_scope  # noqa: E402
from vinchatbot.app.core.observability import (  # noqa: E402
    reset_student_identity,
    set_student_identity,
)

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "eval" / "vn_robustness.json").read_text("utf-8")
)["cases"]


def _blocked(action: str) -> bool:
    return action not in ("allow", "personal", "smalltalk", "capability", "clarify")


async def main() -> None:
    set_student_identity(student_profile_id=uuid.uuid4(), user_id=uuid.uuid4())
    rows = []
    for case in CASES:
        cs = classify_question_scope(case["clean"], authenticated=True)
        xs = classify_question_scope(case["q"], authenticated=True)
        cg = (await resolve_guardrail_decision(case["clean"])).action
        xg = (await resolve_guardrail_decision(case["q"])).action
        lc, lx = answer_language(case["clean"]), answer_language(case["q"])
        rows.append((case, cs, xs, cg, xg, lc, lx, cs != xs, (not _blocked(cg)) and _blocked(xg), lc != lx))
    reset_student_identity()

    by_kind: Counter = Counter()
    for case, cs, xs, cg, xg, lc, lx, sd, gd, ld in rows:
        flags = [f for f, on in (("GUARD-DEGRADE", gd), ("scope-shift", sd), ("lang-shift", ld)) if on]
        if flags:
            by_kind[case["kind"]] += 1
        mark = "! " if (gd or sd) else "  "
        print(f"{mark}{case['id']:20}{case['kind']:13}{cs+'->'+xs:32}{cg+'->'+xg:26}{lc+'/'+lx:7}{','.join(flags)}")
    print(f"\nover {len(rows)} cases: "
          f"GUARD-DEGRADE={sum(r[8] for r in rows)}, scope-shift={sum(r[7] for r in rows)}, "
          f"lang-shift={sum(r[9] for r in rows)}; by kind (any flag): {dict(by_kind)}")


if __name__ == "__main__":
    asyncio.run(main())
