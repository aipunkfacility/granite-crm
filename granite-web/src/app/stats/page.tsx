'use client';

import { useStats } from "@/lib/hooks/use-stats";
import { usePipelineStatus } from "@/lib/hooks/use-pipeline";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  PieChart,
  Pie
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { useState, useEffect, useRef, useCallback, ReactNode } from "react";
import { FUNNEL_STAGES, FunnelStage } from "@/constants/funnel";

/* Semantic palette: primary, success, warning, destructive, accent-purple */
const COLORS = ['#5B6ABF', '#2B9E6F', '#C49008', '#DC2643', '#8B5ABF'];

/* Semantic palette for funnel — HEX for recharts (always rendered inside Card with bg-card) */
const FUNNEL_COLORS: Record<string, string> = {
  slate: '#7A756E',   // muted-foreground (light) / #9DA1A9 (dark handled by CSS)
  blue: '#2E7DB5',    // info
  indigo: '#5B6ABF',  // primary
  violet: '#8B5ABF',  // accent-purple
  green: '#2B9E6F',   // success
  emerald: '#1A8060', // success darker
  teal: '#0D7A6C',    // success teal
  orange: '#C49008',  // warning
  red: '#DC2643',     // destructive
};

/**
 * Замена ResponsiveContainer: измеряет контейнер через ResizeObserver
 * и рендерит children только когда размеры > 0.
 */
function ChartBox({ children, className }: { children: (w: number, h: number) => ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);

  const measure = useCallback(() => {
    if (!ref.current) return;
    const { width, height } = ref.current.getBoundingClientRect();
    if (width > 0 && height > 0) {
      setSize(prev => (prev && prev.w === width && prev.h === height) ? prev : { w: width, h: height });
    }
  }, []);

  useEffect(() => {
    measure();
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [measure]);

  return (
    <div ref={ref} className={className}>
      {size ? children(size.w, size.h) : null}
    </div>
  );
}

export default function StatsPage() {
  const [selectedCity, setSelectedCity] = useState<string>("all");
  const [mounted, setMounted] = useState(false);
  const { data: stats, isLoading } = useStats(selectedCity === "all" ? undefined : selectedCity);
  const { data: cities } = usePipelineStatus();

  useEffect(() => { setMounted(true); }, []);

  /* V-11: все 9 стадий маппятся в цвет через FUNNEL_COLORS */
  const funnelData = stats?.funnel
    ? Object.entries(stats.funnel).map(([stage, count]) => ({
        name: FUNNEL_STAGES[stage as FunnelStage]?.label || stage,
        count: count,
        color: FUNNEL_COLORS[FUNNEL_STAGES[stage as FunnelStage]?.color] || '#7A756E'
      }))
    : [];

  // Данные для сегментов
  const segmentData = stats?.segments
    ? Object.entries(stats.segments).map(([seg, count]) => ({
        name: `Сегмент ${seg}`,
        value: count
      }))
    : [];

  if (isLoading) return <div className="p-8">Загрузка аналитики...</div>;
  if (!stats) return <div className="p-8">Нет данных для отображения</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          {/* V-05: font-semibold вместо font-bold */}
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Аналитика</h1>
          {/* V-27: подзаголовок text-sm */}
          <p className="text-sm text-muted-foreground">Общая статистика базы и эффективность воронки продаж.</p>
        </div>

        <div className="w-64">
          <Select value={selectedCity} onValueChange={setSelectedCity}>
            <SelectTrigger>
              <SelectValue placeholder="Все города" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все города</SelectItem>
              {cities?.map(c => (
                <SelectItem key={c.city} value={c.city}>{c.city}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Основные цифры */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-primary text-primary-foreground border-none shadow-lg">
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase opacity-80">Всего компаний</p>
            <p className="text-3xl font-semibold mt-1">{stats?.total_companies?.toLocaleString() ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-muted-foreground">С мессенджерами</p>
            <p className="text-2xl font-semibold mt-1 text-info">
              TG: {stats?.with_telegram ?? 0} | WA: {stats?.with_whatsapp ?? 0}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-muted-foreground">С Email</p>
            <p className="text-3xl font-semibold mt-1 text-primary">{stats?.with_email?.toLocaleString() ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-muted-foreground">Конверсия (Ответы)</p>
            <p className="text-3xl font-semibold mt-1 text-success">
              {stats?.funnel?.replied ?? 0}
            </p>
          </CardContent>
        </Card>
      </div>

      {mounted && funnelData.length > 0 && segmentData.length > 0 && (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* График воронки */}
        <Card>
          <CardHeader>
            {/* V-20: CardTitle font-semibold */}
            <CardTitle className="text-lg font-semibold">Воронка продаж (распределение)</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartBox className="h-[350px] w-full">
              {(w, h) => (
                <BarChart width={w} height={h} data={funnelData} layout="vertical" margin={{ left: 40, right: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" hide />
                  <YAxis
                    dataKey="name"
                    type="category"
                    width={120}
                    style={{ fontSize: '12px' }}
                  />
                  <Tooltip />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {funnelData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              )}
            </ChartBox>
          </CardContent>
        </Card>

        {/* График сегментов */}
        <Card>
          <CardHeader>
            {/* V-20: CardTitle font-semibold */}
            <CardTitle className="text-lg font-semibold">Качество базы (A/B/C/D)</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartBox className="h-[350px] w-full">
              {(w, h) => (
                <PieChart width={w} height={h}>
                  <Pie
                    data={segmentData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                  >
                    {segmentData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              )}
            </ChartBox>
          </CardContent>
        </Card>
      </div>
      )}
    </div>
  );
}
