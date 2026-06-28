"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import { IconChat } from "@/components/shell/icons";
import { VinnieChatWidget } from "./VinnieChatWidget";

const STR = {
  en: {
    askVinnie: "Ask Vinnie",
    intro:
      "Hi, I'm Vinnie, your VinUni AI assistant for schedules, deadlines, tuition, events, and student services.",
  },
  vi: {
    askVinnie: "Hỏi Vinnie",
    intro:
      "Mình là Vinnie, trợ lý AI hỗ trợ sinh viên VinUni về lịch học, hạn chót, học phí, sự kiện và dịch vụ sinh viên.",
  },
} as const;

const FAB_SIZE = 56;
const MARGIN = 16;
const STORAGE_KEY = "vinnie-fab-pos";
const INTRO_KEY = "vinnie-intro-played";
const INTRO_HOLD_MS = 2800;
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
// collapse button. On page entry, a small speech bubble above it introduces Vinnie once with a
// lightweight typewriter effect.
export function FloatingVinnieButton() {
  const [open, setOpen] = useState(false);
  const chat = useChat();
  const { lang } = useI18n();
  const s = STR[lang];

  // null => use the default bottom-right CSS anchor. A non-null value means the user dragged the
  // bubble, so we position it with left/top (px) instead.
  const [pos, setPos] = useState<Pos | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  // Page-entry greeting: type once, then keep the finished line until the user interacts.
  const [introText, setIntroText] = useState("");
  const [introVisible, setIntroVisible] = useState(false);
  const [introTyping, setIntroTyping] = useState(false);
  const introPlayed = useRef(false);

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

  // Type the intro once when the page shell mounts. Reduced-motion users get the static line.
  useEffect(() => {
    if (open || introPlayed.current) return;
    introPlayed.current = true;

    const full = s.intro;
    try {
      if (sessionStorage.getItem(INTRO_KEY)) return;
      sessionStorage.setItem(INTRO_KEY, "1");
    } catch {
      /* If storage is unavailable, the ref still prevents repeats for this mount. */
    }

    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let hideTimer: ReturnType<typeof setTimeout> | undefined;
    if (reduceMotion) {
      setIntroText(full);
      setIntroVisible(true);
      setIntroTyping(false);
      hideTimer = setTimeout(() => setIntroVisible(false), INTRO_HOLD_MS);
      return () => {
        if (hideTimer) clearTimeout(hideTimer);
      };
    }

    const hideIntroSoon = () => {
      hideTimer = setTimeout(() => setIntroVisible(false), INTRO_HOLD_MS);
    };
    const stopTyping = () => {
      setIntroTyping(false);
      hideIntroSoon();
    };

    let typer: ReturnType<typeof setInterval> | undefined;
    let i = 1;
    setIntroText(full.slice(0, i));
    setIntroVisible(true);
    setIntroTyping(true);
    typer = setInterval(() => {
      i += 1;
      setIntroText(full.slice(0, i));
      if (i >= full.length && typer) {
        clearInterval(typer);
        stopTyping();
      }
    }, 34);

    return () => {
      if (typer) clearInterval(typer);
      if (hideTimer) clearTimeout(hideTimer);
    };
  }, [open, s.intro]);

  function onPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    if (e.button !== 0) return;
    setIntroVisible(false);
    setIntroTyping(false);
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
      // A plain tap/click — reopen the widget on the current/latest chat.
      openWidget();
    }
  }

  // Opening the bubble shows the current/latest conversation. It does not create a new
  // conversation; students can explicitly start one from the widget header.
  function openWidget() {
    setIntroVisible(false);
    setIntroTyping(false);
    setOpen(true);
  }

  const style: React.CSSProperties | undefined = pos
    ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" }
    : undefined;

  // Anchor the greeting just above the bubble, aligned to its nearer edge so the text grows
  // up/inward as it types. Uses the live drag position, or the default bottom-right spot.
  function introStyle(): React.CSSProperties {
    if (typeof window === "undefined") return {};
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
              className="vinnie-intro"
              style={introStyle()}
              onClick={openWidget}
              aria-label={s.askVinnie}
            >
              <span className="vinnie-intro-text">
                {introText}
                {introTyping && <span className="vinnie-intro-caret" aria-hidden="true" />}
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
