"use client";

import Link from "next/link";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getAnalytics, getAdminStats, getKnowledgeSources, getUnansweredQuestions } from "@/lib/api";
import {
  IconChat,
  IconShield,
  IconChart,
  IconAlert,
  IconArrow,
  IconDatabase,
  IconCheck,
} from "@/components/shell/icons";

const STR = {
  en: {
    totalQuestions7d: "Total questions (7d)",
    verifiedRate: "Verified rate",
    avgConfidence: "Avg confidence",
    lowConfidenceAnswers: "Low-confidence answers",
    lowConfidenceHeader: "Low-Confidence Answers",
    reviewQueue: "Review queue",
    noLowConfidence: "No low-confidence answers flagged. 🎉",
    asked: "asked",
    review: "Review",
    missingCitations: "Missing Citations",
    noMissingCitations: "No answers missing citations.",
    noVerifiedSource: "No verified source cited · suggested:",
    linkSource: "Link source",
    mostAskedTopics: "Most Asked Topics",
    sourceUsage: "Source Usage",
    noSources: "No sources yet.",
    studentFeedback: "Student Feedback",
    feedbackHint: "Derived from answer confidence & verified rate (demo).",
  },
  vi: {
    totalQuestions7d: "Tổng câu hỏi (7 ngày)",
    verifiedRate: "Tỉ lệ đã xác minh",
    avgConfidence: "Độ tin cậy trung bình",
    lowConfidenceAnswers: "Câu trả lời độ tin cậy thấp",
    lowConfidenceHeader: "Câu trả lời độ tin cậy thấp",
    reviewQueue: "Hàng đợi rà soát",
    noLowConfidence: "Không có câu trả lời nào bị gắn cờ độ tin cậy thấp. 🎉",
    asked: "lượt hỏi",
    review: "Rà soát",
    missingCitations: "Thiếu trích dẫn",
    noMissingCitations: "Không có câu trả lời nào thiếu trích dẫn.",
    noVerifiedSource: "Chưa trích dẫn nguồn đã xác minh · gợi ý:",
    linkSource: "Liên kết nguồn",
    mostAskedTopics: "Chủ đề được hỏi nhiều nhất",
    sourceUsage: "Mức sử dụng nguồn",
    noSources: "Chưa có nguồn nào.",
    studentFeedback: "Phản hồi sinh viên",
    feedbackHint: "Tính từ độ tin cậy câu trả lời & tỉ lệ đã xác minh (demo).",
  },
} as const;

