"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Toast } from "@/components/ui/primitives";
import {
  previewKnowledgeSource,
  uploadKnowledgeSource,
  type IngestPreview,
  type IngestRunResponse,
} from "@/lib/api";
import { usePortal } from "@/lib/portalI18n";
import type { SourceCategory } from "@/lib/portalTypes";
import { IconUpload, IconCheck, IconExternal, IconArrow } from "@/components/shell/icons";

const CATEGORIES: SourceCategory[] = ["Academic", "Tuition", "Events", "Student Services", "Schedule"];
type SourceType = "url" | "pdf" | "docx";
type Phase = "form" | "review" | "done";

const STR = {
  en: {
    sourceType: "Source Type",
    metadata: "Metadata",
    reviewExtracted: "Review extracted content",
    processingPipeline: "Processing Pipeline",
    sourceUrl: "Source URL",
    uploadFile: "Upload File",
    clickToUpload: "Click to upload or drag and drop",
    upTo: (type: string) => `${type}, up to 50MB`,
    saveDraft: "Save as Draft",
    savedDraft: "Saved as draft (demo).",
    vinnieReadiness: "✦ Vinnie Readiness",
    readinessLow: "Fill out the title and source to improve readiness.",
    readinessReady: "Ready — Vinnie can use this source's metadata to route answers.",
    readinessHint: "Vinnie uses metadata to filter and prioritize context so students get the right answer for their program.",
    extracting: "Extracting…",
    extractMeta: (chars: number, chunks: number) =>
      `${chars.toLocaleString()} characters extracted · ~${chunks} chunks`,
    extractTruncated: "Showing the first part — the full document is indexed on approval.",
    extractFailed: "Couldn't extract content from this source.",
    typeOpts: {
      url: "Official web page",
      pdf: "Document up to 50MB",
      docx: "Word document",
    },
    // True end-to-end order: upload+parse → admin review → chunk+embed → index → ready.
    pipeline: [
      { name: "Upload & Parse", sub: "Extract the document text" },
      { name: "Admin Review", sub: "Check content before publish" },
      { name: "Chunk & Embed", sub: "Split + vectorize" },
      { name: "Index to Vinnie", sub: "Searchable for students" },
    ],
  },
  vi: {
    sourceType: "Loại nguồn",
    metadata: "Siêu dữ liệu",
    reviewExtracted: "Rà soát nội dung trích xuất",
    processingPipeline: "Quy trình xử lý",
    sourceUrl: "URL nguồn",
    uploadFile: "Tải tệp lên",
    clickToUpload: "Nhấn để tải lên hoặc kéo và thả",
    upTo: (type: string) => `${type}, tối đa 50MB`,
    saveDraft: "Lưu bản nháp",
    savedDraft: "Đã lưu bản nháp (demo).",
    vinnieReadiness: "✦ Mức sẵn sàng của Vinnie",
    readinessLow: "Điền tiêu đề và nguồn để tăng mức sẵn sàng.",
    readinessReady: "Sẵn sàng — Vinnie có thể dùng siêu dữ liệu của nguồn này để định tuyến câu trả lời.",
    readinessHint: "Vinnie dùng siêu dữ liệu để lọc và ưu tiên ngữ cảnh, giúp sinh viên nhận đúng câu trả lời cho chương trình của mình.",
    extracting: "Đang trích xuất…",
    extractMeta: (chars: number, chunks: number) =>
      `Đã trích xuất ${chars.toLocaleString()} ký tự · ~${chunks} đoạn`,
    extractTruncated: "Đang hiển thị phần đầu — toàn bộ tài liệu sẽ được lập chỉ mục khi duyệt.",
    extractFailed: "Không trích xuất được nội dung từ nguồn này.",
    typeOpts: {
      url: "Trang web chính thức",
      pdf: "Tài liệu tối đa 50MB",
      docx: "Tài liệu Word",
    },
    // Đúng trình tự thực tế: tải lên+phân tích → duyệt → chia khối+nhúng → lập chỉ mục → sẵn sàng.
    pipeline: [
      { name: "Tải lên & Phân tích", sub: "Trích xuất nội dung tài liệu" },
      { name: "Duyệt quản trị", sub: "Kiểm tra nội dung trước khi xuất bản" },
      { name: "Chia khối & Nhúng", sub: "Tách + vector hóa" },
      { name: "Lập chỉ mục cho Vinnie", sub: "Sinh viên có thể tìm kiếm" },
    ],
  },
} as const;

