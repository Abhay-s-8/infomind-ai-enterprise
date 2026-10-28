import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Role, User } from "../types";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(!!getToken());
  const qc = useQueryClient();

  const clear = useCallback(() => { setToken(null); setUser(null); qc.clear(); }, [qc]);

  useEffect(() => { setUnauthorizedHandler(clear); }, [clear]);
  useEffect(() => {
    if (!getToken()) return;
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    setUser(await api.me());
  }, []);

  const logout = useCallback(async () => {
    try { await api.logout(); } catch { /* token may already be invalid */ }
    clear();
  }, [clear]);

  // UI hint only: the backend enforces every permission.
  const can = useCallback((...roles: Role[]) => !!user && (user.role === "admin" || roles.includes(user.role)), [user]);

  const value = useMemo(() => ({ user, loading, login, logout, can }), [user, loading, login, logout, can]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
