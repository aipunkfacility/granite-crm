import axios from 'axios';

export const apiClient = axios.create({
  // Добавляем завершающий слэш для корректной работы относительных путей
  baseURL: (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '') + '/',
  timeout: 15000,
});

// Добавляем X-API-Key ко всем запросам (если задан)
apiClient.interceptors.request.use((config) => {
  const apiKey = process.env.NEXT_PUBLIC_API_KEY;
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.error || error.message;
    return Promise.reject(new Error(message));
  }
);
