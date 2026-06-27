"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/primitives";
import { usePortal } from "@/lib/portalI18n";
import { relativeTime } from "@/lib/format";
import type { ForumTopic, ForumVoteValue } from "@/lib/portalTypes";
import { VoteControl } from "./VoteControl";

function PinIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 4h6l-1 5 3 3v2H7v-2l3-3-1-5zM12 14v6" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

export function TopicCard({
  topic,
  onVote,
}: {
  topic: ForumTopic;
  onVote: (topicId: string, value: ForumVoteValue) => void;
}) {
  const { p, lang } = usePortal();
  const categoryName = lang === "vi" ? topic.category_name_vi : topic.category_name_en;
  const href = `/student/forum/topics/${topic.id}`;

  return (
    <article className={`forum-topic-card ${topic.is_pinned ? "pinned" : ""}`}>
      <VoteControl
        score={topic.score}
        myVote={topic.my_vote}
        onVote={(value) => onVote(topic.id, value)}
      />

      <div className="forum-topic-main">
        <div className="forum-topic-badges">
          {categoryName && <Badge tone="info">{categoryName}</Badge>}
          {topic.is_pinned && (
            <span className="forum-flag pinned">
              <PinIcon /> {p.forum.pinned}
            </span>
          )}
          {topic.is_locked && (
            <span className="forum-flag locked">
              <LockIcon /> {p.forum.locked}
            </span>
          )}
          {topic.has_official_answer && <Badge tone="success">{p.forum.officialAnswer}</Badge>}
        </div>

        <h3 className="forum-topic-title">
          <Link href={href}>{topic.title}</Link>
        </h3>

        {topic.excerpt && <p className="forum-topic-excerpt">{topic.excerpt}</p>}

        {topic.tags.length > 0 && (
          <div className="forum-tags">
            {topic.tags.map((tag) => (
              <span key={tag} className="forum-tag">#{tag}</span>
            ))}
          </div>
        )}

        <div className="forum-topic-meta">
          <span>
            {p.forum.by} <strong>{topic.author_name ?? "—"}</strong>
          </span>
          <span aria-hidden>·</span>
          <span>{relativeTime(topic.last_activity_at, lang)}</span>
          <span aria-hidden>·</span>
          <Link href={href} className="forum-topic-comments">
            {p.forum.commentCount(topic.comment_count)}
          </Link>
        </div>
      </div>
    </article>
  );
}
