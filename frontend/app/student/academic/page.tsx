"use client";

import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import {
  ApiError,
  getAcademicTranscript,
  getAcademicCurriculum,
  getEligibleCourses,
} from "@/lib/api";
import type {
  AcademicCurriculumProgress,
  AcademicEligibility,
  AcademicEnrollment,
  AcademicTranscript,
  AcademicTranscriptTerm,
  CurriculumProgressCourse,
  EligibleCourse,
} from "@/lib/api";
import { IconChart, IconCheck, IconCap, IconAlert } from "@/components/shell/icons";

type Lang = "en" | "vi";

// Status-aware async state: unlike the shared useAsync, this keeps the HTTP status code so the
// page can show distinct 401 / 403 / 404 messages for the academic endpoints.
type Resource<T> =
  | { status: "loading" }
  | { status: "error"; code: number | null; message: string }
  | { status: "success"; data: T };

function useResource<T>(fetcher: () => Promise<T>, deps: unknown[]): Resource<T> & { reload: () => void } {
  const [state, setState] = useState<Resource<T>>({ status: "loading" });
  const run = useCallback(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const code = err instanceof ApiError ? err.status : null;
        const message = err instanceof Error ? err.message : "Request failed.";
        setState({ status: "error", code, message });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => run(), [run]);
  return { ...state, reload: () => run() } as Resource<T> & { reload: () => void };
}

const MAX_CHIPS = 12; // chips shown per curriculum group before collapsing into "+N more"

