import { apiClient } from "./apiClient";

export const timetableStudioService = {
  getDatasetSummary: () => apiClient.get("/v2/dataset"),
  getFullDataset: () => apiClient.get("/v2/dataset/full"),
  getLookups: () => apiClient.get("/v2/lookups"),
  loadDemoDataset: (profile = "realistic") => apiClient.post(`/v2/dataset/demo?profile=${profile}`, {}),
  analyzeEnrollmentImport: () => apiClient.get("/v2/imports/enrollment-analysis"),
  previewEnrollmentImport: (payload) => apiClient.post("/v2/imports/enrollment-projection", payload),
  materializeEnrollmentImport: (payload) => apiClient.post("/v2/imports/enrollment-materialize", payload),
  getImportWorkspace: (importRunId) => apiClient.get(`/v2/imports/${importRunId}/workspace`),
  publishImportWorkspaceToLegacyDataset: (importRunId) =>
    apiClient.post(`/v2/imports/${importRunId}/publish-legacy`, {}),
  getImportSnapshot: (importRunId) => apiClient.get(`/v2/imports/${importRunId}/snapshot`),
  createSnapshotLecturer: (importRunId, payload) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/lecturers`, payload),
  updateSnapshotLecturer: (importRunId, lecturerId, payload) =>
    apiClient.put(`/v2/imports/${importRunId}/snapshot/lecturers/${lecturerId}`, payload),
  deleteSnapshotLecturer: (importRunId, lecturerId) =>
    apiClient.delete(`/v2/imports/${importRunId}/snapshot/lecturers/${lecturerId}`),
  createSnapshotRoom: (importRunId, payload) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/rooms`, payload),
  updateSnapshotRoom: (importRunId, roomId, payload) =>
    apiClient.put(`/v2/imports/${importRunId}/snapshot/rooms/${roomId}`, payload),
  deleteSnapshotRoom: (importRunId, roomId) =>
    apiClient.delete(`/v2/imports/${importRunId}/snapshot/rooms/${roomId}`),
  createSnapshotSharedSession: (importRunId, payload) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/shared-sessions`, payload),
  updateSnapshotSharedSession: (importRunId, sharedSessionId, payload) =>
    apiClient.put(
      `/v2/imports/${importRunId}/snapshot/shared-sessions/${sharedSessionId}`,
      payload
    ),
  deleteSnapshotSharedSession: (importRunId, sharedSessionId) =>
    apiClient.delete(`/v2/imports/${importRunId}/snapshot/shared-sessions/${sharedSessionId}`),
  loadEnrollmentImport: (payload) => apiClient.post("/v2/imports/enrollment-load", payload),
  saveDataset: (payload) => apiClient.post("/v2/dataset", payload),
  generate: (payload) => apiClient.post("/v2/generate", payload),
  latestGeneration: () => apiClient.get("/v2/generate/latest"),
  setDefault: (solutionId) => apiClient.post("/v2/solutions/default", { solution_id: solutionId }),
  view: ({ mode, lecturerId, studentGroupId, degreeId, pathId }) => {
    const params = new URLSearchParams({ mode });
    if (lecturerId) params.set("lecturer_id", lecturerId);
    if (studentGroupId) params.set("student_group_id", studentGroupId);
    if (degreeId) params.set("degree_id", degreeId);
    if (pathId) params.set("path_id", pathId);
    return apiClient.get(`/v2/views?${params.toString()}`);
  },
  exportView: ({ mode, format, lecturerId, studentGroupId, degreeId, pathId }) => {
    const params = new URLSearchParams({ mode, export_format: format });
    if (lecturerId) params.set("lecturer_id", lecturerId);
    if (studentGroupId) params.set("student_group_id", studentGroupId);
    if (degreeId) params.set("degree_id", degreeId);
    if (pathId) params.set("path_id", pathId);
    return apiClient.get(`/v2/exports?${params.toString()}`);
  },
};