const TYPE_OPTS: { key: SourceType; name: string }[] = [
  { key: "url", name: "URL" },
  { key: "pdf", name: "PDF" },
  { key: "docx", name: "DOCX" },
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
  const { p, lang } = usePortal();
  const tr = STR[lang];
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
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<IngestPreview | null>(null);
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

  // Pipeline stage maps to the 4 real steps (1 Upload&Parse · 2 Admin Review · 3 Chunk&Embed ·
  // 4 Index). 0 = nothing yet, 5 = fully done.
  const stage = phase === "done" ? 5 : working ? 3 : phase === "review" ? 2 : hasInput ? 1 : 0;

  // Step 1 (real): parse the file/URL on the backend and show the actual extracted text.
  async function runPreview() {
    setPreviewing(true);
    try {
      const pv = await previewKnowledgeSource({
        url: isUrl ? url.trim() : undefined,
        file: isUrl ? null : file,
        title: title.trim() || undefined,
      });
      setPreview(pv);
      setPhase("review");
    } catch {
      setToast(tr.extractFailed);
    } finally {
      setPreviewing(false);
    }
  }

  // Step 3+4 (real): chunk → embed → upsert to the vector DB; now retrievable by students.
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
    setPreview(null);
  }

  const PIPELINE = tr.pipeline.map((step, i) => ({ n: i + 1, name: step.name, sub: step.sub }));

  return (
    <div className="page-inner">
      <div className="aup-grid">
        {/* MAIN */}
        <div className="aup-main">
          {phase !== "done" ? (
            <>
              {/* Source type selector */}
              <div className="acard">
                <div className="acard-head"><h2 className="acard-title">{tr.sourceType}</h2></div>
                <div className="aup-types">
                  {TYPE_OPTS.map((t) => (
                    <button
                      key={t.key}
                      className={`aup-type ${sourceType === t.key ? "active" : ""}`}
                      onClick={() => { setSourceType(t.key); setUrl(""); setFile(null); setPreview(null); setPhase("form"); }}
                    >
                      <span className="aup-type-icon">{t.key === "url" ? <IconExternal size={18} /> : <FileGlyph />}</span>
                      <span className="aup-type-name">{t.name}</span>
                      <span className="aup-type-sub">{tr.typeOpts[t.key]}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Upload area */}
              <div className="acard">
                <div className="acard-head"><h2 className="acard-title">{isUrl ? tr.sourceUrl : tr.uploadFile}</h2></div>
                {isUrl ? (
                  <div className="field">
                    <input
                      className="input"
                      placeholder={p.admin.urlPlaceholder}
                      value={url}
                      onChange={(e) => { setUrl(e.target.value); setPreview(null); if (phase === "review") setPhase("form"); }}
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
                    <div className="aup-drop-title">{file ? file.name : tr.clickToUpload}</div>
                    <div className="aup-drop-sub">
                      {file ? p.admin.kbSelected(Number((file.size / 1024).toFixed(0))) : tr.upTo(sourceType.toUpperCase())}
                    </div>
                    <input
                      ref={fileRef}
                      type="file"
                      accept={sourceType === "pdf" ? ".pdf" : ".docx"}
                      hidden
                      onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); if (phase === "review") setPhase("form"); }}
                    />
                  </div>
                )}
              </div>

              {/* Metadata form */}
              <div className="acard">
                <div className="acard-head"><h2 className="acard-title">{tr.metadata}</h2></div>
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

              {/* Review-before-publish: REAL extracted text returned by the backend parser. */}
              {phase === "review" && preview && (
                <div className="acard">
                  <div className="acard-head"><h2 className="acard-title">{tr.reviewExtracted}</h2></div>
                  <p className="field-hint" style={{ marginBottom: 8 }}>
                    {tr.extractMeta(preview.char_count, preview.estimated_chunks)}
                  </p>
                  <div className="aup-extract">{preview.preview_text}</div>
                  {preview.truncated && (
                    <p className="field-hint" style={{ marginTop: 8 }}>{tr.extractTruncated}</p>
                  )}
                </div>
              )}

              {/* Actions */}
              <div className="aup-actions">
                <button className="btn btn-ghost" onClick={() => setToast(tr.savedDraft)}>
                  {tr.saveDraft}
                </button>
                {phase === "form" ? (
                  <button className="btn btn-primary" disabled={!hasInput || previewing} onClick={runPreview}>
                    {previewing ? tr.extracting : <>{p.admin.extractPreview} <IconArrow size={14} /></>}
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
            <div className="acard-head"><h2 className="acard-title">{tr.processingPipeline}</h2></div>
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
            <div className="acard-head"><h2 className="acard-title">{tr.vinnieReadiness}</h2></div>
            <div className="aup-readiness-score">{readiness}%</div>
            <div className="aup-readiness-bar"><div className="aup-readiness-fill" style={{ width: `${readiness}%` }} /></div>
            <p className="field-hint">
              {readiness < 100 ? tr.readinessLow : tr.readinessReady}
            </p>
            <p className="field-hint" style={{ marginTop: 8 }}>
              {tr.readinessHint}
            </p>
          </div>
        </div>
      </div>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
