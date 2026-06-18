"use client";

import {
  AsyncBoundary,
  Card,
  SectionHeader,
  StatCard,
  Badge,
  type BadgeTone,
} from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getTuitionStatus } from "@/lib/api";
import { formatVnd, formatDate } from "@/lib/format";
import type { TuitionItemStatus } from "@/lib/portalTypes";
import { IconWallet } from "@/components/shell/icons";

const STATUS_TONE: Record<TuitionItemStatus, BadgeTone> = {
  paid: "success",
  due: "warning",
  overdue: "danger",
  upcoming: "neutral",
};

export default function StudentTuitionPage() {
  const { p, lang } = usePortal();
  const tuition = useAsync(getTuitionStatus, []);
  const locale = lang === "vi" ? "vi-VN" : "en-US";

  return (
    <div className="page-inner">
      <AsyncBoundary state={tuition} onRetry={tuition.reload} rows={2}>
        {(t) => {
          const pct = t.total_charged_vnd
            ? Math.round((t.total_paid_vnd / t.total_charged_vnd) * 100)
            : 0;
          return (
            <>
              <div className="grid grid-3" style={{ marginBottom: 20 }}>
                <StatCard
                  label={p.tui.totalCharged}
                  value={formatVnd(t.total_charged_vnd)}
                  tone="default"
                  icon={<IconWallet size={18} />}
                />
                <StatCard label={p.tui.paidToDate} value={formatVnd(t.total_paid_vnd)} tone="success" />
                <StatCard
                  label={p.tui.outstanding}
                  value={formatVnd(t.balance_vnd)}
                  hint={
                    t.next_due_at
                      ? p.tui.nextDue(
                          formatVnd(t.next_due_amount_vnd ?? 0),
                          formatDate(t.next_due_at, locale)
                        )
                      : undefined
                  }
                  tone={t.balance_vnd > 0 ? "gold" : "success"}
                />
              </div>

              <Card style={{ marginBottom: 20 }} className="pad-lg">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 8,
                    fontSize: "var(--fs-sm)",
                  }}
                >
                  <span className="kv-key">{p.tui.paymentProgress}</span>
                  <span className="td-strong">{p.tui.pctPaid(pct)}</span>
                </div>
                <div className="progress success">
                  <span style={{ width: `${pct}%` }} />
                </div>
              </Card>

              {t.next_due_at && t.balance_vnd > 0 && (
                <div className="route-card" style={{ marginBottom: 20 }}>
                  <h3>{p.tui.nextPaymentTitle}</h3>
                  <p>
                    {p.tui.nextPaymentBody(
                      formatVnd(t.next_due_amount_vnd ?? 0),
                      formatDate(t.next_due_at, locale)
                    )}
                  </p>
                  <a
                    className="btn btn-primary btn-sm"
                    href="https://vinuni.edu.vn/tuition-payment-schedule"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {p.tui.goToPortal}
                  </a>
                </div>
              )}

              <SectionHeader title={p.tui.statement} />
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{p.tui.colItem}</th>
                      <th>{p.tui.colTerm}</th>
                      <th>{p.tui.colAmount}</th>
                      <th>{p.tui.colStatus}</th>
                      <th>{p.tui.colDate}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {t.items.map((item) => (
                      <tr key={item.id}>
                        <td className="td-strong">{item.label}</td>
                        <td>{item.term}</td>
                        <td>{formatVnd(item.amount_vnd)}</td>
                        <td>
                          <Badge tone={STATUS_TONE[item.status]}>
                            {p.enums.tuitionItemStatus[item.status]}
                          </Badge>
                        </td>
                        <td className="td-sub">
                          {item.paid_at
                            ? p.tui.paidOn(formatDate(item.paid_at, locale))
                            : item.due_at
                            ? p.tui.dueOn(formatDate(item.due_at, locale))
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          );
        }}
      </AsyncBoundary>
    </div>
  );
}
