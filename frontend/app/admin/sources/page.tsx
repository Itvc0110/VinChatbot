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
  const sources = useAsync(getKnowledgeSources, []);
  const [toast, setToast] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function recrawl(s: KnowledgeSource) {
    setBusyId(s.id);
    try {
      const r = await recrawlSource(s.url);
      setToast(`Re-crawled “${s.name}” — ${r.indexed_chunks} chunks indexed.`);
      sources.reload();
    } catch {
      setToast("Re-crawl failed. Check the backend is running.");
    } finally {
      setBusyId(null);
    }
  }

  async function disable(s: KnowledgeSource) {
    setBusyId(s.id);
    try {
      await disableSource(s.id);
      setToast(`Disabled “${s.name}”.`);
      sources.reload();
    } catch {
      setToast("Couldn't disable the source.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page-inner">
      <SectionHeader
        title="All sources"
        action={
          <Link className="btn btn-primary btn-sm" href="/admin/upload">
            <IconUpload size={14} /> Add source
          </Link>
        }
      />
      <AsyncBoundary
        state={sources}
        onRetry={sources.reload}
        errorLabel="Couldn't load sources from the backend."
      >
        {(list) =>
          list.length === 0 ? (
            <EmptyState
              icon={<IconDatabase size={28} />}
              title="No sources indexed"
              description="Upload a document or crawl a URL to populate the knowledge base."
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Source name</th>
                    <th>Type</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Chunks</th>
                    <th>Last crawled</th>
                    <th>Last indexed</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <div className="td-strong">{s.name}</div>
                        <div className="td-sub">
                          {s.is_official ? "Official · " : ""}
                          {s.url}
                        </div>
                      </td>
                      <td>
                        <Badge tone="neutral">{s.type.toUpperCase()}</Badge>
                      </td>
                      <td>{s.category}</td>
                      <td>
                        <Badge tone={STATUS_TONE[s.status]}>{s.status}</Badge>
                      </td>
                      <td>{s.chunk_count}</td>
                      <td className="td-sub">
                        {s.last_crawled_at ? relativeTime(s.last_crawled_at) : "—"}
                      </td>
                      <td className="td-sub">
                        {s.last_indexed_at ? relativeTime(s.last_indexed_at) : "—"}
                      </td>
                      <td>
                        <div className="row-actions">
                          <a className="btn btn-ghost btn-sm" href={s.url} target="_blank" rel="noreferrer">
                            View
                          </a>
                          <button
                            className="btn btn-outline btn-sm"
                            disabled={busyId === s.id || s.status === "disabled"}
                            onClick={() => recrawl(s)}
                          >
                            {busyId === s.id ? "…" : "Re-crawl"}
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setToast(`“${s.name}” has ${s.chunk_count} indexed chunks.`)}
                          >
                            Chunks
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            disabled={busyId === s.id || s.status === "disabled"}
                            onClick={() => disable(s)}
                          >
                            Disable
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
        Live data from <code>GET /sources</code>; re-crawl posts to <code>/ingest/run</code>. Falls
        back to demo rows when the backend is offline.
      </p>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
