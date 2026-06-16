from __future__ import annotations

from scripts.run_eval import _compute_diff


def test_compute_diff_flags_flips_and_set_changes():
    base_rows = [
        {"id": "a", "passed": True},
        {"id": "b", "passed": True},
        {"id": "c", "passed": False},
        {"id": "old-only", "passed": True},
    ]
    cur_rows = [
        {"id": "a", "passed": True},
        {"id": "b", "passed": False},  # lost (pass -> fail)
        {"id": "c", "passed": True},  # gained (fail -> pass)
        {"id": "new-only", "passed": True},  # added (not in baseline)
    ]
    diff = _compute_diff(cur_rows, {"passed": 0.5}, base_rows, {"passed": 0.75})

    assert diff["lost"] == ["b"]
    assert diff["gained"] == ["c"]
    assert diff["added"] == ["new-only"]
    assert diff["removed"] == ["old-only"]
    assert diff["overall_base"] == 0.75
    assert diff["overall_cur"] == 0.5


def test_compute_diff_ignores_unchanged_and_handles_empty_baseline():
    cur_rows = [{"id": "a", "passed": True}, {"id": "b", "passed": False}]
    diff = _compute_diff(cur_rows, {"passed": 0.5}, [], {})
    assert diff["lost"] == [] and diff["gained"] == []
    assert diff["added"] == ["a", "b"]
    assert diff["removed"] == []
