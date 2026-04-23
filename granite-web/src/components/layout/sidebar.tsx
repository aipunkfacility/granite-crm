'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Building2,
  ListTodo,
  CheckSquare,
  Mail,
  Settings2,
  BarChart3,
  LayoutDashboard
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/components/ui/theme-toggle';

const navigation = [
  { name: 'Компании', href: '/companies', icon: Building2 },
  { name: 'Follow-up', href: '/followup', icon: ListTodo },
  { name: 'Задачи', href: '/tasks', icon: CheckSquare },
  { name: 'Кампании', href: '/campaigns', icon: Mail },
  { name: 'Пайплайн', href: '/pipeline', icon: Settings2 },
  { name: 'Статистика', href: '/stats', icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full w-60 flex-col border-r border-border bg-sidebar">
      <div className="flex h-16 items-center border-b border-border px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-sidebar-primary">
          <LayoutDashboard className="h-5 w-5" />
          <span>Granite CRM</span>
        </Link>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'group flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-primary'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground'
              )}
            >
              <item.icon
                className={cn(
                  'mr-3 h-5 w-5 flex-shrink-0',
                  isActive ? 'text-sidebar-primary' : 'text-sidebar-foreground/40 group-hover:text-sidebar-foreground/70'
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
        <div className="rounded-lg bg-sidebar-primary p-3 text-sidebar-primary-foreground">
          <p className="text-xs font-semibold uppercase tracking-wider opacity-75">Статус</p>
          <p className="mt-1 text-sm font-medium">Backend: Online</p>
        </div>
      </div>
    </div>
  );
}
