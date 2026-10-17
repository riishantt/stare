import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "../api/client";
import type { Role, User } from "../api/types";

interface Ctx {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isRole: (...roles: Role[]) => boolean;
}
const AuthCtx = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => (tokenStore.get() ? tokenStore.user() : null));

  const logout = useCallback(() => { tokenStore.clear(); setUser(null); }, []);

  useEffect(() => { setUnauthorizedHandler(logout); }, [logout]);

  useEffect(() => {
    if (tokenStore.get()) {
      api.me().then((u) => { tokenStore.setUser(u); setUser(u); }).catch(() => { /* 401 handled by client */ });
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const t = await api.login(email, password);
    tokenStore.set(t.access_token);
    tokenStore.setUser(t.user);
    setUser(t.user);
  }, []);

  const value = useMemo<Ctx>(() => ({
    user, login, logout,
    isRole: (...roles) => !!user && roles.includes(user.role),
  }), [user, login, logout]);

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): Ctx {
  const c = useContext(AuthCtx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
