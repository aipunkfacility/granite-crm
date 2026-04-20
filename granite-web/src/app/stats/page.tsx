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
  ResponsiveContainer, 
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
import { useState } from "react";
import { FUNNEL_STAGES } from "@/constants/funnel";

const COLORS = ['#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#64748b'];

export default function StatsPage() {
  const [selectedCity, setSelectedCity] = useState<string>("all");
  const { data: stats, isLoading } = useStats(selectedCity === "all" ? undefined : selectedCity);
  const { data: cities } = usePipelineStatus();

  if (isLoading) return <div className="p-8">Загрузка аналитики...</div>;
  if (!stats) return <div className="p-8">Нет данных для отображения</div>;

  // Данные для воронки
  const funnelData = stats?.by_stage 
    ? Object.entries(stats.by_stage).map(([stage, count]) => ({
        name: FUNNEL_STAGES[stage as any]?.label || stage,
        count: count,
        color: FUNNEL_STAGES[stage as any]?.color === 'blue' ? '#3b82f6' : 
               FUNNEL_STAGES[stage as any]?.color === 'green' ? '#10b981' : '#64748b'
      })) 
    : [];

  // Данные для сегментов
  const segmentData = stats?.by_segment 
    ? Object.entries(stats.by_segment).map(([seg, count]) => ({
        name: `Сегмент ${seg}`,
        value: count
      })) 
    : [];


  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Аналитика</h1>
          <p className="text-slate-500">Общая статистика базы и эффективность воронки продаж.</p>
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
        <Card className="bg-indigo-600 text-white border-none">
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase opacity-80">Всего компаний</p>
            <p className="text-3xl font-bold mt-1">{stats?.total_companies.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-slate-500">С Telegram</p>
            <p className="text-3xl font-bold mt-1 text-sky-600">{stats?.with_telegram.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-slate-500">С Email</p>
            <p className="text-3xl font-bold mt-1 text-indigo-600">{stats?.with_email.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs font-medium uppercase text-slate-500">Конверсия (Ответы)</p>
            <p className="text-3xl font-bold mt-1 text-emerald-600">
              {stats?.by_stage?.replied ?? 0}

            </p>


          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* График воронки */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Воронка продаж (распределение)</CardTitle>
          </CardHeader>
          <CardContent className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnelData} layout="vertical" margin={{ left: 40, right: 40 }}>
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
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* График сегментов */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Качество базы (A/B/C/D)</CardTitle>
          </CardHeader>
          <CardContent className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={segmentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {segmentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
