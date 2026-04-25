'use client';

import { Template } from '@/lib/api/templates';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { X, Eye, Mail, MessageCircle, Code, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

const CHANNEL_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  email: { label: 'Email', color: 'bg-primary/10 text-primary', icon: Mail },
  tg: { label: 'TG', color: 'bg-info/10 text-info', icon: MessageCircle },
  wa: { label: 'WA', color: 'bg-success/10 text-success', icon: MessageCircle },
};

const BODY_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  plain: { label: 'Plain', color: 'bg-muted text-muted-foreground' },
  html: { label: 'HTML', color: 'bg-warning/10 text-warning' },
};

const PREVIEW_VALUES: Record<string, string> = {
  city: 'Москва',
  company_name: 'Гранит-М',
  website: 'granit-m.ru',
  from_name: 'Александр',
  contact_name: 'Иван',
  phone: '+7 (495) 123-45-67',
};

function renderPreview(html: string): string {
  return html.replace(/\{(\w+)\}/g, (match, key) => PREVIEW_VALUES[key] || match);
}

interface TemplatePreviewDialogProps {
  isOpen: boolean;
  onClose: () => void;
  template: Template | null;
}

export function TemplatePreviewDialog({ isOpen, onClose, template }: TemplatePreviewDialogProps) {
  if (!isOpen || !template) return null;

  const channelConf = CHANNEL_CONFIG[template.channel] || CHANNEL_CONFIG.email;
  const bodyConf = BODY_TYPE_CONFIG[template.body_type] || BODY_TYPE_CONFIG.plain;
  const ChannelIcon = channelConf.icon;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-4xl overflow-hidden border border-border">
        {/* Header */}
        <div className="p-6 border-b bg-primary/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Eye className="h-5 w-5 text-primary" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">
                Превью: {template.name}
              </h2>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Info bar */}
        <div className="px-6 py-3 border-b bg-muted/30 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Badge className={cn('px-2.5 py-0.5', channelConf.color)} variant="secondary">
              <ChannelIcon className="h-3 w-3 mr-1" />
              {channelConf.label}
            </Badge>
            <Badge className={cn('px-2.5 py-0.5', bodyConf.color)} variant="secondary">
              {template.body_type === 'html' ? <Code className="h-3 w-3 mr-1" /> : <FileText className="h-3 w-3 mr-1" />}
              {bodyConf.label}
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {template.subject && (
              <span>
                Тема: <span className="font-medium text-foreground">{template.subject}</span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-[11px] text-muted-foreground">Плейсхолдеры:</span>
            {Object.entries(PREVIEW_VALUES).map(([key, value]) => (
              <span key={key} className="text-[11px]">
                <span className="font-mono text-muted-foreground">{`{${key}}`}</span>
                <span className="text-muted-foreground">→</span>
                <span className="font-medium text-foreground">{value}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Preview */}
        <div className="p-6">
          {template.body_type === 'html' ? (
            <div className="rounded-lg border border-border overflow-hidden bg-white">
              <iframe
                srcDoc={renderPreview(template.body)}
                sandbox="allow-same-origin"
                className="w-full h-[600px] border-0"
                title={`Превью ${template.name}`}
              />
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-muted/30 p-6">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Текст сообщения</p>
              <p className="text-sm text-foreground whitespace-pre-line leading-relaxed">
                {renderPreview(template.body)}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>
            Закрыть
          </Button>
        </div>
      </div>
    </div>
  );
}
