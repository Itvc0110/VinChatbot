# Phase 5J: VN-input robustness — teencode / no-diacritics / mistyped / CAPSLOCK

Vietnamese students type messily (teencode abbreviations, no diacritics, all-caps, typos). We built a
temporary 42-case test set (clean baseline + corrupted variant per case) and measured divergence through the
real deterministic gates, then fixed the biggest failures.

## Experiment + findings
Method: corrupt each question 4 ways and check whether the corrupted variant classifies + passes the guardrail
the SAME as its clean baseline (authenticated). Test set: `data/eval/vn_robustness.json` (42 cases); analyzer:
`scripts/run_vn_robustness.py`.

Baseline failures:
- **Teencode abbreviations → REFUSAL / mis-route (worst).** `hnay t có tiết j`, `tkb của t`, `t có dl nào ko`,
  `hp 1 năm bao nhiu` → the deterministic term-lists don't know `hnay/t/j/ko/tkb/dl/hp/đk/tn/…` → out_of_scope
  (refused) or personal→general (mis-routed). 6 GUARD-DEGRADE, 7 scope-shift.
- **`answer_language` → English reply to a VN student.** No-diacritics/teencode ("gpa mik bao nhiu", "mau don
  phuc khao diem") lacked VN diacritics + hint words → detected `en`. 6 lang-shift.
- **No-diacritics + CAPSLOCK were already robust** for scope/guard (the normalizer lowercases + strips
  accents) — only their language detection broke.

## Fix (deterministic; the LLM already handles teencode at generation, so this only feeds the GATES)
- **`expand_teencode()`** (`vinchatbot/app/agents/guardrails.py`): a curated, conservative VN
  abbreviation→canonical map (`hnay→hom nay, t→toi, j→gi, ko/hok→khong, tkb→thoi khoa bieu, dl→deadline,
  hp→hoc phi, dk→dieu kien, dki→dang ky, tn→tot nghiep, mik→minh, nhiu→nhieu, bnhiu→bao nhieu, baoh→bao gio,
  dc→duoc, sv→sinh vien`), single word-boundary pass on already-normalized text.
- Wired into the **input gates only**: `assess_user_message` scope check (`scope_normalized = expand_teencode
  (normalized)` for `has_scope`) and `classify_question_scope` (`expand_teencode(normalize_for_matching(...))`).
  **Never** applied to the output grounding/injection checks (which share `normalize_for_matching`).
- **`answer_language`**: expand teencode before the hint check + extended `_VI_WORD_HINTS` with accent-free
  student-domain words that don't collide with English (`hom, tiet, mon, lop, lich, diem, don, phuc, khao,
  nghi, hoi, nhieu, bao, nganh, nhung, mssv, tkb`).

## Results (re-run of the 42-case analyzer)
- GUARD-DEGRADE **6 → 2**, scope-shift **7 → 1**, lang-shift **6 → 1**.
- All teencode CONTENT questions now allowed + correctly routed (`hnay t có tiết j`, `tkb của t`, `t có dl nào`,
  `hp 1 năm` → personal/official + allow).
- Remaining (accepted): 1 typo mis-route (`lịc hoc cua tôii` — not refused; typos deferred), 1 odd greeting
  (`helu shop`), 1 weather (correctly refused).
- **No new over-fire**: `expand_teencode` did not pull any non-personal question into personal (verified —
  vinuni/ngành, học phí ngành Y, thời tiết, quy định thi cuối kỳ all stay non-personal). The one borderline
  "lịch thi cuối kỳ" personal is PRE-EXISTING (unchanged by expansion).

## Verification
- New `tests/test_vn_robustness.py` (26 tests): `expand_teencode` unit; teencode personal questions stay
  personal + not refused (full `resolve_guardrail_decision`); `answer_language` VN-detection for
  no-diacritics/teencode while English stays English; **over-fire guard** (teencode expansion adds no personal
  misfire); eval-set well-formed.
- Full suite **803 passed**, ruff clean. Over-fire audit (test_question_scope negatives + the new guard) green.

## Deferred
- **Typos/misspellings** (e.g. "lịc", "tôii"): the LLM handles them at generation and they caused no
  refusals, only occasional mis-route — left for a future fuzzy-match pass.
- Greeting teencode ("helu") — minor; separate from content robustness.

Branch `fix/vn-teencode-robustness` off `main`.