const STR: Record<Lang, {
  title: string;
  subtitle: string;
  transcript: string;
  curriculum: string;
  eligibility: string;
  termGpa: string;
  cumulativeCpa: string;
  course: string;
  credits: string;
  attempt: string;
  grade10: string;
  grade4: string;
  letter: string;
  result: string;
  passed: string;
  notPassed: string;
  inProgressStatus: string;
  noGrade: string;
  withdrawn: string;
  completed: string;
  inProgress: string;
  failed: string;
  remainingRequired: string;
  remainingZeroCredit: string;
  eligible: string;
  eligibleStatus: string;
  blocked: string;
  none: string;
  required: string;
  retakeImprove: string;
  signIn: string;
  studentOnly: string;
  noProfile: string;
  genericError: string;
  retry: string;
  loading: string;
  // summary
  sumCpa: string;
  sumCredits: string;
  sumStudying: string;
  sumAttention: string;
  coursesUnit: (n: number) => string;
  attentionDetail: (failed: number, blocked: number) => string;
  allClear: string;
  // progress
  creditsLabel: string;
  requiredLabel: string;
  requiredBreakdown: (done: number, prog: number, remaining: number) => string;
  creditsPassedInTerm: (n: number) => string;
  failedCount: (n: number) => string;
  moreCount: (n: number) => string;
  // eligibility
  missingPrereq: string;
  needCoreq: string;
  blockedReason: string;
  needGradeLine: (code: string, name: string, grade: string | null) => string;
}> = {
  en: {
    title: "Academic Record",
    subtitle: "Your transcript, curriculum progress, and next-course eligibility.",
    transcript: "Transcript",
    curriculum: "Program Progress",
    eligibility: "Course Eligibility",
    termGpa: "Term GPA",
    cumulativeCpa: "Cumulative CPA",
    course: "Course",
    credits: "Credits",
    attempt: "Attempt",
    grade10: "Grade (10)",
    grade4: "Grade (4)",
    letter: "Letter",
    result: "Result",
    passed: "Passed",
    notPassed: "Not passed",
    inProgressStatus: "In progress",
    noGrade: "No grade yet",
    withdrawn: "Withdrawn",
    completed: "Completed",
    inProgress: "In progress",
    failed: "Not passed",
    remainingRequired: "Required remaining",
    remainingZeroCredit: "Remaining 0-credit requirements",
    eligible: "Eligible",
    eligibleStatus: "Eligible",
    blocked: "Blocked",
    none: "None",
    required: "Required",
    retakeImprove: "Retake / improvement",
    signIn: "Please sign in to view your academic record.",
    studentOnly: "This page is available to students only.",
    noProfile: "No academic profile is linked to your account yet.",
    genericError: "Couldn't load your academic record.",
    retry: "Retry",
    loading: "Loading…",
    sumCpa: "Cumulative CPA",
    sumCredits: "Credits passed",
    sumStudying: "Currently studying",
    sumAttention: "Needs attention",
    coursesUnit: (n) => `${n} course${n === 1 ? "" : "s"}`,
    attentionDetail: (f, b) => `${f} not passed · ${b} blocked`,
    allClear: "All clear",
    creditsLabel: "Credits",
    requiredLabel: "Required courses",
    requiredBreakdown: (done, prog, remaining) =>
      `${done} completed · ${prog} in progress · ${remaining} remaining`,
    creditsPassedInTerm: (n) => `${n} credits passed`,
    failedCount: (n) => `${n} not passed`,
    moreCount: (n) => `+${n} more`,
    missingPrereq: "Missing prerequisite:",
    needCoreq: "Must be taken alongside:",
    blockedReason: "Why this is blocked:",
    needGradeLine: (code, name, grade) =>
      `Pass ${code} ${name}${grade ? ` with at least ${grade} on the 4.0 scale` : ""}.`,
  },
  vi: {
    title: "Kết quả học tập",
    subtitle: "Bảng điểm, tiến độ chương trình và điều kiện học môn tiếp theo.",
    transcript: "Bảng điểm",
    curriculum: "Tiến độ chương trình",
    eligibility: "Điều kiện đăng ký môn",
    termGpa: "GPA học kỳ",
    cumulativeCpa: "CPA tích lũy",
    course: "Môn học",
    credits: "Tín chỉ",
    attempt: "Lần thi",
    grade10: "Điểm (10)",
    grade4: "Điểm (4)",
    letter: "Điểm chữ",
    result: "Kết quả",
    passed: "Đạt",
    notPassed: "Chưa đạt",
    inProgressStatus: "Đang học",
    noGrade: "Chưa có điểm",
    withdrawn: "Đã rút",
    completed: "Đã hoàn thành",
    inProgress: "Đang học",
    failed: "Chưa đạt",
    remainingRequired: "Bắt buộc còn lại",
    remainingZeroCredit: "Yêu cầu 0 tín chỉ còn lại",
    eligible: "Đủ điều kiện",
    eligibleStatus: "Đủ điều kiện",
    blocked: "Bị chặn",
    none: "Không có",
    required: "Bắt buộc",
    retakeImprove: "Học lại / cải thiện",
    signIn: "Vui lòng đăng nhập để xem kết quả học tập.",
    studentOnly: "Trang này chỉ dành cho sinh viên.",
    noProfile: "Tài khoản của bạn chưa được liên kết hồ sơ học vụ.",
    genericError: "Không tải được kết quả học tập.",
    retry: "Thử lại",
    loading: "Đang tải…",
    sumCpa: "CPA tích lũy",
    sumCredits: "Tín chỉ đã đạt",
    sumStudying: "Đang học",
    sumAttention: "Cần chú ý",
    coursesUnit: (n) => `${n} môn`,
    attentionDetail: (f, b) => `${f} môn chưa đạt · ${b} môn bị chặn`,
    allClear: "Không có",
    creditsLabel: "Tín chỉ",
    requiredLabel: "Môn bắt buộc",
    requiredBreakdown: (done, prog, remaining) =>
      `${done} hoàn thành · ${prog} đang học · ${remaining} còn lại`,
    creditsPassedInTerm: (n) => `${n} tín chỉ đạt`,
    failedCount: (n) => `${n} chưa đạt`,
    moreCount: (n) => `+${n} môn`,
    missingPrereq: "Thiếu điều kiện tiên quyết:",
    needCoreq: "Cần học song hành:",
    blockedReason: "Lý do bị chặn:",
    needGradeLine: (code, name, grade) =>
      `Cần đạt ${code} ${name}${grade ? ` với điểm tối thiểu ${grade} hệ 4` : ""}.`,
  },
};

// ---- Helpers ---------------------------------------------------------------

