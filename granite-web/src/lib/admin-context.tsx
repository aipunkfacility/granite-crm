'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

interface AdminState {
  token: string | null;
  expiresAt: number | null; // epoch ms
  isActive: boolean;
  remainingSeconds: number;
  login: (token: string, expiresIn: number) => void;
  logout: () => void;
}

const AdminContext = createContext<AdminState | null>(null);

export function AdminProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  const isActive = token !== null && expiresAt !== null && Date.now() < expiresAt;

  // Tick every second when active
  useEffect(() => {
    if (!isActive) {
      setRemainingSeconds(0);
      return;
    }

    const update = () => {
      const rem = Math.max(0, Math.floor((expiresAt! - Date.now()) / 1000));
      setRemainingSeconds(rem);
      if (rem <= 0) {
        setToken(null);
        setExpiresAt(null);
      }
    };

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [isActive, expiresAt]);

  const login = useCallback((newToken: string, expiresIn: number) => {
    setToken(newToken);
    setExpiresAt(Date.now() + expiresIn * 1000);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setExpiresAt(null);
    setRemainingSeconds(0);
  }, []);

  return (
    <AdminContext.Provider value={{ token, expiresAt, isActive, remainingSeconds, login, logout }}>
      {children}
    </AdminContext.Provider>
  );
}

export function useAdmin() {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error('useAdmin must be used within AdminProvider');
  return ctx;
}
