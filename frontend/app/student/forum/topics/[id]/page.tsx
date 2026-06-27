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
  getForumTopic,
  moderateForumComment,
  moderateForumTopic,
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
  const { user } = useAuth();
  const canModerate = user?.role === "admin";

  const topicState = useAsync(() => getForumTopic(topicId), [topicId]);
  const [topic, setTopic] = useState<ForumTopic | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [modBusy, setModBusy] = useState(false);

  useEffect(() => {
    if (topicState.status === "success") setTopic(topicState.data);
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
    locked: topic?.is_locked ?? false,
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
    onModerate: (commentId, patch) => {
      moderateForumComment(commentId, patch)
        .then(refreshTopic)
        .catch(() => setToast(p.forum.actionFailed));
    },
  };

  const onModerateTopic = (patch: TopicModeratePatch) => {
    setModBusy(true);
    moderateForumTopic(topicId, patch)
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
          return (
            <>
              <article className="forum-post">
                <VoteControl score={t.score} myVote={t.my_vote} onVote={onVoteTopic} />

                <div className="forum-post-main">
                  <div className="forum-topic-badges">
                    {categoryName && <Badge tone="info">{categoryName}</Badge>}
                    {t.is_pinned && <span className="forum-flag pinned">{p.forum.pinned}</span>}
                    {t.is_locked && <span className="forum-flag locked">{p.forum.locked}</span>}
                    {t.has_official_answer && <Badge tone="success">{p.forum.officialAnswer}</Badge>}
                  </div>

                  <h1 className="forum-post-title">{t.title}</h1>

                  <div className="forum-post-meta">
                    <span>
                      {p.forum.by} <strong>{mine ? p.forum.you : t.author_name ?? "—"}</strong>
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
                    {!mine && (
                      <ReportButton targetType="topic" targetId={t.id} onReported={setToast} />
                    )}
                  </div>

                  {canModerate && (
                    <ModActionBar topic={t} onModerate={onModerateTopic} busy={modBusy} />
                  )}
                </div>
              </article>

              {t.is_locked && <p className="forum-locked-banner">{p.forum.lockedNotice}</p>}

              <section className="forum-comments-section">
                <h2 className="forum-comments-head">{p.forum.commentCount(t.comment_count)}</h2>

                {!t.is_locked && (
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
