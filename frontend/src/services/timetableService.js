import { apiClient } from "./apiClient";

export const timetableService = {
  generate: () => apiClient.post("/timetable/generate", {}),
  preview: () => apiClient.post("/timetable/preview", {}),
  save: (results) => apiClient.post("/timetable/save", { results }),
  getLatestVersion: () => apiClient.get("/timetable/latest-version"),
};
