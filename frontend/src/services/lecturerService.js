import { apiClient } from "./apiClient";

export const lecturerService = {
  list: () => apiClient.get("/lecturers"),
  create: (payload) => apiClient.post("/lecturers", payload),
  update: (id, payload) => apiClient.put(`/lecturers/${id}`, payload),
  remove: (id) => apiClient.del(`/lecturers/${id}`),
};
