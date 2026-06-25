"use client";

import { useMemo, useState } from "react";
import { Toast } from "@/components/ui/primitives";
import { IconCheck, IconSliders, IconChat } from "@/components/shell/icons";

// Admin Context & Personalization (Phase 4, new route). Demo-only: configures which student-profile
// fields act as RETRIEVAL filters vs CONTEXT-ONLY personalization, plus admin personalization rules,
// with a "test as student" preview. No backend/API exists for this yet — state is local demo state,
// so nothing in the live data/API layer is touched.

interface Field { key: string; active: boolean }
interface Rule { id: string; name: string; condition: string; behavior: string }
interface DemoStudent { name: string; program: string; cohort: string; lang: string }

const INITIAL_RETRIEVAL: Field[] = [
  { key: "academic_year", active: true },
  { key: "college", active: true },
  { key: "program", active: true },
  { key: "cohort", active: true },
  { key: "term", active: true },
  { key: "degree_level", active: true },
  { key: "gpa_band", active: false },
];
const INITIAL_CONTEXT: Field[] = [
  { key: "preferred_name", active: true },
  { key: "preferred_language", active: true },
  { key: "schedule", active: true },
  { key: "deadlines", active: true },
  { key: "tuition_balance", active: true },
  { key: "tickets", active: true },
  { key: "advisor", active: true },
];
const INITIAL_RULES: Rule[] = [
  { id: "r1", name: "Computer Science Boost", condition: "program = CS", behavior: "boost CS docs ×1.5" },
  { id: "r2", name: "Cohort Specificity", condition: "cohort = 2024", behavior: "prefer 2024 handbook" },
  { id: "r3", name: "Financial Sensitivity", condition: "tuition_balance > 0", behavior: "append bursar contact" },
  { id: "r4", name: "Language Preference", condition: "pref_lang ≠ EN", behavior: "translate final output" },
];
const STUDENTS: DemoStudent[] = [
  { name: "Minh Anh", program: "BS Computer Science", cohort: "2024", lang: "VI" },
  { name: "Sarah Jenkins", program: "BA Business Admin", cohort: "2023", lang: "EN" },
  { name: "David Chen", program: "BS Data Science", cohort: "2025", lang: "EN" },
];

function IconPencil() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
    </svg>
  );
}
function IconTrash() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" />
    </svg>
  );
}

