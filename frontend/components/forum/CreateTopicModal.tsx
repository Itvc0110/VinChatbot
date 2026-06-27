"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { createForumTopic } from "@/lib/api";
import type { ForumAttachment, ForumCategory, ForumMember, ForumTopic } from "@/lib/portalTypes";
import { MentionTextarea } from "./MentionTextarea";

function normalizeTag(raw: string): string {
  return raw.trim().toLowerCase().replace(/^#+/, "").slice(0, 40);
}

export function CreateTopicModal({
  open,
  onClose,
  categories,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  categories: ForumCategory[];
  onCreated: (topic: ForumTopic) => void;
}) {
  const { p, lang } = usePortal();
  const [title, setTitle] = useState("");
  const [categorySlug, setCategorySlug] = useState("");
  const [content, setContent] = useState("");
  const [mentions, setMentions] = useState<ForumMember[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [attachments, setAttachments] = useState<ForumAttachment[]>([]);
  const [attUrl, setAttUrl] = useState("");
  const [attLabel, setAttLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Default the category to the first one once categories arrive / the modal opens.
  useEffect(() => {
    if (open && !categorySlug && categories.length > 0) {
      setCategorySlug(categories[0].slug);
    }
  }, [open, categories, categorySlug]);

  const reset = () => {
    setTitle("");
    setContent("");
    setMentions([]);
    setTags([]);
    setTagInput("");
    setAttachments([]);
    setAttUrl("");
    setAttLabel("");
    setError(null);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const addTag = () => {
    const tag = normalizeTag(tagInput);
    if (tag && !tags.includes(tag) && tags.length < 8) setTags([...tags, tag]);
    setTagInput("");
  };

  const addAttachment = () => {
    const url = attUrl.trim();
    if (!url) return;
    setAttachments([...attachments, { url, label: attLabel.trim() || undefined }]);
    setAttUrl("");
    setAttLabel("");
  };

  const canSubmit = title.trim().length >= 3 && content.trim().length > 0 && !!categorySlug && !busy;

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const topic = await createForumTopic({
        title: title.trim(),
        content: content.trim(),
        category_slug: categorySlug,
        tags,
        attachments,
        mentioned_user_ids: mentions.map((m) => m.id),
      });
      reset();
      onCreated(topic);
    } catch {
      setError(p.forum.createError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={p.forum.newTopic}
      size="lg"
      footer={
        <>
          <button className="btn btn-ghost" onClick={close} disabled={busy}>
            {p.forum.cancel}
          </button>
          <button className="ah-btn-red" onClick={submit} disabled={!canSubmit}>
            {busy ? p.forum.creating : p.forum.create}
          </button>
        </>
      }
    >
      <div className="form-grid">
        {error && <p className="forum-form-error">{error}</p>}

        <div className="field">
          <label className="field-label" htmlFor="forum-title">{p.forum.titleLabel}</label>
          <input
            id="forum-title"
            className="input"
            value={title}
            maxLength={200}
            placeholder={p.forum.titlePlaceholder}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="field">
          <label className="field-label" htmlFor="forum-category">{p.forum.categoryLabel}</label>
          <select
            id="forum-category"
            className="select"
            value={categorySlug}
            onChange={(e) => setCategorySlug(e.target.value)}
          >
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>
                {lang === "vi" ? c.name_vi : c.name_en}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="forum-content">{p.forum.contentLabel}</label>
          <MentionTextarea
            id="forum-content"
            value={content}
            onChange={setContent}
            mentions={mentions}
            onMentionsChange={setMentions}
            placeholder={p.forum.contentPlaceholder}
            rows={6}
          />
          <p className="field-hint">{p.forum.mentionHint}</p>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="forum-tag">{p.forum.tagsLabel}</label>
          {tags.length > 0 && (
            <div className="forum-tags">
              {tags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  className="forum-tag removable"
                  onClick={() => setTags(tags.filter((t) => t !== tag))}
                >
                  #{tag} ✕
                </button>
              ))}
            </div>
          )}
          <input
            id="forum-tag"
            className="input"
            value={tagInput}
            placeholder={p.forum.tagsPlaceholder}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                addTag();
              }
            }}
          />
        </div>

        <div className="field">
          <span className="field-label">{p.forum.attachmentsLabel}</span>
          {attachments.length > 0 && (
            <ul className="forum-attach-list">
              {attachments.map((a, i) => (
                <li key={`${a.url}-${i}`} className="forum-attach-chip">
                  <span>{a.label || a.url}</span>
                  <button
                    type="button"
                    onClick={() => setAttachments(attachments.filter((_, idx) => idx !== i))}
                    aria-label={p.forum.cancel}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="forum-attach-add">
            <input
              className="input"
              value={attUrl}
              placeholder={p.forum.attachmentUrlPlaceholder}
              onChange={(e) => setAttUrl(e.target.value)}
            />
            <input
              className="input"
              value={attLabel}
              placeholder={p.forum.attachmentLabelPlaceholder}
              onChange={(e) => setAttLabel(e.target.value)}
            />
            <button type="button" className="btn btn-outline btn-sm" onClick={addAttachment} disabled={!attUrl.trim()}>
              {p.forum.addLink}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
