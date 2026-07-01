"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";
import { IconChat, IconClock, IconTicket } from "@/components/shell/icons";
import { LogoVinnie } from "@/components/shell/Logos";

const MENU_W = 156; // px — dropdown width
const MENU_EST_H = 124; // px — approx height (3 items) for flip decision
const PIN_STORAGE_KEY = "vinchatbot-pinned-conversations";

function readPinnedIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(PIN_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function PinIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        d="M14 3 21 10l-4 1-4.5 4.5.5 4.5-1 1-3.7-5L3 12.3l1-1 4.5.5L13 7l1-4Z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Conversation-history rail on the full Ask Vinnie page (PLAN22.6.2 §2). Lists in-memory
// conversations newest-first, with a "New chat" button, per-item rename/delete, and a subtle
// "processing" indicator for any conversation still streaming. Switching is allowed even while
// a reply streams — the in-flight answer lands in its own conversation.
//
// The Rename/Delete menu is rendered through a PORTAL to <body> as a position:fixed layer,
// anchored to the three-dot button via getBoundingClientRect(). This keeps it out of the
// scrollable list's clipping box, so it's never cut off when a row is near the bottom.
export function ConversationRail({
  compact = false,
  onToggleCompact,
}: {
  compact?: boolean;
  onToggleCompact?: () => void;
}) {
  const { p, lang } = usePortal();
  const chat = useChat();
  const copy =
    lang === "vi"
      ? {
          subtitle: "AI Student Assistant",
          collapse: "Thu gọn sidebar",
          expand: "Mở rộng sidebar",
          pinned: "Đã ghim",
          recent: "Gần đây",
          pin: "Ghim",
          unpin: "Bỏ ghim",
          noRecent: "Không có hội thoại gần đây.",
          help: "Hướng dẫn",
          feedback: "Phản hồi",
          feedbackSubject: "Phản hồi về Vinnie",
        }
      : {
          subtitle: "AI Student Assistant",
          collapse: "Collapse sidebar",
          expand: "Expand sidebar",
          pinned: "Pinned",
          recent: "Recent",
          pin: "Pin",
          unpin: "Unpin",
          noRecent: "No recent conversations.",
          help: "Help",
          feedback: "Feedback",
          feedbackSubject: "Feedback about Vinnie",
        };
  // Open menu: which conversation + the fixed-position coordinates measured from its button.
  const [menu, setMenu] = useState<{ id: string; top: number; left: number } | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [recentOpen, setRecentOpen] = useState(true);
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => readPinnedIds());
  const renameRef = useRef<HTMLInputElement>(null);

  const showList =
    !chat.historyLoading && !chat.historyError && chat.conversations.length > 0;

  // Close the floating menu on any outside click, Escape, or scroll (list/window). Scrolling
  // closes rather than chasing the button, which is simplest and avoids a detached menu.
  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenu(null);
    };
    window.addEventListener("click", close);
    window.addEventListener("keydown", onKey);
    // capture=true so a scroll inside the conversation list (not just window) also closes it.
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [menu]);

  useEffect(() => {
    if (renamingId) renameRef.current?.focus();
  }, [renamingId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(PIN_STORAGE_KEY, JSON.stringify(pinnedIds));
    } catch {
      /* pinning is a local UI preference; ignore storage failures */
    }
  }, [pinnedIds]);

  const titleFor = (id: string) => chat.conversations.find((c) => c.id === id)?.title ?? null;
  const isPinned = (id: string) => pinnedIds.includes(id);
  const togglePin = (id: string) => {
    setMenu(null);
    setPinnedIds((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : [id, ...ids]
    );
  };

  const toggleMenu = (e: React.MouseEvent<HTMLButtonElement>, id: string) => {
    e.stopPropagation();
    if (menu?.id === id) {
      setMenu(null);
      return;
    }
    const r = e.currentTarget.getBoundingClientRect();
    // Default: below the button; flip above if there isn't room below.
    let top = r.bottom + 6;
    if (top + MENU_EST_H > window.innerHeight - 8) {
      top = Math.max(8, r.top - 6 - MENU_EST_H);
    }
    // Right-align to the button, then clamp inside the viewport.
    let left = r.right - MENU_W;
    left = Math.max(8, Math.min(left, window.innerWidth - MENU_W - 8));
    setMenu({ id, top, left });
  };

  const startRename = (id: string) => {
    setMenu(null);
    setRenamingId(id);
    setDraft(titleFor(id) ?? "");
  };
  const commitRename = (id: string) => {
    chat.renameConversation(id, draft);
    setRenamingId(null);
    setDraft("");
  };
  const handleDelete = (id: string) => {
    setMenu(null);
    if (window.confirm(p.chatHistory.deleteConfirm)) chat.deleteConversation(id);
  };
  const selectConversation = (id: string) => {
    setMenu(null);
    chat.switchConversation(id);
  };
  type RailConversation = (typeof chat.conversations)[number];
  const pinnedConversations = chat.conversations.filter((c) => isPinned(c.id));
  const recentConversations = chat.conversations.filter((c) => !isPinned(c.id));

  const renderConversationRow = (c: RailConversation) => {
    const label = c.title ?? p.chatHistory.untitled;
    const renaming = renamingId === c.id;
    const menuOpen = menu?.id === c.id;
    const pinned = isPinned(c.id);
    return (
      <li key={c.id} className={`convo-row ${c.active ? "active" : ""}`}>
        {renaming ? (
          <input
            ref={renameRef}
            className="convo-rename-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename(c.id);
              if (e.key === "Escape") {
                setRenamingId(null);
                setDraft("");
              }
            }}
            onBlur={() => commitRename(c.id)}
            aria-label={p.chatHistory.rename}
          />
        ) : (
          <>
            <button
              className="convo-item"
              onClick={() => selectConversation(c.id)}
              disabled={c.active}
              aria-current={c.active ? "true" : undefined}
              title={menuOpen ? undefined : label}
            >
              <span className="convo-item-dot" aria-hidden="true" />
              {pinned && (
                <span className="convo-pin-mark" aria-hidden="true">
                  <PinIcon filled />
                </span>
              )}
              <span className="convo-item-title">{label}</span>
              {c.busy && (
                <span
                  className="convo-spinner"
                  title={p.chatHistory.stillWaiting}
                  aria-label={p.chatHistory.processing}
                />
              )}
            </button>

            <div className="convo-menu-wrap">
              <button
                className="convo-menu-btn"
                aria-label={p.chatHistory.actions}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                title={p.chatHistory.actions}
                onClick={(e) => toggleMenu(e, c.id)}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"
                  fill="currentColor">
                  <circle cx="12" cy="5" r="1.6" />
                  <circle cx="12" cy="12" r="1.6" />
                  <circle cx="12" cy="19" r="1.6" />
                </svg>
              </button>
            </div>
          </>
        )}
      </li>
    );
  };

  return (
    <aside className={`convo-rail ${compact ? "compact" : ""}`} aria-label={p.chatHistory.title}>
      <div className="convo-brand">
        <span className="convo-brand-mark brand-logo-tile" aria-hidden="true">
          <LogoVinnie size={30} />
        </span>
        <span className="convo-brand-copy">
          <strong>Vinnie</strong>
          <span>{copy.subtitle}</span>
        </span>
        {onToggleCompact && (
          <button
            className="convo-rail-toggle"
            type="button"
            onClick={onToggleCompact}
            aria-label={compact ? copy.expand : copy.collapse}
            title={compact ? copy.expand : copy.collapse}
          >
            {compact ? "›" : "‹"}
          </button>
        )}
      </div>

      <div className="convo-rail-head">
        <button
          className="btn btn-primary btn-sm convo-new"
          onClick={chat.newConversation}
        >
          <span className="convo-new-plus" aria-hidden="true">+</span>
          <span className="convo-new-label">{p.chatHistory.newChat}</span>
        </button>
      </div>

      {chat.historyLoading ? (
        <p className="convo-empty">Loading conversations...</p>
      ) : chat.historyError ? (
        <p className="convo-empty">{chat.historyError}</p>
      ) : showList ? (
        <div className="convo-section">
          {pinnedConversations.length > 0 && (
            <div className="convo-pin-section">
              <div className="convo-section-label">{copy.pinned}</div>
              <ul className="convo-list pinned">
                {pinnedConversations.map(renderConversationRow)}
              </ul>
            </div>
          )}

          <button
            className="convo-recent-toggle"
            type="button"
            aria-expanded={recentOpen}
            onClick={() => setRecentOpen((v) => !v)}
          >
            <span className="convo-recent-left">
              <IconClock size={18} />
              <span>{copy.recent}</span>
            </span>
            <span className="convo-recent-caret" aria-hidden="true">
              {recentOpen ? "▾" : "▸"}
            </span>
          </button>

          {recentOpen &&
            (recentConversations.length > 0 ? (
              <ul className="convo-list recent">
                {recentConversations.map(renderConversationRow)}
              </ul>
            ) : (
              <p className="convo-empty">{copy.noRecent}</p>
            ))}
        </div>
      ) : (
        <p className="convo-empty">{p.chatHistory.empty}</p>
      )}

      <div className="convo-rail-footer">
        <Link className="convo-footer-link" href="/student/support" title={copy.help}>
          <IconChat size={18} />
          <span>{copy.help}</span>
        </Link>
        <button
          className="convo-footer-link"
          type="button"
          title={copy.feedback}
          onClick={() =>
            chat.prepareBlankDraft({
              subject: copy.feedbackSubject,
              category: "other",
            })
          }
        >
          <IconTicket size={18} />
          <span>{copy.feedback}</span>
        </button>
      </div>

      {/* Floating menu — portaled to <body>, position: fixed, so the scrollable list can never
          clip it. */}
      {menu &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="convo-menu"
            role="menu"
            style={{ position: "fixed", top: menu.top, left: menu.left }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="convo-menu-item"
              role="menuitem"
              onClick={() => togglePin(menu.id)}
            >
              {isPinned(menu.id) ? copy.unpin : copy.pin}
            </button>
            <button
              className="convo-menu-item"
              role="menuitem"
              onClick={() => startRename(menu.id)}
            >
              {p.chatHistory.rename}
            </button>
            <button
              className="convo-menu-item danger"
              role="menuitem"
              onClick={() => handleDelete(menu.id)}
            >
              {p.chatHistory.delete}
            </button>
          </div>,
          document.body
        )}
    </aside>
  );
}
