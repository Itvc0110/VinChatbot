"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  AsyncBoundary,
  Badge,
  EmptyState,
  Toast,
  type BadgeTone,
} from "@/components/ui/primitives";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { useAuth } from "@/lib/auth";
import { getKnowledgeSources, recrawlSource, disableSource } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type {
  KnowledgeSource,
  SourceStatus,
  SourceType,
  SourceCategory,
} from "@/lib/portalTypes";
import { IconDatabase, IconUpload, IconCheck, IconAlert } from "@/components/shell/icons";

const STATUS_TONE: Record<SourceStatus, BadgeTone> = {
  indexed: "success",
  crawling: "info",
  failed: "danger",
  disabled: "neutral",
  pending: "warning",
};

const TYPES: (SourceType | "all")[] = ["all", "url", "pdf", "docx", "database"];
const CATEGORIES: (SourceCategory | "all")[] = [
  "all",
  "Academic",
  "Tuition",
  "Events",
  "Student Services",
  "Schedule",
];
const STATUSES: (SourceStatus | "all")[] = ["all", "indexed", "pending", "failed", "disabled"];

const STR = {
  en: {
    totalSources: "Total sources",
    indexed: "Indexed",
    pendingReview: "Pending review",
    indexingFailed: "Indexing failed",
    searchSources: "Search sources",
    searchSourcesPlaceholder: "Search sources…",
    typeFilter: "Type filter",
    categoryFilter: "Category filter",
    statusFilter: "Status filter",
    allTypes: "All types",
    allCategories: "All categories",
    allStatus: "All status",
    addUrl: "Add URL",
    notIndexed: "Not indexed",
    showing: (n: number, total: number) => `Showing ${n} of ${total} sources`,
  },
  vi: {
    totalSources: "Tổng nguồn",
    indexed: "Đã lập chỉ mục",
    pendingReview: "Chờ duyệt",
    indexingFailed: "Lập chỉ mục lỗi",
    searchSources: "Tìm nguồn",
    searchSourcesPlaceholder: "Tìm nguồn…",
    typeFilter: "Lọc theo loại",
    categoryFilter: "Lọc theo danh mục",
    statusFilter: "Lọc theo trạng thái",
    allTypes: "Tất cả loại",
    allCategories: "Tất cả danh mục",
    allStatus: "Tất cả trạng thái",
    addUrl: "Thêm URL",
    notIndexed: "Chưa lập chỉ mục",
    showing: (n: number, total: number) => `Hiển thị ${n} trên ${total} nguồn`,
  },
} as const;

function Summary({ value, label, tone = "default" }: { value: number; label: string; tone?: "default" | "success" | "warning" | "danger" }) {
  return (
    <div className={`astat tone-${tone}`}>
      <div className="astat-top">
        <span className="astat-icon"><IconDatabase size={18} /></span>
      </div>
      <div className="astat-value">{value.toLocaleString()}</div>
      <div className="astat-label">{label}</div>
    </div>
  );
}