// A row's display status from the backend enrollment status (conservative: a missing grade is
// NEVER shown as failed — only an explicit `failed` status, or `completed` that didn't pass).
type RowStatus = "passed" | "failed" | "in_progress" | "no_grade" | "withdrawn";
function rowStatus(e: AcademicEnrollment): RowStatus {
  switch (e.status) {
    case "withdrawn":
      return "withdrawn";
    case "failed":
      return "failed";
    case "completed":
      return e.passed ? "passed" : "failed";
    case "enrolled":
    case "retaking":
    case "improvement":
      return "in_progress";
    case "planned":
      return "no_grade";
    default:
      // Defensive fallback for unexpected statuses — still never guess "failed".
      if (e.passed) return "passed";
      if (e.grade_4 == null && e.letter_grade == null) return "no_grade";
      return "in_progress";
  }
}

const STATUS_TONE: Record<RowStatus, string> = {
  passed: "success",
  failed: "error",
  in_progress: "info",
  no_grade: "neutral",
  withdrawn: "neutral",
};
function statusLabel(st: RowStatus, s: (typeof STR)[Lang]): string {
  switch (st) {
    case "passed":
      return s.passed;
    case "failed":
      return s.notPassed;
    case "in_progress":
      return s.inProgressStatus;
    case "no_grade":
      return s.noGrade;
    case "withdrawn":
      return s.withdrawn;
  }
}

// Localize a backend term name ("Fall Term 2025") to Vietnamese ("Học kỳ Thu 2025"). Leaves the
// English string untouched for `en` and when the season pattern isn't recognized.
const SEASON_VI: Record<string, string> = {
  fall: "Thu",
  autumn: "Thu",
  spring: "Xuân",
  summer: "Hè",
  winter: "Đông",
};
function localizeTerm(name: string, lang: Lang): string {
  if (lang !== "vi" || !name) return name;
  const m = name.match(/(fall|autumn|spring|summer|winter)\s*(?:term)?\s*(\d{4})/i);
  if (m) return `Học kỳ ${SEASON_VI[m[1].toLowerCase()]} ${m[2]}`;
  return name;
}

// Index of the most recent term (highest academic_year, then term_order) — opened by default.
function latestTermId(terms: AcademicTranscriptTerm[]): string | null {
  if (terms.length === 0) return null;
  let best = terms[0];
  for (const t of terms) {
    const key = t.term.academic_year * 100 + t.term.term_order;
    const bestKey = best.term.academic_year * 100 + best.term.term_order;
    if (key >= bestKey) best = t;
  }
  return best.term.id;
}

function errorMessage(code: number | null, detail: string, s: (typeof STR)[Lang]): string {
  if (code === 401) return s.signIn;
  if (code === 403) return s.studentOnly;
  if (code === 404) return s.noProfile;
  return detail || s.genericError;
}

function SectionError({
  code,
  detail,
  s,
  onRetry,
}: {
  code: number | null;
  detail: string;
  s: (typeof STR)[Lang];
  onRetry: () => void;
}) {
  return (
    <div className="load-error" role="alert">
      <p>{errorMessage(code, detail, s)}</p>
      <button className="btn btn-outline" onClick={onRetry}>
        {s.retry}
      </button>
    </div>
  );
}

