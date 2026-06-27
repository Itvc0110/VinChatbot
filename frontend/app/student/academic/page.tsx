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
  CurriculumProgressCourse,
  EligibleCourse,
} from "@/lib/api";

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
  completed: string;
  inProgress: string;
  failed: string;
  remainingRequired: string;
  remainingZeroCredit: string;
  eligible: string;
  blocked: string;
  none: string;
  prerequisite: string;
  corequisite: string;
  retakeImprove: string;
  signIn: string;
  studentOnly: string;
  noProfile: string;
  genericError: string;
  retry: string;
  loading: string;
  attemptedCredits: string;
  earnedCredits: string;
}> = {
  en: {
    title: "Academic Record",
    subtitle: "Your transcript, curriculum progress, and next-course eligibility.",
    transcript: "Transcript",
    curriculum: "Curriculum Progress",
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
    completed: "Completed",
    inProgress: "In progress",
    failed: "Failed",
    remainingRequired: "Remaining required",
    remainingZeroCredit: "Remaining 0-credit requirements",
    eligible: "Eligible to take",
    blocked: "Blocked",
    none: "None",
    prerequisite: "Prerequisite",
    corequisite: "Corequisite",
    retakeImprove: "Retake / improvement",
    signIn: "Please sign in to view your academic record.",
    studentOnly: "This page is available to students only.",
    noProfile: "No academic profile is linked to your account yet.",
    genericError: "Couldn't load your academic record.",
    retry: "Retry",
    loading: "Loading…",
    attemptedCredits: "Attempted credits",
    earnedCredits: "Earned credits",
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
    completed: "Đã hoàn thành",
    inProgress: "Đang học",
    failed: "Chưa đạt",
    remainingRequired: "Bắt buộc còn lại",
    remainingZeroCredit: "Yêu cầu 0 tín chỉ còn lại",
    eligible: "Có thể đăng ký",
    blocked: "Bị chặn",
    none: "Không có",
    prerequisite: "Tiên quyết",
    corequisite: "Song hành",
    retakeImprove: "Học lại / cải thiện",
    signIn: "Vui lòng đăng nhập để xem kết quả học tập.",
    studentOnly: "Trang này chỉ dành cho sinh viên.",
    noProfile: "Tài khoản của bạn chưa được liên kết hồ sơ học vụ.",
    genericError: "Không tải được kết quả học tập.",
    retry: "Thử lại",
    loading: "Đang tải…",
    attemptedCredits: "Tín chỉ đã học",
    earnedCredits: "Tín chỉ đạt",
  },
};

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

      {/* Transcript */}
      <Card>
        <div className="dash-section-head">
          <h2 className="dash-section-title">{s.transcript}</h2>
        </div>
        {transcript.status === "loading" ? (
          <p className="rail-empty" style={{ margin: 0 }}>{s.loading}</p>
        ) : transcript.status === "error" ? (
          <SectionError code={transcript.code} detail={transcript.message} s={s} onRetry={transcript.reload} />
        ) : transcript.data.terms.length === 0 ? (
          <p className="rail-empty" style={{ margin: 0 }}>{s.none}</p>
        ) : (
          <TranscriptView data={transcript.data} s={s} />
        )}
      </Card>

      {/* Curriculum progress */}
      <Card>
        <div className="dash-section-head">
          <h2 className="dash-section-title">{s.curriculum}</h2>
        </div>
        {curriculum.status === "loading" ? (
          <p className="rail-empty" style={{ margin: 0 }}>{s.loading}</p>
        ) : curriculum.status === "error" ? (
          <SectionError code={curriculum.code} detail={curriculum.message} s={s} onRetry={curriculum.reload} />
        ) : (
          <CurriculumView data={curriculum.data} s={s} />
        )}
      </Card>

      {/* Eligibility */}
      <Card>
        <div className="dash-section-head">
          <h2 className="dash-section-title">{s.eligibility}</h2>
        </div>
        {eligibility.status === "loading" ? (
          <p className="rail-empty" style={{ margin: 0 }}>{s.loading}</p>
        ) : eligibility.status === "error" ? (
          <SectionError code={eligibility.code} detail={eligibility.message} s={s} onRetry={eligibility.reload} />
        ) : (
          <EligibilityView data={eligibility.data} s={s} />
        )}
      </Card>
    </div>
  );
}

