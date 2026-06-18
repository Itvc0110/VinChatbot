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
  const { lang } = usePortal();
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
                  label="Total charged"
                  value={formatVnd(t.total_charged_vnd)}
                  tone="default"
                  icon={<IconWallet size={18} />}
                />
                <StatCard label="Paid to date" value={formatVnd(t.total_paid_vnd)} tone="success" />
                <StatCard
                  label="Outstanding balance"
                  value={formatVnd(t.balance_vnd)}
                  hint={
                    t.next_due_at
                      ? `Next ${formatVnd(t.next_due_amount_vnd ?? 0)} due ${formatDate(
                          t.next_due_at,
                          locale
                        )}`
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
                  <span className="kv-key">Payment progress</span>
                  <span className="td-strong">{pct}% paid</span>
                </div>
                <div className="progress success">
                  <span style={{ width: `${pct}%` }} />
                </div>
              </Card>

              {t.next_due_at && t.balance_vnd > 0 && (
                <div className="route-card" style={{ marginBottom: 20 }}>
                  <h3>💳 Next payment due</h3>
                  <p>
                    {formatVnd(t.next_due_amount_vnd ?? 0)} is due on{" "}
                    <strong>{formatDate(t.next_due_at, locale)}</strong>. Pay via the VinUni
                    Student Financial Services portal to avoid a late fee.
                  </p>
                  <a
                    className="btn btn-primary btn-sm"
                    href="https://vinuni.edu.vn/tuition-payment-schedule"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Go to payment portal
                  </a>
                </div>
              )}

              <SectionHeader title="Statement of account" />
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Term</th>
                      <th>Amount</th>
                      <th>Status</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {t.items.map((item) => (
                      <tr key={item.id}>
                        <td className="td-strong">{item.label}</td>
                        <td>{item.term}</td>
                        <td>{formatVnd(item.amount_vnd)}</td>
                        <td>
                          <Badge tone={STATUS_TONE[item.status]}>{item.status}</Badge>
                        </td>
                        <td className="td-sub">
                          {item.paid_at
                            ? `Paid ${formatDate(item.paid_at, locale)}`
                            : item.due_at
                            ? `Due ${formatDate(item.due_at, locale)}`
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
