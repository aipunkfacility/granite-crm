'use client';

import { usePipelineStatus } from "@/lib/hooks/use-pipeline";
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
import { 
  Database, 
  Search, 
  Zap, 
  CheckCircle2, 
  MapPin,
  RefreshCcw,
  Play,
  Clock
} from "lucide-react";
import { cn } from "@/lib/utils";

const STAGE_CONFIG: Record<string, { label: string, variant: "default" | "secondary" | "outline" | "ghost", icon: any }> = {
  scraped: { label: "Сбор", variant: "secondary", icon: Search },
  deduped: { label: "Дедуп", variant: "outline", icon: Database },
  enriched: { label: "Обогащение", variant: "default", icon: Zap },
  scored: { label: "Готов", variant: "outline", icon: CheckCircle2 },
  start: { label: "Начало", variant: "ghost", icon: Clock },
};

export default function PipelinePage() {
  const { data: statuses, isLoading, refetch } = usePipelineStatus();

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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">Всего городов</p>
              <MapPin className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="text-2xl font-bold mt-1">{statuses?.length || 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">В обработке</p>
              <Play className="h-4 w-4 text-primary" />
            </div>
            <p className="text-2xl font-bold mt-1">
              {statuses?.filter(s => s.is_running).length || 0}
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
              {statuses?.reduce((acc, s) => acc + s.company_count, 0).toLocaleString() || 0}
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
              ) : !statuses || statuses.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-10 text-muted-foreground">Нет данных по городам</TableCell>
                </TableRow>
              ) : statuses.map((status) => {
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
