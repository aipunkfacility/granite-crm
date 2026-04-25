'use client';

import { useState, useEffect, useRef } from 'react';
import { Template, Channel, BodyType } from '@/lib/api/templates';
import { useCreateTemplate, useUpdateTemplate } from '@/lib/hooks/use-templates';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  X,
  Loader2,
  FileText,
  Code,
  Upload,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

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

const AVAILABLE_PLACEHOLDERS = [
  '{city}',
  '{company_name}',
  '{website}',
  '{from_name}',
  '{contact_name}',
  '{phone}',
];

interface TemplateFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  template?: Template | null;
}

export function TemplateFormDialog({ isOpen, onClose, template }: TemplateFormDialogProps) {
  const isEdit = !!template;
  const createMutation = useCreateTemplate();
  const updateMutation = useUpdateTemplate();

  const [name, setName] = useState('');
  const [channel, setChannel] = useState<Channel>('email');
  const [bodyType, setBodyType] = useState<BodyType>('plain');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [description, setDescription] = useState('');
  const [fileWarning, setFileWarning] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset form when dialog opens or template changes
  useEffect(() => {
    if (isOpen) {
      if (template) {
        setName(template.name);
        setChannel(template.channel);
        setBodyType(template.body_type);
        setSubject(template.subject);
        setBody(template.body);
        setDescription(template.description);
      } else {
        setName('');
        setChannel('email');
        setBodyType('plain');
        setSubject('');
        setBody('');
        setDescription('');
      }
      setFileWarning(false);
    }
  }, [isOpen, template]);

  // If channel is tg or wa, force bodyType to plain
  useEffect(() => {
    if (channel === 'tg' || channel === 'wa') {
      setBodyType('plain');
    }
  }, [channel]);

  if (!isOpen) return null;

  const isSaving = createMutation.isPending || updateMutation.isPending;

  const handleNameChange = (value: string) => {
    // Only allow latin, numbers, underscore
    if (value === '' || /^[a-z0-9_]+$/.test(value)) {
      setName(value);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 500 * 1024) {
      setFileWarning(true);
    } else {
      setFileWarning(false);
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setBody(text);
    };
    reader.readAsText(file);
  };

  const handleSave = async () => {
    if (!name.trim() || !body.trim()) return;

    if (isEdit) {
      updateMutation.mutate(
        {
          name: template!.name,
          payload: {
            channel,
            subject: subject || undefined,
            body,
            body_type: bodyType,
            description: description || undefined,
          },
        },
        {
          onSuccess: () => {
            onClose();
          },
        },
      );
    } else {
      createMutation.mutate(
        {
          name: name.trim(),
          channel,
          subject: subject || undefined,
          body,
          body_type: bodyType,
          description: description || undefined,
        },
        {
          onSuccess: () => {
            onClose();
          },
        },
      );
    }
  };

  const htmlDisabled = channel === 'tg' || channel === 'wa';

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border border-border">
        {/* Header */}
        <div className="p-6 border-b bg-primary/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <FileText className="h-5 w-5 text-primary" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">
                {isEdit ? 'Редактирование шаблона' : 'Новый шаблон'}
              </h2>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="tpl-name" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Название
            </Label>
            <Input
              id="tpl-name"
              value={name}
              onChange={e => handleNameChange(e.target.value)}
              placeholder="например: cold_email_msk"
              disabled={isEdit}
              className="font-mono"
            />
            <p className="text-[11px] text-muted-foreground">Только латинские буквы, цифры и подчёркивания</p>
          </div>

          {/* Channel */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Канал</Label>
            <Select value={channel} onValueChange={(v) => setChannel(v as Channel)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="tg">Telegram</SelectItem>
                <SelectItem value="wa">WhatsApp</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Body type toggle */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Тип содержимого</Label>
            <div className="flex gap-2">
              <button
                type="button"
                className={cn(
                  'flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors',
                  bodyType === 'plain'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setBodyType('plain')}
              >
                <FileText className="h-4 w-4" />
                Plain text
              </button>
              <button
                type="button"
                className={cn(
                  'flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors relative',
                  bodyType === 'html'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted',
                  htmlDisabled && 'opacity-50 cursor-not-allowed hover:bg-transparent'
                )}
                onClick={() => !htmlDisabled && setBodyType('html')}
                disabled={htmlDisabled}
                title={htmlDisabled ? 'HTML недоступен для Telegram и WhatsApp' : ''}
              >
                <Code className="h-4 w-4" />
                HTML
              </button>
            </div>
            {htmlDisabled && (
              <p className="text-[11px] text-muted-foreground">HTML недоступен для каналов Telegram и WhatsApp</p>
            )}
          </div>

          {/* Subject */}
          <div className="space-y-1.5">
            <Label htmlFor="tpl-subject" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Тема письма
            </Label>
            <Input
              id="tpl-subject"
              value={subject}
              onChange={e => setSubject(e.target.value)}
              placeholder="Тема сообщения"
            />
          </div>

          {/* Body */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Тело
            </Label>
            {bodyType === 'plain' ? (
              <Textarea
                value={body}
                onChange={e => setBody(e.target.value)}
                placeholder="Текст сообщения..."
                rows={8}
              />
            ) : (
              <div className="space-y-3">
                {/* File upload */}
                <div className="flex items-center gap-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".html,.htm"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    Загрузить HTML-файл
                  </Button>
                  {body && (
                    <span className="text-xs text-muted-foreground">Файл загружен</span>
                  )}
                </div>
                {fileWarning && (
                  <div className="flex items-center gap-2 rounded-md border border-warning/30 bg-warning/5 px-3 py-2">
                    <AlertTriangle className="h-4 w-4 text-warning shrink-0" />
                    <p className="text-xs text-warning">Файл превышает 500 КБ. Рекомендуется использовать файлы меньшего размера.</p>
                  </div>
                )}
                {/* HTML preview */}
                {body && (
                  <div className="rounded-lg border border-border overflow-hidden bg-white">
                    <iframe
                      srcDoc={renderPreview(body)}
                      sandbox="allow-same-origin"
                      className="w-full h-[300px] border-0"
                      title="Превью HTML"
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Placeholders info */}
          <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Доступные плейсхолдеры
            </p>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_PLACEHOLDERS.map(ph => (
                <Badge key={ph} variant="outline" className="text-[11px] font-mono">
                  {ph}
                </Badge>
              ))}
            </div>
            <p className="text-[11px] text-muted-foreground">
              Только в тексте тегов, не в атрибутах (href, src, alt).
            </p>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <Label htmlFor="tpl-desc" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Описание
            </Label>
            <Input
              id="tpl-desc"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Краткое описание шаблона"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="p-5 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button
            onClick={handleSave}
            disabled={!name.trim() || !body.trim() || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Сохранение...
              </>
            ) : (
              'Сохранить'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
