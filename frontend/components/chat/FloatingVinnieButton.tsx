"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import { IconChat } from "@/components/shell/icons";
import { VinnieChatWidget } from "./VinnieChatWidget";

const STR = {
  en: {
    askVinnie: "Ask Vinnie",
    intro: "Hi! I'm Vinnie. Ask me about your schedule, deadlines, tuition, events and student services.",
  },
  vi: {
    askVinnie: "Hỏi Vinnie",
    intro: "Chào bạn! Mình là Vinnie. Hỏi mình về lịch học, hạn chót, học phí, sự kiện và dịch vụ sinh viên nhé.",
  },
} as const;

const FAB_SIZE = 56;
const MARGIN = 16;
const STORAGE_KEY = "vinnie-fab-pos";
const INTRO_KEY = "vinnie-intro-shown"; // session flag so the greeting plays once per session
const DRAG_THRESHOLD = 5; // px of movement before a press becomes a drag (so a tap still opens)

// Widget panel size (mirrors portal.css .vinnie-widget) — used to anchor it near the bubble.
const WIDGET_W = 400;
const WIDGET_H = 600;
const GAP = 12;

type Pos = { x: number; y: number };

// Position the open widget next to the bubble. Returns undefined to fall back to the default
// bottom-right CSS anchor (bubble never moved, or a small/mobile viewport where the widget is a
// full-screen sheet). Otherwise it opens above the bubble (or below if there isn't room) and
// aligns to the bubble's nearest edge, clamped on-screen.
function computeWidgetStyle(pos: Pos | null): React.CSSProperties | undefined {
  if (!pos || typeof window === "undefined" || window.innerWidth <= 560) return undefined;
  const w = Math.min(WIDGET_W, window.innerWidth - 32);
  const h = Math.min(WIDGET_H, window.innerHeight - 32);
  let top = pos.y - GAP - h;
  if (top < MARGIN) top = pos.y + FAB_SIZE + GAP; // not enough room above → open below
  top = Math.max(MARGIN, Math.min(top, window.innerHeight - h - MARGIN));
  let left = pos.x + FAB_SIZE - w; // align widget right edge to bubble right edge
  left = Math.max(MARGIN, Math.min(left, window.innerWidth - w - MARGIN));
  return { left, top, right: "auto", bottom: "auto", width: w, height: h };
}

