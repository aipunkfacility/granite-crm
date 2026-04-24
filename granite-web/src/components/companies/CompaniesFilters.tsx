'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { FilterToggle } from '@/components/ui/filter-toggle';
import { Input } from '@/components/ui/input';
import { ChevronDown, X } from 'lucide-react';
import { FilterState } from '@/lib/hooks/use-company-filters';
import { SEGMENT_CONFIG, FUNNEL_STAGES } from '@/constants/funnel';
import type { Segment, FunnelStage } from '@/lib/types/api';

interface CompaniesFiltersProps {
  filters: FilterState;
  onFilterChange: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  onClearAll: () => void;
  activeCount: number;
  total: number;
  cities: string[];
  regions: string[];
  cmsTypes: string[];
}

/* focus ring для нативных select */
const selectClass =
  'mt-1 w-full rounded-md border border-border bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition-colors';

/* ========================================
   Collapsible Group
   — Используем CSS grid trick для плавной
     анимации max-height (0 ↔ 1fr)
   ======================================== */
function FilterGroup({
  label,
  activeCount,
  defaultOpen = true,
  children,
}: {
  label: string;
  activeCount?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [maxH, setMaxH] = useState(open ? 'none' : '0px');
  const [settled, setSettled] = useState(open); // true = анимация завершена, overflow-visible

  /* Измеряем реальную высоту контента для анимации */
  useEffect(() => {
    if (!bodyRef.current) return;
    if (open) {
      /* Разворачиваем: сначала ставим точную высоту (для transition), потом none */
      setSettled(false);
      const h = bodyRef.current.scrollHeight;
      setMaxH(`${h + 16}px`); // +16 запас
      /* После анимации — убираем ограничение + разрешаем overflow-visible */
      const timer = setTimeout(() => { setMaxH('none'); setSettled(true); }, 350);
      return () => clearTimeout(timer);
    } else {
      /* Сворачиваем: сначала задаём точную высоту (для transition), потом 0 */
      setSettled(false);
      const h = bodyRef.current.scrollHeight;
      setMaxH(`${h}px`);
      /* Нужно 2 кадра: установить точную высоту → затем 0 */
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setMaxH('0px');
        });
      });
    }
  }, [open]);

  return (
    <div className={open ? 'mt-3' : 'mt-2'}>
      {/* Group header — clickable */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 py-0.5 text-left group"
      >
        <ChevronDown
          className={`h-3 w-3 shrink-0 text-muted-foreground transition-transform duration-200 ${
            !open ? '-rotate-90' : ''
          }`}
        />
        <span className="text-[10px] font-bold uppercase tracking-widest text-primary group-hover:text-primary/80 transition-colors">
          {label}
        </span>
        {/* Active count badge — shown when collapsed */}
        {!open && activeCount !== undefined && activeCount > 0 && (
          <span className="rounded-full bg-primary/10 px-1.5 py-px text-[10px] font-semibold text-primary">
            {activeCount}
          </span>
        )}
        <span className="flex-1 border-b border-border" />
      </button>

      {/* Group body — collapsible via measured max-height */}
      <div
        ref={bodyRef}
        className={`${settled ? 'overflow-visible' : 'overflow-hidden'} transition-[max-height,opacity] duration-300 ease-in-out`}
        style={{ maxHeight: maxH, opacity: open ? 1 : 0 }}
      >
        <div className="pt-2">{children}</div>
      </div>
    </div>
  );
}

/* ========================================
   Active Filter Pills (for collapsed panel header)
   ======================================== */
