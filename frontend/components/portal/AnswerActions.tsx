"use client";

import { useState } from "react";
import type { ChatResponse } from "@/lib/types";
import { deriveState } from "@/lib/responseState";
import { usePortal } from "@/lib/portalI18n";
import {
  IconCalendar,
  IconBell,
  IconChat,
  IconExternal,
  IconTicket,
} from "@/components/shell/icons";

// Builds and downloads a minimal .ics so "Add to calendar" produces a real file.
function downloadIcs(title: string, description: string) {
  const stamp = new Date();
  const start = new Date(stamp.getTime() + 24 * 3600 * 1000);
  const fmt = (d: Date) => d.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//VinUni Student Copilot//EN",
    "BEGIN:VEVENT",
    `UID:${stamp.getTime()}@vinuni-copilot`,
    `DTSTAMP:${fmt(stamp)}`,
    `DTSTART:${fmt(start)}`,
    `SUMMARY:${title.replace(/\n/g, " ").slice(0, 120)}`,
    `DESCRIPTION:${description.replace(/\n/g, " ").slice(0, 600)}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "vinuni-reminder.ics";
  a.click();
  URL.revokeObjectURL(url);
}

// PLAN22.6.2 action row — a tidy hierarchy of next-step actions anchored to a completed
// answer. Primary: Ask follow-up. Secondary: Open source (only if cited) + Prepare ticket
// (opens the Review drawer; Vinnie NEVER auto-submits). Contextual: Add to calendar / Set
// reminder appear ONLY when the answer is actually about a date/deadline/event/schedule, so
// irrelevant actions don't clutter a plain or couldn't-answer reply. "Report issue" is the
// existing FlagForm rendered below this in MessageBubble.
export function AnswerActions({
  question,
  response,
  hasDateContext,
  onPrepareTicket,
  onAskFollowUp,
  onOpenPolicy,
  onToast,
}: {
  question: string;
  response: ChatResponse;
  hasDateContext: boolean;
  onPrepareTicket: () => void;
  onAskFollowUp: () => void;
  // Present only when the answer has citations — opens the shared SourceDrawer.
  onOpenPolicy?: () => void;
  onToast: (msg: string) => void;
}) {
  const { p } = usePortal();
  const [reminded, setReminded] = useState(false);
  const state = deriveState(response);

  // For conversational replies there's nothing actionable. Source access lives in the
  // per-answer citation list (ChatCitationList), so there's no "View source" here.
  if (state === "conversational") return null;

  return (
    <div className="answer-actions">
      <button className="answer-action primary" onClick={onAskFollowUp}>
        <IconChat size={13} /> {p.actAskFollowUp}
      </button>
      {onOpenPolicy && (
        <button className="answer-action" onClick={onOpenPolicy}>
          <IconExternal size={13} /> {p.actOpenPolicy}
        </button>
      )}
      <button className="answer-action" onClick={onPrepareTicket}>
        <IconTicket size={13} /> {p.actPrepareTicket}
      </button>
      {hasDateContext && (
        <>
          <button
            className="answer-action"
            onClick={() => downloadIcs(question, response.answer)}
          >
            <IconCalendar size={13} /> {p.actAddCalendar}
          </button>
          <button
            className={`answer-action ${reminded ? "done" : ""}`}
            onClick={() => {
              setReminded(true);
              onToast(`${p.actSetReminder} ✓`);
            }}
          >
            <IconBell size={13} /> {p.actSetReminder}
          </button>
        </>
      )}
    </div>
  );
}
