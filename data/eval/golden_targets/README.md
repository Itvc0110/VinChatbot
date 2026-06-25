# Golden TARGETS (aspirational — not in the scored baseline)

These golden cases probe **failure modes whose general fix has not shipped yet** (Phase 1.30 roadmap:
cross-domain, underspecified, multi-hop, refusal-calibration, confidence, affirmative entity-enumeration).
They are **expected to FAIL** on the current system — they are the **A/B substrate** for each fix.

**Why separate from `data/eval/golden/`:** the scored set feeds `data/eval/baseline.json` and the promote gate
(`run_eval --diff baseline`). Putting known-red target cases there would drag the baseline and make `--diff`
noisy. Keeping them here lets `--diff baseline` stay a meaningful regression signal.

## How to use
- Score the standing set (default): `python scripts/run_eval.py`
- Measure targets on demand: `python scripts/run_eval.py --golden-dir data/eval/golden_targets`

## Lifecycle
When a fix ships and its target cases pass on a `--runs 3` A/B, **move those cases into `data/eval/golden/`**
(the scored set) and refresh `baseline.json`. Track per fix in the relevant `LOGS/PHASE1.3x_LOG.md` and the
living plan `LOGS/PHASE1.29_PLAN.md`.
