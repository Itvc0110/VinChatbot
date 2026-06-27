"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  ApiError,
  clearStoredAccessToken,
  getMe,
  getStoredAccessToken,
  login as apiLogin,
  logout as apiLogout,
  setStoredAccessToken,
  type BackendCurrentUser,
  type BackendRole,
} from "@/lib/api";

export type Role = "student" | "admin";

const ADMIN_ROLES = new Set(["global_admin", "institute_admin", "staff"]);
const USER_STORAGE_KEY = "vinuni-copilot-user";

export interface SessionUser extends BackendCurrentUser {
  role: Role;
  name: string;
  program?: string;
  year?: number;
  student_id?: string;
  department?: string;
}

interface AuthContextValue {
  user: SessionUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  // Backward-compatible alias used by existing route guards.
  hydrated: boolean;
  login: (email: string, password: string) => Promise<SessionUser>;
  logout: () => Promise<void>;
  hasRole: (role: BackendRole) => boolean;
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function primaryRole(roles: BackendRole[]): Role {
  return roles.some((role) => ADMIN_ROLES.has(role)) ? "admin" : "student";
}

function adminDepartment(user: BackendCurrentUser): string | undefined {
  if (user.roles.includes("global_admin")) return "Global Administration";
  if (user.institute) return `${user.institute.code} · ${user.institute.name_en}`;
  if (user.roles.includes("staff")) return "Staff";
  if (user.roles.includes("institute_admin")) return "Institute Administration";
  return undefined;
}

function toSessionUser(user: BackendCurrentUser): SessionUser {
  const role = primaryRole(user.roles);
  const profile = user.student_profile;
  return {
    ...user,
    role,
    name: user.preferred_name || user.full_name,
    program: profile?.program ?? profile?.major ?? undefined,
    year: profile?.academic_year ?? undefined,
    student_id: profile?.student_id,
    department: role === "admin" ? adminDepartment(user) : undefined,
  };
}

function persistUser(user: SessionUser | null): void {
  const storage = browserStorage();
  if (!storage) return;
  try {
    if (user) storage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
    else storage.removeItem(USER_STORAGE_KEY);
  } catch {
    /* ignore storage errors; auth still lives in memory for this tab */
  }
}

function readCachedUser(): SessionUser | null {
  const storage = browserStorage();
  if (!storage) return null;
  try {
    const raw = storage.getItem(USER_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  } catch {
    storage.removeItem(USER_STORAGE_KEY);
    return null;
  }
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  hydrated: false,
  login: async () => {
    throw new Error("AuthProvider is not mounted.");
  },
  logout: async () => {},
  hasRole: () => false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearSession = useCallback(() => {
    setUser(null);
    setToken(null);
    clearStoredAccessToken();
    persistUser(null);
  }, []);

  useEffect(() => {
    let alive = true;
    const storedToken = getStoredAccessToken();
    if (storedToken) {
      const cachedUser = readCachedUser();
      if (cachedUser) setUser(cachedUser);
      setToken(storedToken);
    } else {
      persistUser(null);
    }

    async function restore() {
      if (!storedToken) {
        if (alive) setIsLoading(false);
        return;
      }

      try {
        const currentUser = toSessionUser(await getMe(storedToken));
        if (!alive) return;
        setUser(currentUser);
        persistUser(currentUser);
      } catch (error) {
        if (!alive) return;
        if (error instanceof ApiError && error.status === 401) {
          clearSession();
        } else {
          clearSession();
        }
      } finally {
        if (alive) setIsLoading(false);
      }
    }

    void restore();
    return () => {
      alive = false;
    };
  }, [clearSession]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password);
    const nextUser = toSessionUser(response.user);
    setStoredAccessToken(response.access_token);
    persistUser(nextUser);
    setToken(response.access_token);
    setUser(nextUser);
    return nextUser;
  }, []);

  const logout = useCallback(async () => {
    const activeToken = token ?? getStoredAccessToken();
    try {
      if (activeToken) await apiLogout(activeToken);
    } catch {
      /* logout is best-effort; local session is cleared either way */
    } finally {
      clearSession();
    }
  }, [clearSession, token]);

  const hasRole = useCallback(
    (role: BackendRole) => user?.roles.includes(role) ?? false,
    [user]
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(user && token),
      isLoading,
      hydrated: !isLoading,
      login,
      logout,
      hasRole,
    }),
    [hasRole, isLoading, login, logout, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
