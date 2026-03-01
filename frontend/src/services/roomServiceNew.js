import { apiClient } from "./apiClient";

export const roomService = {
  list: () => apiClient.get("/rooms"),
  create: (payload) => apiClient.post("/rooms", payload),
  update: (id, payload) => apiClient.put(`/rooms/${id}`, payload),
  remove: (id) => apiClient.del(`/rooms/${id}`),
};
