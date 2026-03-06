import { apiClient } from "./apiClient";

export const timetableViewService = {
  listEntries: (version) => {
    const url = version ? `/timetable/entries?version=${version}` : "/timetable/entries";
    return apiClient.get(url);
  },
  createEntry: (payload) => apiClient.post("/timetable/entries", payload),
  validate: (entries) => apiClient.post("/timetable/validate", { entries }),
  resolve: (entries) => apiClient.post("/timetable/resolve", { entries }),
  getLatestVersion: () => apiClient.get("/timetable/latest-version"),
};
