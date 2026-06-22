"use client";

import { useState } from "react";
import type { ChatResponse } from "@/lib/types";
import { deriveState } from "@/lib/responseState";
import { usePortal } from "@/lib/portalI18n";
import { IconCalendar, IconBell, IconArrow } from "@/components/shell/icons";

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

// Action row shown under a completed assistant answer. "Report issue" is handled by the
// existing FlagForm rendered right below this in MessageBubble.
export function AnswerActions({
  question,
  response,
  onForward,
  onToast,
}: {
  question: string;
  response: ChatResponse;
  onForward: () => void;
  onToast: (msg: string) => void;
}) {
  const { p } = usePortal();
  const [reminded, setReminded] = useState(false);
  const [forwarded, setForwarded] = useState(false);
  const state = deriveState(response);

  // For conversational replies there's nothing actionable. Source access lives in the
  // per-answer citation list (ChatCitationList), so there's no "View source" here.
  if (state === "conversational") return null;

  const handleForward = () => {
    if (forwarded) return;
    setForwarded(true);
    onForward();
  };

  return (
    <div className="answer-actions">
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
      <button
        className={`answer-action ${forwarded ? "done" : ""}`}
        onClick={handleForward}
      >
        <IconArrow size={13} /> {forwarded ? `${p.actForward} ✓` : p.actForward}
      </button>
    </div>
  );
}
