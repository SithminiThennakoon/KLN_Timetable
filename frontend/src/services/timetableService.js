import { apiClient } from "./apiClient";

export const timetableService = {
  generate: () => apiClient.post("/timetable/generate", {}),
};
