"use client";

// Frontend demo auth layer. The FastAPI backend has no auth/session endpoint (only
// /chat, /chat/stream, /sources, /ingest/run, /health), so role is held client-side in
// localStorage. This is intentionally a DEMO session — swap login()/logout() for real
// calls (e.g. POST /auth/login -> {token, role}) when the backend grows auth; the rest
// of the app only depends on the `useAuth()` shape below.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

export type Role = "student" | "admin";

export interface SessionUser {
  role: Role;
  name: string;
  // student-only
  program?: string;
  year?: number;
  student_id?: string;
  // admin-only
  department?: string;
}

// Demo accounts surfaced on the login screen.
export const DEMO_STUDENT: SessionUser = {
  role: "student",
  name: "Minh Anh",
  program: "BS Computer Science",
  year: 2,
  student_id: "V2024001",
};

export const DEMO_ADMIN: SessionUser = {
  role: "admin",
  name: "Academic Office Admin",
  department: "Student Services / Academic Office",
};

const STORAGE_KEY = "vinuni-copilot-session";

interface AuthContextValue {
  user: SessionUser | null;
  // false until the first client read of localStorage completes — guards SSR/first paint
  // so ProtectedRoute doesn't redirect before the session is known.
  hydrated: boolean;
  login: (role: Role) => SessionUser;
  loginAs: (user: SessionUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  hydrated: false,
  login: () => DEMO_STUDENT,
  loginAs: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setUser(JSON.parse(raw) as SessionUser);
    } catch {
      /* corrupt / blocked storage — treat as logged out */
    }
    setHydrated(true);
  }, []);

  const persist = (next: SessionUser | null) => {
    try {
      if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore storage errors — session still lives in memory for this tab */
    }
  };

  const loginAs = (next: SessionUser) => {
    setUser(next);
    persist(next);
  };

  const login = (role: Role): SessionUser => {
    const next = role === "admin" ? DEMO_ADMIN : DEMO_STUDENT;
    loginAs(next);
    return next;
  };

  const logout = () => {
    setUser(null);
    persist(null);
  };

  return (
    <AuthContext.Provider value={{ user, hydrated, login, loginAs, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
