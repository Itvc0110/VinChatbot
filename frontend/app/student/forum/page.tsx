"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AsyncBoundary, EmptyState, Toast } from "@/components/ui/primitives";
import { CategoryList } from "@/components/forum/CategoryList";
import { TopicCard } from "@/components/forum/TopicCard";
import { CreateTopicModal } from "@/components/forum/CreateTopicModal";
import { useAsync } from "@/lib/useAsync";
import { usePortal } from "@/lib/portalI18n";
import { getForumCategories, getForumTopics, voteForumTopic } from "@/lib/api";
import type { ForumSort, ForumTopic, ForumVoteValue } from "@/lib/portalTypes";
import { IconForum } from "@/components/shell/icons";

const PAGE_SIZE = 8;

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={dir === "left" ? "M15 18l-6-6 6-6" : "M9 18l6-6-6-6"} />
    </svg>
  );
}

const SORTS: ForumSort[] = ["active", "new", "top"];

export default function StudentForumPage() {
  const { p } = usePortal();
  const router = useRouter();

  const [category, setCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<ForumSort>("active");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ForumTopic[] | null>(null);

  // Debounce the search box into the fetch dependency.
  useEffect(() => {
    const handle = setTimeout(() => setAppliedSearch(search.trim()), 250);
    return () => clearTimeout(handle);
  }, [search]);

  const categoriesState = useAsync(getForumCategories, []);
  const topicsState = useAsync(
    () => getForumTopics({ category: category ?? undefined, sort, q: appliedSearch }),
    [category, sort, appliedSearch]
  );

  useEffect(() => {
    if (topicsState.status === "success") setItems(topicsState.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicsState.status, topicsState.status === "success" ? topicsState.data : null]);

  useEffect(() => setPage(1), [category, sort, appliedSearch]);

  const categories = categoriesState.status === "success" ? categoriesState.data : [];
  const all = items ?? [];

  const onVote = (topicId: string, value: ForumVoteValue) => {
    setItems((cur) =>
      (cur ?? []).map((t) => (t.id === topicId ? { ...t, my_vote: value } : t))
    );
    voteForumTopic(topicId, value)
      .then((res) =>
        setItems((cur) =>
          (cur ?? []).map((t) =>
            t.id === topicId ? { ...t, score: res.score, my_vote: res.my_vote } : t
          )
        )
      )
      .catch(() => setToast(p.forum.actionFailed));
  };

  const pageCount = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageItems = useMemo(
    () => all.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE),
    [all, safePage]
  );

  return (
    <div className="page-inner">
      <div className="ah-pagehead">
        <div>
          <h1 className="ah-pagehead-title">{p.forum.title}</h1>
          <p className="ah-pagehead-sub">{p.forum.subtitle}</p>
        </div>
        <button className="ah-btn-red" onClick={() => setCreating(true)}>
          <PlusIcon /> {p.forum.newTopic}
        </button>
      </div>

      <div className="forum-layout">
        <aside className="forum-sidebar">
          <CategoryList categories={categories} active={category} onSelect={setCategory} />
        </aside>

        <div className="forum-main">
          <div className="forum-toolbar">
            <div className="seg" role="group" aria-label={p.forum.sortActive}>
              {SORTS.map((s) => (
                <button
                  key={s}
                  className={`seg-opt ${sort === s ? "active" : ""}`}
                  aria-pressed={sort === s}
                  onClick={() => setSort(s)}
                >
                  {s === "active" ? p.forum.sortActive : s === "new" ? p.forum.sortNew : p.forum.sortTop}
                </button>
              ))}
            </div>
            <input
              className="input forum-search"
              type="search"
              placeholder={p.forum.searchPlaceholder}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <AsyncBoundary state={topicsState} onRetry={topicsState.reload}>
            {() =>
              all.length === 0 ? (
                <EmptyState
                  icon={<IconForum size={28} />}
                  title={p.forum.emptyTitle}
                  description={p.forum.emptyDesc}
                />
              ) : (
                <>
                  <div className="forum-topiclist">
                    {pageItems.map((topic) => (
                      <TopicCard key={topic.id} topic={topic} onVote={onVote} />
                    ))}
                  </div>

                  {pageCount > 1 && (
                    <nav className="ah-pagination" aria-label="Pagination">
                      <button
                        className="ah-page-btn"
                        onClick={() => setPage(safePage - 1)}
                        disabled={safePage <= 1}
                        aria-label="Previous"
                      >
                        <Chevron dir="left" />
                      </button>
                      {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
                        <button
                          key={n}
                          className={`ah-page-btn ${n === safePage ? "active" : ""}`}
                          onClick={() => setPage(n)}
                          aria-current={n === safePage ? "page" : undefined}
                        >
                          {n}
                        </button>
                      ))}
                      <button
                        className="ah-page-btn"
                        onClick={() => setPage(safePage + 1)}
                        disabled={safePage >= pageCount}
                        aria-label="Next"
                      >
                        <Chevron dir="right" />
                      </button>
                    </nav>
                  )}
                </>
              )
            }
          </AsyncBoundary>
        </div>
      </div>

      <CreateTopicModal
        open={creating}
        onClose={() => setCreating(false)}
        categories={categories}
        onCreated={(topic) => {
          setCreating(false);
          router.push(`/student/forum/topics/${topic.id}`);
        }}
      />

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
