'use client';

import { FilterToggle } from '@/components/ui/filter-toggle';
import { Input } from '@/components/ui/input';
import { X } from 'lucide-react';
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

/* V-14: focus ring на всех 4 нативных select */
const selectClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500";

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
  return (
    <div className="space-y-4 rounded-lg border bg-white p-4">
      {/* Шапка: всего найдено + сброс */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">
          Всего найдено: <span className="font-semibold text-slate-900">{total}</span>
        </span>
        {activeCount > 0 && (
          <button
            type="button"
            onClick={onClearAll}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            <X className="h-3.5 w-3.5" />
            Сбросить всё ({activeCount})
          </button>
        )}
      </div>

      {/* Сегменты */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-500 w-16 shrink-0">Сегмент:</span>
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
              className={`rounded-md border px-2.5 py-1 text-sm font-medium transition-colors ${
                active
                  ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                  : 'border-slate-200 text-slate-500 hover:border-slate-300'
              }`}
            >
              {seg}
            </button>
          );
        })}
      </div>

      {/* Dropdowns */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="text-xs font-medium text-slate-500">Регион</label>
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
          <label className="text-xs font-medium text-slate-500">Город</label>
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
                  className="inline-flex items-center gap-0.5 rounded bg-indigo-100 px-1.5 py-0.5 text-xs text-indigo-700"
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
          <label className="text-xs font-medium text-slate-500">Воронка</label>
          <select
            value={filters.funnel_stage || ''}
            onChange={e => onFilterChange('funnel_stage', (e.target.value || undefined) as string | undefined)}
            className={selectClass}
          >
            <option value="">Все стадии</option>
            {(Object.entries(FUNNEL_STAGES) as [FunnelStage, any][]).map(([key, cfg]) => (
              <option key={key} value={key}>{cfg.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-slate-500">CMS</label>
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

      {/* Toggle-фильтры */}
      <div className="flex flex-wrap gap-2">
        <FilterToggle label="Telegram" value={filters.has_telegram} onChange={v => onFilterChange('has_telegram', v)} />
        <FilterToggle label="WhatsApp" value={filters.has_whatsapp} onChange={v => onFilterChange('has_whatsapp', v)} />
        <FilterToggle label="Email" value={filters.has_email} onChange={v => onFilterChange('has_email', v)} />
        <FilterToggle label="С сайтом" value={filters.has_website} onChange={v => onFilterChange('has_website', v)} />
        <FilterToggle label="VK" value={filters.has_vk} onChange={v => onFilterChange('has_vk', v)} />
        <FilterToggle label="С адресом" value={filters.has_address} onChange={v => onFilterChange('has_address', v)} />
        <FilterToggle label="Сети" value={filters.is_network} onChange={v => onFilterChange('is_network', v)} />
        <FilterToggle label="Марquiz" value={filters.has_marquiz} onChange={v => onFilterChange('has_marquiz', v)} />
        <FilterToggle label="На проверке" value={filters.needs_review} onChange={v => onFilterChange('needs_review', v)} />
        <FilterToggle label="Автопауза" value={filters.stop_automation} onChange={v => onFilterChange('stop_automation', v)} />
      </div>

      {/* Score range */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-slate-500">Score (от–до):</span>
        <Input
          type="number"
          placeholder="от"
          value={filters.min_score ?? ''}
          onChange={e => onFilterChange('min_score', e.target.value ? parseInt(e.target.value) : undefined)}
          className="w-20"
        />
        <span className="text-slate-400">—</span>
        <Input
          type="number"
          placeholder="до"
          value={filters.max_score ?? ''}
          onChange={e => onFilterChange('max_score', e.target.value ? parseInt(e.target.value) : undefined)}
          className="w-20"
        />
      </div>

    </div>
  );
}