function ActivePills({ filters }: { filters: FilterState }) {
  const pills = useMemo(() => {
    const result: { label: string; variant: 'primary' | 'success' | 'destructive' | 'muted' }[] = [];

    filters.segment.forEach(s => {
      result.push({ label: s === 'spam' ? 'Spam' : s, variant: 'primary' });
    });

    if (filters.funnel_stage) {
      const cfg = FUNNEL_STAGES[filters.funnel_stage as FunnelStage];
      result.push({ label: cfg?.label ?? filters.funnel_stage, variant: 'muted' });
    }

    if (filters.region) {
      result.push({
        label: filters.region.length > 20 ? filters.region.slice(0, 18) + '...' : filters.region,
        variant: 'muted',
      });
    }
    if (filters.city.length > 0) {
      result.push({ label: `${filters.city.length} гор.`, variant: 'muted' });
    }

    if (filters.cms) {
      result.push({ label: filters.cms, variant: 'muted' });
    }

    const toggleMap: [keyof FilterState, string][] = [
      ['has_telegram', 'TG'], ['has_whatsapp', 'WA'], ['has_email', 'Email'],
      ['has_website', 'Сайт'], ['has_vk', 'VK'], ['has_address', 'Адр.'],
      ['is_network', 'Сети'], ['has_marquiz', 'Marquiz'],
      ['needs_review', 'Проверка'], ['stop_automation', 'Пауза'],
    ];
    toggleMap.forEach(([key, short]) => {
      const v = filters[key] as 0 | 1 | undefined;
      if (v === 1) result.push({ label: short, variant: 'success' });
      else if (v === 0) result.push({ label: `~${short}`, variant: 'destructive' });
    });

    if (filters.min_score !== undefined || filters.max_score !== undefined) {
      const lo = filters.min_score ?? '';
      const hi = filters.max_score ?? '';
      result.push({ label: `S:${lo}–${hi}`, variant: 'muted' });
    }

    if (filters.include_spam === 1) result.push({ label: '+Спам', variant: 'primary' });
    if (filters.include_spam === 2) result.push({ label: 'Спам!', variant: 'destructive' });
    if (filters.include_deleted === 1) result.push({ label: '+Удал.', variant: 'muted' });
    if (filters.tg_trust_min !== undefined) result.push({ label: `TG≥${filters.tg_trust_min}`, variant: 'primary' });
    if (filters.tg_trust_max !== undefined) result.push({ label: `TG≤${filters.tg_trust_max}`, variant: 'destructive' });

    return result;
  }, [filters]);

  if (pills.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1 min-w-0 flex-1">
      {pills.slice(0, 8).map((p, i) => (
        <span
          key={i}
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium leading-none max-w-[140px] truncate ${
            p.variant === 'primary'
              ? 'bg-primary/10 text-primary'
              : p.variant === 'success'
                ? 'bg-success/10 text-success'
                : p.variant === 'destructive'
                  ? 'bg-destructive/10 text-destructive'
                  : 'bg-muted text-muted-foreground'
          }`}
        >
          {p.label}
        </span>
      ))}
      {pills.length > 8 && (
        <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium leading-none text-muted-foreground">
          +{pills.length - 8}
        </span>
      )}
    </div>
  );
}

/* ========================================
   Main Component
   ======================================== */
export function CompaniesFilters({
  filters,
  onFilterChange,
  onClearAll,
  activeCount,
  total,
  cities,
  regions,
  cmsTypes,
}: CompaniesFiltersProps) {
  const [panelOpen, setPanelOpen] = useState(true);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [panelMaxH, setPanelMaxH] = useState(panelOpen ? 'none' : '0px');
  const [panelSettled, setPanelSettled] = useState(panelOpen); // true = анимация завершена

  /* Анимация панели — тот же pattern что и группы */
  useEffect(() => {
    if (!bodyRef.current) return;
    if (panelOpen) {
      setPanelSettled(false);
      const h = bodyRef.current.scrollHeight;
      setPanelMaxH(`${h + 32}px`);
      const timer = setTimeout(() => { setPanelMaxH('none'); setPanelSettled(true); }, 400);
      return () => clearTimeout(timer);
    } else {
      setPanelSettled(false);
      const h = bodyRef.current.scrollHeight;
      setPanelMaxH(`${h}px`);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setPanelMaxH('0px');
        });
      });
    }
  }, [panelOpen]);

  /* Keyboard shortcut: F to toggle panel */
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key !== 'f' || e.ctrlKey || e.metaKey || e.altKey) return;
      const el = e.target as HTMLElement;
      const tag = el.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      /* Также пропускаем если фокус на кнопке / contentEditable */
      if (el.isContentEditable) return;
      if (tag === 'BUTTON' || el.closest('button')) return;
      setPanelOpen(prev => !prev);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  /* Count active filters per group */
  const classCount = useMemo(() => {
    let c = 0;
    if (filters.segment.length > 0) c++;
    if (filters.funnel_stage) c++;
    return c;
  }, [filters.segment, filters.funnel_stage]);

  const geoCount = useMemo(() => {
    let c = 0;
    if (filters.region) c++;
    if (filters.city.length > 0) c++;
    if (filters.cms) c++;
    return c;
  }, [filters.region, filters.city, filters.cms]);

  const channelCount = useMemo(() => {
    let c = 0;
    if (filters.has_telegram !== undefined) c++;
    if (filters.has_whatsapp !== undefined) c++;
    if (filters.has_email !== undefined) c++;
    if (filters.has_vk !== undefined) c++;
    if (filters.has_website !== undefined) c++;
    if (filters.has_address !== undefined) c++;
    return c;
  }, [filters.has_telegram, filters.has_whatsapp, filters.has_email, filters.has_vk, filters.has_website, filters.has_address]);

  const propsCount = useMemo(() => {
    let c = 0;
    if (filters.is_network !== undefined) c++;
    if (filters.has_marquiz !== undefined) c++;
    if (filters.needs_review !== undefined) c++;
    if (filters.stop_automation !== undefined) c++;
    if (filters.min_score !== undefined) c++;
    if (filters.max_score !== undefined) c++;
    return c;
  }, [filters.is_network, filters.has_marquiz, filters.needs_review, filters.stop_automation, filters.min_score, filters.max_score]);

  return (
    <div className="rounded-lg border bg-card transition-all duration-300">
      {/* ======== Panel Header (always visible) ======== */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
        onClick={() => setPanelOpen(!panelOpen)}
      >
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
            !panelOpen ? '-rotate-90' : ''
          }`}
        />
        <span className="text-sm font-semibold text-foreground">Фильтры</span>

        {/* Active pills — always visible, useful when collapsed */}
        <ActivePills filters={filters} />

        {/* Right side: count + clear */}
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Найдено: <span className="font-semibold text-foreground">{total}</span>
          </span>
          {activeCount > 0 && (
            <button
              type="button"
              onClick={e => {
                e.stopPropagation();
                onClearAll();
              }}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-foreground hover:border-destructive hover:text-destructive transition-colors"
            >
              <X className="h-3 w-3" />
              Сбросить ({activeCount})
            </button>
          )}
        </div>
      </div>

      {/* ======== Panel Body (collapsible) ======== */}
      <div
        ref={bodyRef}
        className={`${panelSettled ? 'overflow-visible' : 'overflow-hidden'} transition-[max-height,opacity] duration-300 ease-in-out`}
        style={{ maxHeight: panelMaxH, opacity: panelOpen ? 1 : 0 }}
      >
        <div className="border-t border-border px-4 pb-4 pt-1">

          {/* ─── Group 1: Классификация ─── */}
          <FilterGroup label="Классификация" activeCount={classCount}>
            <div className="flex flex-wrap items-center gap-4">
              {/* Сегменты — pills */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Сегмент</span>
                {(Object.keys(SEGMENT_CONFIG) as Segment[]).map(seg => {
                  const active = filters.segment.includes(seg);
                  return (
                    <button
                      key={seg}
                      type="button"
                      onClick={() => {
                        const next = active
                          ? filters.segment.filter(s => s !== seg)
                          : [...filters.segment, seg];
                        onFilterChange('segment', next.length ? next : []);
                      }}
                      className={`rounded-full border px-3 py-0.5 text-sm font-semibold transition-colors ${
                        active
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border text-muted-foreground hover:border-primary/30 hover:text-foreground'
                      }`}
                    >
                      {seg}
                    </button>
                  );
                })}
              </div>

              {/* Воронка */}
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground">Воронка</span>
                <select
                  value={filters.funnel_stage || ''}
                  onChange={e => onFilterChange('funnel_stage', (e.target.value || undefined) as string | undefined)}
                  className="rounded-md border border-border bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition-colors"
                >
                  <option value="">Все стадии</option>
                  {(Object.entries(FUNNEL_STAGES) as [FunnelStage, any][]).map(([key, cfg]) => (
                    <option key={key} value={key}>{cfg.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </FilterGroup>

          {/* ─── Group 2: География и платформа ─── */}
          <FilterGroup label="География и платформа" activeCount={geoCount}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1.5fr_1fr]">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Регион</label>
                <select
                  value={filters.region || ''}
                  onChange={e => onFilterChange('region', (e.target.value || undefined) as string | undefined)}
                  className={selectClass}
                >
                  <option value="">Все регионы</option>
                  {regions.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">Город</label>
                <select
                  value=""
                  onChange={e => {
                    if (!e.target.value) return;
                    const next = filters.city.includes(e.target.value)
                      ? filters.city.filter(c => c !== e.target.value)
                      : [...filters.city, e.target.value];
                    onFilterChange('city', next);
                  }}
                  className={selectClass}
                >
                  <option value="">Выберите город...</option>
                  {cities.map(c => (
                    <option key={c} value={c} disabled={filters.city.includes(c)}>
                      {filters.city.includes(c) ? `✓ ${c}` : c}
                    </option>
                  ))}
                </select>
                {filters.city.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {filters.city.map(c => (
                      <span
                        key={c}
                        className="inline-flex items-center gap-0.5 rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary"
                      >
                        {c}
                        <button onClick={() => onFilterChange('city', filters.city.filter(x => x !== c))}>
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">CMS</label>
                <select
                  value={filters.cms || ''}
                  onChange={e => onFilterChange('cms', (e.target.value || undefined) as string | undefined)}
                  className={selectClass}
                >
                  <option value="">Все CMS</option>
                  {cmsTypes.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>
          </FilterGroup>

          {/* ─── Group 3: Каналы связи ─── */}
          <FilterGroup label="Каналы связи" activeCount={channelCount}>
            <div className="flex flex-wrap items-center gap-2">
              <FilterToggle label="Telegram" value={filters.has_telegram} onChange={v => onFilterChange('has_telegram', v)} />
              <FilterToggle label="WhatsApp" value={filters.has_whatsapp} onChange={v => onFilterChange('has_whatsapp', v)} />
              <FilterToggle label="Email" value={filters.has_email} onChange={v => onFilterChange('has_email', v)} />
              <FilterToggle label="VK" value={filters.has_vk} onChange={v => onFilterChange('has_vk', v)} />
              {/* Визуальный разделитель */}
              <span className="mx-1 h-5 w-px bg-border" />
              <FilterToggle label="С сайтом" value={filters.has_website} onChange={v => onFilterChange('has_website', v)} />
              <FilterToggle label="С адресом" value={filters.has_address} onChange={v => onFilterChange('has_address', v)} />
            </div>
          </FilterGroup>

          {/* ─── Group 4: Свойства ─── */}
          <FilterGroup label="Свойства" activeCount={propsCount}>
            <div className="flex flex-wrap items-center gap-2">
              <FilterToggle label="Сети" value={filters.is_network} onChange={v => onFilterChange('is_network', v)} />
              <FilterToggle label="Марquiz" value={filters.has_marquiz} onChange={v => onFilterChange('has_marquiz', v)} />
              <FilterToggle label="На проверке" value={filters.needs_review} onChange={v => onFilterChange('needs_review', v)} />
              <FilterToggle label="Автопауза" value={filters.stop_automation} onChange={v => onFilterChange('stop_automation', v)} />

              {/* Спам / удалённые */}
              <span className="mx-1 h-5 w-px bg-border" />
              <FilterToggle label="Спам" value={filters.include_spam === 0 ? undefined : (filters.include_spam === 2 ? 1 : 1)} onChange={v => {
                if (v === undefined) onFilterChange('include_spam', 0);
                else if (v === 1) onFilterChange('include_spam', filters.include_spam === 1 ? 2 : 1);
                else onFilterChange('include_spam', 0);
              }} />
              <FilterToggle label="Удалённые" value={filters.include_deleted as 0 | 1 | undefined} onChange={v => onFilterChange('include_deleted', (v ?? 0) as 0 | 1)} />

              {/* TG Trust */}
              <span className="mx-1 h-5 w-px bg-border" />
              <div className="flex items-center gap-1">
                <span className="text-xs text-muted-foreground whitespace-nowrap">TG Trust</span>
                <select
                  value={filters.tg_trust_min ?? ''}
                  onChange={e => onFilterChange('tg_trust_min', e.target.value ? parseInt(e.target.value) : undefined)}
                  className="rounded-md border border-border bg-card px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Все</option>
                  <option value="0">≥0</option>
                  <option value="1">≥1</option>
                  <option value="2">≥2</option>
                  <option value="3">≥3</option>
                </select>
              </div>

              {/* Score — справа с разделителем */}
              <div className="ml-auto flex items-center gap-2 border-l border-border pl-4">
                <span className="text-xs text-muted-foreground whitespace-nowrap">Score</span>
                <Input
                  type="number"
                  placeholder="от"
                  value={filters.min_score ?? ''}
                  onChange={e => onFilterChange('min_score', e.target.value ? parseInt(e.target.value) : undefined)}
                  className="w-[4.5rem] text-center text-xs"
                />
                <span className="text-muted-foreground">—</span>
                <Input
                  type="number"
                  placeholder="до"
                  value={filters.max_score ?? ''}
                  onChange={e => onFilterChange('max_score', e.target.value ? parseInt(e.target.value) : undefined)}
                  className="w-[4.5rem] text-center text-xs"
                />
              </div>
            </div>
          </FilterGroup>

        </div>
      </div>
    </div>
  );
}
