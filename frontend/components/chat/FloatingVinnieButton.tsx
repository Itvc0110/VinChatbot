"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";
import { IconChat } from "@/components/shell/icons";
import { VinnieChatWidget } from "./VinnieChatWidget";

const STR = {
  en: { askVinnie: "Ask Vinnie" },
  vi: { askVinnie: "Hỏi Vinnie" },
} as const;

const FAB_SIZE = 56;
const MARGIN = 16;
const STORAGE_KEY = "vinnie-fab-pos";
const DRAG_THRESHOLD = 5; // px of movement before a press becomes a drag (so a tap still opens)

type Pos = { x: number; y: number };

// Global floating chat bubble (default bottom-right) available across student pages. It is
// draggable — the user can reposition it anywhere and the spot is remembered (localStorage).
// Opening the bubble shows the compact Vinnie widget, which shares conversation state with the
// full Ask Vinnie page. While the widget is open the bubble itself is hidden (the widget has
// its own close control), so there is no separate bottom collapse button.
export function FloatingVinnieButton() {
  const [open, setOpen] = useState(false);
  const chat = useChat();
  const { lang } = useI18n();
  const s = STR[lang];

  // null => use the default bottom-right CSS anchor. A non-null value means the user dragged the
  // bubble, so we position it with left/top (px) instead.
  const [pos, setPos] = useState<Pos | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
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

  function onPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    if (e.button !== 0) return;
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
      // A plain tap/click — open the widget.
      setOpen(true);
    }
  }

  const style: React.CSSProperties | undefined = pos
    ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" }
    : undefined;

  return (
    <>
      {open && <VinnieChatWidget onClose={() => setOpen(false)} />}
      {!open && (
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
      )}
    </>
  );
}
