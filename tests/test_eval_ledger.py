from __future__ import annotations

from scripts.run_eval import _fact_matches, _percentile, _summarize_ledger, confidently_wrong
from vinchatbot.app.agents.guardrails import normalize_for_matching


def test_or_synonym_fact_matching():
    ans = normalize_for_matching("complete the application for a leave of absence")
    # "form" alone is absent, but the OR-synonym "form|application" is satisfied by "application".
    assert _fact_matches(ans, "form", strict=False) is False
    assert _fact_matches(ans, "form|application", strict=False) is True
    assert _fact_matches(ans, "form|application", strict=True) is True
    # Bilingual bridge: a VI answer satisfies "liêm chính|academic integrity" via the VI alternative.
    vi = normalize_for_matching("VinUni có chính sách liêm chính học thuật")
    assert _fact_matches(vi, "liêm chính|academic integrity", strict=False) is True
    # A genuinely-absent fact still fails (no false positives from OR).
    assert _fact_matches(ans, "withdrawal|expulsion", strict=False) is False


def test_numeral_word_equivalence():
    N = normalize_for_matching
    # The loa-return case: bot answers "1 tháng" (correct); required "một tháng|one month" must now match.
    ans = N("Nộp đơn xin trở lại ít nhất 1 tháng trước khi bắt đầu học kỳ mới")
    assert _fact_matches(ans, "một tháng|one month", strict=False) is True
    # EN numeral both directions.
    assert _fact_matches(N("submit at least 1 month before"), "one month", strict=False) is True
    assert _fact_matches(N("submit at least one month before"), "1 month", strict=False) is True
    # Number-SPECIFIC: a different number is NOT accepted (no padding).
    assert _fact_matches(N("at least 2 months"), "one month", strict=False) is False
    # Boundary: the "2" inside a year does not satisfy a standalone-number fact.
    assert _fact_matches(N("the deadline is in 2027"), "two", strict=False) is False
    # VI homonym excluded: "năm" stays plain substring (5/year not conflated).
    assert _fact_matches(N("năm học 2026"), "năm", strict=False) is True


def test_confidently_wrong_truth_table():
    # Served a wrong/unsupported answer with citations and did not decline → True.
    assert confidently_wrong(
        expects_refusal=False, facts_ok=False, declined=False, has_citations=True
    )
    # Refusal cases can never be "confidently wrong".
    assert not confidently_wrong(
        expects_refusal=True, facts_ok=False, declined=False, has_citations=True
    )
    # Already declined (graceful-degradation) → safe, not confidently wrong.
    assert not confidently_wrong(
        expects_refusal=False, facts_ok=False, declined=True, has_citations=True
    )
    # Facts correct → not wrong.
    assert not confidently_wrong(
        expects_refusal=False, facts_ok=True, declined=False, has_citations=True
    )
    # No citations → not a confidently-served answer.
    assert not confidently_wrong(
        expects_refusal=False, facts_ok=False, declined=False, has_citations=False
    )


def test_percentile():
    assert _percentile([], 0.95) == 0.0
    assert _percentile([42.0], 0.95) == 42.0
    # n=4: rank = 3 * 0.95 = 2.85 → 30 + (40-30)*0.85 = 38.5
    assert _percentile([10.0, 20.0, 30.0, 40.0], 0.95) == 38.5
    assert _percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 25.0


def test_summarize_ledger_aggregates_and_confidently_wrong_rate():
    rows = [
        {
            "expects_refusal": False,
            "confidently_wrong": True,
            "est_cost_usd": 0.01,
            "latency_ms": 100,
            "model_calls": 3,
            "rerank_calls": 1,
            "tokens_in": 100,
            "tokens_out": 50,
            "stages": {
                "supervisor": {"calls": 1, "latency_ms": 10.0, "est_cost_usd": 0.001},
                "answer": {"calls": 2, "latency_ms": 80.0, "est_cost_usd": 0.009},
            },
        },
        {
            "expects_refusal": False,
            "confidently_wrong": False,
            "est_cost_usd": 0.02,
            "latency_ms": 200,
            "model_calls": 2,
            "rerank_calls": 1,
            "tokens_in": 200,
            "tokens_out": 80,
            "stages": {"answer": {"calls": 2, "latency_ms": 150.0, "est_cost_usd": 0.02}},
        },
        {
            "expects_refusal": True,
            "confidently_wrong": False,
            "est_cost_usd": 0.005,
            "latency_ms": 50,
            "model_calls": 1,
            "rerank_calls": 0,
            "tokens_in": 30,
            "tokens_out": 10,
            "stages": {"llm_guard": {"calls": 1, "latency_ms": 20.0, "est_cost_usd": 0.005}},
        },
    ]

    led = _summarize_ledger(rows)

    assert led["confidently_wrong"] == 1
    assert led["confidently_wrong_rate"] == 0.5  # 1 of 2 answerable cases
    assert led["est_cost_usd_total"] == round(0.035, 6)
    assert led["rerank_calls_total"] == 2
    assert led["model_calls_mean"] == 2.0  # (3 + 2 + 1) / 3
    assert led["tokens_in_total"] == 330
    assert led["latency_ms_mean"] == round((100 + 200 + 50) / 3, 1)

    answer_stage = led["by_stage"]["answer"]
    assert answer_stage["turns"] == 2
    assert answer_stage["calls"] == 4
    assert answer_stage["latency_ms_mean"] == 115.0  # (80 + 150) / 2
    assert answer_stage["est_cost_usd_total"] == round(0.029, 8)


def test_summarize_ledger_handles_rows_without_telemetry():
    # An error-branch row carries no stages/cost fields; aggregation must not crash.
    rows = [
        {"expects_refusal": False, "confidently_wrong": False, "passed": False},
        {"expects_refusal": True, "confidently_wrong": False, "passed": True},
    ]
    led = _summarize_ledger(rows)
    assert led["confidently_wrong"] == 0
    assert led["confidently_wrong_rate"] == 0.0
    assert led["est_cost_usd_total"] == 0.0
    assert led["by_stage"] == {}
