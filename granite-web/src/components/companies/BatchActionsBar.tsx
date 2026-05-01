'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Ban, CheckCircle2, X, Mail } from 'lucide-react';
import { AddToCampaignDialog } from './AddToCampaignDialog';

interface BatchActionsBarProps {
  selectedCount: number;
  selectedCompanyIds: number[];
  onBatchSpam: () => void;
  onBatchApprove: () => void;
  onClearSelection: () => void;
  isAdmin: boolean;
}

export function BatchActionsBar({
  selectedCount,
  selectedCompanyIds,
  onBatchSpam,
  onBatchApprove,
  onClearSelection,
  isAdmin,
}: BatchActionsBarProps) {
  const [addToCampaignOpen, setAddToCampaignOpen] = useState(false);

  if (selectedCount === 0) return null;

  return (
    <div
      className="fixed bottom-6 left-1/2 z-[100] -translate-x-1/2"
      style={{ position: 'fixed' }}
    >
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-5 py-3 shadow-2xl">
        <span className="text-sm font-medium text-foreground">
          Выбрано: <span className="text-primary">{selectedCount}</span>
        </span>

        <div className="h-5 w-px bg-border" />

        {isAdmin ? (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAddToCampaignOpen(true)}
              className="gap-1.5"
            >
              <Mail className="h-3.5 w-3.5" />
              В кампанию
            </Button>
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

      <AddToCampaignDialog
        open={addToCampaignOpen}
        onOpenChange={setAddToCampaignOpen}
        companyIds={selectedCompanyIds}
        count={selectedCount}
        onSuccess={onClearSelection}
      />
    </div>
  );
}
