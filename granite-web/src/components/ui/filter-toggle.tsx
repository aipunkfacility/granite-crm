'use client';

import { useState, useRef, useEffect } from 'react';
import { Check, X, ChevronDown } from 'lucide-react';

type FilterValue = 0 | 1 | undefined;

interface FilterToggleProps {
  label: string;
  value: FilterValue;
  onChange: (value: FilterValue) => void;
}

/**
 * Трёхпозиционный фильтр-тоггл с dropdown.
 *
 * Состояния:
 * - undefined → «Любые» (серый outline) — не передаётся в API
 * - 1 → «Только с» (зелёный, ✓) — has_X=1
 * - 0 → «Только без» (rose outline, ✕) — has_X=0
 */
export function FilterToggle({ label, value, onChange }: FilterToggleProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  /* V-17, V-19: red → rose (destructive palette #E11D48) */
  const buttonClass = value === undefined
    ? 'border-border text-foreground hover:border-border bg-card'
    : value === 1
      ? 'border-success text-success bg-success/10 hover:bg-success/20'
      : 'border-destructive text-destructive bg-destructive/10 hover:bg-destructive/20';

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${buttonClass}`}
      >
        {value === 1 && <Check className="h-3.5 w-3.5" />}
        {value === 0 && <X className="h-3.5 w-3.5" />}
        {label}
        <ChevronDown className="h-3.5 w-3.5 opacity-50" />
      </button>

      {open && (
        <div className="absolute top-full left-0 z-50 mt-1 w-40 rounded-md border border-border bg-card py-1 shadow-lg">
          <button
            type="button"
            className="w-full px-3 py-1.5 text-left text-sm hover:bg-muted/50"
            onClick={() => { onChange(undefined); setOpen(false); }}
          >
            <span className={value === undefined ? 'font-medium' : ''}>Любые</span>
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-muted/50 text-success"
            onClick={() => { onChange(1); setOpen(false); }}
          >
            <Check className="h-3.5 w-3.5" />
            <span className={value === 1 ? 'font-medium' : ''}>Только с</span>
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-muted/50 text-destructive"
            onClick={() => { onChange(0); setOpen(false); }}
          >
            <X className="h-3.5 w-3.5" />
            <span className={value === 0 ? 'font-medium' : ''}>Только без</span>
          </button>
        </div>
      )}
    </div>
  );
}
