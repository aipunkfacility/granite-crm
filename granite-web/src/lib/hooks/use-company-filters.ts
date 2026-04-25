'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { CompanyFilters } from '@/lib/api/companies';

type ToggleFilterValue = 0 | 1 | undefined;

export interface FilterState {
  segment: string[];
  funnel_stage: string | undefined;
  city: string[];
  region: string | undefined;
  search: string;
  has_telegram: ToggleFilterValue;
  has_whatsapp: ToggleFilterValue;
  has_email: ToggleFilterValue;
  is_network: ToggleFilterValue;
  has_website: ToggleFilterValue;
  has_vk: ToggleFilterValue;
  has_address: ToggleFilterValue;
  needs_review: ToggleFilterValue;
  stop_automation: ToggleFilterValue;
  has_marquiz: ToggleFilterValue;
  min_score: number | undefined;
  max_score: number | undefined;
  cms: string | undefined;
  // Фаза 1: Спам/удалённые
  include_spam: 0 | 1 | 2;
  include_deleted: 0 | 1;
  // Фаза 2: TG Trust
  tg_trust_min: number | undefined;
  tg_trust_max: number | undefined;
  // Фаза 10: Source
  source: string | undefined;
}

const DEFAULTS: FilterState = {
  segment: [],
  funnel_stage: undefined,
  city: [],
  region: undefined,
  search: '',
  has_telegram: undefined,
  has_whatsapp: undefined,
  has_email: undefined,
  is_network: undefined,
  has_website: undefined,
  has_vk: undefined,
  has_address: undefined,
  needs_review: undefined,
  stop_automation: undefined,
  has_marquiz: undefined,
  min_score: undefined,
  max_score: undefined,
  cms: undefined,
  include_spam: 0,
  include_deleted: 0,
  tg_trust_min: undefined,
  tg_trust_max: undefined,
  source: undefined,
};

const TOGGLE_KEYS = [
  'has_telegram', 'has_whatsapp', 'has_email', 'is_network',
  'has_website', 'has_vk', 'has_address', 'needs_review',
  'stop_automation', 'has_marquiz',
] as const;

/**
 * Хук управления фильтрами компаний.
 *
 * Ответственности:
 * - Хранение состояния всех фильтров
 * - Чтение/запись в URL searchParams
 * - Конвертация в CompanyFilters для API
 * - Подсчёт активных фильтров
 */