function Stat({ value, label, icon, tone = "default" }: { value: React.ReactNode; label: string; icon: React.ReactNode; tone?: "default" | "success" | "warning" | "danger" }) {
  return (
    <div className={`astat tone-${tone}`}>
      <div className="astat-top"><span className="astat-icon">{icon}</span></div>
      <div className="astat-value">{value}</div>
      <div className="astat-label">{label}</div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { p, lang } = usePortal();
  const tr = STR[lang];
  const analytics = useAsync(() => getAnalytics(), []);
  const stats = useAsync(() => getAdminStats(), []);
  const sources = useAsync(() => getKnowledgeSources(), []);
  const questions = useAsync(() => getUnansweredQuestions(), []);

  const a = analytics.status === "success" ? analytics.data : null;
  const s = stats.status === "success" ? stats.data : null;
  const src = sources.status === "success" ? sources.data : [];
  const qs = questions.status === "success" ? questions.data : [];

  const lowConf = qs.filter((q) => q.reason === "low_confidence" || q.reason === "ambiguous").slice(0, 4);
  const missingCite = qs.filter((q) => q.reason === "no_verified_source").slice(0, 4);
  const topSources = [...src].sort((x, y) => y.chunk_count - x.chunk_count).slice(0, 5);
  const maxChunks = Math.max(...topSources.map((x) => x.chunk_count), 1);
  const maxTopic = Math.max(...(a?.top_topics.map((t) => t.count) ?? [1]), 1);
  const maxTotal = Math.max(...(a?.questions_per_day.map((d) => d.total) ?? [1]), 1);
  const satisfaction = a ? (3.4 + a.avg_confidence * 1.5).toFixed(1) : "—";

  return (
    <div className="page-inner">
      {/* Top metrics */}
      <div className="amon-stats">
        <Stat value={a ? a.total_questions.toLocaleString() : "—"} label={tr.totalQuestions7d} icon={<IconChat size={18} />} />
        <Stat value={a ? `${Math.round(a.verified_rate * 100)}%` : "—"} label={tr.verifiedRate} icon={<IconShield size={18} />} tone="success" />
        <Stat value={a ? a.avg_confidence.toFixed(2) : "—"} label={tr.avgConfidence} icon={<IconChart size={18} />} />
        <Stat value={s?.low_confidence_responses ?? 0} label={tr.lowConfidenceAnswers} icon={<IconAlert size={18} />} tone={(s?.low_confidence_responses ?? 0) > 0 ? "warning" : "success"} />
      </div>

      <div className="amon-grid">
        {/* MAIN */}
        <div className="amon-main">
          {/* Questions per day */}
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{p.admin.questionsPerDay}</h2></div>
            {a && (
              <>
                <div className="bars">
                  {a.questions_per_day.map((d) => {
                    const h = (d.total / maxTotal) * 100;
                    const unansweredH = (d.unanswered / Math.max(d.total, 1)) * 100;
                    return (
                      <div className="bar-col" key={d.label}>
                        <div className="bar-stack" style={{ height: `${h}%` }} title={`${d.total} total · ${d.verified} verified · ${d.unanswered} unanswered`}>
                          <div className="bar-unanswered" style={{ height: `${unansweredH}%`, flex: "0 0 auto" }} />
                          <div className="bar-verified" style={{ flex: "1 1 auto" }} />
                        </div>
                        <span className="bar-label">{d.label}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="legend">
                  <span><i style={{ background: "var(--ah-brand)" }} /> {p.admin.verified}</span>
                  <span><i style={{ background: "var(--ah-warning)" }} /> {p.admin.unanswered}</span>
                </div>
              </>
            )}
          </div>

          {/* Low-confidence answers */}
          <div className="acard">
            <div className="acard-head">
              <h2 className="acard-title">{tr.lowConfidenceHeader}</h2>
              <Link className="acard-link" href="/admin/unanswered">{tr.reviewQueue} <IconArrow size={13} /></Link>
            </div>
            {lowConf.length === 0 ? (
              <p className="attn-sub">{tr.noLowConfidence}</p>
            ) : (
              lowConf.map((q) => (
                <div key={q.id} className="amon-item">
                  <span className="attn-icon"><IconAlert size={15} /></span>
                  <div className="amon-item-main">
                    <div className="amon-item-q">{q.question}</div>
                    <div className="amon-item-sub">{p.enums.questionReason[q.reason]} · {tr.asked} {q.asked_count}×</div>
                  </div>
                  <Link className="btn btn-outline btn-sm amon-item-act" href={`/admin/unanswered/${q.id}`}>{tr.review}</Link>
                </div>
              ))
            )}
          </div>

          {/* Missing citations */}
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{tr.missingCitations}</h2></div>
            {missingCite.length === 0 ? (
              <p className="attn-sub">{tr.noMissingCitations}</p>
            ) : (
              missingCite.map((q) => (
                <div key={q.id} className="amon-item">
                  <span className="attn-icon danger"><IconAlert size={15} /></span>
                  <div className="amon-item-main">
                    <div className="amon-item-q">{q.question}</div>
                    <div className="amon-item-sub">{tr.noVerifiedSource} {p.enums.department[q.suggested_department] ?? q.suggested_department}</div>
                  </div>
                  <Link className="btn btn-outline btn-sm amon-item-act" href={`/admin/unanswered/${q.id}`}>{tr.linkSource}</Link>
                </div>
              ))
            )}
          </div>
        </div>

        {/* RAIL */}
        <div className="amon-rail">
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{tr.mostAskedTopics}</h2></div>
            {a?.top_topics.map((t) => (
              <div key={t.topic} className="bd-row">
                <span className="bd-label">{t.topic}</span>
                <span className="bd-track"><span className="bd-fill" style={{ width: `${(t.count / maxTopic) * 100}%` }} /></span>
                <span className="bd-val">{t.count}</span>
              </div>
            ))}
          </div>

          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{tr.sourceUsage}</h2></div>
            {topSources.length === 0 ? (
              <p className="attn-sub">{tr.noSources}</p>
            ) : (
              topSources.map((x) => (
                <div key={x.id} className="bd-row" title={x.name}>
                  <span className="bd-label"><IconDatabase size={12} /> {x.name}</span>
                  <span className="bd-track"><span className="bd-fill" style={{ width: `${(x.chunk_count / maxChunks) * 100}%` }} /></span>
                  <span className="bd-val">{x.chunk_count}</span>
                </div>
              ))
            )}
          </div>

          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">{tr.studentFeedback}</h2></div>
            <div className="amon-feedback-score">{satisfaction} / 5.0</div>
            <p className="field-hint" style={{ marginTop: 8 }}>
              <IconCheck size={12} /> {tr.feedbackHint}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