export default function AdminContextPage() {
  const [retrieval, setRetrieval] = useState<Field[]>(INITIAL_RETRIEVAL);
  const [context, setContext] = useState<Field[]>(INITIAL_CONTEXT);
  const [rules, setRules] = useState<Rule[]>(INITIAL_RULES);
  const [student, setStudent] = useState<DemoStudent>(STUDENTS[0]);
  const [toast, setToast] = useState<string | null>(null);

  const retrievalActive = retrieval.filter((f) => f.active).length;
  const contextActive = context.filter((f) => f.active).length;

  const toggle = (setter: typeof setRetrieval) => (key: string) =>
    setter((cur) => cur.map((f) => (f.key === key ? { ...f, active: !f.active } : f)));

  const preview = useMemo(() => {
    const filters = retrieval.filter((f) => f.active).map((f) => f.key);
    const docs = Math.max(1, Math.min(filters.length, 3));
    return { docs, filters };
  }, [retrieval]);

  return (
    <div className="page-inner">
      <p className="field-hint" style={{ margin: "0 0 16px" }}>
        Configure how student profile data influences Vinnie&apos;s answers. Retrieval filters narrow which
        documents Vinnie searches; context-only fields personalize tone &amp; content without filtering.
      </p>

      <div className="actx-grid">
        <div className="actx-main">
          {/* Retrieval filters */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">Retrieval Filters</h2>
              <span className="ah-chip">{retrievalActive} active</span>
            </div>
            <div className="actx-chips">
              {retrieval.map((f) => (
                <button key={f.key} className={`actx-chip ${f.active ? "on" : ""}`} onClick={() => toggle(setRetrieval)(f.key)}>
                  <span className="actx-chip-dot" />{f.key}
                </button>
              ))}
              <button className="actx-chip add" onClick={() => setToast("Add field (demo).")}>+ add field</button>
            </div>
            <p className="field-hint" style={{ marginTop: 10 }}>
              These fields filter the knowledge base before answering — only matching documents are retrieved.
            </p>
          </div>

          {/* Context-only fields */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">Context-Only Fields</h2>
              <span className="ah-chip neutral">{contextActive} active</span>
            </div>
            <div className="actx-chips">
              {context.map((f) => (
                <button key={f.key} className={`actx-chip ctx ${f.active ? "on" : ""}`} onClick={() => toggle(setContext)(f.key)}>
                  <span className="actx-chip-dot" />{f.key}
                </button>
              ))}
            </div>
            <p className="field-hint" style={{ marginTop: 10 }}>
              Used to personalize the answer (tone, examples) but never to filter retrieval.
            </p>
          </div>

          {/* Personalization rules (admin-only config) */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">Personalization Rules</h2>
              <button className="btn btn-primary btn-sm" onClick={() =>
                setRules((cur) => [...cur, { id: `r${cur.length + 1}`, name: "New rule", condition: "condition", behavior: "behavior" }])
              }>+ Add Rule</button>
            </div>
            {rules.map((r, i) => (
              <div key={r.id} className="actx-rule">
                <span className="actx-rule-num">{String(i + 1).padStart(2, "0")}</span>
                <div className="actx-rule-main">
                  <div className="actx-rule-name">{r.name}</div>
                  <div className="actx-rule-logic">
                    If <code>{r.condition}</code> → {r.behavior}
                  </div>
                </div>
                <div className="actx-rule-actions">
                  <button className="icon-action" aria-label="Edit rule" onClick={() => setToast("Edit rule (demo).")}><IconPencil /></button>
                  <button className="icon-action danger" aria-label="Delete rule" onClick={() => setRules((cur) => cur.filter((x) => x.id !== r.id))}><IconTrash /></button>
                </div>
              </div>
            ))}
          </div>

          <div className="actx-legend">
            <span><i style={{ background: "var(--ah-brand)" }} /> Retrieval filter</span>
            <span><i style={{ background: "var(--ah-secondary)" }} /> Context-only</span>
            <span><i style={{ background: "var(--ah-primary-tint)" }} /> Admin rule</span>
          </div>
        </div>

        {/* Test as student */}
        <div className="actx-rail">
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">✦ Test as Student</h2></div>
            <div className="field">
              <label className="field-label" htmlFor="ctx-student">Student profile</label>
              <select
                id="ctx-student"
                className="select"
                value={student.name}
                onChange={(e) => setStudent(STUDENTS.find((s) => s.name === e.target.value) ?? STUDENTS[0])}
              >
                {STUDENTS.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
              </select>
            </div>
            <div className="actx-test-profile">
              <span className="ah-chip">{student.program}</span>
              <span className="ah-chip neutral">Cohort {student.cohort}</span>
              <span className="ah-chip info">{student.lang}</span>
            </div>
            <div className="actx-test-out">
              <IconCheck size={13} /> Retrieved <strong>{preview.docs}</strong> document
              {preview.docs === 1 ? "" : "s"} using {preview.filters.length} active filter
              {preview.filters.length === 1 ? "" : "s"}.
            </div>
            <div className="actx-test-bubble">
              <IconChat size={13} /> Based on your {student.program} ({student.cohort}) profile, here&apos;s a
              personalized answer{student.lang !== "EN" ? " (translated to your preferred language)" : ""}.
            </div>
            <button className="btn btn-outline btn-sm" style={{ marginTop: 12 }} onClick={() => setToast("Ran test query (demo).")}>
              <IconSliders size={14} /> Run test query
            </button>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
