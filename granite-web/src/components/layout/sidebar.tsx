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
    <div className="flex h-full w-60 flex-col border-r bg-slate-50/50">
      <div className="flex h-16 items-center border-b px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-indigo-600">
          {/* V-18: h-6 w-6 → h-5 w-5 (20px) */}
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
                  ? 'bg-indigo-50 text-indigo-600'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              )}
            >
              <item.icon
                className={cn(
                  'mr-3 h-5 w-5 flex-shrink-0',
                  isActive ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-500'
                )}
                aria-hidden="true"
              />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-4">
        <div className="rounded-lg bg-indigo-600 p-4 text-white">
          <p className="text-xs font-semibold uppercase tracking-wider opacity-75">Статус</p>
          <p className="mt-1 text-sm font-medium">Backend: Online</p>
        </div>
      </div>
    </div>
  );
}
