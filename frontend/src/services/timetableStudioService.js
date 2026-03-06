import { apiClient } from "./apiClient";

export const timetableStudioService = {
  getDatasetSummary: () => apiClient.get("/v2/dataset"),
  getLookups: () => apiClient.get("/v2/lookups"),
  loadDemoDataset: () => apiClient.post("/v2/dataset/demo", {}),
  saveDataset: (payload) => apiClient.post("/v2/dataset", payload),
  generate: (payload) => apiClient.post("/v2/generate", payload),
  latestGeneration: () => apiClient.get("/v2/generate/latest"),
  setDefault: (solutionId) => apiClient.post("/v2/solutions/default", { solution_id: solutionId }),
  view: ({ mode, lecturerId, studentGroupId }) => {
    const params = new URLSearchParams({ mode });
    if (lecturerId) params.set("lecturer_id", lecturerId);
    if (studentGroupId) params.set("student_group_id", studentGroupId);
    return apiClient.get(`/v2/views?${params.toString()}`);
  },
  exportView: ({ mode, format, lecturerId, studentGroupId }) => {
    const params = new URLSearchParams({ mode, export_format: format });
    if (lecturerId) params.set("lecturer_id", lecturerId);
    if (studentGroupId) params.set("student_group_id", studentGroupId);
    return apiClient.get(`/v2/exports?${params.toString()}`);
  },
};
