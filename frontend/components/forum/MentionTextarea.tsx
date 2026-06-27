"use client";

import { useEffect, useRef, useState } from "react";
import { searchForumMembers } from "@/lib/api";
import { usePortal } from "@/lib/portalI18n";
import type { ForumMember } from "@/lib/portalTypes";

function displayName(m: ForumMember): string {
  return m.preferred_name || m.full_name;
}

// Find the @mention token currently being typed: the run of non-space characters that follows
// the most recent "@" up to the caret. Returns null when the caret is not inside such a token.
function activeToken(text: string, caret: number): { start: number; query: string } | null {
  const upto = text.slice(0, caret);
  const at = upto.lastIndexOf("@");
  if (at === -1) return null;
  // "@" must start a word (begin of string or preceded by whitespace).
  if (at > 0 && !/\s/.test(upto[at - 1])) return null;
  const query = upto.slice(at + 1);
  if (/\s/.test(query)) return null; // a space closed the token
  return { start: at, query };
}

// Controlled textarea with @mention autocomplete. The parent owns both the text (`value`) and
// the resolved `mentions` list (so it can send mentioned_user_ids on submit). Selecting a member
// inserts "@Name " and records the member; deleting that text drops the mention.
export function MentionTextarea({
  value,
  onChange,
  mentions,
  onMentionsChange,
  placeholder,
  rows = 4,
  disabled = false,
  autoFocus = false,
  id,
}: {
  value: string;
  onChange: (text: string) => void;
  mentions: ForumMember[];
  onMentionsChange: (members: ForumMember[]) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  autoFocus?: boolean;
  id?: string;
}) {
  const { p } = usePortal();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [query, setQuery] = useState<string | null>(null);
  const [matches, setMatches] = useState<ForumMember[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  // Debounced member search whenever the active @token changes.
  useEffect(() => {
    if (query === null || query.length < 1) {
      setMatches([]);
      return;
    }
    let alive = true;
    const handle = setTimeout(() => {
      searchForumMembers(query)
        .then((found) => {
          if (!alive) return;
          setMatches(found);
          setActive(0);
          setOpen(found.length > 0);
        })
        .catch(() => {
          if (alive) setMatches([]);
        });
    }, 180);
    return () => {
      alive = false;
      clearTimeout(handle);
    };
  }, [query]);

  const syncToken = () => {
    const el = ref.current;
    if (!el) return;
    const token = activeToken(el.value, el.selectionStart ?? el.value.length);
    setQuery(token ? token.query : null);
    if (!token) setOpen(false);
  };

  const prune = (text: string, current: ForumMember[]): ForumMember[] =>
    current.filter((m) => text.includes(`@${displayName(m)}`));

  const handleChange = (next: string) => {
    onChange(next);
    onMentionsChange(prune(next, mentions));
    // token detection runs after the value/caret settle
    requestAnimationFrame(syncToken);
  };

  const select = (member: ForumMember) => {
    const el = ref.current;
    if (!el) return;
    const caret = el.selectionStart ?? value.length;
    const token = activeToken(value, caret);
    if (!token) return;
    const inserted = `@${displayName(member)} `;
    const next = value.slice(0, token.start) + inserted + value.slice(caret);
    onChange(next);
    const deduped = mentions.some((m) => m.id === member.id)
      ? mentions
      : [...mentions, member];
    onMentionsChange(prune(next, deduped));
    setOpen(false);
    setQuery(null);
    // Restore focus + place caret right after the inserted mention.
    requestAnimationFrame(() => {
      const pos = token.start + inserted.length;
      el.focus();
      el.setSelectionRange(pos, pos);
    });
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!open || matches.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (a + 1) % matches.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (a - 1 + matches.length) % matches.length);
    } else if (e.key === "Enter" || e.key === "Tab") {
      e.preventDefault();
      select(matches[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="forum-mention-wrap">
      <textarea
        id={id}
        ref={ref}
        className="textarea forum-mention-input"
        value={value}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        autoFocus={autoFocus}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={onKeyDown}
        onKeyUp={syncToken}
        onClick={syncToken}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
      />
      {open && (
        <ul className="forum-mention-menu" role="listbox">
          {matches.map((m, i) => (
            <li key={m.id}>
              <button
                type="button"
                role="option"
                aria-selected={i === active}
                className={`forum-mention-opt ${i === active ? "active" : ""}`}
                // onMouseDown (not onClick) so it fires before the textarea blur closes the menu.
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(m);
                }}
              >
                <span className="forum-mention-name">{displayName(m)}</span>
                {m.email && <span className="forum-mention-email">{m.email}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {query !== null && query.length >= 1 && matches.length === 0 && (
        <p className="forum-mention-hint">{p.forum.mentionNoResults}</p>
      )}
    </div>
  );
}
