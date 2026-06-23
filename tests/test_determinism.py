from __future__ import annotations

from vinchatbot.app.rag.retriever import _round_score, stable_rerank_order


class _Item:
    def __init__(self, index: int, score: float) -> None:
        self.index = index
        self.score = score


def test_rerank_tiebreak_and_threshold_desensitize():
    """A2a: the rerank order must be reproducible despite (a) sub-granularity float jitter in the scores
    and (b) the reranker returning the pool in a different order — and the score rounding that de-sensitizes
    the reactive-trigger / dynamic-k cutoffs must collapse jitter while preserving genuine differences."""
    # Two runs of the SAME pool: 0.50-ish scores jitter below 1e-3 AND come back in a different order.
    run_a = [_Item(0, 0.5000), _Item(1, 0.5004), _Item(2, 0.3000)]
    run_b = [_Item(1, 0.4997), _Item(0, 0.5003), _Item(2, 0.3001)]
    order_a = [it.index for it in stable_rerank_order(run_a)]
    order_b = [it.index for it in stable_rerank_order(run_b)]
    # 0.500-ties broken by index ASC; the 0.300 item last — identical across runs despite jitter + input order.
    assert order_a == order_b == [0, 1, 2]

    # Threshold de-sensitize: sub-granularity jitter collapses to one value (so a near-boundary score can't
    # flip the reactive-trigger / dynamic-k membership run-to-run)...
    assert _round_score(0.5004) == _round_score(0.4997) == 0.5
    # ...while genuinely-different scores stay distinct.
    assert _round_score(0.3489) != _round_score(0.3512)
    assert _round_score(None) is None
