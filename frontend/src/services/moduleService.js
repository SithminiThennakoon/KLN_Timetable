import { apiClient } from "./apiClient";

export const moduleService = {
  list: () => apiClient.get("/modules"),
  create: (payload) => apiClient.post("/modules", payload),
  update: (id, payload) => apiClient.put(`/modules/${id}`, payload),
  remove: (id) => apiClient.del(`/modules/${id}`),
};
