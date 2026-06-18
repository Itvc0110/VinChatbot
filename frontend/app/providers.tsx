"use client";

import { ThemeProvider } from "@/lib/theme";
import { LanguageProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";

// App-wide context: theme (light/dark) + UI language + auth/role session. Lives in the
// root layout so every route shares one theme, language and session state (the top-bar
// toggles + role guards all read from here).
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <AuthProvider>{children}</AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  );
}
