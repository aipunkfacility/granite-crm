'use client';

import { usePipelineStatus } from "@/lib/hooks/use-pipeline";
import { useCities } from "@/lib/hooks/use-pipeline";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Database, 
  Search, 
  Zap, 
  CheckCircle2, 
  MapPin,
  RefreshCcw,
  Play,
  Clock,
  Filter,
  X,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useMemo, useRef, useEffect } from "react";
import { runPipeline } from "@/lib/api/pipeline";

const STAGE_CONFIG: Record<string, { label: string, variant: "default" | "secondary" | "outline" | "ghost", icon: any }> = {
  scraped: { label: "Сбор", variant: "secondary", icon: Search },
  deduped: { label: "Дедуп", variant: "outline", icon: Database },
  enriched: { label: "Обогащение", variant: "default", icon: Zap },
  scored: { label: "Готов", variant: "outline", icon: CheckCircle2 },
  start: { label: "Начало", variant: "ghost", icon: Clock },
};

export default function PipelinePage() {
  const { data: statuses, isLoading, refetch } = usePipelineStatus();
  const { data: citiesData } = useCities();
  const [regionFilter, setRegionFilter] = useState('');
  const [citySearch, setCitySearch] = useState('');
  const [runCity, setRunCity] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [cityDropdownOpen, setCityDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setCityDropdownOpen(false);
      }
    }
    if (cityDropdownOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [cityDropdownOpen]);

  // Unique regions from cities reference
  const regions = useMemo(() => {
    if (!citiesData?.cities) return [];
    const set = new Set(citiesData.cities.map(c => c.region).filter(Boolean));
    return Array.from(set).sort();
  }, [citiesData]);

  // Filtered cities for the run dropdown
  const filteredCities = useMemo(() => {
    if (!citiesData?.cities) return [];
    let list = citiesData.cities;
    if (regionFilter) {
      list = list.filter(c => c.region === regionFilter);
    }
    if (citySearch) {
      const q = citySearch.toLowerCase();
      list = list.filter(c => c.name.toLowerCase().includes(q));
    }
    return list;
  }, [citiesData, regionFilter, citySearch]);

  // Filtered pipeline statuses
  const filteredStatuses = useMemo(() => {
    if (!statuses) return [];
    if (!regionFilter) return statuses;
    // Cities in selected region
    const regionCities = new Set(
      (citiesData?.cities || []).filter(c => c.region === regionFilter).map(c => c.name)
    );
    return statuses.filter(s => regionCities.has(s.city));
  }, [statuses, regionFilter, citiesData]);

  const handleRunPipeline = async () => {
    if (!runCity) return;
    setIsRunning(true);
    setRunError(null);
    try {
      await runPipeline(runCity);
      refetch();
    } catch (e: any) {
      setRunError(e?.message || 'Ошибка запуска');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Пайплайн</h1>
          <p className="text-muted-foreground">Мониторинг процесса сбора и обработки данных по городам.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCcw className="mr-2 h-4 w-4" /> Обновить
          </Button>
        </div>
      </div>

      {/* Run pipeline controls */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Play className="h-4 w-4" /> Запуск скрапинга
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            {/* Region select */}
            <div className="w-48">
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Регион</label>
              <select
                value={regionFilter}
                onChange={e => { setRegionFilter(e.target.value); setRunCity(''); }}
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              >
                <option value="">Все регионы</option>
                {regions.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>

            {/* City dropdown with search */}
            <div className="w-64" ref={dropdownRef}>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Город</label>
              <div className="relative">
                <Input
                  placeholder="Поиск города..."
                  value={citySearch || (runCity ? runCity : '')}
                  onChange={e => { setCitySearch(e.target.value); setRunCity(''); setCityDropdownOpen(true); }}
                  onFocus={() => setCityDropdownOpen(true)}
                  className="pr-8"
                />
                {(citySearch || runCity) && (
                  <button
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => { setCitySearch(''); setRunCity(''); }}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
                {cityDropdownOpen && filteredCities.length > 0 && (
                  <div className="absolute z-50 left-0 right-0 top-full mt-1 max-h-60 overflow-y-auto rounded-md border border-border bg-card shadow-lg">
                    {filteredCities.slice(0, 100).map(city => (
                      <button
                        key={city.name}
                        className={cn(
                          "w-full text-left px-3 py-1.5 text-sm hover:bg-muted/50 transition-colors",
                          runCity === city.name && "bg-primary/10 text-primary font-medium"
                        )}
                        onClick={() => {
                          setRunCity(city.name);
                          setCitySearch('');
                          setCityDropdownOpen(false);
                        }}
                      >
                        <span>{city.name}</span>
                        <span className="text-muted-foreground text-xs ml-2">{city.region}</span>
                      </button>
                    ))}
                    {filteredCities.length > 100 && (
                      <div className="px-3 py-2 text-xs text-muted-foreground border-t">
                        Показано 100 из {filteredCities.length}. Уточните поиск.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <Button
              onClick={handleRunPipeline}
              disabled={!runCity || isRunning}
              className="bg-success hover:bg-success/90 text-success-foreground"
            >
              {isRunning ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Запуск...</>
              ) : (
                <><Play className="mr-2 h-4 w-4" /> Запустить</>
              )}
            </Button>
          </div>
          {runError && (
            <p className="mt-2 text-sm text-destructive">{runError}</p>
          )}
        </CardContent>
      </Card>

      {/* Region filter for table */}
      {regionFilter && (
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Фильтр по региону:</span>
          <Badge variant="secondary">{regionFilter}</Badge>
          <button onClick={() => setRegionFilter('')} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">Всего городов</p>
              <MapPin className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="text-2xl font-bold mt-1">{filteredStatuses?.length || 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">В обработке</p>
              <Play className="h-4 w-4 text-primary" />
            </div>
            <p className="text-2xl font-bold mt-1">
              {filteredStatuses?.filter(s => s.is_running).length || 0}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">База компаний</p>
              <Database className="h-4 w-4 text-success" />
            </div>
            <p className="text-2xl font-bold mt-1">
              {filteredStatuses?.reduce((acc, s) => acc + s.company_count, 0).toLocaleString() || 0}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Статус по городам</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Город</TableHead>
                <TableHead>Стадия</TableHead>
                <TableHead>Прогресс</TableHead>
                <TableHead className="text-right">Raw</TableHead>
                <TableHead className="text-right">Компании</TableHead>
                <TableHead className="text-right">Обогащено</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                [1,2,3].map(i => (
                  <TableRow key={i}>
                    <TableCell colSpan={6}><div className="h-8 w-full bg-muted animate-pulse rounded" /></TableCell>
                  </TableRow>
                ))
              ) : !filteredStatuses || filteredStatuses.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-10 text-muted-foreground">Нет данных по городам</TableCell>
                </TableRow>
              ) : filteredStatuses.map((status) => {
                const config = STAGE_CONFIG[status.stage] || STAGE_CONFIG.scraped;
                const progressPerc = Math.round(status.enrichment_progress * 100);
                
                return (
                  <TableRow key={status.city}>
                    <TableCell>
                      <div className="font-medium flex items-center gap-2">
                        {status.city}
                        {status.is_running && <RefreshCcw className="h-3 w-3 animate-spin text-primary" />}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={config.variant as any} className="flex items-center w-fit gap-1">
                        <config.icon className="h-3 w-3" />
                        {config.label}
                      </Badge>
                    </TableCell>
                    <TableCell className="w-48">
                      <div className="flex items-center gap-3">
                        <Progress value={progressPerc} className="h-2 w-24" />
                        <span className="text-xs font-medium text-foreground">{progressPerc}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">{status.raw_count}</TableCell>
                    <TableCell className="text-right font-medium">{status.company_count}</TableCell>
                    <TableCell className="text-right">
                      <span className={cn(
                        "text-sm font-bold",
                        status.enriched_count > 0 ? "text-success" : "text-muted-foreground"
                      )}>
                        {status.enriched_count}
                      </span>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
