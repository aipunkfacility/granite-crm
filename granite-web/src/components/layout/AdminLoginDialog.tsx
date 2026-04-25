'use client';

import React, { useState } from 'react';
import { adminLogin } from '@/lib/api/admin';
import { useAdmin } from '@/lib/admin-context';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Shield, ShieldOff } from 'lucide-react';

interface AdminLoginDialogProps {
  open: boolean;
  onClose: () => void;
}

export function AdminLoginDialog({ open, onClose }: AdminLoginDialogProps) {
  const { login, isActive, remainingSeconds, logout } = useAdmin();
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const handleLogin = async () => {
    if (!password.trim()) return;
    setLoading(true);
    try {
      const result = await adminLogin(password);
      login(result.token, result.expires_in);
      toast.success(`Админ-режим активирован на ${Math.floor(result.expires_in / 60)} мин`);
      setPassword('');
      onClose();
    } catch (err: any) {
      if (err.message?.includes('403')) {
        toast.error('Админ-режим не настроен на сервере (GRANITE_ADMIN_PASSWORD)');
      } else {
        toast.error('Неверный пароль');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleLogin();
    if (e.key === 'Escape') onClose();
  };

  const handleLogout = () => {
    logout();
    toast.info('Админ-режим отключён');
    onClose();
  };

  // If already active — show status + logout
  if (isActive) {
    const mins = Math.floor(remainingSeconds / 60);
    const secs = remainingSeconds % 60;
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
        <div
          className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-success/10">
              <Shield className="h-5 w-5 text-success" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Админ-режим активен</h3>
              <p className="text-sm text-muted-foreground">
                Осталось {mins}:{secs.toString().padStart(2, '0')}
              </p>
            </div>
          </div>

          <p className="text-sm text-muted-foreground mb-4">
            Доступны batch-операции: массовая пометка спамом и подтверждение.
          </p>

          <Button
            variant="outline"
            className="w-full border-destructive/30 text-destructive hover:bg-destructive/10"
            onClick={handleLogout}
          >
            <ShieldOff className="mr-2 h-4 w-4" />
            Отключить админ-режим
          </Button>
        </div>
      </div>
    );
  }

  // Login form
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            <Shield className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-foreground">Админ-режим</h3>
            <p className="text-sm text-muted-foreground">Введите пароль для batch-операций</p>
          </div>
        </div>

        <Input
          type="password"
          placeholder="Пароль администратора"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
          className="mb-4"
        />

        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={onClose}>
            Отмена
          </Button>
          <Button
            className="flex-1"
            onClick={handleLogin}
            disabled={loading || !password.trim()}
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Shield className="mr-2 h-4 w-4" />}
            Войти
          </Button>
        </div>
      </div>
    </div>
  );
}
