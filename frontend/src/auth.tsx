import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, setAuthToken, UserProfile } from "@/src/api";
import { storage } from "@/src/utils/storage";

const TOKEN_KEY = "auth_token";

type AuthState = {
  ready: boolean;
  user: UserProfile | null;
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthCtx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const t = await storage.secureGet<string>(TOKEN_KEY, "");
        if (t) {
          setAuthToken(t as string);
          const me = await api.me();
          setUser(me);
        }
      } catch {
        setAuthToken(null);
        await storage.secureRemove(TOKEN_KEY).catch(() => {});
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const persist = useCallback(async (token: string, u: UserProfile) => {
    setAuthToken(token);
    await storage.secureSet(TOKEN_KEY, token);
    setUser(u);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    await persist(res.access_token, res.user);
  }, [persist]);

  const register = useCallback(async (email: string, password: string) => {
    const res = await api.register(email, password);
    await persist(res.access_token, res.user);
  }, [persist]);

  const signOut = useCallback(async () => {
    setAuthToken(null);
    await storage.secureRemove(TOKEN_KEY).catch(() => {});
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    try { setUser(await api.me()); } catch {}
  }, []);

  return (
    <AuthCtx.Provider value={{ ready, user, signIn, register, signOut, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
