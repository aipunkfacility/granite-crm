'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { fetchCompanies } from '@/lib/api/companies';
import { Company } from '@/lib/types/api';
import { Copy, Loader2, MapPin, X, Search } from 'lucide-react';
import { SEGMENT_CONFIG } from '@/constants/funnel';

interface MarkDuplicateDialogProps {
  companyId: number;
  companyName: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (targetId: number) => void;
  isSaving: boolean;
}

export function MarkDuplicateDialog({
  companyId,
  companyName,
  isOpen,
  onClose,
  onConfirm,
  isSaving,
}: MarkDuplicateDialogProps) {
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<Company[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* Дебаунс-поиск */
  const doSearch = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetchCompanies({ search: q.trim(), per_page: 10 });
      /* Исключаем текущую компанию из результатов */
      setResults(res.items.filter(c => c.id !== companyId));
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    if (!isOpen) return;
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => doSearch(search), 300);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search, isOpen, doSearch]);

  /* Сброс при закрытии */
  const handleClose = () => {
    setSearch('');
    setResults([]);
    setSelectedId(null);
    setConfirmed(false);
    onClose();
  };

  const selectedCompany = results.find(c => c.id === selectedId);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-foreground/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border border-border">
        {/* Header */}
        <div className="p-6 border-b bg-muted">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-400/10">
                <Copy className="h-5 w-5 text-orange-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">Это дубль</h2>
                <p className="text-sm text-muted-foreground truncate max-w-[300px]">{companyName}</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          <p className="text-sm text-muted-foreground">
            Найдите оригинальную компанию, дубликатом которой является текущая.
            Компания будет скрыта из списка, данные не переносятся.
          </p>

          {/* Поиск */}
          <div className="space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => { setSearch(e.target.value); setSelectedId(null); setConfirmed(false); }}
                placeholder="Поиск по названию компании..."
                className="pl-9 h-10"
                autoFocus
              />
              {loading && (
                <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>

            {/* Результаты */}
            {results.length > 0 && !selectedId && (
              <div className="border rounded-lg max-h-[240px] overflow-y-auto divide-y">
                {results.map((c) => {
                  const segment = c.segment ? SEGMENT_CONFIG[c.segment] : null;
                  return (
                    <button
                      key={c.id}
                      className="w-full text-left px-3 py-2.5 hover:bg-muted/50 transition-colors flex items-center gap-3"
                      onClick={() => { setSelectedId(c.id); setConfirmed(false); }}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-foreground truncate">{c.name}</p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                          <MapPin className="h-3 w-3 shrink-0" />
                          <span>{c.city}</span>
                          {segment && (
                            <Badge variant={segment.variant} className="h-4 px-1 text-[10px]">
                              {segment.label}
                            </Badge>
                          )}
                          <span className="font-mono-code">{c.crm_score}</span>
                        </div>
                      </div>
                      <span className="text-xs text-muted-foreground shrink-0">ID {c.id}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Нет результатов */}
            {search.trim().length >= 2 && !loading && results.length === 0 && !selectedId && (
              <p className="text-sm text-muted-foreground py-3 text-center">
                Ничего не найдено. Попробуйте другое название.
              </p>
            )}
          </div>

          {/* Выбранная компания — подтверждение */}
          {selectedCompany && (
            <div className="p-4 rounded-lg border border-orange-400/30 bg-orange-400/5 space-y-3">
              <div className="flex items-center gap-2">
                <Copy className="h-4 w-4 text-orange-400" />
                <span className="text-sm font-medium text-foreground">Оригинал</span>
              </div>
              <div className="space-y-1">
                <p className="font-medium text-foreground">{selectedCompany.name}</p>
                <p className="text-sm text-muted-foreground">
                  {selectedCompany.city} · ID {selectedCompany.id}
                </p>
              </div>

              {!confirmed ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="border-orange-400/30 text-orange-400 hover:bg-orange-400/10"
                  onClick={() => setConfirmed(true)}
                >
                  Подтвердить выбор
                </Button>
              ) : (
                <p className="text-xs text-destructive font-medium">
                  Нажмите «Пометить как дубль» для подтверждения. Это действие скроет компанию из списка.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 border-t bg-muted flex justify-end gap-3">
          <Button variant="ghost" onClick={handleClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button
            variant="destructive"
            onClick={() => selectedId && onConfirm(selectedId)}
            disabled={!confirmed || !selectedId || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Обработка...
              </>
            ) : (
              <>
                <Copy className="mr-2 h-4 w-4" />
                Пометить как дубль
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
