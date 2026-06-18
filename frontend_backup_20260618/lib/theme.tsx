"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

export type Theme = "light" | "dark";

// Inlined into <head> so the theme is applied BEFORE first paint — no white flash.
// Reads the persisted choice, else falls back to the OS preference. Keep this in sync
// with the ThemeProvider's storage key and the data-theme attribute it toggles.
export const THEME_INIT_SCRIPT = `(function(){try{var k=localStorage.getItem("vinchatbot-theme");var d=window.matchMedia("(prefers-color-scheme: dark)").matches;var t=k==="light"||k==="dark"?k:(d?"dark":"light");document.documentElement.dataset.theme=t;}catch(e){}})();`;

const STORAGE_KEY = "vinchatbot-theme";

const ThemeContext = createContext<{
  theme: Theme;
  toggle: () => void;
}>({ theme: "light", toggle: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Hydration-safe: start from whatever the pre-paint script already set on <html>.
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const current = (document.documentElement.dataset.theme as Theme) || "light";
    setTheme(current);
  }, []);

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* private mode / storage blocked — theme still applies for the session */
      }
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
