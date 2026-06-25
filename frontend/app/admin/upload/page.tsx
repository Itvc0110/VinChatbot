"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Toast } from "@/components/ui/primitives";
import { uploadKnowledgeSource, type IngestRunResponse } from "@/lib/api";
import { usePortal } from "@/lib/portalI18n";
import type { SourceCategory } from "@/lib/portalTypes";
import { IconUpload, IconCheck, IconExternal, IconArrow } from "@/components/shell/icons";

const CATEGORIES: SourceCategory[] = ["Academic", "Tuition", "Events", "Student Services", "Schedule"];
type SourceType = "url" | "pdf" | "docx";
type Phase = "form" | "review" | "done";

const SAMPLE_EXTRACT = `VINUNIVERSITY — ACADEMIC CALENDAR 2025–2026

Fall Semester 2025
  • Classes begin: 25 August 2025
  • Add/Drop deadline: 5 September 2025
  • Course Withdrawal deadline: 7 November 2025
  • Final examinations: 8–19 December 2025

Spring Semester 2026
  • Classes begin: 12 January 2026
  • Tuition installment 2 due: 30 June 2026
  ...`;

const TYPE_OPTS: { key: SourceType; name: string; sub: string }[] = [
  { key: "url", name: "URL", sub: "Official web page" },
  { key: "pdf", name: "PDF", sub: "Document up to 50MB" },
  { key: "docx", name: "DOCX", sub: "Word document" },
];

function FileGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 3v5h5M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
    </svg>
  );
}

