"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, Badge, Toast } from "@/components/ui/primitives";
import { uploadKnowledgeSource, type IngestRunResponse } from "@/lib/api";
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
      setToast("Indexing failed. Check the backend.");
    } finally {
      setWorking(false);
    }
  }

  const steps: { n: Step; label: string }[] = [
    { n: 1, label: "Source" },
    { n: 2, label: "Preview" },
    { n: 3, label: "Approve" },
    { n: 4, label: "Indexed" },
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
                Source title
              </label>
              <input
                id="u-title"
                className="input"
                placeholder="e.g. Academic Calendar 2025–2026"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="grid grid-2">
              <div className="field">
                <label className="field-label" htmlFor="u-type">
                  Source type
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
                  <option value="url">Official URL</option>
                  <option value="pdf">PDF</option>
                  <option value="docx">DOCX</option>
                </select>
              </div>
              <div className="field">
                <label className="field-label" htmlFor="u-cat">
                  Category
                </label>
                <select
                  id="u-cat"
                  className="select"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as SourceCategory)}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {isUrl ? (
              <div className="field">
                <label className="field-label" htmlFor="u-url">
                  Official URL
                </label>
                <input
                  id="u-url"
                  className="input"
                  placeholder="https://vinuni.edu.vn/…"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
                <span className="field-hint">
                  URLs crawl + index through the live <code>/ingest/run</code> pipeline.
                </span>
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
                  {file ? file.name : `Upload ${sourceType.toUpperCase()} file`}
                </div>
                <div className="dz-sub">
                  {file ? `${(file.size / 1024).toFixed(0)} KB selected` : "Click to choose a file"}
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
              Extract & preview
            </button>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card className="pad-lg">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
            <strong>Extracted text preview</strong>
            <Badge tone="info">{category}</Badge>
          </div>
          <div className="extract-preview">{SAMPLE_EXTRACT}</div>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="btn btn-outline" onClick={() => setStep(1)}>
              Back
            </button>
            <button className="btn btn-primary" onClick={() => setStep(3)}>
              Looks good — continue
            </button>
          </div>
        </Card>
      )}

      {step === 3 && (
        <Card className="pad-lg">
          <strong>Approve for chatbot</strong>
          <div style={{ marginTop: 12 }}>
            <div className="kv">
              <span className="kv-key">Title</span>
              <span className="kv-val">{title}</span>
            </div>
            <div className="kv">
              <span className="kv-key">Source</span>
              <span className="kv-val">{isUrl ? url : file?.name}</span>
            </div>
            <div className="kv">
              <span className="kv-key">Type</span>
              <span className="kv-val">{sourceType.toUpperCase()}</span>
            </div>
            <div className="kv">
              <span className="kv-key">Category</span>
              <span className="kv-val">{category}</span>
            </div>
          </div>
          <p className="field-hint" style={{ marginTop: 12 }}>
            Approving indexes this source into the vector store so the chatbot can cite it.
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="btn btn-outline" onClick={() => setStep(2)} disabled={working}>
              Back
            </button>
            <button className="btn btn-primary" onClick={index} disabled={working}>
              {working ? "Indexing…" : "Approve & index"}
            </button>
          </div>
        </Card>
      )}

      {step === 4 && result && (
        <Card className="pad-lg" style={{ textAlign: "center" }}>
          <span className="empty-icon" style={{ color: "var(--success)", display: "inline-flex" }}>
            <IconCheck size={32} />
          </span>
          <h3 style={{ margin: "8px 0 4px" }}>Indexed into the knowledge base</h3>
          <p className="field-hint">
            {result.crawled_documents} document(s) processed · {result.indexed_chunks} chunks indexed ·{" "}
            {result.skipped_documents} skipped.
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
              Add another
            </button>
            <button className="btn btn-primary" onClick={() => router.push("/admin/sources")}>
              View sources
            </button>
          </div>
        </Card>
      )}

      {toast && <Toast message={toast} tone="danger" onClose={() => setToast(null)} />}
    </div>
  );
}
