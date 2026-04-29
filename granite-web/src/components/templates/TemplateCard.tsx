'use client';

import { Template } from '@/lib/api/templates';
import { Card, CardContent, CardHeader, CardTitle, CardAction } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Eye, FileText, Code, Mail, MessageCircle } from 'lucide-react';
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

function extractPlaceholders(text: string): string[] {
  const matches = text.match(/\{(\w+)\}/g);
  if (!matches) return [];
  const unique = new Set(matches.map(m => m.slice(1, -1)));
  return Array.from(unique);
}

interface TemplateCardProps {
  template: Template;
  onPreview?: (template: Template) => void;
}

export function TemplateCard({ template, onPreview }: TemplateCardProps) {
  const channelConf = CHANNEL_CONFIG[template.channel] || CHANNEL_CONFIG.email;
  const bodyConf = BODY_TYPE_CONFIG[template.body_type] || BODY_TYPE_CONFIG.plain;
  const ChannelIcon = channelConf.icon;

  const placeholders = extractPlaceholders(template.body);

  return (
    <Card className="overflow-hidden border-border hover:shadow-md transition-shadow">
      <CardHeader className="border-b bg-muted/50 py-4 px-6 flex flex-row items-center justify-between space-y-0">
        <div className="space-y-1">
          <CardTitle className="text-lg font-bold">{template.name}</CardTitle>
          {template.description && (
            <p className="text-xs text-muted-foreground">{template.description}</p>
          )}
        </div>
        <CardAction>
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
        </CardAction>
      </CardHeader>
      <CardContent className="p-6 space-y-4">
        {/* Subject */}
        {template.subject && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Тема</p>
            <p className="text-sm font-medium text-foreground">{template.subject}</p>
          </div>
        )}

        {/* Body */}
        {template.body_type === 'html' ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Превью</p>
            <div className="rounded-lg border border-border overflow-hidden bg-white">
              <iframe
                srcDoc={renderPreview(template.body)}
                sandbox="allow-same-origin"
                className="w-full h-[300px] border-0"
                title={`Превью ${template.name}`}
              />
            </div>
            {onPreview && (
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => onPreview(template)}
              >
                <Eye className="mr-2 h-4 w-4" />
                Превью
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Текст</p>
            <p className="text-sm text-foreground whitespace-pre-line line-clamp-6">
              {renderPreview(template.body)}
            </p>
          </div>
        )}

        {/* Placeholders */}
        {placeholders.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Плейсхолдеры</p>
            <div className="flex flex-wrap gap-1.5">
              {placeholders.map(ph => (
                <Badge key={ph} variant="outline" className="text-[11px] font-mono">
                  {`{${ph}}`}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Footer: edit hint */}
        <div className="flex items-center justify-between pt-3 border-t">
          <p className="text-[11px] text-muted-foreground">
            Редактирование: data/email_templates.json
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
