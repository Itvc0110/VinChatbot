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
  const { p } = usePortal();
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
        <Stat value={a ? a.total_questions.toLocaleString() : "—"} label="Total questions (7d)" icon={<IconChat size={18} />} />
        <Stat value={a ? `${Math.round(a.verified_rate * 100)}%` : "—"} label="Verified rate" icon={<IconShield size={18} />} tone="success" />
        <Stat value={a ? a.avg_confidence.toFixed(2) : "—"} label="Avg confidence" icon={<IconChart size={18} />} />
        <Stat value={s?.low_confidence_responses ?? 0} label="Low-confidence answers" icon={<IconAlert size={18} />} tone={(s?.low_confidence_responses ?? 0) > 0 ? "warning" : "success"} />
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
              <h2 className="acard-title">Low-Confidence Answers</h2>
              <Link className="acard-link" href="/admin/unanswered">Review queue <IconArrow size={13} /></Link>
            </div>
            {lowConf.length === 0 ? (
              <p className="attn-sub">No low-confidence answers flagged. 🎉</p>
            ) : (
              lowConf.map((q) => (
                <div key={q.id} className="amon-item">
                  <span className="attn-icon"><IconAlert size={15} /></span>
                  <div className="amon-item-main">
                    <div className="amon-item-q">{q.question}</div>
                    <div className="amon-item-sub">{p.enums.questionReason[q.reason]} · asked {q.asked_count}×</div>
                  </div>
                  <Link className="btn btn-outline btn-sm amon-item-act" href={`/admin/unanswered/${q.id}`}>Review</Link>
                </div>
              ))
            )}
          </div>

          {/* Missing citations */}
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">Missing Citations</h2></div>
            {missingCite.length === 0 ? (
              <p className="attn-sub">No answers missing citations.</p>
            ) : (
              missingCite.map((q) => (
                <div key={q.id} className="amon-item">
                  <span className="attn-icon danger"><IconAlert size={15} /></span>
                  <div className="amon-item-main">
                    <div className="amon-item-q">{q.question}</div>
                    <div className="amon-item-sub">No verified source cited · suggested: {p.enums.department[q.suggested_department] ?? q.suggested_department}</div>
                  </div>
                  <Link className="btn btn-outline btn-sm amon-item-act" href={`/admin/unanswered/${q.id}`}>Link source</Link>
                </div>
              ))
            )}
          </div>
        </div>

        {/* RAIL */}
        <div className="amon-rail">
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">Most Asked Topics</h2></div>
            {a?.top_topics.map((t) => (
              <div key={t.topic} className="bd-row">
                <span className="bd-label">{t.topic}</span>
                <span className="bd-track"><span className="bd-fill" style={{ width: `${(t.count / maxTopic) * 100}%` }} /></span>
                <span className="bd-val">{t.count}</span>
              </div>
            ))}
          </div>

          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">Source Usage</h2></div>
            {topSources.length === 0 ? (
              <p className="attn-sub">No sources yet.</p>
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
            <div className="acard-head"><h2 className="acard-title">Student Feedback</h2></div>
            <div className="amon-feedback-score">{satisfaction} / 5.0</div>
            <p className="field-hint" style={{ marginTop: 8 }}>
              <IconCheck size={12} /> Derived from answer confidence &amp; verified rate (demo).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
