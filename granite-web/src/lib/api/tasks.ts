import { apiClient } from './client';
import { Task, PaginatedResponse } from '@/lib/types/api';

export interface TaskFilters {
  status?: 'pending' | 'done' | 'cancelled';
  priority?: number;
  task_type?: string;
  page?: number;
  per_page?: number;
}

export const fetchTasks = async (params: TaskFilters = {}): Promise<PaginatedResponse<Task>> => {
  const { data } = await apiClient.get<PaginatedResponse<Task>>('tasks', { params });
  return data;
};

export const createTask = async (companyId: number, task: Partial<Task>): Promise<Task> => {
  const { data } = await apiClient.post<Task>(`companies/${companyId}/tasks`, task);
  return data;
};

export const updateTask = async (taskId: number, updates: Partial<Task>): Promise<Task> => {
  const { data } = await apiClient.patch<Task>(`tasks/${taskId}`, updates);
  return data;
};

export const deleteTask = async (taskId: number): Promise<void> => {
  await apiClient.delete(`tasks/${taskId}`);
};