export default function UploadPage() {
  const { p } = usePortal();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>("form");
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("url");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<SourceCategory>("Academic");
  const [result, setResult] = useState<IngestRunResponse | null>(null);
  const [working, setWorking] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const isUrl = sourceType === "url";
  const hasInput = title.trim() !== "" && (isUrl ? url.trim() !== "" : Boolean(file));

  // Vinnie readiness: metadata completeness drives retrieval quality.
  const readiness = useMemo(() => {
    let score = 20; // category always set
    if (title.trim()) score += 40;
    if (isUrl ? url.trim() : file) score += 40;
    return score;
  }, [title, url, file, isUrl]);

  // Pipeline stage: 0 idle · 1 parsed · 2 chunked · 3 review · 4 indexing · 5 done
  const stage = working ? 4 : phase === "done" ? 5 : phase === "review" ? 3 : hasInput ? 1 : 0;

  async function index() {
    setWorking(true);
    try {
      const r = await uploadKnowledgeSource({
        url: isUrl ? url.trim() : undefined,
        file: isUrl ? null : file,
        category,
        title: title.trim(),
        source_type: sourceType,
      });
      setResult(r);
      setPhase("done");
    } catch {
      setToast(p.admin.indexFailed);
    } finally {
      setWorking(false);
    }
  }

  function reset() {
    setPhase("form");
    setTitle("");
    setUrl("");
    setFile(null);
    setResult(null);
  }

  const PIPELINE = [
    { n: 1, name: "Upload & Parse", sub: "Read the document text" },
    { n: 2, name: "Chunk & Embed", sub: "Split + vectorize" },
    { n: 3, name: "Admin Review", sub: "Approve before publish" },
    { n: 4, name: "Index to Vinnie", sub: "Make searchable" },
  ];

  return (
    <div className="page-inner">
      <div className="aup-grid">
        {/* MAIN */}
        <div className="aup-main">
          {phase !== "done" ? (
            <>
              {/* Source type selector */}
              <div className="acard">
                <div className="acard-head"><h2 className="acard-title">Source Type</h2></div>
                <div className="aup-types">
                  {TYPE_OPTS.map((t) => (
                    <button
                      key={t.key}
                      className={`aup-type ${sourceType === t.key ? "active" : ""}`}
                      onClick={() => { setSourceType(t.key); setUrl(""); setFile(null); }}
                    >
                      <span className="aup-type-icon">{t.key === "url" ? <IconExternal size={18} /> : <FileGlyph />}</span>
                      <span className="aup-type-name">{t.name}</span>
                      <span className="aup-type-sub">{t.sub}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Upload area */}
              <div className="acard">
                <div className="acard-head"><h2 className="acard-title">{isUrl ? "Source URL" : "Upload File"}</h2></div>
                {isUrl ? (
                  <div className="field">
                    <input
                      className="input"
                      placeholder={p.admin.urlPlaceholder}
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      aria-label={p.admin.officialUrl}
                    />
                    <span className="field-hint">{p.admin.urlHint}</span>
                  </div>
                ) : (
                  <div
                    className="aup-drop"
                    onClick={() => fileRef.current?.click()}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
                  >
                    <span className="aup-drop-icon"><IconUpload size={26} /></span>
                    <div className="aup-drop-title">{file ? file.name : "Click to upload or drag and drop"}</div>
                    <div className="aup-drop-sub">
                      {file ? p.admin.kbSelected(Number((file.size / 1024).toFixed(0))) : `${sourceType.toUpperCase()}, up to 50MB`}
                    </div>
                    <input
                      ref={fileRef}
                      type="file"
                      accept={sourceType === "pdf" ? ".pdf" : ".docx"}
                      hidden
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </div>
                )}
              </div>

              {/* Metadata form */}
              <div className="acard">
                <div className="acard-head"><h2 className="acard-title">Metadata</h2></div>
                <div className="form-grid">
                  <div className="field">
                    <label className="field-label" htmlFor="u-title">{p.admin.sourceTitle} *</label>
                    <input
                      id="u-title"
                      className="input"
                      placeholder={p.admin.sourceTitlePlaceholder}
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label className="field-label" htmlFor="u-cat">{p.admin.category}</label>
                    <select
                      id="u-cat"
                      className="select"
                      value={category}
                      onChange={(e) => setCategory(e.target.value as SourceCategory)}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>{p.enums.category[c] ?? c}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Review-before-publish */}
              {phase === "review" && (
                <div className="acard">
                  <div className="acard-head"><h2 className="acard-title">Review extracted content</h2></div>
                  <div className="aup-extract">{SAMPLE_EXTRACT}</div>
                </div>
              )}

              {/* Actions */}
              <div className="aup-actions">
                <button className="btn btn-ghost" onClick={() => setToast("Saved as draft (demo).")}>
                  Save as Draft
                </button>
                {phase === "form" ? (
                  <button className="btn btn-primary" disabled={!hasInput} onClick={() => setPhase("review")}>
                    {p.admin.extractPreview} <IconArrow size={14} />
                  </button>
                ) : (
                  <>
                    <button className="btn btn-outline" onClick={() => setPhase("form")} disabled={working}>
                      {p.back}
                    </button>
                    <button className="btn btn-primary" onClick={index} disabled={working}>
                      {working ? p.admin.indexing : p.admin.approveIndex}
                    </button>
                  </>
                )}
              </div>
            </>
          ) : (
            /* Done */
            <div className="acard" style={{ textAlign: "center", padding: 32 }}>
              <span className="astat-icon" style={{ background: "var(--ah-success-bg)", color: "var(--ah-success)", margin: "0 auto" }}>
                <IconCheck size={20} />
              </span>
              <h2 className="acard-title" style={{ marginTop: 12 }}>{p.admin.indexedTitle}</h2>
              {result && (
                <p className="field-hint" style={{ marginTop: 4 }}>
                  {p.admin.indexedResult(result.crawled_documents, result.indexed_chunks, result.skipped_documents)}
                </p>
              )}
              <div className="aup-actions" style={{ justifyContent: "center", marginTop: 16 }}>
                <button className="btn btn-outline" onClick={reset}>{p.admin.addAnother}</button>
                <button className="btn btn-primary" onClick={() => router.push("/admin/sources")}>
                  {p.admin.viewSources}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* RAIL */}
        <div className="aup-rail">
          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">Processing Pipeline</h2></div>
            {PIPELINE.map((s) => {
              const done = s.n < stage || phase === "done";
              const active = !done && s.n === stage;
              return (
                <div key={s.n} className={`aup-pipeline-step ${done ? "done" : ""} ${active ? "active" : ""}`}>
                  <span className="aup-step-num">{done ? <IconCheck size={13} /> : s.n}</span>
                  <span className="aup-step-main">
                    <span className="aup-step-name">{s.name}</span>
                    <span className="aup-step-sub">{s.sub}</span>
                  </span>
                </div>
              );
            })}
          </div>

          <div className="acard">
            <div className="acard-head"><h2 className="acard-title">✦ Vinnie Readiness</h2></div>
            <div className="aup-readiness-score">{readiness}%</div>
            <div className="aup-readiness-bar"><div className="aup-readiness-fill" style={{ width: `${readiness}%` }} /></div>
            <p className="field-hint">
              {readiness < 100
                ? "Fill out the title and source to improve readiness."
                : "Ready — Vinnie can use this source's metadata to route answers."}
            </p>
            <p className="field-hint" style={{ marginTop: 8 }}>
              Vinnie uses metadata to filter and prioritize context so students get the right answer for their program.
            </p>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