function TranscriptView({ data, s }: { data: AcademicTranscript; s: (typeof STR)[Lang] }) {
  return (
    <div className="academic-terms">
      <div className="profile-card-grid" style={{ marginBottom: 16 }}>
        <Field k={s.attemptedCredits} v={String(data.summary.attempted_credits)} />
        <Field k={s.earnedCredits} v={String(data.summary.earned_credits)} />
        <Field k={s.cumulativeCpa} v={data.summary.gpa ?? "—"} />
      </div>
      {data.terms.map((term) => (
        <div key={term.term.id} style={{ marginBottom: 20 }}>
          <div className="dash-section-head">
            <h3 className="dash-section-title" style={{ fontSize: 15 }}>
              {term.term.name}
            </h3>
            <span className="profile-field-v" style={{ fontSize: 13 }}>
              {s.termGpa}: {term.term_gpa ?? "—"} · {s.cumulativeCpa}: {term.cumulative_cpa ?? "—"}
            </span>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="academic-table" style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={th}>{s.course}</th>
                  <th style={th}>{s.credits}</th>
                  <th style={th}>{s.attempt}</th>
                  <th style={th}>{s.grade10}</th>
                  <th style={th}>{s.grade4}</th>
                  <th style={th}>{s.letter}</th>
                  <th style={th}>{s.result}</th>
                </tr>
              </thead>
              <tbody>
                {term.enrollments.map((e) => (
                  <EnrollmentRow key={e.id} e={e} s={s} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

function EnrollmentRow({ e, s }: { e: AcademicEnrollment; s: (typeof STR)[Lang] }) {
  return (
    <tr>
      <td style={td}>
        <strong>{e.course.code}</strong> {e.course.name}
      </td>
      <td style={td}>{e.course.credits}</td>
      <td style={td}>{e.attempt_no}</td>
      <td style={td}>{e.grade_10 ?? "—"}</td>
      <td style={td}>{e.grade_4 ?? "—"}</td>
      <td style={td}>{e.letter_grade ?? "—"}</td>
      <td style={td}>
        <span className={`ah-chip ${e.passed ? "success" : "warning"}`}>
          {e.passed ? s.passed : s.notPassed}
        </span>
      </td>
    </tr>
  );
}

function CurriculumView({ data, s }: { data: AcademicCurriculumProgress; s: (typeof STR)[Lang] }) {
  const buckets: { label: string; items: CurriculumProgressCourse[]; tone: string }[] = [
    { label: s.completed, items: data.completed, tone: "success" },
    { label: s.inProgress, items: data.in_progress, tone: "info" },
    { label: s.failed, items: data.failed, tone: "warning" },
    { label: s.remainingRequired, items: data.remaining_required, tone: "neutral" },
    { label: s.remainingZeroCredit, items: data.remaining_zero_credit, tone: "neutral" },
  ];
  return (
    <div>
      {buckets.map((b) => (
        <div key={b.label} style={{ marginBottom: 14 }}>
          <div className="profile-field-k" style={{ marginBottom: 8 }}>
            {b.label} ({b.items.length})
          </div>
          {b.items.length === 0 ? (
            <p className="rail-empty" style={{ margin: 0 }}>{s.none}</p>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {b.items.map((c) => (
                <span key={c.course.id} className={`ah-chip ${b.tone}`} title={c.course.name}>
                  {c.course.code}
                  {c.grade_4 ? ` · ${c.grade_4}` : ""}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function EligibilityView({ data, s }: { data: AcademicEligibility; s: (typeof STR)[Lang] }) {
  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div className="profile-field-k" style={{ marginBottom: 8 }}>
          {s.eligible} ({data.eligible.length})
        </div>
        {data.eligible.length === 0 ? (
          <p className="rail-empty" style={{ margin: 0 }}>{s.none}</p>
        ) : (
          <div className="dash-list">
            {data.eligible.map((c) => (
              <EligibleRow key={c.course.id} c={c} s={s} />
            ))}
          </div>
        )}
      </div>
      <div>
        <div className="profile-field-k" style={{ marginBottom: 8 }}>
          {s.blocked} ({data.blocked.length})
        </div>
        {data.blocked.length === 0 ? (
          <p className="rail-empty" style={{ margin: 0 }}>{s.none}</p>
        ) : (
          <div className="dash-list">
            {data.blocked.map((c) => (
              <EligibleRow key={c.course.id} c={c} s={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EligibleRow({ c, s }: { c: EligibleCourse; s: (typeof STR)[Lang] }) {
  return (
    <div className="dash-ticket-card" style={{ cursor: "default", alignItems: "flex-start" }}>
      <div className="dash-ticket-main">
        <div className="dash-ticket-title">
          {c.course.code} {c.course.name}
          {c.can_retake_or_improve && (
            <span className="ah-chip info" style={{ marginLeft: 8 }}>{s.retakeImprove}</span>
          )}
        </div>
        {c.blocking_reasons.length > 0 && (
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {c.blocking_reasons.map((reason, i) => (
              <li key={i} className="dash-ticket-desc" style={{ margin: 0 }}>
                {reason}
              </li>
            ))}
          </ul>
        )}
        {(c.prerequisites.length > 0 || c.corequisites.length > 0) && (
          <div className="dash-ticket-time" style={{ marginTop: 6 }}>
            {c.prerequisites.map((r) => (
              <div key={`pre-${r.required_course.id}`}>
                {s.prerequisite}: {r.required_course.code} — {r.satisfied ? "✓" : "✗"}
              </div>
            ))}
            {c.corequisites.map((r) => (
              <div key={`co-${r.required_course.id}`}>
                {s.corequisite}: {r.required_course.code} — {r.satisfied ? "✓" : "✗"}
              </div>
            ))}
          </div>
        )}
      </div>
      <span className={`ah-chip ${c.eligible ? "success" : "warning"}`}>
        {c.eligible ? s.eligible : s.blocked}
      </span>
    </div>
  );
}

function Field({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="profile-field-k">{k}</div>
      <div className="profile-field-v">{v}</div>
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 10px",
  fontSize: 12,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  opacity: 0.7,
  borderBottom: "1px solid var(--border, rgba(0,0,0,0.1))",
};
const td: React.CSSProperties = {
  padding: "8px 10px",
  fontSize: 14,
  borderBottom: "1px solid var(--border, rgba(0,0,0,0.06))",
};
