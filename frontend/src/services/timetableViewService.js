import { apiClient } from "./apiClient";

export const timetableViewService = {
  listEntries: () => apiClient.get("/timetable/entries"),
  createEntry: (payload) => apiClient.post("/timetable/entries", payload),
  validate: (entries) => apiClient.post("/timetable/validate", { entries }),
  resolve: (entries) => apiClient.post("/timetable/resolve", { entries }),
};
