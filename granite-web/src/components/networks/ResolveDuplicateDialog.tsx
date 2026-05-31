'use client';

import React, { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as RadioGroup from '@radix-ui/react-radio-group';
import { NetworkCandidateGroup } from '@/lib/types/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { resolveNetworkGroup } from '@/lib/api/networks';
import { toast } from 'sonner';
import { Copy, Loader2, MapPin, X } from 'lucide-react';

interface ResolveDuplicateDialogProps {
  group: NetworkCandidateGroup;
  isOpen: boolean;
  onClose: () => void;
  onResolved: () => void;
}

export function ResolveDuplicateDialog({
  group,
  isOpen,
  onClose,
  onResolved,
}: ResolveDuplicateDialogProps) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const handleResolve = async () => {
    if (!selectedId) return;
    setLoading(true);
    try {
      const result = await resolveNetworkGroup({
        group_id: group.group_id,
        action: 'duplicate',
        target_id: selectedId,
      });
      toast.success(result.message || 'Группа обработана как дубли');
      onResolved();
    } catch (err: any) {
      toast.error(`Ошибка: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-foreground/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-card p-6 shadow-2xl focus:outline-none">
          <Dialog.Title className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Copy className="h-5 w-5 text-orange-400" />
            Это дубли
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted-foreground">
            Выберите компанию, которая является оригиналом. Остальные будут помечены как дубликаты.
          </Dialog.Description>

          <Dialog.Close asChild>
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-3 top-3 h-7 w-7"
            >
              <X className="h-4 w-4" />
            </Button>
          </Dialog.Close>

          <RadioGroup.Root
            className="mt-4 space-y-2"
            value={selectedId?.toString() ?? ''}
            onValueChange={(val) => setSelectedId(Number(val))}
          >
            {group.companies.map((company) => (
              <div key={company.id} className="flex items-start gap-3">
                <RadioGroup.Item
                  id={`company-${company.id}`}
                  value={company.id.toString()}
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-border bg-background data-[state=checked]:border-primary data-[state=checked]:bg-primary"
                >
                  <RadioGroup.Indicator className="flex h-2 w-2 rounded-full bg-primary-foreground" />
                </RadioGroup.Item>
                <Label
                  htmlFor={`company-${company.id}`}
                  className="flex-1 cursor-pointer rounded-lg border border-border/60 bg-muted/30 px-3 py-2 has-data-[state=checked]:border-primary"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground">{company.name}</span>
                    <span className="text-xs text-muted-foreground shrink-0">ID {company.id}</span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                    <MapPin className="h-3 w-3 shrink-0" />
                    <span>{company.city}</span>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-1 text-xs text-muted-foreground">
                    {company.phones.length > 0 && <span>{company.phones[0]}</span>}
                    {company.emails.length > 0 && <span>{company.emails[0]}</span>}
                  </div>
                </Label>
              </div>
            ))}
          </RadioGroup.Root>

          <div className="mt-6 flex justify-end gap-2">
            <Button variant="outline" onClick={onClose} disabled={loading}>
              Отмена
            </Button>
            <Button
              onClick={handleResolve}
              disabled={!selectedId || loading}
              className="bg-orange-500 hover:bg-orange-600 text-white"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Обработка...
                </>
              ) : (
                <>
                  <Copy className="mr-2 h-4 w-4" />
                  Подтвердить
                </>
              )}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
