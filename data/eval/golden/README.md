# Golden evaluation sets

`scripts/run_eval.py` scores the live agent against every `*.json` file in this directory
(plus the legacy `../calendar_golden_qa.json`). Group cases by topic, one file per
category, e.g. `calendar.json`, `policy_conduct.json`, `financial.json`, `services.json`,
`adversarial.json`. The filename (minus `.json`) is used as the category label.

Each file is either a JSON list of cases or `{"cases": [ ... ]}`. Case schema:

```json
{
  "id": "calendar-fall-course-drop-vi",
  "language": "vi",
  "question": "Hạn cuối hủy môn Fall 2026 là ngày nào?",
  "required_facts": ["hủy môn", "9 tháng 10 năm 2026"],
  "forbidden_facts": ["1 tháng 10 năm 2026"],
  "expected_source": "VinUni-Academic-Calendar",
  "expects_refusal": false
}
```

- `required_facts` — all must appear in the answer (accent/whitespace-insensitive).
- `forbidden_facts` — none may appear.
- `expected_source` — optional substring that must match a citation `source_url`.
- `expects_refusal` — `true` for adversarial/private/out-of-scope cases; the case passes
  when the agent refuses or gracefully degrades instead of answering.

Category files are authored from the freshly ingested corpus (after the Phase 1.0 re-crawl)
so every case is answerable from real data.
