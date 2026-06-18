"use client";

import { useState } from "react";
import Link from "next/link";
import {
  AsyncBoundary,
  SectionHeader,
  Badge,
  EmptyState,
  Toast,
  type BadgeTone,
} from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getKnowledgeSources, recrawlSource, disableSource } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { KnowledgeSource, SourceStatus } from "@/lib/portalTypes";
import { IconDatabase, IconUpload } from "@/components/shell/icons";

const STATUS_TONE: Record<SourceStatus, BadgeTone> = {
  indexed: "success",
  crawling: "info",
  failed: "danger",
  disabled: "neutral",
  pending: "warning",
};

export default function SourcesPage() {
  const { p, lang } = usePortal();
  const sources = useAsync(getKnowledgeSources, []);
  const [toast, setToast] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function recrawl(s: KnowledgeSource) {
    setBusyId(s.id);
    try {
      const r = await recrawlSource(s.url);
      setToast(p.admin.recrawled(s.name, r.indexed_chunks));
      sources.reload();
    } catch {
      setToast(p.admin.recrawlFailed);
    } finally {
      setBusyId(null);
    }
  }

  async function disable(s: KnowledgeSource) {
    setBusyId(s.id);
    try {
      await disableSource(s.id);
      setToast(p.admin.disabled(s.name));
      sources.reload();
    } catch {
      setToast(p.admin.disableFailed);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page-inner">
      <SectionHeader
        title={p.admin.allSources}
        action={
          <Link className="btn btn-primary btn-sm" href="/admin/upload">
            <IconUpload size={14} /> {p.admin.addSource}
          </Link>
        }
      />
      <AsyncBoundary
        state={sources}
        onRetry={sources.reload}
        errorLabel={p.admin.loadSourcesError}
      >
        {(list) =>
          list.length === 0 ? (
            <EmptyState
              icon={<IconDatabase size={28} />}
              title={p.admin.noSourcesTitle}
              description={p.admin.noSourcesDesc}
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{p.admin.colSourceName}</th>
                    <th>{p.admin.colType}</th>
                    <th>{p.admin.colCategory}</th>
                    <th>{p.admin.colStatus}</th>
                    <th>{p.admin.colChunks}</th>
                    <th>{p.admin.colLastCrawled}</th>
                    <th>{p.admin.colLastIndexed}</th>
                    <th>{p.admin.colActions}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <div className="td-strong">{s.name}</div>
                        <div className="td-sub">
                          {s.is_official ? `${p.admin.official} · ` : ""}
                          {s.url}
                        </div>
                      </td>
                      <td>
                        <Badge tone="neutral">{s.type.toUpperCase()}</Badge>
                      </td>
                      <td>{p.enums.category[s.category] ?? s.category}</td>
                      <td>
                        <Badge tone={STATUS_TONE[s.status]}>{p.enums.sourceStatus[s.status]}</Badge>
                      </td>
                      <td>{s.chunk_count}</td>
                      <td className="td-sub">
                        {s.last_crawled_at ? relativeTime(s.last_crawled_at, lang) : "—"}
                      </td>
                      <td className="td-sub">
                        {s.last_indexed_at ? relativeTime(s.last_indexed_at, lang) : "—"}
                      </td>
                      <td>
                        <div className="row-actions">
                          <a className="btn btn-ghost btn-sm" href={s.url} target="_blank" rel="noreferrer">
                            {p.view}
                          </a>
                          <button
                            className="btn btn-outline btn-sm"
                            disabled={busyId === s.id || s.status === "disabled"}
                            onClick={() => recrawl(s)}
                          >
                            {busyId === s.id ? "…" : p.admin.recrawl}
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setToast(p.admin.chunksInfo(s.name, s.chunk_count))}
                          >
                            {p.admin.chunks}
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            disabled={busyId === s.id || s.status === "disabled"}
                            onClick={() => disable(s)}
                          >
                            {p.admin.disable}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </AsyncBoundary>
      <p className="td-sub" style={{ marginTop: 12 }}>
        {p.admin.sourcesNote}
      </p>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
