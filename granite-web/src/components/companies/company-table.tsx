'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Company } from "@/lib/types/api";
import { FUNNEL_STAGES, SEGMENT_CONFIG } from "@/constants/funnel";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";
import { ExternalLink, MessageCircle, Phone, Shield, ShieldOff, ShieldAlert, ShieldCheck, Smartphone, ArrowUp, ArrowDown, ArrowUpDown, Columns3 } from "lucide-react";

/* TG Trust badge — индикатор «живости» Telegram-аккаунта */
function TgTrustBadge({ trust }: { trust: Record<string, any> }) {
  const score = trust?.trust_score;
  if (score === undefined || score === null) return null;

  const config: Record<number, { icon: React.ElementType; color: string; label: string }> = {
    0: { icon: ShieldOff, color: 'text-destructive', label: 'Мёртвый' },
    1: { icon: ShieldAlert, color: 'text-orange-400', label: 'Частичный' },
    2: { icon: Shield, color: 'text-info', label: 'Живой' },
    3: { icon: ShieldCheck, color: 'text-success', label: 'Активный' },
  };

  const { icon: Icon, color, label } = config[score] ?? config[0];

  return (
    <span className={`${color} inline-flex items-center`} title={`TG Trust: ${label} (${score}/3)`}>
      <Icon className="h-3 w-3" />
    </span>
  );
}

/* Column definitions */
export interface ColumnDef {
  key: string;
  label: string;
  sortable: boolean;
  defaultVisible: boolean;
  width?: string;
}

export const COLUMNS: ColumnDef[] = [
  { key: 'name', label: 'Название', sortable: true, defaultVisible: true, width: 'w-[300px]' },
  { key: 'city', label: 'Город', sortable: true, defaultVisible: true },
  { key: 'segment', label: 'Сегмент', sortable: true, defaultVisible: true },
  { key: 'crm_score', label: 'Score', sortable: true, defaultVisible: true },
  { key: 'funnel_stage', label: 'Воронка', sortable: true, defaultVisible: true },
  { key: 'contact', label: 'Контакт', sortable: false, defaultVisible: true },
  { key: 'last_contact_at', label: 'Последний контакт', sortable: true, defaultVisible: true },
  { key: 'is_network', label: 'Сеть', sortable: true, defaultVisible: false },
  { key: 'updated_at', label: 'Обновлено', sortable: true, defaultVisible: false },
];

const VISIBILITY_STORAGE_KEY = 'granite-column-visibility';

