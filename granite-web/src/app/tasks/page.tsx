'use client';

import { useTasks, useUpdateTask, useDeleteTask } from "@/lib/hooks/use-tasks";
import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { 
  Calendar, 
  Trash2, 
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Clock
} from "lucide-react";
import Link from "next/link";
import { format } from "date-fns";
import { ru } from "date-fns/locale";
import { cn } from "@/lib/utils";

const TASK_TYPES: Record<string, string> = {
  follow_up: "Дожим",
  send_portfolio: "Портфолио",
  send_test_offer: "Тестовое",
  check_response: "Проверка",
  other: "Другое"
};

export default function TasksPage() {
  const [status, setStatus] = useState<'pending' | 'done'>('pending');
  const { data, isLoading } = useTasks({ status });
  const updateMutation = useUpdateTask();
  const deleteMutation = useDeleteTask();

  const tasks = data?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Задачи</h1>
          <p className="text-slate-500">Список дел и напоминаний по клиентам.</p>
        </div>
        
        <div className="flex bg-slate-100 p-1 rounded-lg">
          <Button 
            variant={status === 'pending' ? 'white' as any : 'ghost'} 
            size="sm"
            onClick={() => setStatus('pending')}
            className={cn(status === 'pending' && "shadow-sm")}
          >
            В работе
          </Button>
          <Button 
            variant={status === 'done' ? 'white' as any : 'ghost'} 
            size="sm"
            onClick={() => setStatus('done')}
            className={cn(status === 'done' && "shadow-sm")}
          >
            Завершенные
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1,2,3].map(i => <div key={i} className="h-20 w-full bg-slate-100 animate-pulse rounded-lg" />)}
        </div>
      ) : tasks.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed rounded-xl">
          <CheckCircle2 className="mx-auto h-12 w-12 text-slate-200" />
          <h3 className="mt-4 text-lg font-medium text-slate-900">Задач нет</h3>
          <p className="text-slate-500">Все дела на сегодня выполнены.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <Card key={task.id} className={cn("transition-opacity", task.status === 'done' && "opacity-60")}>
              <CardContent className="p-4 flex items-center gap-4">
                <Checkbox 
                  checked={task.status === 'done'} 
                  onCheckedChange={(checked) => {
                    updateMutation.mutate({ 
                      id: task.id, 
                      updates: { status: checked ? 'done' : 'pending' } 
                    });
                  }}
                />
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {TASK_TYPES[task.task_type] || task.task_type}
                    </Badge>
                    {task.priority > 1 && (
                      <AlertCircle className="h-4 w-4 text-orange-500" />
                    )}
                    <Link 
                      href={`/companies/${task.company_id}`}
                      className="text-xs font-medium text-indigo-600 hover:underline flex items-center gap-1"
                    >
                      {task.company_name}
                      <span className="text-slate-400">({task.company_city})</span>
                    </Link>
                  </div>
                  <p className={cn("text-sm font-medium truncate", task.status === 'done' && "line-through text-slate-500")}>
                    {task.description}
                  </p>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right hidden sm:block">
                    <div className="flex items-center text-xs text-slate-500">
                      <Calendar className="mr-1 h-3 w-3" />
                      {task.due_date ? format(new Date(task.due_date), 'dd MMM', { locale: ru }) : 'Без даты'}
                    </div>
                  </div>
                  
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="text-slate-400 hover:text-destructive"
                    onClick={() => {
                      if (confirm("Удалить задачу?")) deleteMutation.mutate(task.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
