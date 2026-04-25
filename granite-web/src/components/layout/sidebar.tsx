'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Building2,
  ListTodo,
  CheckSquare,
  Mail,
  Settings2,
  BarChart3,
  LayoutDashboard,
  ClipboardCheck,
  Shield,
  ShieldCheck,
  Wifi,
  WifiOff,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { AdminLoginDialog } from '@/components/layout/AdminLoginDialog';
import { useAdmin } from '@/lib/admin-context';

const navigation = [
  { name: 'Компании', href: '/companies', icon: Building2 },
  { name: 'На проверке', href: '/review', icon: ClipboardCheck },
  { name: 'Follow-up', href: '/followup', icon: ListTodo },
  { name: 'Задачи', href: '/tasks', icon: CheckSquare },
  { name: 'Кампании', href: '/campaigns', icon: Mail },
  { name: 'Пайплайн', href: '/pipeline', icon: Settings2 },
  { name: 'Статистика', href: '/stats', icon: BarChart3 },
];

type BackendStatus = 'checking' | 'ok' | 'degraded' | 'offline';

interface HealthData {
  status: string;
  db: boolean;
  version?: string;
  total_companies?: number;
  campaigns_running?: number;
}

export function Sidebar() {
  const pathname = usePathname();
  const { isActive, remainingSeconds } = useAdmin();
  const [adminDialogOpen, setAdminDialogOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking');
  const [healthData, setHealthData] = useState<HealthData | null>(null);

  const mins = Math.floor(remainingSeconds / 60);
  const secs = remainingSeconds % 60;

  // Health check every 30 seconds
  useEffect(() => {
    let mounted = true;

    const check = async () => {
      try {
        const baseUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1\/?$/, '');
        const res = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(5000) });
        const data = await res.json();
        if (mounted) {
          setBackendStatus(data.status === 'ok' ? 'ok' : 'degraded');
          setHealthData(data);
        }
      } catch {
        if (mounted) setBackendStatus('offline');
      }
    };

    check();
    const interval = setInterval(check, 30000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const statusConfig: Record<BackendStatus, { label: string; icon: React.ElementType; color: string }> = {
    checking: { label: 'Проверка...', icon: Loader2, color: 'text-muted-foreground' },
    ok: { label: 'Online', icon: Wifi, color: 'text-success' },
    degraded: { label: 'Degraded', icon: WifiOff, color: 'text-yellow-500' },
    offline: { label: 'Offline', icon: WifiOff, color: 'text-destructive' },
  };

  const st = statusConfig[backendStatus];
  const StatusIcon = st.icon;

  return (
    <>
      <div className="flex h-full w-60 flex-col border-r border-border bg-sidebar">
        <div className="flex h-16 items-center border-b border-border px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold text-sidebar-primary">
            <LayoutDashboard className="h-5 w-5" />
            <span>Granite CRM</span>
          </Link>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {navigation.map((item) => {
            const isActiveRoute = pathname.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'group flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActiveRoute
                    ? 'bg-sidebar-accent text-sidebar-primary'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground'
                )}
              >
                <item.icon
                  className={cn(
                    'mr-3 h-5 w-5 flex-shrink-0',
                    isActiveRoute ? 'text-sidebar-primary' : 'text-sidebar-foreground/40 group-hover:text-sidebar-foreground/70'
                  )}
                  aria-hidden="true"
                />
                {item.name}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3 space-y-2">
          <ThemeToggle />
          <button
            onClick={() => setAdminDialogOpen(true)}
            className={cn(
              'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-success/10 text-success hover:bg-success/20'
                : 'bg-sidebar-primary/5 text-sidebar-foreground/70 hover:bg-sidebar-primary/10'
            )}
          >
            {isActive ? (
              <ShieldCheck className="h-4 w-4 shrink-0" />
            ) : (
              <Shield className="h-4 w-4 shrink-0" />
            )}
            {isActive ? (
              <span className="truncate">
                Админ {mins}:{secs.toString().padStart(2, '0')}
              </span>
            ) : (
              <span>Админ</span>
            )}
          </button>
          <div className={cn(
            "rounded-lg p-3 border",
            backendStatus === 'ok' && "bg-success/5 border-success/20",
            backendStatus === 'degraded' && "bg-yellow-500/5 border-yellow-500/20",
            backendStatus === 'offline' && "bg-destructive/5 border-destructive/20",
            backendStatus === 'checking' && "bg-muted border-border",
          )}>
            <p className="text-xs font-semibold uppercase tracking-wider opacity-75">Статус</p>
            <p className={cn("mt-1 text-sm font-medium flex items-center gap-1.5", st.color)}>
              <StatusIcon className={cn("h-3.5 w-3.5", backendStatus === 'checking' && "animate-spin")} />
              Backend: {st.label}
            </p>
            {healthData && backendStatus === 'ok' && (
              <div className="mt-2 space-y-0.5 text-[11px] text-muted-foreground">
                {healthData.version && <p>v{healthData.version}</p>}
                {healthData.total_companies !== undefined && (
                  <p>Компаний: {healthData.total_companies.toLocaleString()}</p>
                )}
                {healthData.campaigns_running !== undefined && healthData.campaigns_running > 0 && (
                  <p className="text-primary">Кампаний: {healthData.campaigns_running}</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <AdminLoginDialog
        open={adminDialogOpen}
        onClose={() => setAdminDialogOpen(false)}
      />
    </>
  );
}
