import { useState, useEffect, useCallback } from 'react';

export interface User {
  id: number;
  email: string;
  ho_ten: string;
  role: string;
  plan?: string;
}

export interface AuthState {
  token: string | null;
  user: User | null;
}

const STORAGE_TOKEN = 'vntaxdb_token';
const STORAGE_USER = 'vntaxdb_user';

function loadAuth(): AuthState {
  const token = localStorage.getItem(STORAGE_TOKEN);
  const raw = localStorage.getItem(STORAGE_USER);
  let user: User | null = null;
  if (raw) {
    try { user = JSON.parse(raw); } catch { /* ignore */ }
  }
  return { token, user };
}

export function useAuth() {
  const [auth, setAuth] = useState<AuthState>(loadAuth);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Đăng nhập thất bại');
    }
    const data = await res.json();
    localStorage.setItem(STORAGE_TOKEN, data.token);
    localStorage.setItem(STORAGE_USER, JSON.stringify(data.user));
    setAuth({ token: data.token, user: data.user });
  }, []);

  const register = useCallback(async (email: string, password: string, ho_ten: string) => {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, ho_ten }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Đăng ký thất bại');
    }
    const data = await res.json();
    localStorage.setItem(STORAGE_TOKEN, data.token);
    localStorage.setItem(STORAGE_USER, JSON.stringify(data.user));
    setAuth({ token: data.token, user: data.user });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_TOKEN);
    localStorage.removeItem(STORAGE_USER);
    setAuth({ token: null, user: null });
  }, []);

  // Check token validity on mount
  useEffect(() => {
    if (!auth.token) return;
    fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${auth.token}` },
    }).then(res => {
      if (res.status === 401) logout();
    }).catch(() => {});
  }, []); // eslint-disable-line

  return { ...auth, login, register, logout, isLoggedIn: !!auth.token };
}

export function authHeaders(token: string | null): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}
