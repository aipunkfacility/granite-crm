import axios from 'axios';

export const apiClient = axios.create({
  // Добавляем завершающий слэш для корректной работы относительных путей
  baseURL: (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '') + '/',
  timeout: 15000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.error || error.message;
    return Promise.reject(new Error(message));
  }
);
