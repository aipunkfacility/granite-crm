'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Preset, usePresets } from '@/lib/hooks/use-presets';
import { FilterState } from '@/lib/hooks/use-company-filters';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Bookmark,
  ChevronDown,
  Plus,
  Trash2,
  Star,
  Save,
  X,
} from 'lucide-react';

interface PresetManagerProps {
  filters: FilterState;
  onApplyPreset: (filters: Partial<FilterState>) => void;
}

export function PresetManager({ filters, onApplyPreset }: PresetManagerProps) {
  const { allPresets, systemPresets, customPresets, savePreset, deletePreset } = usePresets();
  const [open, setOpen] = useState(false);
  const [saveMode, setSaveMode] = useState(false);
  const [presetName, setPresetName] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
        setSaveMode(false);
      }
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  // Focus input on save mode
  useEffect(() => {
    if (saveMode && inputRef.current) inputRef.current.focus();
  }, [saveMode]);

  const handleSave = () => {
    const trimmed = presetName.trim();
    if (!trimmed) return;
    savePreset(trimmed, filters);
    setPresetName('');
    setSaveMode(false);
    setOpen(false);
  };

  const handleApply = (preset: Preset) => {
    onApplyPreset(preset.filters);
    setOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={() => { setOpen(!open); setSaveMode(false); }}
      >
        <Bookmark className="h-3.5 w-3.5" />
        Пресеты
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </Button>

      {open && (
        <div className="absolute top-full left-0 z-50 mt-1 w-64 rounded-lg border border-border bg-card shadow-lg">
          {/* Save current filters */}
          {!saveMode ? (
            <button
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-primary hover:bg-primary/5 border-b border-border"
              onClick={() => setSaveMode(true)}
            >
              <Save className="h-3.5 w-3.5" />
              Сохранить текущие фильтры
            </button>
          ) : (
            <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border">
              <Input
                ref={inputRef}
                value={presetName}
                onChange={e => setPresetName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setSaveMode(false); }}
                placeholder="Название пресета..."
                className="h-7 text-xs"
              />
              <Button size="sm" className="h-7 px-2" onClick={handleSave} disabled={!presetName.trim()}>
                <Plus className="h-3 w-3" />
              </Button>
              <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => setSaveMode(false)}>
                <X className="h-3 w-3" />
              </Button>
            </div>
          )}

          {/* System presets */}
          <div className="px-2 py-1.5">
            <p className="px-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Системные</p>
          </div>
          {systemPresets.map(preset => (
            <button
              key={preset.id}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted/50 transition-colors"
              onClick={() => handleApply(preset)}
            >
              <Star className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <span className="truncate">{preset.name}</span>
            </button>
          ))}

          {/* Custom presets */}
          {customPresets.length > 0 && (
            <>
              <div className="px-2 py-1.5 border-t border-border mt-1">
                <p className="px-1 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Пользовательские</p>
              </div>
              {customPresets.map(preset => (
                <div
                  key={preset.id}
                  className="flex items-center gap-1 px-3 py-1.5 hover:bg-muted/50 transition-colors group"
                >
                  <button
                    className="flex flex-1 items-center gap-2 text-sm truncate"
                    onClick={() => handleApply(preset)}
                  >
                    <Bookmark className="h-3.5 w-3.5 text-primary shrink-0" />
                    <span className="truncate">{preset.name}</span>
                  </button>
                  <button
                    className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                    onClick={(e) => { e.stopPropagation(); deletePreset(preset.id); }}
                    title="Удалить пресет"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </>
          )}

          {customPresets.length === 0 && (
            <p className="px-3 py-2 text-xs text-muted-foreground italic">
              Нет сохранённых пресетов
            </p>
          )}
        </div>
      )}
    </div>
  );
}
