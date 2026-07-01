"use client";

import { ReviewFormDrawer } from "@/components/forms/ReviewFormDrawer";
import { ReviewTicketDrawer } from "@/components/tickets/ReviewTicketDrawer";
import { Toast } from "@/components/ui/primitives";
import { useChat } from "@/lib/chat";

// Student-wide chat overlays mounted once in RoleShell (inside ChatProvider): the Review
// Ticket drawer and the shared chat toast. Mounting here means the draft-review flow and its
// toasts work on every student page — the full chat page, the floating widget, and the
// support page — from a single instance, so there are never two competing drawers/toasts.
export function StudentChatOverlays() {
  const chat = useChat();
  return (
    <>
      <ReviewTicketDrawer />
      <ReviewFormDrawer />
      {chat.toast && <Toast message={chat.toast} onClose={() => chat.setToast(null)} />}
    </>
  );
}
