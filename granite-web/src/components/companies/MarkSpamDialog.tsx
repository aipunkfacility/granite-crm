'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Ban, Loader2, X } from 'lucide-react';

/* Причины спама — whitelist бэкенда */
const SPAM_REASONS = [
  { value: 'aggregator', label: 'Агрегатор', description: 'Сайт-каталог, не ритуальная компания' },
  { value: 'closed', label: 'Закрылась', description: 'Компания прекратила деятельность' },
  { value: 'wrong_category', label: 'Не та категория', description: 'Не ритуальные услуги' },
  { value: 'duplicate_contact', label: 'Дубликат контактов', description: 'Телефон/email совпадает с другой компанией' },
  { value: 'other', label: 'Другое', description: 'Укажите причину в примечании' },
] as const;

type SpamReason = (typeof SPAM_REASONS)[number]['value'];

interface MarkSpamDialogProps {
  companyName: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string, note?: string) => void;
  isSaving: boolean;
}

export function MarkSpamDialog({
  companyName,
  isOpen,
  onClose,
  onConfirm,
  isSaving,
}: MarkSpamDialogProps) {
  const [reason, setReason] = useState<SpamReason | ''>('');
  const [note, setNote] = useState('');

  if (!isOpen) return null;

  const handleSubmit = () => {
    if (!reason) return;
    onConfirm(reason, note.trim() || undefined);
  };

  const handleResetAndClose = () => {
    setReason('');
    setNote('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-border">
        {/* Header */}
        <div className="p-6 border-b bg-destructive/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
                <Ban className="h-5 w-5 text-destructive" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">В спам</h2>
                <p className="text-sm text-muted-foreground truncate max-w-[260px]">{companyName}</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleResetAndClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          <p className="text-sm text-muted-foreground">
            Компания будет скрыта из списка. Сегмент сменится на «Спам», автоматизация остановится.
          </p>

          {/* Радио-кнопки причин */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest">Причина</p>
            <div className="space-y-1.5">
              {SPAM_REASONS.map((r) => (
                <label
                  key={r.value}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    reason === r.value
                      ? 'border-destructive/40 bg-destructive/5'
                      : 'border-border hover:bg-muted/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="spam-reason"
                    value={r.value}
                    checked={reason === r.value}
                    onChange={() => setReason(r.value)}
                    className="mt-0.5 h-4 w-4 border-border text-destructive focus:ring-destructive/30"
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">{r.label}</p>
                    <p className="text-xs text-muted-foreground">{r.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Примечание */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest">Примечание (необязательно)</p>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Дополнительная информация..."
              className="min-h-[72px] resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="p-5 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={handleResetAndClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={!reason || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Перемещение...
              </>
            ) : (
              <>
                <Ban className="mr-2 h-4 w-4" />
                В спам
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