// Global floating chat bubble (default bottom-right) available across student pages. It is
// draggable — the user can reposition it anywhere and the spot is remembered (localStorage).
// Opening the bubble shows the compact Vinnie widget (anchored to the bubble's position), which
// shares conversation state with the full Ask Vinnie page. While the widget is open the bubble
// itself is hidden (the widget has its own close control), so there is no separate bottom
// collapse button. On the first visit of a session — before the bubble is ever opened — a small
// speech bubble types out a one-line greeting, then slides away.
export function FloatingVinnieButton() {
  const [open, setOpen] = useState(false);
  const chat = useChat();
  const { lang } = useI18n();
  const s = STR[lang];

  // null => use the default bottom-right CSS anchor. A non-null value means the user dragged the
  // bubble, so we position it with left/top (px) instead.
  const [pos, setPos] = useState<Pos | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  // First-visit greeting: a typewriter speech bubble shown until the user interacts with the FAB.
  const [introText, setIntroText] = useState("");
  const [introVisible, setIntroVisible] = useState(false);
  const [introLeaving, setIntroLeaving] = useState(false);

  const drag = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    moved: boolean;
    last: Pos;
  } | null>(null);

  function clamp(p: Pos): Pos {
    const maxX = Math.max(MARGIN, window.innerWidth - FAB_SIZE - MARGIN);
    const maxY = Math.max(MARGIN, window.innerHeight - FAB_SIZE - MARGIN);
    return {
      x: Math.min(Math.max(MARGIN, p.x), maxX),
      y: Math.min(Math.max(MARGIN, p.y), maxY),
    };
  }

  // Restore a saved position on mount (clamped to the current viewport).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setPos(clamp(JSON.parse(raw) as Pos));
    } catch {
      /* ignore malformed/absent storage */
    }
  }, []);

  // Keep the bubble on-screen if the window is resized.
  useEffect(() => {
    if (!pos) return;
    const onResize = () => setPos((p) => (p ? clamp(p) : p));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [pos]);

  // First-visit greeting: type the intro out once per session, hold, then slide it away. Any FAB
  // interaction (tap/drag) hides it early via dismissIntro(). Cancelled cleanly on unmount.
  useEffect(() => {
    if (open) return;
    try {
      if (sessionStorage.getItem(INTRO_KEY)) return;
    } catch {
      return;
    }
    let typer: ReturnType<typeof setInterval> | undefined;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const start = setTimeout(() => {
      try {
        sessionStorage.setItem(INTRO_KEY, "1");
      } catch {
        /* ignore */
      }
      setIntroVisible(true);
      const full = s.intro;
      let i = 0;
      typer = setInterval(() => {
        i += 1;
        setIntroText(full.slice(0, i));
        if (i >= full.length) {
          if (typer) clearInterval(typer);
          timers.push(setTimeout(() => setIntroLeaving(true), 3400));
          timers.push(setTimeout(() => setIntroVisible(false), 3800));
        }
      }, 34);
    }, 900);
    timers.push(start);
    return () => {
      if (typer) clearInterval(typer);
      timers.forEach(clearTimeout);
    };
  }, [open, s.intro]);

  function dismissIntro() {
    setIntroVisible(false);
    setIntroLeaving(false);
  }

  function onPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    if (e.button !== 0) return;
    dismissIntro();
    const rect = btnRef.current?.getBoundingClientRect();
    if (!rect) return;
    drag.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      originX: rect.left,
      originY: rect.top,
      moved: false,
      last: { x: rect.left, y: rect.top },
    };
    btnRef.current?.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: React.PointerEvent<HTMLButtonElement>) {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    const dx = e.clientX - d.startX;
    const dy = e.clientY - d.startY;
    if (!d.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    d.moved = true;
    d.last = clamp({ x: d.originX + dx, y: d.originY + dy });
    setPos(d.last);
  }

  function onPointerUp(e: React.PointerEvent<HTMLButtonElement>) {
    const d = drag.current;
    drag.current = null;
    if (!d || d.pointerId !== e.pointerId) return;
    btnRef.current?.releasePointerCapture?.(e.pointerId);
    if (d.moved) {
      // A drag — persist the new spot and DON'T toggle the widget.
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(d.last));
      } catch {
        /* ignore storage failures */
      }
    } else {
      // A plain tap/click — open the widget on a clean new chat.
      openWidget();
    }
  }

  // Opening the bubble always starts on a fresh new-chat draft rather than auto-loading an old
  // conversation. newConversation() is a no-op when the active conversation is already an empty
  // draft, so reopening without having sent anything keeps the same clean draft (no duplicates),
  // and once a message is sent that conversation continues for the rest of the open session.
  function openWidget() {
    chat.newConversation();
    setOpen(true);
  }

  const style: React.CSSProperties | undefined = pos
    ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" }
    : undefined;

  // Anchor the greeting just above the bubble, aligned to its nearer edge so the text grows
  // up/inward as it types. Uses the live drag position, or the default bottom-right spot.
  function introStyle(): React.CSSProperties {
    const fab =
      pos ?? {
        x: window.innerWidth - FAB_SIZE - 22,
        y: window.innerHeight - FAB_SIZE - 22,
      };
    const onRight = fab.x + FAB_SIZE / 2 > window.innerWidth / 2;
    return {
      bottom: window.innerHeight - fab.y + 12,
      ...(onRight
        ? { right: window.innerWidth - (fab.x + FAB_SIZE) }
        : { left: fab.x }),
    };
  }

  return (
    <>
      {open && (
        <VinnieChatWidget onClose={() => setOpen(false)} style={computeWidgetStyle(pos)} />
      )}
      {!open && (
        <>
          {introVisible && (
            <button
              type="button"
              className={`vinnie-intro ${introLeaving ? "leaving" : ""}`}
              style={introStyle()}
              onClick={() => {
                dismissIntro();
                openWidget();
              }}
              aria-label={s.askVinnie}
            >
              <span className="vinnie-intro-text">
                {introText}
                <span className="vinnie-intro-caret" aria-hidden="true" />
              </span>
            </button>
          )}
          <button
            ref={btnRef}
            className="vinnie-fab"
            style={style}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            aria-label={s.askVinnie}
            title={s.askVinnie}
          >
            <IconChat size={24} />
            {chat.unread > 0 && (
              <span className="vinnie-fab-badge" aria-hidden="true">
                {chat.unread > 9 ? "9+" : chat.unread}
              </span>
            )}
          </button>
        </>
      )}
    </>
  );
}
