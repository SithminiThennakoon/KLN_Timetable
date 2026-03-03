import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const login = (username, password) => {
  return apiClient.post('/auth/login', { username, password });
};

export const register = (username, email, password, name, role) => {
  return apiClient.post('/auth/register', { username, email, password, name, role });
};

export const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userRole');
};

export default apiClient;
