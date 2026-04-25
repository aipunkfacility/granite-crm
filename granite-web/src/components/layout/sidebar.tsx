'use client';

import React, { useState } from 'react';
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

export function Sidebar() {
  const pathname = usePathname();
  const { isActive, remainingSeconds } = useAdmin();
  const [adminDialogOpen, setAdminDialogOpen] = useState(false);

  const mins = Math.floor(remainingSeconds / 60);
  const secs = remainingSeconds % 60;

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
          <div className="rounded-lg bg-sidebar-primary p-3 text-sidebar-primary-foreground">
            <p className="text-xs font-semibold uppercase tracking-wider opacity-75">Статус</p>
            <p className="mt-1 text-sm font-medium">Backend: Online</p>
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
