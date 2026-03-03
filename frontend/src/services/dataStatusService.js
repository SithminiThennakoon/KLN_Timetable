import { apiClient } from "./apiClient";

export const dataStatusService = {
  get: () => apiClient.get("/data-status"),
};
