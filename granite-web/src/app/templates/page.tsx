'use client';

import { useState, useMemo } from 'react';
import { Channel } from '@/lib/api/templates';
import { useTemplates, useReloadTemplates } from '@/lib/hooks/use-templates';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { TemplateCard } from '@/components/templates/TemplateCard';
import { TemplatePreviewDialog } from '@/components/templates/TemplatePreviewDialog';
import {
  FileText,
  RefreshCw,
  Search,
  Mail,
  MessageCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const CHANNEL_FILTERS: { value: Channel | 'all'; label: string; icon?: React.ElementType }[] = [
  { value: 'all', label: 'Все' },
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'tg', label: 'TG', icon: MessageCircle },
  { value: 'wa', label: 'WA', icon: MessageCircle },
];

export default function TemplatesPage() {
  const [channelFilter, setChannelFilter] = useState<Channel | 'all'>('all');
  const [search, setSearch] = useState('');

  const { data, isLoading } = useTemplates(
    channelFilter !== 'all' ? { channel: channelFilter as Channel } : {},
  );
  const reloadMutation = useReloadTemplates();

  // Dialog state
  const [previewTemplate, setPreviewTemplate] = useState<any>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const templates = data?.items || [];
  const total = data?.total || 0;

  // Client-side search filter
  const filteredTemplates = useMemo(() => {
    if (!search.trim()) return templates;
    const q = search.toLowerCase();
    return templates.filter(
      t =>
        t.name.toLowerCase().includes(q) ||
        t.subject?.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q),
    );
  }, [templates, search]);

  const handlePreview = (template: any) => {
    setPreviewTemplate(template);
    setPreviewOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Шаблоны</h1>
          <p className="text-muted-foreground">
            Шаблоны сообщений для email, Telegram и WhatsApp.{' '}
            <span className="text-xs">(JSON — единственный source of truth)</span>
          </p>
        </div>
        <Button
          onClick={() => reloadMutation.mutate()}
          disabled={reloadMutation.isPending}
          variant="outline"
        >
          <RefreshCw className={cn('mr-2 h-4 w-4', reloadMutation.isPending && 'animate-spin')} />
          Перезагрузить из JSON
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        {/* Channel filter tabs */}
        <div className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-1">
          {CHANNEL_FILTERS.map(filter => (
            <button
              key={filter.value}
              type="button"
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                channelFilter === filter.value
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              onClick={() => setChannelFilter(filter.value)}
            >
              {filter.icon && <filter.icon className="h-3.5 w-3.5" />}
              {filter.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Поиск шаблонов..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>

        {/* Count */}
        <p className="text-sm text-muted-foreground">
          {filteredTemplates.length} из {total} шаблонов
        </p>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="space-y-4 rounded-xl border border-border p-6">
              <Skeleton className="h-6 w-1/3" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-24 w-full" />
              <div className="flex gap-2">
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-5 w-16" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredTemplates.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed rounded-xl bg-muted/50">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-medium text-foreground">
            {templates.length === 0 ? 'Нет шаблонов' : 'Ничего не найдено'}
          </h3>
          <p className="text-muted-foreground mt-1">
            {templates.length === 0
              ? 'Добавьте шаблоны в data/email_templates.json и нажмите «Перезагрузить».'
              : 'Попробуйте изменить фильтры или поисковый запрос.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredTemplates.map(template => (
            <TemplateCard
              key={template.name}
              template={template}
              onPreview={handlePreview}
            />
          ))}
        </div>
      )}

      {/* Dialogs */}
      <TemplatePreviewDialog
        isOpen={previewOpen}
        onClose={() => {
          setPreviewOpen(false);
          setPreviewTemplate(null);
        }}
        template={previewTemplate}
      />
    </div>
  );
}
