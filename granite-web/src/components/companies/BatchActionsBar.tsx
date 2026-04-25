'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Ban, CheckCircle2, X } from 'lucide-react';

interface BatchActionsBarProps {
  selectedCount: number;
  onBatchSpam: () => void;
  onBatchApprove: () => void;
  onClearSelection: () => void;
  isAdmin: boolean;
}

export function BatchActionsBar({
  selectedCount,
  onBatchSpam,
  onBatchApprove,
  onClearSelection,
  isAdmin,
}: BatchActionsBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-4 duration-200">
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-3 shadow-2xl">
        <span className="text-sm font-medium text-foreground">
          Выбрано: <span className="text-primary">{selectedCount}</span>
        </span>

        <div className="h-5 w-px bg-border" />

        {isAdmin ? (
          <>
            <Button
              variant="destructive"
              size="sm"
              onClick={onBatchSpam}
              className="gap-1.5"
            >
              <Ban className="h-3.5 w-3.5" />
              В спам
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onBatchApprove}
              className="gap-1.5"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Подтвердить
            </Button>
          </>
        ) : (
          <span className="text-xs text-muted-foreground">
            Войдите как администратор для batch-операций
          </span>
        )}

        <div className="h-5 w-px bg-border" />

        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onClearSelection}
          title="Снять выделение"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
