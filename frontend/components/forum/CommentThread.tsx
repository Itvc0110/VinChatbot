"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { relativeTime } from "@/lib/format";
import type { ForumComment, ForumVoteValue } from "@/lib/portalTypes";
import { VoteControl } from "./VoteControl";
import { CommentComposer, type CommentSubmitPayload } from "./CommentComposer";
import { ReportButton } from "./ReportButton";

// Shared callbacks/flags threaded through the recursive tree (kept in one object to avoid
// drilling a long prop list at every level).
export interface CommentHandlers {
  onVote: (commentId: string, value: ForumVoteValue) => void;
  onReply: (parentId: string, payload: CommentSubmitPayload) => Promise<boolean>;
  onEdit: (commentId: string, content: string) => Promise<boolean>;
  onDelete: (commentId: string) => void;
  onModerate: (commentId: string, patch: { is_official?: boolean; deleted?: boolean }) => void;
  onToast: (message: string) => void;
  canModerate: boolean;
  currentUserId?: string;
  topicAuthorId?: string;
  locked: boolean;
}

const MAX_INDENT = 5;

function CommentItem({
  comment,
  depth,
  handlers,
}: {
  comment: ForumComment;
  depth: number;
  handlers: CommentHandlers;
}) {
  const { p, lang } = usePortal();
  const [replyOpen, setReplyOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(comment.content);
  const [busy, setBusy] = useState(false);
  const mine = !!handlers.currentUserId && comment.author_user_id === handlers.currentUserId;
  const authorOfTopic = !!handlers.topicAuthorId && comment.author_user_id === handlers.topicAuthorId;
  const staffAuthor = comment.author_roles.some((role) =>
    ["global_admin", "institute_admin", "staff"].includes(role)
  );

  useEffect(() => {
    setDraft(comment.content);
  }, [comment.content]);

  const submitReply = async (payload: CommentSubmitPayload) => {
    const ok = await handlers.onReply(comment.id, payload);
    if (ok) setReplyOpen(false);
    return ok;
  };

  const submitEdit = async () => {
    const next = draft.trim();
    if (!next || next === comment.content || busy) {
      setEditing(false);
      setDraft(comment.content);
      return;
    }
    setBusy(true);
    const ok = await handlers.onEdit(comment.id, next);
    setBusy(false);
    if (ok) setEditing(false);
  };

  return (
    <div
      className={`forum-comment ${comment.is_official ? "official" : ""} ${comment.deleted ? "removed" : ""}`}
      style={{ marginLeft: depth > 0 ? `${Math.min(depth, MAX_INDENT) * 18}px` : undefined }}
    >
      <div className="forum-comment-body">
        {!comment.deleted && (
          <VoteControl
            score={comment.score}
            myVote={comment.my_vote}
            onVote={(value) => handlers.onVote(comment.id, value)}
            orientation="horizontal"
          />
        )}

        <div className="forum-comment-content">
          <div className="forum-comment-head">
            <span className="forum-comment-author">
              {comment.deleted ? "—" : mine ? p.forum.you : comment.author_name ?? "—"}
            </span>
            {authorOfTopic && !comment.deleted && <Badge tone="info">{p.forum.authorBadge}</Badge>}
            {staffAuthor && !comment.deleted && <span className="forum-flag staff">{p.forum.staffBadge}</span>}
            {comment.is_official && <Badge tone="success">{p.forum.officialAnswer}</Badge>}
            {comment.deleted && <Badge tone="neutral">{p.forum.hiddenCommentBadge}</Badge>}
            <span className="forum-comment-time">{relativeTime(comment.created_at, lang)}</span>
          </div>

          {editing ? (
            <div className="forum-reply-box">
              <textarea
                className="textarea forum-mention-input"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                rows={3}
                disabled={busy}
              />
              <div className="forum-composer-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setEditing(false);
                    setDraft(comment.content);
                  }}
                  disabled={busy}
                >
                  {p.forum.cancel}
                </button>
                <button
                  type="button"
                  className="ah-btn-red"
                  onClick={submitEdit}
                  disabled={!draft.trim() || busy}
                >
                  {p.forum.save}
                </button>
              </div>
            </div>
          ) : (
            <p className="forum-comment-text">{comment.deleted && !handlers.canModerate ? p.forum.hiddenComment : comment.content}</p>
          )}

          {!comment.deleted ? (
            <div className="forum-comment-actions">
              {!handlers.locked && (
                <button
                  type="button"
                  className="forum-link-btn"
                  onClick={() => setReplyOpen((o) => !o)}
                >
                  {p.forum.reply}
                </button>
              )}
              {mine && !handlers.locked && (
                <>
                  <button
                    type="button"
                    className="forum-link-btn"
                    onClick={() => setEditing(true)}
                  >
                    {p.forum.edit}
                  </button>
                  <button
                    type="button"
                    className="forum-link-btn danger"
                    onClick={() => handlers.onDelete(comment.id)}
                  >
                    {p.forum.delete}
                  </button>
                </>
              )}
              {!mine && (
                <ReportButton targetType="comment" targetId={comment.id} onReported={handlers.onToast} />
              )}
              {handlers.canModerate && (
                <>
                  <button
                    type="button"
                    className="forum-link-btn"
                    onClick={() =>
                      handlers.onModerate(comment.id, { is_official: !comment.is_official })
                    }
                  >
                    {comment.is_official ? p.forum.unmarkOfficial : p.forum.markOfficial}
                  </button>
                  <button
                    type="button"
                    className="forum-link-btn danger"
                    onClick={() => handlers.onModerate(comment.id, { deleted: true })}
                  >
                    {p.forum.hide}
                  </button>
                </>
              )}
            </div>
          ) : handlers.canModerate ? (
            <div className="forum-comment-actions">
              <button
                type="button"
                className="forum-link-btn"
                onClick={() => handlers.onModerate(comment.id, { deleted: false })}
              >
                {p.forum.unhide}
              </button>
            </div>
          ) : null}

          {replyOpen && !editing && (
            <div className="forum-reply-box">
              <CommentComposer
                onSubmit={submitReply}
                placeholder={p.forum.replyPlaceholder}
                submitLabel={p.forum.postReply}
                autoFocus
                onCancel={() => setReplyOpen(false)}
              />
            </div>
          )}
        </div>
      </div>

      {comment.replies.length > 0 && (
        <div className="forum-comment-replies">
          {comment.replies.map((reply) => (
            <CommentItem key={reply.id} comment={reply} depth={depth + 1} handlers={handlers} />
          ))}
        </div>
      )}
    </div>
  );
}

export function CommentThread({
  comments,
  handlers,
}: {
  comments: ForumComment[];
  handlers: CommentHandlers;
}) {
  return (
    <div className="forum-thread">
      {comments.map((comment) => (
        <CommentItem key={comment.id} comment={comment} depth={0} handlers={handlers} />
      ))}
    </div>
  );
}
