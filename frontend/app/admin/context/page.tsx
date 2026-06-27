"use client";

import { useMemo, useState } from "react";
import { Toast } from "@/components/ui/primitives";
import { IconCheck, IconSliders, IconChat } from "@/components/shell/icons";
import { usePortal } from "@/lib/portalI18n";

// Admin Context & Personalization (Phase 4, new route). Demo-only: configures which student-profile
// fields act as RETRIEVAL filters vs CONTEXT-ONLY personalization, plus admin personalization rules,
// with a "test as student" preview. No backend/API exists for this yet — state is local demo state,
// so nothing in the live data/API layer is touched.

// Colocated EN/VI copy so the top-bar language toggle localizes this whole screen. Reuses the shared
// `lang` from portalI18n's LanguageProvider — no new provider/context. Demo data (student names,
// programs, rule logic / code expressions, internal field keys) stays literal on purpose.
const STR = {
  en: {
    intro1: "Configure how student profile data influences Vinnie's answers. Retrieval filters narrow which",
    intro2: "documents Vinnie searches; context-only fields personalize tone & content without filtering.",
    retrievalTitle: "Retrieval Filters",
    contextTitle: "Context-Only Fields",
    rulesTitle: "Personalization Rules",
    active: (n: number) => `${n} active`,
    addField: "+ add field",
    addFieldToast: "Add field (demo).",
    retrievalHint:
      "These fields filter the knowledge base before answering — only matching documents are retrieved.",
    contextHint: "Used to personalize the answer (tone, examples) but never to filter retrieval.",
    addRule: "+ Add Rule",
    newRuleName: "New rule",
    newRuleCondition: "condition",
    newRuleBehavior: "behavior",
    ruleIf: "If",
    editRule: "Edit rule",
    deleteRule: "Delete rule",
    editRuleToast: "Edit rule (demo).",
    legendRetrieval: "Retrieval filter",
    legendContext: "Context-only",
    legendRule: "Admin rule",
    testTitle: "✦ Test as Student",
    studentProfile: "Student profile",
    cohort: (c: string) => `Cohort ${c}`,
    retrievedDoc: "Retrieved",
    retrievedDocSuffix: (docs: number, filters: number) =>
      `document${docs === 1 ? "" : "s"} using ${filters} active filter${filters === 1 ? "" : "s"}.`,
    bubblePrefix: (program: string, cohort: string) =>
      `Based on your ${program} (${cohort}) profile, here's a personalized answer`,
    bubbleTranslated: " (translated to your preferred language)",
    bubbleEnd: ".",
    runTest: "Run test query",
    runTestToast: "Ran test query (demo).",
  },
  vi: {
    intro1:
      "Cấu hình cách dữ liệu hồ sơ sinh viên ảnh hưởng đến câu trả lời của Vinnie. Bộ lọc truy xuất thu hẹp",
    intro2:
      "những tài liệu Vinnie tìm kiếm; trường chỉ dùng ngữ cảnh cá nhân hoá giọng văn & nội dung mà không lọc.",
    retrievalTitle: "Bộ lọc truy xuất",
    contextTitle: "Trường chỉ dùng ngữ cảnh",
    rulesTitle: "Quy tắc cá nhân hoá",
    active: (n: number) => `${n} đang bật`,
    addField: "+ thêm trường",
    addFieldToast: "Thêm trường (demo).",
    retrievalHint:
      "Các trường này lọc kho tri thức trước khi trả lời — chỉ những tài liệu khớp mới được truy xuất.",
    contextHint:
      "Dùng để cá nhân hoá câu trả lời (giọng văn, ví dụ) nhưng không bao giờ dùng để lọc truy xuất.",
    addRule: "+ Thêm quy tắc",
    newRuleName: "Quy tắc mới",
    newRuleCondition: "điều kiện",
    newRuleBehavior: "hành vi",
    ruleIf: "Nếu",
    editRule: "Sửa quy tắc",
    deleteRule: "Xoá quy tắc",
    editRuleToast: "Sửa quy tắc (demo).",
    legendRetrieval: "Bộ lọc truy xuất",
    legendContext: "Chỉ dùng ngữ cảnh",
    legendRule: "Quy tắc quản trị",
    testTitle: "✦ Kiểm tra như sinh viên",
    studentProfile: "Hồ sơ sinh viên",
    cohort: (c: string) => `Khoá ${c}`,
    retrievedDoc: "Đã truy xuất",
    retrievedDocSuffix: (docs: number, filters: number) =>
      `tài liệu bằng ${filters} bộ lọc đang bật.`,
    bubblePrefix: (program: string, cohort: string) =>
      `Dựa trên hồ sơ ${program} (${cohort}) của bạn, đây là câu trả lời cá nhân hoá`,
    bubbleTranslated: " (đã dịch sang ngôn ngữ ưa thích của bạn)",
    bubbleEnd: ".",
    runTest: "Chạy truy vấn kiểm tra",
    runTestToast: "Đã chạy truy vấn kiểm tra (demo).",
  },
} as const;

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
  const { lang } = usePortal();
  const s = STR[lang];
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
        {s.intro1} {s.intro2}
      </p>

      <div className="actx-grid">
        <div className="actx-main">
          {/* Retrieval filters */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{s.retrievalTitle}</h2>
              <span className="ah-chip">{s.active(retrievalActive)}</span>
            </div>
            <div className="actx-chips">
              {retrieval.map((f) => (
                <button key={f.key} className={`actx-chip ${f.active ? "on" : ""}`} onClick={() => toggle(setRetrieval)(f.key)}>
                  <span className="actx-chip-dot" />{f.key}
                </button>
              ))}
              <button className="actx-chip add" onClick={() => setToast(s.addFieldToast)}>{s.addField}</button>
            </div>
            <p className="field-hint" style={{ marginTop: 10 }}>
              {s.retrievalHint}
            </p>
          </div>

          {/* Context-only fields */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{s.contextTitle}</h2>
              <span className="ah-chip neutral">{s.active(contextActive)}</span>
            </div>
            <div className="actx-chips">
              {context.map((f) => (
                <button key={f.key} className={`actx-chip ctx ${f.active ? "on" : ""}`} onClick={() => toggle(setContext)(f.key)}>
                  <span className="actx-chip-dot" />{f.key}
                </button>
              ))}
            </div>
            <p className="field-hint" style={{ marginTop: 10 }}>
              {s.contextHint}
            </p>
          </div>

          {/* Personalization rules (admin-only config) */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{s.rulesTitle}</h2>
              <button className="btn btn-primary btn-sm" onClick={() =>
                setRules((cur) => [...cur, { id: `r${cur.length + 1}`, name: s.newRuleName, condition: s.newRuleCondition, behavior: s.newRuleBehavior }])
              }>{s.addRule}</button>
            </div>
            {rules.map((r, i) => (
              <div key={r.id} className="actx-rule">
                <span className="actx-rule-num">{String(i + 1).padStart(2, "0")}</span>
                <div className="actx-rule-main">
                  <div className="actx-rule-name">{r.name}</div>
                  <div className="actx-rule-logic">
                    {s.ruleIf} <code>{r.condition}</code> → {r.behavior}
                  </div>
                </div>
                <div className="actx-rule-actions">
                  <button className="icon-action" aria-label={s.editRule} onClick={() => setToast(s.editRuleToast)}><IconPencil /></button>
                  <button className="icon-action danger" aria-label={s.deleteRule} onClick={() => setRules((cur) => cur.filter((x) => x.id !== r.id))}><IconTrash /></button>
                </div>
              </div>
            ))}
          </div>

          <div className="actx-legend">
            <span><i style={{ background: "var(--ah-brand)" }} /> {s.legendRetrieval}</span>
            <span><i style={{ background: "var(--ah-secondary)" }} /> {s.legendContext}</span>
            <span><i style={{ background: "var(--ah-primary-tint)" }} /> {s.legendRule}</span>
          </div>
        </div>

        {/* Test as student */}
        <div className="actx-rail">
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{s.testTitle}</h2></div>
            <div className="field">
              <label className="field-label" htmlFor="ctx-student">{s.studentProfile}</label>
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
              <span className="ah-chip neutral">{s.cohort(student.cohort)}</span>
              <span className="ah-chip info">{student.lang}</span>
            </div>
            <div className="actx-test-out">
              <IconCheck size={13} /> {s.retrievedDoc} <strong>{preview.docs}</strong>{" "}
              {s.retrievedDocSuffix(preview.docs, preview.filters.length)}
            </div>
            <div className="actx-test-bubble">
              <IconChat size={13} /> {s.bubblePrefix(student.program, student.cohort)}
              {student.lang !== "EN" ? s.bubbleTranslated : ""}{s.bubbleEnd}
            </div>
            <button className="btn btn-outline btn-sm" style={{ marginTop: 12 }} onClick={() => setToast(s.runTestToast)}>
              <IconSliders size={14} /> {s.runTest}
            </button>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
