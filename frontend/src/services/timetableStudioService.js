import { apiClient } from "./apiClient";

const IMPORT_DEBUG_PREFIX = "[SetupImport]";

function buildImportFormData(payload = {}, file) {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  }
  formData.append("rules_json", JSON.stringify(payload.rules || []));
  formData.append(
    "allowed_attempts_json",
    JSON.stringify(payload.allowed_attempts || ["1"])
  );
  if (payload.target_academic_year) {
    formData.append("target_academic_year", payload.target_academic_year);
  }
  return formData;
}

function logImportRequest(step, payload = {}, file) {
  console.log(`${IMPORT_DEBUG_PREFIX} ${step} request`, {
    fileName: file?.name || null,
    hasFile: Boolean(file),
    rulesCount: (payload.rules || []).length,
    targetAcademicYear: payload.target_academic_year || null,
    allowedAttempts: payload.allowed_attempts || ["1"],
  });
}

export const timetableStudioService = {
  getDatasetSummary: () => apiClient.get("/v2/dataset"),
  getFullDataset: () => apiClient.get("/v2/dataset/full"),
  getLookups: () => apiClient.get("/v2/lookups"),
  loadDemoDataset: (profile = "realistic") => apiClient.post(`/v2/dataset/demo?profile=${profile}`, {}),
  analyzeEnrollmentImport: (file) => {
    logImportRequest("analyze", {}, file);
    return apiClient.postForm("/v2/imports/enrollment-analysis-upload", buildImportFormData({}, file));
  },
  previewEnrollmentImport: (payload, file) => {
    logImportRequest("review", payload, file);
    return apiClient.postForm(
      "/v2/imports/enrollment-projection-upload",
      buildImportFormData(payload, file)
    );
  },
  materializeEnrollmentImport: (payload, file) => {
    logImportRequest("use-import", payload, file);
    return apiClient.postForm(
      "/v2/imports/enrollment-materialize-upload",
      buildImportFormData(payload, file)
    );
  },
  getImportWorkspace: (importRunId) => apiClient.get(`/v2/imports/${importRunId}/workspace`),
  publishImportWorkspaceToLegacyDataset: (importRunId) =>
    apiClient.post(`/v2/imports/${importRunId}/publish-legacy`, {}),
  seedRealisticSnapshotMissingData: (importRunId) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/seed-realistic-missing-data`, {}),
  getImportSnapshot: (importRunId) => apiClient.get(`/v2/imports/${importRunId}/snapshot`),
  createSnapshotLecturersBatch: (importRunId, lecturers) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/lecturers/batch`, { lecturers }),
  createSnapshotLecturer: (importRunId, payload) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/lecturers`, payload),
  updateSnapshotLecturer: (importRunId, lecturerId, payload) =>
    apiClient.put(`/v2/imports/${importRunId}/snapshot/lecturers/${lecturerId}`, payload),
  deleteSnapshotLecturer: (importRunId, lecturerId) =>
    apiClient.delete(`/v2/imports/${importRunId}/snapshot/lecturers/${lecturerId}`),
  createSnapshotRoomsBatch: (importRunId, rooms) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/rooms/batch`, { rooms }),
  createSnapshotRoom: (importRunId, payload) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/rooms`, payload),
  updateSnapshotRoom: (importRunId, roomId, payload) =>
    apiClient.put(`/v2/imports/${importRunId}/snapshot/rooms/${roomId}`, payload),
  deleteSnapshotRoom: (importRunId, roomId) =>
    apiClient.delete(`/v2/imports/${importRunId}/snapshot/rooms/${roomId}`),
  createSnapshotSharedSessionsBatch: (importRunId, sharedSessions) =>
    apiClient.post(`/v2/imports/${importRunId}/snapshot/shared-sessions/batch`, {
      shared_sessions: sharedSessions,
    }),
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