export default function StudentAcademicPage() {
  const { lang } = usePortal();
  const { token } = useAuth();
  const s = STR[lang];

  const transcript = useResource<AcademicTranscript>(() => getAcademicTranscript(), [token]);
  const curriculum = useResource<AcademicCurriculumProgress>(() => getAcademicCurriculum(), [token]);
  const eligibility = useResource<AcademicEligibility>(() => getEligibleCourses(), [token]);

  return (
    <div className="page-inner">
      <div className="ah-pagehead">
        <div>
          <h1 className="ah-pagehead-title">{s.title}</h1>
          <p className="ah-pagehead-sub">{s.subtitle}</p>
        </div>
      </div>

      <AcademicSummary transcript={transcript} curriculum={curriculum} eligibility={eligibility} s={s} />

      {/* Section navigation (anchor pills) */}
      <nav className="acad-nav" aria-label={s.title}>
        <a className="acad-nav-link" href="#acad-transcript">{s.transcript}</a>
        <a className="acad-nav-link" href="#acad-curriculum">{s.curriculum}</a>
        <a className="acad-nav-link" href="#acad-eligibility">{s.eligibility}</a>
      </nav>

      {/* Transcript */}
      <Card className="acad-section" id="acad-transcript">
        <div className="dash-section-head">
          <h2 className="dash-section-title">{s.transcript}</h2>
        </div>
        {transcript.status === "loading" ? (
          <p className="rail-empty">{s.loading}</p>
        ) : transcript.status === "error" ? (
          <SectionError code={transcript.code} detail={transcript.message} s={s} onRetry={transcript.reload} />
        ) : transcript.data.terms.length === 0 ? (
          <p className="rail-empty">{s.none}</p>
        ) : (
          <TranscriptView data={transcript.data} s={s} lang={lang} />
        )}
      </Card>

      {/* Curriculum progress */}
      <Card className="acad-section" id="acad-curriculum">
        <div className="dash-section-head">
          <h2 className="dash-section-title">{s.curriculum}</h2>
        </div>
        {curriculum.status === "loading" ? (
          <p className="rail-empty">{s.loading}</p>
        ) : curriculum.status === "error" ? (
          <SectionError code={curriculum.code} detail={curriculum.message} s={s} onRetry={curriculum.reload} />
        ) : (
          <CurriculumView data={curriculum.data} s={s} />
        )}
      </Card>

      {/* Eligibility */}
      <Card className="acad-section" id="acad-eligibility">
        <div className="dash-section-head">
          <h2 className="dash-section-title">{s.eligibility}</h2>
        </div>
        {eligibility.status === "loading" ? (
          <p className="rail-empty">{s.loading}</p>
        ) : eligibility.status === "error" ? (
          <SectionError code={eligibility.code} detail={eligibility.message} s={s} onRetry={eligibility.reload} />
        ) : (
          <EligibilityView data={eligibility.data} s={s} />
        )}
      </Card>
    </div>
  );
}

// ---- Academic Summary (KPI tiles) ------------------------------------------

function AcademicSummary({
  transcript,
  curriculum,
  eligibility,
  s,
}: {
  transcript: Resource<AcademicTranscript>;
  curriculum: Resource<AcademicCurriculumProgress>;
  eligibility: Resource<AcademicEligibility>;
  s: (typeof STR)[Lang];
}) {
  const t = transcript.status === "success" ? transcript.data : null;
  const c = curriculum.status === "success" ? curriculum.data : null;
  const e = eligibility.status === "success" ? eligibility.data : null;

  const ph = (r: Resource<unknown>) => (r.status === "loading" ? "…" : "—");

  const cpa = t ? t.summary.gpa ?? "—" : ph(transcript);
  const credits = c
    ? `${c.summary.earned_credits} / ${c.summary.required_credits}`
    : t
    ? String(t.summary.earned_credits)
    : ph(curriculum);
  const studyingValue = c ? String(c.in_progress.length) : ph(curriculum);
  const studyingDetail = c ? s.coursesUnit(c.in_progress.length) : "";

  const failed = c?.failed.length ?? 0;
  const blocked = e?.blocked.length ?? 0;
  const attentionKnown = c !== null || e !== null;
  const attentionValue = attentionKnown ? String(failed + blocked) : ph(curriculum);
  const attentionDetail = attentionKnown
    ? failed + blocked === 0
      ? s.allClear
      : s.attentionDetail(failed, blocked)
    : "";

  return (
    <section className="acad-summary" aria-label={s.title}>
      <KpiTile icon={<IconChart size={18} />} label={s.sumCpa} value={cpa} />
      <KpiTile icon={<IconCheck size={18} />} label={s.sumCredits} value={credits} />
      <KpiTile icon={<IconCap size={18} />} label={s.sumStudying} value={studyingValue} detail={studyingDetail} />
      <KpiTile
        icon={<IconAlert size={18} />}
        label={s.sumAttention}
        value={attentionValue}
        detail={attentionDetail}
        tone={failed + blocked > 0 ? "alert" : undefined}
      />
    </section>
  );
}

function KpiTile({
  icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail?: string;
  tone?: "alert";
}) {
  return (
    <div className="focus-card focus-card--static">
      <span className={`focus-icon ${tone === "alert" ? "acad-icon-alert" : ""}`}>{icon}</span>
      <div className="focus-body">
        <div className="focus-label">{label}</div>
        <div className="acad-kpi-value">{value}</div>
        {detail && <div className="acad-kpi-detail">{detail}</div>}
      </div>
    </div>
  );
}

// ---- Transcript ------------------------------------------------------------

