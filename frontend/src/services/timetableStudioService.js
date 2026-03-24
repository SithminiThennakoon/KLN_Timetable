import { apiClient, resolveApiBaseUrl } from "./apiClient";

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

function buildSimpleCsvFormData(file) {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  }
  return formData;
}

async function downloadCsvTemplate(path) {
  const response = await fetch(`${resolveApiBaseUrl()}${path}`);
  if (!response.ok) {
    const payload = await response.text();
    throw new Error(payload || "Failed to download the CSV template");
  }
  return {
    filename:
      response.headers
        .get("content-disposition")
        ?.match(/filename=\"?([^";]+)\"?/)?.[1] || "template.csv",
    content: await response.text(),
  };
}

export const timetableStudioService = {
  getLookups: (importRunId = null) => {
    if (!importRunId) {
      return apiClient.get("/v2/lookups");
    }
    return apiClient.get(`/v2/lookups?import_run_id=${importRunId}`);
  },
  analyzeEnrollmentImport: (file) => {
    return apiClient.postForm("/v2/imports/enrollment-analysis-upload", buildImportFormData({}, file));
  },
  previewEnrollmentImport: (payload, file) => {
    return apiClient.postForm(
      "/v2/imports/enrollment-projection-upload",
      buildImportFormData(payload, file)
    );
  },
  materializeEnrollmentImport: (payload, file) => {
    return apiClient.postForm(
      "/v2/imports/enrollment-materialize-upload",
      buildImportFormData(payload, file)
    );
  },
  listImportTemplates: () => apiClient.get("/v2/imports/templates"),
  downloadImportTemplate: (templateName) =>
    downloadCsvTemplate(`/v2/imports/templates/${templateName}`),
  uploadModulesCsv: (importRunId, file) =>
    apiClient.postForm(`/v2/imports/${importRunId}/modules-upload`, buildSimpleCsvFormData(file)),
  uploadRoomsCsv: (importRunId, file) =>
    apiClient.postForm(`/v2/imports/${importRunId}/rooms-upload`, buildSimpleCsvFormData(file)),
  uploadLecturersCsv: (importRunId, file) =>
    apiClient.postForm(`/v2/imports/${importRunId}/lecturers-upload`, buildSimpleCsvFormData(file)),
  uploadSessionsCsv: (importRunId, file) =>
    apiClient.postForm(`/v2/imports/${importRunId}/sessions-upload`, buildSimpleCsvFormData(file)),
  uploadSessionLecturersCsv: (importRunId, file) =>
    apiClient.postForm(
      `/v2/imports/${importRunId}/session-lecturers-upload`,
      buildSimpleCsvFormData(file)
    ),
  getImportWorkspace: (importRunId) => apiClient.get(`/v2/imports/${importRunId}/workspace`),
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
  generate: (payload) => apiClient.post("/v2/generate", payload),
  latestGeneration: (importRunId = null) => {
    if (!importRunId) {
      return apiClient.get("/v2/generate/latest");
    }
    return apiClient.get(`/v2/generate/latest?import_run_id=${importRunId}`);
  },
  verifySnapshotGeneration: (importRunId) =>
    apiClient.get(`/v2/imports/${importRunId}/verification`),
  verifySnapshotGenerationPython: (importRunId) =>
    apiClient.get(`/v2/imports/${importRunId}/verification/python`),
  setDefault: (solutionId, importRunId = null) =>
    apiClient.post("/v2/solutions/default", {
      solution_id: solutionId,
      import_run_id: importRunId || undefined,
    }),
  view: ({ mode, lecturerId, studentGroupId, degreeId, pathId, studyYear, importRunId }) => {
    const params = new URLSearchParams({ mode });
    if (lecturerId) params.set("lecturer_id", lecturerId);
    if (studentGroupId) params.set("student_group_id", studentGroupId);
    if (degreeId) params.set("degree_id", degreeId);
    if (pathId) params.set("path_id", pathId);
    if (studyYear) params.set("study_year", studyYear);
    if (importRunId) params.set("import_run_id", importRunId);
    return apiClient.get(`/v2/views?${params.toString()}`);
  },
  exportView: ({ mode, format, lecturerId, studentGroupId, degreeId, pathId, studyYear, importRunId }) => {
    const params = new URLSearchParams({ mode, export_format: format });
    if (lecturerId) params.set("lecturer_id", lecturerId);
    if (studentGroupId) params.set("student_group_id", studentGroupId);
    if (degreeId) params.set("degree_id", degreeId);
    if (pathId) params.set("path_id", pathId);
    if (studyYear) params.set("study_year", studyYear);
    if (importRunId) params.set("import_run_id", importRunId);
    return apiClient.get(`/v2/exports?${params.toString()}`);
  },
};
