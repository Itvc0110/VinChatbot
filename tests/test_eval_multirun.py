from __future__ import annotations

from scripts.run_eval import _aggregate_runs


def _row(cid: str, passed: bool, cat: str = "policy") -> dict:
    return {
        "id": cid, "category": cat, "passed": passed, "facts_ok": passed,
        "citation_ok": passed, "expects_refusal": False, "question": "q",
        "answer": "a", "citations": [],
    }


def test_aggregate_runs_stability_classification():
    # 3 runs: A always passes, B always fails, C flips (pass, fail, pass) → noisy.
    runs = [
        [_row("A", True), _row("B", False), _row("C", True)],
        [_row("A", True), _row("B", False), _row("C", False)],
        [_row("A", True), _row("B", False), _row("C", True)],
    ]
    summary, cases = _aggregate_runs(runs)
    by_id = {c["id"]: c for c in cases}

    assert by_id["A"]["stable"] == "pass" and by_id["A"]["passed_rate"] == 1.0
    assert by_id["B"]["stable"] == "fail" and by_id["B"]["passed_rate"] == 0.0
    assert by_id["C"]["stable"] == "noisy" and by_id["C"]["passed_rate"] == 0.667

    st = summary["stability"]
    assert st == {"runs": 3, "stable_pass": 1, "stable_fail": 1, "noisy": 1, "noisy_ids": ["C"]}
    # overall mean = mean of per-run pass rates (0.667, 0.333, 0.667)
    assert summary["passed"] == 0.556
    assert summary["runs"] == 3


def test_aggregate_runs_noisy_majority_bool_for_diff_compat():
    # A noisy case that mostly passes keeps passed=True (majority) so a future SINGLE-run --diff against
    # this report still behaves, while `stable` records that it flipped.
    runs = [[_row("C", True)], [_row("C", True)], [_row("C", False)]]
    _, cases = _aggregate_runs(runs)
    assert cases[0]["passed"] is True
    assert cases[0]["stable"] == "noisy"
    assert cases[0]["passed_rate"] == 0.667