export default function SourcesPage() {
  const { p, lang } = usePortal();
  const { token } = useAuth();
  const tr = STR[lang];
  const sources = useAsync(getKnowledgeSources, [token]);
  const [toast, setToast] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeF, setTypeF] = useState<SourceType | "all">("all");
  const [catF, setCatF] = useState<SourceCategory | "all">("all");
  const [statusF, setStatusF] = useState<SourceStatus | "all">("all");

  const list = sources.status === "success" ? sources.data : [];
  const counts = {
    total: list.length,
    indexed: list.filter((s) => s.status === "indexed").length,
    pending: list.filter((s) => s.status === "pending").length,
    failed: list.filter((s) => s.status === "failed").length,
  };

  const filtered = useMemo(
    () =>
      list
        .filter((s) => typeF === "all" || s.type === typeF)
        .filter((s) => catF === "all" || s.category === catF)
        .filter((s) => statusF === "all" || s.status === statusF)
        .filter((s) => {
          const q = search.trim().toLowerCase();
          if (!q) return true;
          return [s.name, s.url].some((x) => x.toLowerCase().includes(q));
        }),
    [list, typeF, catF, statusF, search]
  );

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
      {/* Summary cards */}
      <div className="akb-stats">
        <Summary value={counts.total} label={tr.totalSources} />
        <Summary value={counts.indexed} label={tr.indexed} tone="success" />
        <Summary value={counts.pending} label={tr.pendingReview} tone={counts.pending > 0 ? "warning" : "success"} />
        <Summary value={counts.failed} label={tr.indexingFailed} tone={counts.failed > 0 ? "danger" : "success"} />
      </div>

      {/* Search + filters + actions */}
      <div className="akb-toolbar">
        <input
          className="input"
          placeholder={tr.searchSourcesPlaceholder}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label={tr.searchSources}
        />
        <select className="select" value={typeF} onChange={(e) => setTypeF(e.target.value as SourceType | "all")} aria-label={tr.typeFilter}>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t === "all" ? tr.allTypes : t.toUpperCase()}</option>
          ))}
        </select>
        <select className="select" value={catF} onChange={(e) => setCatF(e.target.value as SourceCategory | "all")} aria-label={tr.categoryFilter}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c === "all" ? tr.allCategories : (p.enums.category[c] ?? c)}</option>
          ))}
        </select>
        <select className="select" value={statusF} onChange={(e) => setStatusF(e.target.value as SourceStatus | "all")} aria-label={tr.statusFilter}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s === "all" ? tr.allStatus : p.enums.sourceStatus[s]}</option>
          ))}
        </select>
        <div className="akb-actions">
          <Link className="btn btn-primary btn-sm" href="/admin/sources/upload">
            <IconUpload size={14} /> {p.admin.addSource}
          </Link>
        </div>
      </div>

      <AsyncBoundary state={sources} onRetry={sources.reload} errorLabel={p.admin.loadSourcesError}>
        {() =>
          list.length === 0 ? (
            <EmptyState
              icon={<IconDatabase size={28} />}
              title={p.admin.noSourcesTitle}
              description={p.admin.noSourcesDesc}
            />
          ) : (
            <>
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
                      <th>{p.admin.colActions}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <div className="td-strong">{s.name}</div>
                          <div className="td-sub">
                            {s.is_official ? `${p.admin.official} · ` : ""}
                            {s.url}
                          </div>
                        </td>
                        <td><Badge tone="neutral">{s.type.toUpperCase()}</Badge></td>
                        <td>{p.enums.category[s.category] ?? s.category}</td>
                        <td>
                          <Badge tone={STATUS_TONE[s.status]}>{p.enums.sourceStatus[s.status]}</Badge>
                          <div className={`akb-indexing ${s.chunk_count > 0 ? "ok" : ""}`}>
                            {s.chunk_count > 0 ? <IconCheck size={12} /> : <IconAlert size={12} />}
                            {s.chunk_count > 0 ? tr.indexed : tr.notIndexed}
                          </div>
                        </td>
                        <td>{s.chunk_count}</td>
                        <td className="td-sub">
                          {s.last_crawled_at ? relativeTime(s.last_crawled_at, lang) : "—"}
                        </td>
                        <td>
                          <div className="row-actions">
                            {/* Uploaded files use a non-navigable upload:// id — only show View
                                and Re-crawl for real web sources. */}
                            {/^https?:\/\//i.test(s.url) && (
                              <a className="btn btn-ghost btn-sm" href={s.url} target="_blank" rel="noreferrer">{p.view}</a>
                            )}
                            <button
                              className="btn btn-outline btn-sm"
                              disabled={busyId === s.id || s.status === "disabled" || !/^https?:\/\//i.test(s.url)}
                              onClick={() => recrawl(s)}
                            >
                              {busyId === s.id ? "…" : p.admin.recrawl}
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
              <p className="akb-foot">
                {tr.showing(filtered.length, list.length)} · {p.admin.sourcesNote}
              </p>
            </>
          )
        }
      </AsyncBoundary>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
