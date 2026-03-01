import { apiClient } from "./apiClient";

export const subjectService = {
  list: () => apiClient.get("/subjects"),
  create: (payload) => apiClient.post("/subjects", payload),
  update: (id, payload) => apiClient.put(`/subjects/${id}`, payload),
  remove: (id) => apiClient.del(`/subjects/${id}`),
};
