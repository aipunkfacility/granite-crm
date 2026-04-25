'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Ban, CheckCircle2, Loader2, X, AlertTriangle } from 'lucide-react';

/* Причины спама — whitelist бэкенда */
const SPAM_REASONS = [
  { value: 'aggregator', label: 'Агрегатор', description: 'Сайт-каталог, не ритуальная компания' },
  { value: 'closed', label: 'Закрылась', description: 'Компания прекратила деятельность' },
  { value: 'wrong_category', label: 'Не та категория', description: 'Не ритуальные услуги' },
  { value: 'duplicate_contact', label: 'Дубликат контактов', description: 'Телефон/email совпадает с другой компанией' },
  { value: 'other', label: 'Другое', description: 'Укажите причину в примечании' },
] as const;

type SpamReason = (typeof SPAM_REASONS)[number]['value'];

export type BatchAction = 'spam' | 'approve';

interface BatchResult {
  ok: boolean;
  processed: number;
  total: number;
}

interface BatchConfirmDialogProps {
  isOpen: boolean;
  action: BatchAction;
  selectedCount: number;
  onClose: () => void;
  onConfirm: (action: BatchAction, reason?: string) => Promise<BatchResult>;
}

export function BatchConfirmDialog({
  isOpen,
  action,
  selectedCount,
  onClose,
  onConfirm,
}: BatchConfirmDialogProps) {
  const [reason, setReason] = useState<SpamReason | ''>('');
  const [note, setNote] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [result, setResult] = useState<BatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isSpam = action === 'spam';

  const handleSubmit = async () => {
    if (isSpam && !reason) return;
    setIsSaving(true);
    setError(null);
    try {
      const fullReason = note.trim() ? `${reason}:${note.trim()}` : reason;
      const res = await onConfirm(action, isSpam ? fullReason : undefined);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || 'Произошла ошибка');
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetAndClose = () => {
    setReason('');
    setNote('');
    setResult(null);
    setError(null);
    onClose();
  };

  // Results screen
  if (result) {
    const hasFailures = result.processed < result.total;
    return (
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
        <div className="bg-card rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-border">
          <div className="p-6 border-b">
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${hasFailures ? 'bg-yellow-500/10' : 'bg-success/10'}`}>
                {hasFailures ? (
                  <AlertTriangle className="h-5 w-5 text-yellow-500" />
                ) : (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                )}
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  {hasFailures ? 'Частично выполнено' : 'Готово'}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Обработано {result.processed} из {result.total} компаний
                </p>
              </div>
            </div>
          </div>

          {hasFailures && (
            <div className="px-6 py-4 bg-yellow-500/5 border-b">
              <p className="text-sm text-yellow-600">
                {result.total - result.processed} компаний не обработаны (уже удалены или не найдены)
              </p>
            </div>
          )}

          <div className="p-5 flex justify-end">
            <Button onClick={handleResetAndClose}>
              Закрыть
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-border">
        {/* Header */}
        <div className={`p-6 border-b ${isSpam ? 'bg-destructive/5' : 'bg-success/5'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${isSpam ? 'bg-destructive/10' : 'bg-success/10'}`}>
                {isSpam ? (
                  <Ban className="h-5 w-5 text-destructive" />
                ) : (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                )}
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  {isSpam ? 'Массовый спам' : 'Массовое подтверждение'}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {selectedCount} компаний
                </p>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleResetAndClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {isSpam ? (
            <>
              <p className="text-sm text-muted-foreground">
                Выбранные компании будут помечены как спам и скрыты из списка. Автоматизация будет остановлена.
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
                        name="batch-spam-reason"
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
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Флаг «Требует проверки» будет снят для {selectedCount} компаний. Они вернутся в общий список.
            </p>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="px-6 py-3 bg-destructive/5 border-t">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Footer */}
        <div className="p-5 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={handleResetAndClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button
            variant={isSpam ? 'destructive' : 'default'}
            onClick={handleSubmit}
            disabled={isSpam ? !reason || isSaving : isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Выполняется...
              </>
            ) : isSpam ? (
              <>
                <Ban className="mr-2 h-4 w-4" />
                В спам ({selectedCount})
              </>
            ) : (
              <>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Подтвердить ({selectedCount})
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
