"use client";

import { usePathname } from "next/navigation";
import { StudentTopNav } from "@/components/shell/StudentTopNav";
import { ChatProvider } from "@/lib/chat";
import { FloatingVinnieButton } from "@/components/chat/FloatingVinnieButton";
import { StudentChatOverlays } from "@/components/chat/StudentChatOverlays";

// Academic Horizon student shell: horizontal top nav + content area, scoped to `.ah-ui` so the
// student pages adopt the Academic Horizon tokens. This preserves the behavior that previously
// lived in RoleShell's student branch — the shared ChatProvider (so the full chat page and the
// floating bubble are ONE conversation), the floating Vinnie button (everywhere except the full
// chat page), the chat overlays, and the "flush" full-height layout for /student/chat. No chat,
// streaming, API, auth, or mock logic is changed here.
export function StudentShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // The chat screen manages its own full-height layout.
  const flush = pathname.startsWith("/student/chat");
  // Floating Vinnie bubble: across student pages, but NOT on the full chat page itself.
  const showFloatingVinnie = !flush;

  return (
    <ChatProvider>
      <div className="ah-ui">
        <div className="ah-studentshell">
          <StudentTopNav />
          <main className={`ah-student-content ${flush ? "flush" : ""}`}>
            {children}
          </main>
        </div>
        {showFloatingVinnie && <FloatingVinnieButton />}
        <StudentChatOverlays />
      </div>
    </ChatProvider>
  );
}
