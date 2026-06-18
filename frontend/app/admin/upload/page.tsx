"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, Badge, Toast } from "@/components/ui/primitives";
import { uploadKnowledgeSource, type IngestRunResponse } from "@/lib/api";
import { usePortal } from "@/lib/portalI18n";
import type { SourceCategory } from "@/lib/portalTypes";
import { IconUpload, IconCheck } from "@/components/shell/icons";

const CATEGORIES: SourceCategory[] = [
  "Academic",
  "Tuition",
  "Events",
  "Student Services",
  "Schedule",
];

type SourceType = "url" | "pdf" | "docx";
type Step = 1 | 2 | 3 | 4;

const SAMPLE_EXTRACT = `VINUNIVERSITY — ACADEMIC CALENDAR 2025–2026

Fall Semester 2025
  • Classes begin: 25 August 2025
  • Add/Drop deadline: 5 September 2025
  • Course Withdrawal deadline: 7 November 2025
  • Final examinations: 8–19 December 2025

Spring Semester 2026
  • Classes begin: 12 January 2026
  • Add/Drop deadline: 23 January 2026
  • Tuition installment 2 due: 30 June 2026
  ...`;

export default function UploadPage() {
  const { p } = usePortal();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>(1);
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
      setStep(4);
    } catch {
      setToast(p.admin.indexFailed);
    } finally {
      setWorking(false);
    }
  }

  const steps: { n: Step; label: string }[] = [
    { n: 1, label: p.admin.stepSource },
    { n: 2, label: p.admin.stepPreview },
    { n: 3, label: p.admin.stepApprove },
    { n: 4, label: p.admin.stepIndexed },
  ];

  return (
    <div className="page-inner" style={{ maxWidth: 820 }}>
      <div className="stepper">
        {steps.map((s, i) => (
          <div key={s.n} style={{ display: "contents" }}>
            <div className={`step ${step === s.n ? "active" : ""} ${step > s.n ? "done" : ""}`}>
              <span className="step-num">{step > s.n ? <IconCheck size={13} /> : s.n}</span>
              {s.label}
            </div>
            {i < steps.length - 1 && <span className="step-divider" />}
          </div>
        ))}
      </div>

      {step === 1 && (
        <Card className="pad-lg">
          <div className="form-grid">
            <div className="field">
              <label className="field-label" htmlFor="u-title">
                {p.admin.sourceTitle}
              </label>
              <input
                id="u-title"
                className="input"
                placeholder={p.admin.sourceTitlePlaceholder}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="grid grid-2">
              <div className="field">
                <label className="field-label" htmlFor="u-type">
                  {p.admin.sourceType}
                </label>
                <select
                  id="u-type"
                  className="select"
                  value={sourceType}
                  onChange={(e) => {
                    setSourceType(e.target.value as SourceType);
                    setUrl("");
                    setFile(null);
                  }}
                >
                  <option value="url">{p.admin.optUrl}</option>
                  <option value="pdf">PDF</option>
                  <option value="docx">DOCX</option>
                </select>
              </div>
              <div className="field">
                <label className="field-label" htmlFor="u-cat">
                  {p.admin.category}
                </label>
                <select
                  id="u-cat"
                  className="select"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as SourceCategory)}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {p.enums.category[c] ?? c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {isUrl ? (
              <div className="field">
                <label className="field-label" htmlFor="u-url">
                  {p.admin.officialUrl}
                </label>
                <input
                  id="u-url"
                  className="input"
                  placeholder={p.admin.urlPlaceholder}
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
                <span className="field-hint">{p.admin.urlHint}</span>
              </div>
            ) : (
              <div
                className="dropzone"
                onClick={() => fileRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
              >
                <span className="dz-icon">
                  <IconUpload size={26} />
                </span>
                <div className="dz-title">
                  {file ? file.name : p.admin.uploadFile(sourceType.toUpperCase())}
                </div>
                <div className="dz-sub">
                  {file ? p.admin.kbSelected(Number((file.size / 1024).toFixed(0))) : p.admin.clickToChoose}
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

            <button className="btn btn-primary" disabled={!hasInput} onClick={() => setStep(2)}>
              {p.admin.extractPreview}
            </button>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card className="pad-lg">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
            <strong>{p.admin.extractedPreview}</strong>
            <Badge tone="info">{p.enums.category[category] ?? category}</Badge>
          </div>
          <div className="extract-preview">{SAMPLE_EXTRACT}</div>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="btn btn-outline" onClick={() => setStep(1)}>
              {p.back}
            </button>
            <button className="btn btn-primary" onClick={() => setStep(3)}>
              {p.admin.looksGood}
            </button>
          </div>
        </Card>
      )}

      {step === 3 && (
        <Card className="pad-lg">
          <strong>{p.admin.approveForChatbot}</strong>
          <div style={{ marginTop: 12 }}>
            <div className="kv">
              <span className="kv-key">{p.admin.fTitle}</span>
              <span className="kv-val">{title}</span>
            </div>
            <div className="kv">
              <span className="kv-key">{p.admin.fSource}</span>
              <span className="kv-val">{isUrl ? url : file?.name}</span>
            </div>
            <div className="kv">
              <span className="kv-key">{p.admin.fType}</span>
              <span className="kv-val">{sourceType.toUpperCase()}</span>
            </div>
            <div className="kv">
              <span className="kv-key">{p.admin.category}</span>
              <span className="kv-val">{p.enums.category[category] ?? category}</span>
            </div>
          </div>
          <p className="field-hint" style={{ marginTop: 12 }}>
            {p.admin.approveHint}
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="btn btn-outline" onClick={() => setStep(2)} disabled={working}>
              {p.back}
            </button>
            <button className="btn btn-primary" onClick={index} disabled={working}>
              {working ? p.admin.indexing : p.admin.approveIndex}
            </button>
          </div>
        </Card>
      )}

      {step === 4 && result && (
        <Card className="pad-lg" style={{ textAlign: "center" }}>
          <span className="empty-icon" style={{ color: "var(--success)", display: "inline-flex" }}>
            <IconCheck size={32} />
          </span>
          <h3 style={{ margin: "8px 0 4px" }}>{p.admin.indexedTitle}</h3>
          <p className="field-hint">
            {p.admin.indexedResult(
              result.crawled_documents,
              result.indexed_chunks,
              result.skipped_documents
            )}
          </p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
            <button
              className="btn btn-outline"
              onClick={() => {
                setStep(1);
                setTitle("");
                setUrl("");
                setFile(null);
                setResult(null);
              }}
            >
              {p.admin.addAnother}
            </button>
            <button className="btn btn-primary" onClick={() => router.push("/admin/sources")}>
              {p.admin.viewSources}
            </button>
          </div>
        </Card>
      )}

      {toast && <Toast message={toast} tone="danger" onClose={() => setToast(null)} />}
    </div>
  );
}
