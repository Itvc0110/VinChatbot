"use client";

import { usePortal } from "@/lib/portalI18n";
import type { ForumCategory } from "@/lib/portalTypes";

// Left rail of forum categories. "All topics" plus one row per category, with a live topic
// count and a small color dot. Selecting a row filters the topic list (null = all).
export function CategoryList({
  categories,
  active,
  onSelect,
}: {
  categories: ForumCategory[];
  active: string | null;
  onSelect: (slug: string | null) => void;
}) {
  const { p, lang } = usePortal();
  const totalTopics = categories.reduce((sum, c) => sum + c.topic_count, 0);

  return (
    <nav className="forum-rail" aria-label={p.forum.allCategories}>
      <button
        type="button"
        className={`forum-cat ${active === null ? "active" : ""}`}
        onClick={() => onSelect(null)}
        aria-current={active === null ? "true" : undefined}
      >
        <span className="forum-cat-dot all" aria-hidden />
        <span className="forum-cat-name">{p.forum.allCategories}</span>
        <span className="forum-cat-count">{totalTopics}</span>
      </button>

      {categories.map((c) => {
        const name = lang === "vi" ? c.name_vi : c.name_en;
        return (
          <button
            key={c.id}
            type="button"
            className={`forum-cat ${active === c.slug ? "active" : ""}`}
            onClick={() => onSelect(c.slug)}
            aria-current={active === c.slug ? "true" : undefined}
          >
            <span className="forum-cat-dot" style={{ background: c.color }} aria-hidden />
            <span className="forum-cat-name">{name}</span>
            <span className="forum-cat-count">{c.topic_count}</span>
          </button>
        );
      })}
    </nav>
  );
}
