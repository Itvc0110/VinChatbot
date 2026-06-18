"use client";

import { AsyncBoundary, Card, SectionHeader, StatCard } from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { getAnalytics } from "@/lib/api";

export default function AnalyticsPage() {
  const analytics = useAsync(getAnalytics, []);

  return (
    <div className="page-inner">
      <AsyncBoundary state={analytics} onRetry={analytics.reload} rows={2}>
        {(a) => {
          const maxTotal = Math.max(...a.questions_per_day.map((d) => d.total), 1);
          const maxTopic = Math.max(...a.top_topics.map((t) => t.count), 1);
          return (
            <>
              <div className="grid grid-3" style={{ marginBottom: 20 }}>
                <StatCard
                  label="Total questions (7 days)"
                  value={a.total_questions.toLocaleString()}
                  tone="default"
                />
                <StatCard
                  label="Verified answer rate"
                  value={`${Math.round(a.verified_rate * 100)}%`}
                  tone="success"
                />
                <StatCard label="Average confidence" value={a.avg_confidence.toFixed(2)} tone="gold" />
              </div>

              <Card className="pad-lg" style={{ marginBottom: 20 }}>
                <SectionHeader title="Questions per day" />
                <div className="bars">
                  {a.questions_per_day.map((d) => {
                    const h = (d.total / maxTotal) * 100;
                    const unansweredH = (d.unanswered / d.total) * 100;
                    return (
                      <div className="bar-col" key={d.label}>
                        <div
                          className="bar-stack"
                          style={{ height: `${h}%` }}
                          title={`${d.total} total · ${d.verified} verified · ${d.unanswered} unanswered`}
                        >
                          <div
                            className="bar-unanswered"
                            style={{ height: `${unansweredH}%`, flex: "0 0 auto" }}
                          />
                          <div className="bar-verified" style={{ flex: "1 1 auto" }} />
                        </div>
                        <span className="bar-label">{d.label}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="legend">
                  <span>
                    <i style={{ background: "var(--primary)" }} /> Verified
                  </span>
                  <span>
                    <i style={{ background: "var(--warning)" }} /> Unanswered
                  </span>
                </div>
              </Card>

              <Card className="pad-lg">
                <SectionHeader title="Top topics" />
                {a.top_topics.map((t) => (
                  <div className="topic-row" key={t.topic}>
                    <span className="td-strong">{t.topic}</span>
                    <span className="topic-track">
                      <span style={{ width: `${(t.count / maxTopic) * 100}%` }} />
                    </span>
                    <span className="td-sub">{t.count}</span>
                  </div>
                ))}
              </Card>
            </>
          );
        }}
      </AsyncBoundary>
    </div>
  );
}