function TranscriptView({ data, s, lang }: { data: AcademicTranscript; s: (typeof STR)[Lang]; lang: Lang }) {
  const latestId = latestTermId(data.terms);
  return (
    <div className="academic-terms">
      {data.terms.map((term) => (
        <TermBlock key={term.term.id} term={term} s={s} lang={lang} open={term.term.id === latestId} />
      ))}
    </div>
  );
}

function TermBlock({
  term,
  s,
  lang,
  open,
}: {
  term: AcademicTranscriptTerm;
  s: (typeof STR)[Lang];
  lang: Lang;
  open: boolean;
}) {
  const passedCredits = term.enrollments.reduce((sum, e) => sum + (e.earned_credits || 0), 0);
  const failedCount = term.enrollments.filter((e) => rowStatus(e) === "failed").length;

  return (
    <details className="acad-term" open={open}>
      <summary className="acad-term-summary">
        <span className="acad-term-title">{localizeTerm(term.term.name, lang)}</span>
        <span className="acad-term-meta">
          <span>
            {s.termGpa} <b>{term.term_gpa ?? "—"}</b>
          </span>
          <span>
            {s.cumulativeCpa} <b>{term.cumulative_cpa ?? "—"}</b>
          </span>
          <span>{s.creditsPassedInTerm(passedCredits)}</span>
          {failedCount > 0 && <span className="ah-chip error">{s.failedCount(failedCount)}</span>}
          <svg className="acad-term-caret" viewBox="0 0 24 24" width="16" height="16" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            aria-hidden="true">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </span>
      </summary>
      <div className="acad-table-wrap">
        <table className="acad-table">
          <thead>
            <tr>
              <th>{s.course}</th>
              <th className="num">{s.credits}</th>
              <th className="num">{s.attempt}</th>
              <th className="num">{s.grade10}</th>
              <th className="num">{s.grade4}</th>
              <th>{s.letter}</th>
              <th>{s.result}</th>
            </tr>
          </thead>
          <tbody>
            {term.enrollments.map((e) => {
              const st = rowStatus(e);
              return (
                <tr key={e.id}>
                  <td>
                    <span className="acad-course-code">{e.course.code}</span>{" "}
                    <span className="acad-course-name">{e.course.name}</span>
                  </td>
                  <td className="num">{e.course.credits}</td>
                  <td className="num">{e.attempt_no}</td>
                  <td className="num">{e.grade_10 ?? "—"}</td>
                  <td className="num">{e.grade_4 ?? "—"}</td>
                  <td>{e.letter_grade ?? "—"}</td>
                  <td>
                    <span className={`ah-chip ${STATUS_TONE[st]}`}>{statusLabel(st, s)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ---- Curriculum / Program Progress -----------------------------------------

function CurriculumView({ data, s }: { data: AcademicCurriculumProgress; s: (typeof STR)[Lang] }) {
  const pct = Math.max(0, Math.min(100, Number(data.summary.progress_percent) || 0));
  const completed = data.completed.length;
  const inProgress = data.in_progress.length;
  const remaining = data.summary.remaining_required_courses;

  const groups: { label: string; items: CurriculumProgressCourse[]; tone: string }[] = [
    { label: s.completed, items: data.completed, tone: "success" },
    { label: s.inProgress, items: data.in_progress, tone: "info" },
    { label: s.failed, items: data.failed, tone: "error" },
    { label: s.remainingRequired, items: data.remaining_required, tone: "neutral" },
  ];
  if (data.remaining_zero_credit.length > 0) {
    groups.push({ label: s.remainingZeroCredit, items: data.remaining_zero_credit, tone: "neutral" });
  }

  return (
    <div className="acad-progress">
      <div className="acad-progress-top">
        <div className="snapshot-progress-meta">
          <span className="profile-field-k">{s.creditsLabel}</span>
          <span className="profile-field-v">
            {data.summary.earned_credits} / {data.summary.required_credits} · {pct}%
          </span>
        </div>
        <div className="academic-progress-bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className="academic-progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="acad-required-line">
          <span className="profile-field-k">{s.requiredLabel}</span>
          <span className="acad-required-detail">{s.requiredBreakdown(completed, inProgress, remaining)}</span>
        </div>
      </div>

      <div className="acad-chip-groups">
        {groups.map((g) => (
          <ChipGroup key={g.label} label={g.label} items={g.items} tone={g.tone} s={s} />
        ))}
      </div>
    </div>
  );
}

function ChipGroup({
  label,
  items,
  tone,
  s,
}: {
  label: string;
  items: CurriculumProgressCourse[];
  tone: string;
  s: (typeof STR)[Lang];
}) {
  const shown = items.slice(0, MAX_CHIPS);
  const extra = items.length - shown.length;
  return (
    <div className="acad-chip-group">
      <div className="acad-chip-group-label">
        {label} <span className="acad-chip-count">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="rail-empty">{s.none}</p>
      ) : (
        <div className="chip-row">
          {shown.map((c) => (
            <span key={c.course.id} className={`ah-chip ${tone}`} title={c.course.name}>
              {c.course.code}
              {c.grade_4 ? ` · ${c.grade_4}` : ""}
            </span>
          ))}
          {extra > 0 && <span className="ah-chip neutral chip-more">{s.moreCount(extra)}</span>}
        </div>
      )}
    </div>
  );
}

// ---- Course Eligibility ----------------------------------------------------

function EligibilityView({ data, s }: { data: AcademicEligibility; s: (typeof STR)[Lang] }) {
  return (
    <div className="acad-elig">
      <div className="acad-elig-block">
        <div className="acad-chip-group-label">
          {s.eligible} <span className="acad-chip-count">{data.eligible.length}</span>
        </div>
        {data.eligible.length === 0 ? (
          <p className="rail-empty">{s.none}</p>
        ) : (
          <div className="acad-elig-grid">
            {data.eligible.map((c) => (
              <EligibleCard key={c.course.id} c={c} s={s} />
            ))}
          </div>
        )}
      </div>

      <div className="acad-elig-block">
        <div className="acad-chip-group-label">
          {s.blocked} <span className="acad-chip-count">{data.blocked.length}</span>
        </div>
        {data.blocked.length === 0 ? (
          <p className="rail-empty">{s.none}</p>
        ) : (
          <div className="acad-elig-grid">
            {data.blocked.map((c) => (
              <BlockedCard key={c.course.id} c={c} s={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EligibleCard({ c, s }: { c: EligibleCourse; s: (typeof STR)[Lang] }) {
  return (
    <div className="acad-elig-card">
      <div className="acad-elig-head">
        <div className="acad-elig-title">
          <span className="acad-course-code">{c.course.code}</span>{" "}
          <span className="acad-course-name">{c.course.name}</span>
        </div>
        <span className="ah-chip success">{s.eligibleStatus}</span>
      </div>
      <div className="acad-elig-tags">
        {c.is_required && <span className="ah-chip neutral">{s.required}</span>}
        {c.can_retake_or_improve && <span className="ah-chip info">{s.retakeImprove}</span>}
      </div>
    </div>
  );
}

function BlockedCard({ c, s }: { c: EligibleCourse; s: (typeof STR)[Lang] }) {
  const unmetPre = c.prerequisites.filter((r) => !r.satisfied);
  const unmetCo = c.corequisites.filter((r) => !r.satisfied);

  let heading: string | null = null;
  let lines: string[] = [];
  if (unmetPre.length > 0) {
    heading = s.missingPrereq;
    lines = unmetPre.map((r) => s.needGradeLine(r.required_course.code, r.required_course.name, r.min_grade_4 ?? null));
  } else if (unmetCo.length > 0) {
    heading = s.needCoreq;
    lines = unmetCo.map((r) => `${r.required_course.code} ${r.required_course.name}`);
  } else if (c.blocking_reasons.length > 0) {
    // Fall back to the backend-provided reason text (preserved verbatim).
    heading = s.blockedReason;
    lines = c.blocking_reasons;
  }

  return (
    <div className="acad-elig-card">
      <div className="acad-elig-head">
        <div className="acad-elig-title">
          <span className="acad-course-code">{c.course.code}</span>{" "}
          <span className="acad-course-name">{c.course.name}</span>
        </div>
        <span className="ah-chip error">{s.blocked}</span>
      </div>
      {heading && (
        <div className="acad-reason">
          <div className="acad-reason-head">{heading}</div>
          {lines.map((line, i) => (
            <div key={i} className="acad-reason-line">{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}
