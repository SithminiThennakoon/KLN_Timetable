import { apiClient } from "./apiClient";

export const departmentService = {
  list: () => apiClient.get("/departments"),
  create: (payload) => apiClient.post("/departments", payload),
  update: (id, payload) => apiClient.put(`/departments/${id}`, payload),
  remove: (id) => apiClient.del(`/departments/${id}`),
};
