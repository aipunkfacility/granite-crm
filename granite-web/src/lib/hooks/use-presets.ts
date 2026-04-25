'use client';

import { useState, useCallback, useEffect } from 'react';
import { FilterState } from './use-company-filters';

export interface Preset {
  id: string;
  name: string;
  filters: Partial<FilterState>;
  isSystem?: boolean;
  createdAt: number;
}

const STORAGE_KEY = 'granite-presets';

/* Системные пресеты — неизменяемые */
export const SYSTEM_PRESETS: Preset[] = [
  {
    id: 'hot-leads',
    name: 'Горячие лиды',
    isSystem: true,
    createdAt: 0,
    filters: {
      segment: ['A'],
      has_telegram: 1,
    },
  },
  {
    id: 'tg-outreach',
    name: 'TG-аутрич',
    isSystem: true,
    createdAt: 0,
    filters: {
      has_telegram: 1,
      tg_trust_min: 2,
    },
  },
  {
    id: 'email-candidates',
    name: 'Email-кандидаты',
    isSystem: true,
    createdAt: 0,
    filters: {
      has_email: 1,
    },
  },
  {
    id: 'bitrix-tg',
    name: 'Bitrix+TG',
    isSystem: true,
    createdAt: 0,
    filters: {
      cms: 'bitrix',
      has_telegram: 1,
    },
  },
  {
    id: 'dead-tg',
    name: 'Мёртвые TG',
    isSystem: true,
    createdAt: 0,
    filters: {
      has_telegram: 1,
      tg_trust_max: 0,
    },
  },
  {
    id: 'needs-review',
    name: 'На проверке',
    isSystem: true,
    createdAt: 0,
    filters: {
      needs_review: 1,
    },
  },
];

function loadCustomPresets(): Preset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function saveCustomPresets(presets: Preset[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    // localStorage quota exceeded — ignore
  }
}

export function usePresets() {
  const [customPresets, setCustomPresets] = useState<Preset[]>([]);

  // Load on mount
  useEffect(() => {
    setCustomPresets(loadCustomPresets());
  }, []);

  const allPresets = [...SYSTEM_PRESETS, ...customPresets];

  const savePreset = useCallback((name: string, filters: Partial<FilterState>) => {
    const preset: Preset = {
      id: `custom-${Date.now()}`,
      name,
      filters,
      createdAt: Date.now(),
    };
    setCustomPresets(prev => {
      const next = [...prev, preset];
      saveCustomPresets(next);
      return next;
    });
    return preset;
  }, []);

  const deletePreset = useCallback((id: string) => {
    setCustomPresets(prev => {
      const next = prev.filter(p => p.id !== id);
      saveCustomPresets(next);
      return next;
    });
  }, []);

  return {
    allPresets,
    systemPresets: SYSTEM_PRESETS,
    customPresets,
    savePreset,
    deletePreset,
  };
}
