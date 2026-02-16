import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

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

export const login = (email, password) => {
  return apiClient.post('/auth/login', { email, password });
};

export const register = (email, password, name, role) => {
  return apiClient.post('/auth/register', { email, password, name, role });
};

export const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userRole');
};

export default apiClient;
