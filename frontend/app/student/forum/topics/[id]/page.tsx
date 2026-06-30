"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AsyncBoundary, Badge, Toast } from "@/components/ui/primitives";
import { VoteControl } from "@/components/forum/VoteControl";
import { CommentComposer, type CommentSubmitPayload } from "@/components/forum/CommentComposer";
import { CommentThread, type CommentHandlers } from "@/components/forum/CommentThread";
import { ModActionBar, type TopicModeratePatch } from "@/components/forum/ModActionBar";
import { ReportButton } from "@/components/forum/ReportButton";
import { useAsync } from "@/lib/useAsync";
import { useAuth } from "@/lib/auth";
import { usePortal } from "@/lib/portalI18n";
import { relativeTime } from "@/lib/format";
import {
  addForumComment,
  archiveForumTopic,
  createForumTopicNotification,
  deleteForumComment,
  deleteForumTopic,
  getForumTopic,
  hideForumComment,
  lockForumTopic,
  moderateForumComment,
  moderateForumTopic,
  pinForumTopic,
  updateForumComment,
  updateForumTopic,
  voteForumComment,
  voteForumTopic,
} from "@/lib/api";
import type { ForumTopic, ForumVoteValue } from "@/lib/portalTypes";
import { IconExternal } from "@/components/shell/icons";

