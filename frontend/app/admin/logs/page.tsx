"use client";

import { Badge, SectionHeader, type BadgeTone } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";

// System Logs — a lightweight operational feed (crawls, indexing, guardrail events).
// [MOCK] TODO backend contract: GET /admin/logs -> { ts, level, source, message }[]
// (the FastAPI app already emits structured logs via core/observability + request IDs).
type Level = "info" | "warn" | "error" | "success";
const LEVEL_TONE: Record<Level, BadgeTone> = {
  info: "info",
  warn: "warning",
  error: "danger",
  success: "success",
};

const LOGS: { ts: string; level: Level; source: string; message: string }[] = [
  { ts: "08:02:11", level: "success", source: "ingest", message: "Indexed 'Tuition & Payment Schedule' — 27 chunks." },
  { ts: "08:01:54", level: "info", source: "crawler", message: "Crawl started for 9 official VinUni URLs." },
  { ts: "08:01:02", level: "warn", source: "guardrail", message: "Low-confidence answer flagged for review (conf 0.41)." },
  { ts: "07:58:40", level: "error", source: "crawler", message: "Failed to fetch /student-services/health (HTTP 504)." },
  { ts: "07:55:20", level: "success", source: "ingest", message: "Re-crawl of Academic Calendar completed — 42 chunks." },
  { ts: "07:50:09", level: "info", source: "chat", message: "Conversation web-7f3a resolved (grounded, 3 citations)." },
];

export default function LogsPage() {
  const { p } = usePortal();
  return (
    <div className="page-inner">
      <SectionHeader title={p.admin.recentEvents} />
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{p.admin.colTime}</th>
              <th>{p.admin.colLevel}</th>
              <th>{p.admin.colSource}</th>
              <th>{p.admin.colMessage}</th>
            </tr>
          </thead>
          <tbody>
            {LOGS.map((l, i) => (
              <tr key={i}>
                <td className="td-sub mono">{l.ts}</td>
                <td>
                  <Badge tone={LEVEL_TONE[l.level]}>{p.enums.logLevel[l.level]}</Badge>
                </td>
                <td className="mono td-sub">{l.source}</td>
                <td>{l.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="td-sub" style={{ marginTop: 12 }}>
        {p.admin.logsNote}
      </p>
    </div>
  );
}
