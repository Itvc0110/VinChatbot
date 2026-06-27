"use client";

import { usePortal } from "@/lib/portalI18n";
import type { ForumVoteValue } from "@/lib/portalTypes";

// Reddit-style up/down voter, shared by topics and comments. Presentational: it reports the
// desired new vote value (clicking the active arrow again clears the vote → 0) and the parent
// owns the score/my_vote state.
export function VoteControl({
  score,
  myVote,
  onVote,
  orientation = "vertical",
  disabled = false,
}: {
  score: number;
  myVote: ForumVoteValue;
  onVote: (value: ForumVoteValue) => void;
  orientation?: "vertical" | "horizontal";
  disabled?: boolean;
}) {
  const { p } = usePortal();

  const cast = (target: ForumVoteValue) => {
    if (disabled) return;
    onVote(myVote === target ? 0 : target);
  };

  return (
    <div className={`forum-vote forum-vote-${orientation}`}>
      <button
        type="button"
        className={`forum-vote-btn up ${myVote === 1 ? "active" : ""}`}
        onClick={() => cast(1)}
        disabled={disabled}
        aria-label={p.forum.upvote}
        aria-pressed={myVote === 1}
        title={p.forum.upvote}
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
          strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 5l7 8H5z" />
        </svg>
      </button>
      <span className={`forum-score ${myVote === 1 ? "up" : myVote === -1 ? "down" : ""}`}>
        {score}
      </span>
      <button
        type="button"
        className={`forum-vote-btn down ${myVote === -1 ? "active" : ""}`}
        onClick={() => cast(-1)}
        disabled={disabled}
        aria-label={p.forum.downvote}
        aria-pressed={myVote === -1}
        title={p.forum.downvote}
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
          strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 19l-7-8h14z" />
        </svg>
      </button>
    </div>
  );
}
