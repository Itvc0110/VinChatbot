"use client";

import Link from "next/link";
import {
  AsyncBoundary,
  Card,
  SectionHeader,
  StatCard,
  Badge,
  EmptyState,
} from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getAdminStats, getUnansweredQuestions } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import {
  IconDatabase,
  IconUpload,
  IconInbox,
  IconChart,
  IconShield,
  IconArrow,
} from "@/components/shell/icons";
import type { QuestionPriority } from "@/lib/portalTypes";

const PRIORITY_TONE: Record<QuestionPriority, "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

export default function AdminDashboardPage() {
  const { p, lang } = usePortal();
  const stats = useAsync(getAdminStats, []);
  const questions = useAsync(getUnansweredQuestions, []);

  return (
    <div className="page-inner">
      <AsyncBoundary state={stats} onRetry={stats.reload} rows={2}>
        {(s) => (
          <div className="grid grid-3" style={{ marginBottom: 8 }}>
            <StatCard
              label={p.admin.indexedDocs}
              value={s.indexed_documents.toLocaleString()}
              tone="default"
              icon={<IconDatabase size={18} />}
            />
            <StatCard label={p.admin.sourcesCrawledToday} value={s.sources_crawled_today} tone="success" />
            <StatCard
              label={p.admin.failedCrawls}
              value={s.failed_crawls}
              tone={s.failed_crawls > 0 ? "danger" : "success"}
            />
            <StatCard
              label={p.admin.unansweredQuestions}
              value={s.unanswered_questions}
              tone={s.unanswered_questions > 0 ? "warning" : "success"}
              icon={<IconInbox size={18} />}
            />
            <StatCard
              label={p.admin.verifiedRate}
              value={`${Math.round(s.verified_answer_rate * 100)}%`}
              tone="success"
              icon={<IconShield size={18} />}
            />
            <StatCard
              label={p.admin.lowConfidence}
              value={s.low_confidence_responses}
              tone="warning"
            />
          </div>
        )}
      </AsyncBoundary>

      <div className="grid cols-2-1" style={{ marginTop: 16 }}>
        <Card>
          <SectionHeader
            title={p.admin.inboxTitle}
            action={
              <Link className="btn btn-ghost btn-sm" href="/admin/unanswered">
                {p.viewAll} <IconArrow size={14} />
              </Link>
            }
          />
          <AsyncBoundary state={questions} onRetry={questions.reload}>
            {(list) =>
              list.length === 0 ? (
                <EmptyState title={p.admin.inboxZero} description={p.admin.inboxZeroDesc} />
              ) : (
                <>
                  {list.slice(0, 4).map((q) => (
                    <Link
                      key={q.id}
                      href={`/admin/unanswered/${q.id}`}
                      className="list-row"
                      style={{ textDecoration: "none", color: "inherit" }}
                    >
                      <div className="list-row-main">
                        <div className="list-row-title">{q.question}</div>
                        <div className="list-row-sub">
                          {p.enums.department[q.suggested_department] ?? q.suggested_department} ·{" "}
                          {p.admin.askedTimes(q.asked_count)} · {relativeTime(q.created_at, lang)}
                        </div>
                      </div>
                      <div className="list-row-aside">
                        <Badge tone={PRIORITY_TONE[q.priority]}>
                          {p.enums.questionPriority[q.priority]}
                        </Badge>
                      </div>
                    </Link>
                  ))}
                </>
              )
            }
          </AsyncBoundary>
        </Card>

        <Card>
          <SectionHeader title={p.admin.quickActions} />
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <Link className="btn btn-outline" href="/admin/upload">
              <IconUpload size={16} /> {p.admin.qaUpload}
            </Link>
            <Link className="btn btn-outline" href="/admin/sources">
              <IconDatabase size={16} /> {p.admin.qaManageSources}
            </Link>
            <Link className="btn btn-outline" href="/admin/unanswered">
              <IconInbox size={16} /> {p.admin.qaReview}
            </Link>
            <Link className="btn btn-outline" href="/admin/analytics">
              <IconChart size={16} /> {p.admin.qaAnalytics}
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