function loadVisibility(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(VISIBILITY_STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch { return {}; }
}

function saveVisibility(vis: Record<string, boolean>) {
  try { localStorage.setItem(VISIBILITY_STORAGE_KEY, JSON.stringify(vis)); } catch {}
}

/* Sortable header */
function SortableHead({
  label,
  sortKey,
  currentSort,
  currentDir,
  onSort,
  width,
}: {
  label: string;
  sortKey: string;
  currentSort: string;
  currentDir: 'asc' | 'desc';
  onSort: (key: string) => void;
  width?: string;
}) {
  const isActive = currentSort === sortKey;
  return (
    <TableHead className={`${width ?? ''} cursor-pointer select-none hover:bg-muted/50 transition-colors`} onClick={() => onSort(sortKey)}>
      <span className="inline-flex items-center gap-1">
        {label}
        {isActive ? (
          currentDir === 'asc' ? <ArrowUp className="h-3 w-3 text-primary" /> : <ArrowDown className="h-3 w-3 text-primary" />
        ) : (
          <ArrowUpDown className="h-3 w-3 text-muted-foreground/40" />
        )}
      </span>
    </TableHead>
  );
}

interface CompanyTableProps {
  companies: Company[];
  onSelectCompany?: (companyId: number) => void;
  orderBy?: string;
  orderDir?: 'asc' | 'desc';
  onSortChange?: (orderBy: string, orderDir: 'asc' | 'desc') => void;
  /** Selected company IDs for batch operations */
  selectedIds?: Set<number>;
  /** Toggle selection of a single row */
  onToggleSelect?: (companyId: number) => void;
  /** Toggle select-all on current page */
  onToggleSelectAll?: () => void;
}

export function CompanyTable({
  companies,
  onSelectCompany,
  orderBy = 'crm_score',
  orderDir = 'desc',
  onSortChange,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
}: CompanyTableProps) {
  const [visibleCols, setVisibleCols] = useState<Record<string, boolean>>({});
  const [colsOpen, setColsOpen] = useState(false);
  const colsRef = useRef<HTMLDivElement>(null);

  const isBatchMode = selectedIds !== undefined;

  // Load visibility on mount
  useEffect(() => {
    const saved = loadVisibility();
    if (Object.keys(saved).length > 0) {
      setVisibleCols(saved);
    } else {
      // Defaults
      const defaults: Record<string, boolean> = {};
      COLUMNS.forEach(c => { defaults[c.key] = c.defaultVisible; });
      setVisibleCols(defaults);
    }
  }, []);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (colsRef.current && !colsRef.current.contains(e.target as Node)) setColsOpen(false);
    }
    if (colsOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [colsOpen]);

  const isVisible = (key: string) => visibleCols[key] !== false; // default true

  const toggleCol = (key: string) => {
    const next = { ...visibleCols, [key]: !isVisible(key) };
    setVisibleCols(next);
    saveVisibility(next);
  };

  const handleSort = (key: string) => {
    if (!onSortChange) return;
    if (orderBy === key) {
      onSortChange(key, orderDir === 'asc' ? 'desc' : 'asc');
    } else {
      onSortChange(key, 'desc');
    }
  };

  const visibleColumns = COLUMNS.filter(c => isVisible(c.key));
  const colSpan = visibleColumns.length + (isBatchMode ? 1 : 0);

  // Select-all state
  const allOnPageSelected = isBatchMode && companies.length > 0 && companies.every(c => selectedIds.has(c.id));
  const someOnPageSelected = isBatchMode && !allOnPageSelected && companies.some(c => selectedIds.has(c.id));

  return (
    <div className="space-y-2">
      {/* Column visibility toggle */}
      <div className="flex items-center justify-end" ref={colsRef}>
        <div className="relative">
          <button
            className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            onClick={() => setColsOpen(!colsOpen)}
          >
            <Columns3 className="h-3.5 w-3.5" />
            Колонки
          </button>
          {colsOpen && (
            <div className="absolute right-0 top-full z-50 mt-1 w-48 rounded-lg border border-border bg-card shadow-lg p-2 space-y-1">
              {COLUMNS.map(col => (
                <label key={col.key} className="flex items-center gap-2 px-2 py-1 rounded hover:bg-muted/50 cursor-pointer text-sm">
                  <Checkbox
                    checked={isVisible(col.key)}
                    onCheckedChange={() => toggleCol(col.key)}
                  />
                  {col.label}
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              {/* Checkbox column */}
              {isBatchMode && (
                <TableHead className="w-[40px] px-2">
                  <div
                    className="flex items-center justify-center"
                    onClick={e => e.stopPropagation()}
                    onPointerDown={e => e.stopPropagation()}
                  >
                    <Checkbox
                      checked={allOnPageSelected ? true : someOnPageSelected ? 'indeterminate' : false}
                      onCheckedChange={() => onToggleSelectAll?.()}
                    />
                  </div>
                </TableHead>
              )}
              {COLUMNS.map(col => {
                if (!isVisible(col.key)) return null;
                if (col.sortable) {
                  return (
                    <SortableHead
                      key={col.key}
                      label={col.label}
                      sortKey={col.key}
                      currentSort={orderBy}
                      currentDir={orderDir}
                      onSort={handleSort}
                      width={col.width}
                    />
                  );
                }
                return (
                  <TableHead key={col.key} className={col.width}>
                    {col.label}
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {companies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={colSpan} className="h-24 text-center text-muted-foreground">
                  Компании не найдены
                </TableCell>
              </TableRow>
            ) : (
              companies.map((company) => {
                const stage = FUNNEL_STAGES[company.funnel_stage];
                const segment = company.segment ? SEGMENT_CONFIG[company.segment] : null;
                const isSelected = isBatchMode && selectedIds.has(company.id);

                return (
                  <TableRow
                    key={company.id}
                    className={`group hover:bg-muted/50 cursor-pointer ${isSelected ? 'bg-primary/5' : ''}`}
                    onClick={() => onSelectCompany?.(company.id)}
                  >
                    {/* Checkbox */}
                    {isBatchMode && (
                      <TableCell className="px-2">
                        <div
                          className="flex items-center justify-center"
                          onClick={e => { e.stopPropagation(); e.preventDefault(); }}
                          onPointerDown={e => e.stopPropagation()}
                        >
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={() => onToggleSelect?.(company.id)}
                          />
                        </div>
                      </TableCell>
                    )}
                    {/* Название */}
                    {isVisible('name') && (
                      <TableCell className="font-medium">
                        <span className="text-primary hover:underline">{company.name}</span>
                      </TableCell>
                    )}
                    {/* Город */}
                    {isVisible('city') && (
                      <TableCell className="text-muted-foreground">{company.city}</TableCell>
                    )}
                    {/* Сегмент */}
                    {isVisible('segment') && (
                      <TableCell>
                        {segment && <Badge variant={segment.variant}>{segment.label}</Badge>}
                      </TableCell>
                    )}
                    {/* Score */}
                    {isVisible('crm_score') && (
                      <TableCell>
                        <span className="font-mono-code font-medium text-foreground">{company.crm_score}</span>
                      </TableCell>
                    )}
                    {/* Воронка */}
                    {isVisible('funnel_stage') && (
                      <TableCell>
                        <Badge variant={stage.variant} className="whitespace-nowrap">{stage.label}</Badge>
                      </TableCell>
                    )}
                    {/* Контакт */}
                    {isVisible('contact') && (
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {company.telegram && (
                            <span className="inline-flex items-center gap-0.5">
                              <a
                                href={`https://t.me/${company.telegram.replace('@', '')}`}
                                target="_blank" rel="noreferrer"
                                className="text-info hover:scale-110 transition-transform"
                                onClick={e => e.stopPropagation()}
                              >
                                <MessageCircle className="h-4 w-4" />
                              </a>
                              <TgTrustBadge trust={company.tg_trust} />
                            </span>
                          )}
                          {company.phones.length > 0 && (
                            <a href={`tel:${company.phones[0]}`} className="text-muted-foreground hover:text-foreground" onClick={e => e.stopPropagation()}>
                              <Phone className="h-4 w-4" />
                            </a>
                          )}
                          {company.website && (
                            <a href={company.website} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-foreground" onClick={e => e.stopPropagation()}>
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          )}
                          {company.vk && (
                            <a
                              href={company.vk.startsWith('http') ? company.vk : `https://vk.com/${company.vk}`}
                              target="_blank" rel="noreferrer"
                              className="text-blue-500 hover:text-blue-600"
                              onClick={e => e.stopPropagation()}
                            >
                              <Smartphone className="h-4 w-4" />
                            </a>
                          )}
                        </div>
                      </TableCell>
                    )}
                    {/* Последний контакт */}
                    {isVisible('last_contact_at') && (
                      <TableCell className="text-right text-xs text-muted-foreground">
                        {company.last_contact_at
                          ? formatDistanceToNow(new Date(company.last_contact_at), { addSuffix: true, locale: ru })
                          : '—'}
                      </TableCell>
                    )}
                    {/* Сеть */}
                    {isVisible('is_network') && (
                      <TableCell className="text-center">
                        {company.is_network ? <ShieldCheck className="h-4 w-4 text-success mx-auto" /> : <span className="text-muted-foreground text-xs">—</span>}
                      </TableCell>
                    )}
                    {/* Обновлено */}
                    {isVisible('updated_at') && (
                      <TableCell className="text-xs text-muted-foreground">
                        {company.updated_at
                          ? formatDistanceToNow(new Date(company.updated_at), { addSuffix: true, locale: ru })
                          : '—'}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
