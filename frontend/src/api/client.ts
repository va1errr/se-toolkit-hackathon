/**
 * API client with automatic JWT token attachment.
 *
 * All API calls go through this module. It reads the token from localStorage
 * and adds it to every request. If the token expires, requests will get 401.
 */

import axios from "axios";

const API_BASE = "/api/v1";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to every request if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Export typed API methods
export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ access_token: string }>("/auth/login", { username, password }),
  register: (username: string, password: string, role = "student") =>
    api.post("/auth/register", { username, password, role }),
};

export const questionsApi = {
  list: (status?: string) =>
    api.get("/questions", { params: status ? { status } : {} }),
  get: (id: string) => api.get(`/questions/${id}`),
  create: (title: string, body: string) =>
    api.post("/questions", { title, body }),
};

export const answersApi = {
  add: (questionId: string, bodyText: string) =>
    api.post(`/questions/${questionId}/answer`, { body: bodyText }),
  rate: (answerId: string, helpful: boolean) =>
    api.post(`/answers/${answerId}/rate`, { helpful }),
};

export const taApi = {
  flagged: () => api.get("/ta/flagged"),
  addAnswer: (questionId: string, bodyText: string) =>
    api.post(`/ta/questions/${questionId}/answer`, { body: bodyText }),
  editAnswer: (answerId: string, bodyText: string) =>
    api.put(`/ta/answers/${answerId}`, { body: bodyText }),
  deleteAnswer: (answerId: string) =>
    api.delete(`/ta/answers/${answerId}`),
  hideQuestion: (questionId: string) =>
    api.put(`/ta/questions/${questionId}/hide`),
  unhideQuestion: (questionId: string) =>
    api.put(`/ta/questions/${questionId}/unhide`),
};

export const healthApi = {
  check: () => api.get<{ status: string }>("/health"),
};

export default api;
