import { createContext, useContext, useState, useCallback } from 'react';
import { api } from '../lib/apiClient';

export const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

function loadUser() {
  try {
    const raw = sessionStorage.getItem('clf_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function useAuthState() {
  const [user, setUser] = useState(loadUser);

  const login = useCallback(async (username, password, empresa_id) => {
    const data = await api.post('/api/auth/login', { username, password, empresa_id: empresa_id ?? '' });
    sessionStorage.setItem('clf_token', data.access_token);
    sessionStorage.setItem('clf_user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/api/auth/logout', {});
    } catch { /* best-effort */ }
    sessionStorage.removeItem('clf_token');
    sessionStorage.removeItem('clf_user');
    setUser(null);
  }, []);

  return { user, login, logout };
}
