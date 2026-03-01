import { apiClient } from "./apiClient";

export const sessionService = {
  list: () => apiClient.get("/sessions"),
  listExpanded: () => apiClient.get("/sessions/expanded"),
  listUnscheduled: () => apiClient.get("/sessions/unscheduled"),
  create: (payload) => apiClient.post("/sessions", payload),
  update: (id, payload) => apiClient.put(`/sessions/${id}`, payload),
  remove: (id) => apiClient.del(`/sessions/${id}`),
};