export function useCompanyFilters() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [filters, setFiltersState] = useState<FilterState>(() => {
    const p = searchParams;
    return {
      segment: p.getAll('segment').filter(Boolean),
      funnel_stage: p.get('funnel_stage') || undefined,
      city: p.getAll('city').filter(Boolean),
      region: p.get('region') || undefined,
      search: p.get('search') || '',
      has_telegram: parseToggle(p.get('has_telegram')),
      has_whatsapp: parseToggle(p.get('has_whatsapp')),
      has_email: parseToggle(p.get('has_email')),
      is_network: parseToggle(p.get('is_network')),
      has_website: parseToggle(p.get('has_website')),
      has_vk: parseToggle(p.get('has_vk')),
      has_address: parseToggle(p.get('has_address')),
      needs_review: parseToggle(p.get('needs_review')),
      stop_automation: parseToggle(p.get('stop_automation')),
      has_marquiz: parseToggle(p.get('has_marquiz')),
      min_score: parseNum(p.get('min_score')),
      max_score: parseNum(p.get('max_score')),
      cms: p.get('cms') || undefined,
      include_spam: (parseInt(p.get('include_spam') || '0', 10) as 0 | 1 | 2) || 0,
      include_deleted: (parseInt(p.get('include_deleted') || '0', 10) as 0 | 1) || 0,
      tg_trust_min: parseNum(p.get('tg_trust_min')),
      tg_trust_max: parseNum(p.get('tg_trust_max')),
      source: p.get('source') || undefined,
    };
  });

  // Debounced URL sync (500ms)
  const urlSyncTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    if (urlSyncTimer.current) clearTimeout(urlSyncTimer.current);
    urlSyncTimer.current = setTimeout(() => {
      const params = new URLSearchParams();
      if (filters.segment.length) filters.segment.forEach(s => params.append('segment', s));
      if (filters.funnel_stage) params.set('funnel_stage', filters.funnel_stage);
      if (filters.city.length) filters.city.forEach(c => params.append('city', c));
      if (filters.region) params.set('region', filters.region);
      if (filters.search) params.set('search', filters.search);
      TOGGLE_KEYS.forEach(key => {
        const v = filters[key as keyof FilterState] as ToggleFilterValue;
        if (v !== undefined) params.set(key, String(v));
      });
      if (filters.min_score !== undefined) params.set('min_score', String(filters.min_score));
      if (filters.max_score !== undefined) params.set('max_score', String(filters.max_score));
      if (filters.cms) params.set('cms', filters.cms);
      if (filters.include_spam) params.set('include_spam', String(filters.include_spam));
      if (filters.include_deleted) params.set('include_deleted', String(filters.include_deleted));
      if (filters.tg_trust_min !== undefined) params.set('tg_trust_min', String(filters.tg_trust_min));
      if (filters.tg_trust_max !== undefined) params.set('tg_trust_max', String(filters.tg_trust_max));
      if (filters.source) params.set('source', filters.source);

      const qs = params.toString();
      router.replace(pathname + (qs ? `?${qs}` : ''), { scroll: false });
    }, 500);
    return () => { if (urlSyncTimer.current) clearTimeout(urlSyncTimer.current); };
  }, [filters, router, pathname]);

  // Actions
  const setFilter = useCallback(<K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    setFiltersState(prev => ({ ...prev, [key]: value }));
  }, []);

  const clearFilter = useCallback(<K extends keyof FilterState>(key: K) => {
    setFiltersState(prev => ({ ...prev, [key]: DEFAULTS[key] }));
  }, []);

  const clearAll = useCallback(() => {
    setFiltersState({ ...DEFAULTS });
  }, []);

  // Active count
  const activeCount = useMemo(() => {
    let count = 0;
    if (filters.segment.length > 0) count++;
    if (filters.funnel_stage) count++;
    if (filters.city.length > 0) count++;
    if (filters.region) count++;
    if (filters.search.trim()) count++;
    TOGGLE_KEYS.forEach(key => {
      if (filters[key as keyof FilterState] !== undefined) count++;
    });
    if (filters.min_score !== undefined) count++;
    if (filters.max_score !== undefined) count++;
    if (filters.cms) count++;
    if (filters.include_spam) count++;
    if (filters.include_deleted) count++;
    if (filters.tg_trust_min !== undefined) count++;
    if (filters.tg_trust_max !== undefined) count++;
    if (filters.source) count++;
    return count;
  }, [filters]);

  const isActive = activeCount > 0;

  // Конвертация в API-параметры
  const toApiParams = useCallback((): CompanyFilters => {
    const p: CompanyFilters = {};
    if (filters.search) p.search = filters.search;
    if (filters.segment.length > 0) p.segment = filters.segment;
    if (filters.city.length > 0) p.city = filters.city;
    if (filters.funnel_stage) p.funnel_stage = filters.funnel_stage;
    if (filters.region) p.region = filters.region;
    if (filters.cms) p.cms = filters.cms;
    TOGGLE_KEYS.forEach(key => {
      const v = filters[key as keyof FilterState] as ToggleFilterValue;
      if (v !== undefined) {
        (p as any)[key] = v;
      }
    });
    if (filters.min_score !== undefined) p.min_score = filters.min_score;
    if (filters.max_score !== undefined) p.max_score = filters.max_score;
    if (filters.include_spam) p.include_spam = filters.include_spam;
    if (filters.include_deleted) p.include_deleted = filters.include_deleted;
    if (filters.tg_trust_min !== undefined) p.tg_trust_min = filters.tg_trust_min;
    if (filters.tg_trust_max !== undefined) p.tg_trust_max = filters.tg_trust_max;
    if (filters.source) p.source = filters.source;
    return p;
  }, [filters]);

  const applyPreset = useCallback((presetFilters: Partial<FilterState>) => {
    setFiltersState({ ...DEFAULTS, ...presetFilters });
  }, []);

  return {
    filters,
    setFilter,
    clearFilter,
    clearAll,
    applyPreset,
    activeCount,
    isActive,
    toApiParams,
  };
}

function parseToggle(raw: string | null): ToggleFilterValue {
  if (raw === '1') return 1;
  if (raw === '0') return 0;
  return undefined;
}

function parseNum(raw: string | null): number | undefined {
  if (!raw) return undefined;
  const n = parseInt(raw, 10);
  return isNaN(n) ? undefined : n;
}
