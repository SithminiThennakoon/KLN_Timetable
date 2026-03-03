import { apiClient } from "./apiClient";

export const pathwayService = {
  list: () => apiClient.get("/pathways"),
  create: (payload) => apiClient.post("/pathways", payload),
  update: (id, payload) => apiClient.put(`/pathways/${id}`, payload),
  remove: (id) => apiClient.del(`/pathways/${id}`),
};
