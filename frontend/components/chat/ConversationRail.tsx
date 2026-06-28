"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useChat } from "@/lib/chat";
import { usePortal } from "@/lib/portalI18n";

const MENU_W = 140; // px — dropdown width
const MENU_EST_H = 88; // px — approx height (2 items) for flip decision

// Conversation-history rail on the full Ask Vinnie page (PLAN22.6.2 §2). Lists in-memory
// conversations newest-first, with a "New chat" button, per-item rename/delete, and a subtle
// "processing" indicator for any conversation still streaming. Switching is allowed even while
// a reply streams — the in-flight answer lands in its own conversation.
//
// The Rename/Delete menu is rendered through a PORTAL to <body> as a position:fixed layer,
// anchored to the three-dot button via getBoundingClientRect(). This keeps it out of the
// scrollable list's clipping box, so it's never cut off when a row is near the bottom.
export function ConversationRail() {
  const { p } = usePortal();
  const chat = useChat();
  // Open menu: which conversation + the fixed-position coordinates measured from its button.
  const [menu, setMenu] = useState<{ id: string; top: number; left: number } | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const renameRef = useRef<HTMLInputElement>(null);

  const onlyEmptyActive =
    chat.conversations.length === 1 &&
    chat.conversations[0].empty &&
    !chat.conversations[0].persisted;
  const showList = !chat.historyLoading && !chat.historyError && !onlyEmptyActive;

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

  const titleFor = (id: string) => chat.conversations.find((c) => c.id === id)?.title ?? null;

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

  return (
    <aside className="convo-rail" aria-label={p.chatHistory.title}>
      <div className="convo-rail-head">
        <button
          className="btn btn-primary btn-sm convo-new"
          onClick={chat.newConversation}
        >
          + {p.chatHistory.newChat}
        </button>
      </div>

      {chat.historyLoading ? (
        <p className="convo-empty">Loading conversations...</p>
      ) : chat.historyError ? (
        <p className="convo-empty">{chat.historyError}</p>
      ) : onlyEmptyActive ? (
        <p className="convo-empty">{p.chatHistory.empty}</p>
      ) : showList ? (
        <ul className="convo-list">
          {chat.conversations.map((c) => {
            const label = c.title ?? p.chatHistory.untitled;
            const renaming = renamingId === c.id;
            const menuOpen = menu?.id === c.id;
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
                      // Suppress the native full-title tooltip while this row's menu is open.
                      title={menuOpen ? undefined : label}
                    >
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
          })}
        </ul>
      ) : null}

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