export default function ForumTopicDetailPage() {
  const params = useParams<{ id: string }>();
  const topicId = Array.isArray(params.id) ? params.id[0] : params.id;
  const router = useRouter();
  const { p, lang } = usePortal();
  const { token, user } = useAuth();
  const canModerate =
    user?.roles.some((role) => ["global_admin", "institute_admin", "staff"].includes(role)) ?? false;

  const topicState = useAsync(() => getForumTopic(topicId), [topicId, token, user?.id]);
  const [topic, setTopic] = useState<ForumTopic | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [modBusy, setModBusy] = useState(false);
  const [editingTopic, setEditingTopic] = useState(false);
  const [topicTitle, setTopicTitle] = useState("");
  const [topicContent, setTopicContent] = useState("");
  const [topicBusy, setTopicBusy] = useState(false);

  useEffect(() => {
    setTopic(null);
    setToast(null);
    setModBusy(false);
    setEditingTopic(false);
    setTopicTitle("");
    setTopicContent("");
    setTopicBusy(false);
  }, [token, user?.id, topicId]);

  useEffect(() => {
    if (topicState.status === "success") {
      setTopic(topicState.data);
      setTopicTitle(topicState.data.title);
      setTopicContent(topicState.data.content ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicState.status, topicState.status === "success" ? topicState.data : null]);

  // Silent refresh (no skeleton flash) after a comment / vote / moderation mutation.
  const refreshTopic = () =>
    getForumTopic(topicId)
      .then(setTopic)
      .catch(() => setToast(p.forum.actionFailed));

  const onVoteTopic = (value: ForumVoteValue) => {
    setTopic((cur) => (cur ? { ...cur, my_vote: value } : cur));
    voteForumTopic(topicId, value)
      .then((res) => setTopic((cur) => (cur ? { ...cur, score: res.score, my_vote: res.my_vote } : cur)))
      .catch(() => setToast(p.forum.actionFailed));
  };

  const postComment = async (payload: CommentSubmitPayload): Promise<boolean> => {
    try {
      await addForumComment(topicId, {
        content: payload.content,
        mentioned_user_ids: payload.mentioned_user_ids,
      });
      await refreshTopic();
      return true;
    } catch {
      setToast(p.forum.actionFailed);
      return false;
    }
  };

  const handlers: CommentHandlers = {
    currentUserId: user?.id,
    canModerate,
    topicAuthorId: topic?.author_user_id,
    locked: Boolean(topic?.is_locked || topic?.deleted),
    onToast: setToast,
    onVote: (commentId, value) => {
      voteForumComment(commentId, value)
        .then(refreshTopic)
        .catch(() => setToast(p.forum.actionFailed));
    },
    onReply: async (parentId, payload) => {
      try {
        await addForumComment(topicId, {
          content: payload.content,
          parent_comment_id: parentId,
          mentioned_user_ids: payload.mentioned_user_ids,
        });
        await refreshTopic();
        return true;
      } catch {
        setToast(p.forum.actionFailed);
        return false;
      }
    },
    onEdit: async (commentId, content) => {
      try {
        await updateForumComment(commentId, { content });
        await refreshTopic();
        return true;
      } catch {
        setToast(p.forum.actionFailed);
        return false;
      }
    },
    onDelete: (commentId) => {
      deleteForumComment(commentId)
        .then(refreshTopic)
        .catch(() => setToast(p.forum.actionFailed));
    },
    onModerate: (commentId, patch) => {
      const action =
        typeof patch.deleted === "boolean"
          ? hideForumComment(commentId, patch.deleted)
          : moderateForumComment(commentId, patch);
      action
        .then(refreshTopic)
        .catch(() => setToast(p.forum.actionFailed));
    },
  };

  const createTopicNotification = async () => {
    if (modBusy) return;
    setModBusy(true);
    try {
      await createForumTopicNotification(topicId);
      setToast(p.forum.notificationCreated);
    } catch {
      setToast(p.forum.actionFailed);
    } finally {
      setModBusy(false);
    }
  };

  const onModerateTopic = (patch: TopicModeratePatch) => {
    setModBusy(true);
    const action =
      typeof patch.deleted === "boolean"
        ? archiveForumTopic(topicId)
        : typeof patch.is_pinned === "boolean"
        ? pinForumTopic(topicId, patch.is_pinned)
        : typeof patch.is_locked === "boolean"
        ? lockForumTopic(topicId, patch.is_locked)
        : moderateForumTopic(topicId, patch);
    action
      .then((updated) => {
        if (patch.deleted) {
          router.push("/student/forum");
          return;
        }
        setTopic(updated);
      })
      .catch(() => setToast(p.forum.actionFailed))
      .finally(() => setModBusy(false));
  };

  const saveTopicEdit = async () => {
    const nextTitle = topicTitle.trim();
    const nextContent = topicContent.trim();
    if (!nextTitle || !nextContent || topicBusy) return;
    setTopicBusy(true);
    try {
      const updated = await updateForumTopic(topicId, {
        title: nextTitle,
        content: nextContent,
      });
      setTopic(updated);
      setEditingTopic(false);
    } catch {
      setToast(p.forum.actionFailed);
    } finally {
      setTopicBusy(false);
    }
  };

  const deleteOwnTopic = async () => {
    setTopicBusy(true);
    try {
      await deleteForumTopic(topicId);
      router.push("/student/forum");
    } catch {
      setToast(p.forum.actionFailed);
      setTopicBusy(false);
    }
  };

  return (
    <div className="page-inner forum-detail-page">
      <Link href="/student/forum" className="forum-back">
        ← {p.forum.backToForum}
      </Link>

      <AsyncBoundary state={topicState} onRetry={topicState.reload}>
        {(data) => {
          const t = topic ?? data;
          const categoryName = lang === "vi" ? t.category_name_vi : t.category_name_en;
          const comments = t.comments ?? [];
          const mine = !!user?.id && t.author_user_id === user.id;
          const readOnly = t.is_locked || t.deleted;
          const staffAuthor = t.author_roles.some((role) =>
            ["global_admin", "institute_admin", "staff"].includes(role)
          );
          return (
            <>
              <article className="forum-post">
                <VoteControl score={t.score} myVote={t.my_vote} onVote={onVoteTopic} />

                <div className="forum-post-main">
                  <div className="forum-topic-badges">
                    {categoryName && <Badge tone="info">{categoryName}</Badge>}
                    {t.is_pinned && <span className="forum-flag pinned">{p.forum.pinned}</span>}
                    {t.is_locked && <span className="forum-flag locked">{p.forum.locked}</span>}
                    {t.deleted && <span className="forum-flag archived">{p.forum.archived}</span>}
                    {t.has_official_answer && <Badge tone="success">{p.forum.officialAnswer}</Badge>}
                    {staffAuthor && <span className="forum-flag staff">{p.forum.staffBadge}</span>}
                  </div>

                  {editingTopic ? (
                    <div className="forum-reply-box">
                      <input
                        className="input"
                        value={topicTitle}
                        onChange={(event) => setTopicTitle(event.target.value)}
                        disabled={topicBusy}
                      />
                      <textarea
                        className="textarea forum-mention-input"
                        value={topicContent}
                        onChange={(event) => setTopicContent(event.target.value)}
                        rows={5}
                        disabled={topicBusy}
                      />
                      <div className="forum-composer-actions">
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => {
                            setEditingTopic(false);
                            setTopicTitle(t.title);
                            setTopicContent(t.content ?? "");
                          }}
                          disabled={topicBusy}
                        >
                          {p.forum.cancel}
                        </button>
                        <button
                          type="button"
                          className="ah-btn-red"
                          onClick={saveTopicEdit}
                          disabled={!topicTitle.trim() || !topicContent.trim() || topicBusy}
                        >
                          {p.forum.save}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <h1 className="forum-post-title">{t.title}</h1>
                  )}

                  <div className="forum-post-meta">
                    <span>
                      {p.forum.by} <strong>{mine ? p.forum.you : t.author_name ?? "—"}</strong>
                      {mine && <span className="forum-inline-badge">{p.forum.authorBadge}</span>}
                    </span>
                    <span aria-hidden>·</span>
                    <span>{relativeTime(t.created_at, lang)}</span>
                    <span aria-hidden>·</span>
                    <span>{p.forum.viewCount(t.view_count)}</span>
                  </div>

                  {t.tags.length > 0 && (
                    <div className="forum-tags">
                      {t.tags.map((tag) => (
                        <span key={tag} className="forum-tag">#{tag}</span>
                      ))}
                    </div>
                  )}

                  <div className="forum-post-content">{t.content}</div>

                  {t.attachments && t.attachments.length > 0 && (
                    <ul className="forum-post-attachments">
                      {t.attachments.map((a, i) => (
                        <li key={`${a.url}-${i}`}>
                          <a href={a.url} target="_blank" rel="noreferrer" className="forum-attach-link">
                            <IconExternal size={13} /> {a.label || a.url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="forum-post-foot">
                    {mine && !readOnly && !editingTopic && (
                      <>
                        <button
                          type="button"
                          className="forum-link-btn"
                          onClick={() => setEditingTopic(true)}
                        >
                          {p.forum.edit}
                        </button>
                        <button
                          type="button"
                          className="forum-link-btn danger"
                          onClick={deleteOwnTopic}
                          disabled={topicBusy}
                        >
                          {p.forum.delete}
                        </button>
                      </>
                    )}
                    {!mine && !t.deleted && (
                      <ReportButton targetType="topic" targetId={t.id} onReported={setToast} />
                    )}
                  </div>

                  {canModerate && (
                    <ModActionBar
                      topic={t}
                      onModerate={onModerateTopic}
                      onCreateNotification={createTopicNotification}
                      busy={modBusy}
                    />
                  )}
                </div>
              </article>

              {t.is_locked && <p className="forum-locked-banner">{p.forum.lockedNotice}</p>}
              {t.deleted && <p className="forum-locked-banner">{p.forum.archivedNotice}</p>}

              <section className="forum-comments-section">
                <h2 className="forum-comments-head">{p.forum.commentCount(t.comment_count)}</h2>

                {!readOnly && (
                  <CommentComposer
                    onSubmit={postComment}
                    placeholder={p.forum.commentPlaceholder}
                    submitLabel={p.forum.postComment}
                  />
                )}

                {comments.length === 0 ? (
                  <p className="forum-nocomments">{p.forum.noComments}</p>
                ) : (
                  <CommentThread comments={comments} handlers={handlers} />
                )}
              </section>
            </>
          );
        }}
      </AsyncBoundary>

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
