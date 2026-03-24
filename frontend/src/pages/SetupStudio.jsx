import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { timetableStudioService } from "../services/timetableStudioService";

const activeImportRunStorageKey = "kln_active_import_run_id";

const emptyWorkspace = {
  import_run_id: null,
  selected_academic_year: "",
  programmes: [],
  programme_paths: [],
  curriculum_modules: [],
  attendance_groups: [],
  lecturers: [],
  rooms: [],
  shared_sessions: [],
};

const emptyLecturerForm = {
  name: "",
  email: "",
  notes: "",
};

const emptyRoomForm = {
  name: "",
  capacity: "",
  room_type: "lecture",
  lab_type: "",
  location: "",
  year_restriction: "",
  notes: "",
};

const emptySessionForm = {
  name: "",
  session_type: "lecture",
  duration_minutes: 60,
  occurrences_per_week: 1,
  required_room_type: "lecture",
  required_lab_type: "",
  specific_room_id: "",
  max_students_per_group: "",
  allow_parallel_rooms: false,
  notes: "",
  lecturer_ids: [],
  curriculum_module_ids: [],
  attendance_group_ids: [],
};

function buildSessionFormFromWorkspaceSession(session) {
  return {
    name: session.name || "",
    session_type: session.session_type || "lecture",
    duration_minutes: Number(session.duration_minutes || 60),
    occurrences_per_week: Number(session.occurrences_per_week || 1),
    required_room_type: session.required_room_type || "lecture",
    required_lab_type: session.required_lab_type || "",
    specific_room_id: session.specific_room_id ? String(session.specific_room_id) : "",
    max_students_per_group: session.max_students_per_group
      ? String(session.max_students_per_group)
      : "",
    allow_parallel_rooms: Boolean(session.allow_parallel_rooms),
    notes: session.notes || "",
    lecturer_ids: [...(session.lecturer_ids || [])],
    curriculum_module_ids: [...(session.curriculum_module_ids || [])],
    attendance_group_ids: [...(session.attendance_group_ids || [])],
  };
}

function describeSessionRepairNeeds(session, readinessBlocking) {
  const missing = [];
  if (!session.lecturer_ids?.length) {
    missing.push("lecturers");
  }
  if (!session.curriculum_module_ids?.length) {
    missing.push("module links");
  }
  if (!session.attendance_group_ids?.length) {
    missing.push("attendance groups");
  }
  const roomIssues = readinessBlocking.filter(
    (item) =>
      item.form === "session" &&
      (item.key === `room-mismatch-${session.id}` ||
        item.key === `lab-mismatch-${session.id}` ||
        item.key === `room-capacity-${session.id}`)
  );
  if (roomIssues.length > 0) {
    missing.push("room assignment");
  }
  return missing;
}

const supportCsvDefinitions = [
  {
    key: "rooms",
    title: "Rooms",
    templateName: "rooms",
    upload: "uploadRoomsCsv",
    detail: "Rooms, capacities, room types, lab types, locations, and restrictions.",
    statusFromWorkspace: (workspace) =>
      workspace.rooms.length > 0 ? `${workspace.rooms.length} imported` : "Import needed",
  },
  {
    key: "lecturers",
    title: "Lecturers",
    templateName: "lecturers",
    upload: "uploadLecturersCsv",
    detail: "Lecturer identities that sessions can be linked to.",
    statusFromWorkspace: (workspace) =>
      workspace.lecturers.length > 0
        ? `${workspace.lecturers.length} imported`
        : "Import needed",
  },
  {
    key: "modules",
    title: "Modules",
    templateName: "modules",
    upload: "uploadModulesCsv",
    detail: "Optional corrections and enrichment for module metadata.",
    statusFromWorkspace: (workspace) =>
      workspace.curriculum_modules.length > 0
        ? `${workspace.curriculum_modules.length} available`
        : "Import needed",
  },
  {
    key: "sessions",
    title: "Sessions",
    templateName: "sessions",
    upload: "uploadSessionsCsv",
    detail: "The shared teaching sessions the solver should schedule.",
    statusFromWorkspace: (workspace) =>
      workspace.shared_sessions.length > 0
        ? `${workspace.shared_sessions.length} imported`
        : "Import needed",
  },
  {
    key: "session_lecturers",
    title: "Session Lecturers",
    templateName: "session_lecturers",
    upload: "uploadSessionLecturersCsv",
    detail: "Links existing sessions to existing lecturers.",
    statusFromWorkspace: () => "Import after sessions + lecturers",
  },
];

const localImportTemplates = {
  student_enrollments: {
    filename: "student_enrollments_template.csv",
    label: "Student Enrollments",
    columns: [
      "CoursePathNo",
      "CourseCode",
      "Year",
      "AcYear",
      "Attempt",
      "stream",
      "batch",
      "student_hash",
    ],
    rows: [
      ["1", "CHEM 11612", "1", "2022/2023", "1", "PS", "2022", "stu_hash_0001"],
      ["1", "AMAT 11113", "1", "2022/2023", "1", "PS", "2022", "stu_hash_0001"],
    ],
  },
  rooms: {
    filename: "rooms_template.csv",
    label: "Rooms",
    columns: [
      "room_code",
      "room_name",
      "capacity",
      "room_type",
      "lab_type",
      "location",
      "year_restriction",
    ],
    rows: [
      ["A7-H1", "A7 Hall 1", "180", "lecture", "", "A7 Building", ""],
      ["CHEM-LAB-1", "Chemistry Lab 1", "30", "lab", "chemistry", "Science Block", ""],
    ],
  },
  lecturers: {
    filename: "lecturers_template.csv",
    label: "Lecturers",
    columns: ["lecturer_code", "name", "email"],
    rows: [
      ["LECT-CHEM-01", "Dr. Silva", "silva@example.edu"],
      ["LECT-MATH-01", "Prof. Perera", "perera@example.edu"],
    ],
  },
  modules: {
    filename: "modules_template.csv",
    label: "Modules",
    columns: [
      "module_code",
      "module_name",
      "subject_name",
      "nominal_year",
      "semester_bucket",
      "is_full_year",
    ],
    rows: [
      ["CHEM 11612", "Foundations of Chemistry", "Chemistry", "1", "1", "false"],
      ["AMAT 11113", "Calculus I", "Applied Mathematics", "1", "1", "false"],
    ],
  },
  sessions: {
    filename: "sessions_template.csv",
    label: "Sessions",
    columns: [
      "session_code",
      "module_code",
      "session_name",
      "session_type",
      "duration_minutes",
      "occurrences_per_week",
      "required_room_type",
      "required_lab_type",
      "specific_room_code",
      "max_students_per_group",
      "allow_parallel_rooms",
      "notes",
    ],
    rows: [
      [
        "CHEM11612-LEC",
        "CHEM 11612",
        "Chemistry Lecture",
        "lecture",
        "120",
        "2",
        "lecture",
        "",
        "",
        "",
        "false",
        "Main weekly lecture",
      ],
      [
        "CHEM11612-LAB",
        "CHEM 11612",
        "Chemistry Lab",
        "lab",
        "180",
        "1",
        "lab",
        "chemistry",
        "CHEM-LAB-1",
        "30",
        "true",
        "Split if needed by lab capacity",
      ],
    ],
  },
  session_lecturers: {
    filename: "session_lecturers_template.csv",
    label: "Session Lecturers",
    columns: ["session_code", "lecturer_code"],
    rows: [
      ["CHEM11612-LEC", "LECT-CHEM-01"],
      ["CHEM11612-LAB", "LECT-CHEM-01"],
    ],
  },
};

function downloadTextFile(filename, content, contentType = "text/csv;charset=utf-8") {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function readActiveImportRunId() {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(activeImportRunStorageKey);
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function buildLocalTemplateCsv(template) {
  if (!template?.columns?.length) {
    return "";
  }
  const rows = [template.columns, ...(template.rows || [])];
  return `${rows.map((row) => row.join(",")).join("\n")}\n`;
}

function buildWorkspaceSummary(workspace) {
  return [
    { label: "Programmes", value: workspace.programmes.length },
    { label: "Programme Paths", value: workspace.programme_paths.length },
    { label: "Attendance Groups", value: workspace.attendance_groups.length },
    { label: "Modules", value: workspace.curriculum_modules.length },
    { label: "Lecturers", value: workspace.lecturers.length },
    { label: "Rooms", value: workspace.rooms.length },
    { label: "Shared Sessions", value: workspace.shared_sessions.length },
  ];
}

function buildReadiness(workspace) {
  const blocking = [];
  const warnings = [];

  if (workspace.rooms.length === 0) {
    blocking.push({
      key: "rooms-empty",
      title: "No rooms yet",
      detail: "Add at least one room before generation.",
      action: "Add rooms",
      form: "room",
    });
  }

  if (workspace.lecturers.length === 0) {
    blocking.push({
      key: "lecturers-empty",
      title: "No lecturers yet",
      detail: "Add at least one lecturer before generation.",
      action: "Add lecturers",
      form: "lecturer",
    });
  }

  if (workspace.shared_sessions.length === 0) {
    blocking.push({
      key: "sessions-empty",
      title: "No shared sessions yet",
      detail: "Create the real teaching sessions that the solver should schedule.",
      action: "Add shared sessions",
      form: "session",
    });
  }

  const sessionsMissingLecturers = workspace.shared_sessions.filter(
    (session) => !session.lecturer_ids?.length
  );
  if (sessionsMissingLecturers.length > 0) {
    blocking.push({
      key: "sessions-missing-lecturers",
      title: "Sessions missing lecturers",
      detail: `${sessionsMissingLecturers.length} session${
        sessionsMissingLecturers.length === 1 ? "" : "s"
      } still need lecturer assignments.`,
      action: "Add lecturers",
      form: "lecturer",
    });
  }

  const sessionsMissingModules = workspace.shared_sessions.filter(
    (session) => !session.curriculum_module_ids?.length
  );
  if (sessionsMissingModules.length > 0) {
    blocking.push({
      key: "sessions-missing-modules",
      title: "Sessions missing module links",
      detail: `${sessionsMissingModules.length} session${
        sessionsMissingModules.length === 1 ? "" : "s"
      } are not linked to any curriculum module.`,
      action: "Add shared sessions",
      form: "session",
    });
  }

  const sessionsMissingAttendance = workspace.shared_sessions.filter(
    (session) => !session.attendance_group_ids?.length
  );
  if (sessionsMissingAttendance.length > 0) {
    blocking.push({
      key: "sessions-missing-attendance",
      title: "Sessions missing attendance groups",
      detail: `${sessionsMissingAttendance.length} session${
        sessionsMissingAttendance.length === 1 ? "" : "s"
      } have no attendance mapping yet.`,
      action: "Add shared sessions",
      form: "session",
    });
  }

  const labSessionsWithInvalidDuration = workspace.shared_sessions.filter((session) => {
    const type = String(session.session_type || "").toLowerCase();
    return (type === "lab" || type === "practical") && Number(session.duration_minutes) !== 180;
  });
  if (labSessionsWithInvalidDuration.length > 0) {
    blocking.push({
      key: "lab-duration",
      title: "Lab-like sessions need 180 minutes",
      detail: `${labSessionsWithInvalidDuration.length} lab or practical session${
        labSessionsWithInvalidDuration.length === 1 ? "" : "s"
      } do not use the required 180-minute duration.`,
      action: "Add shared sessions",
      form: "session",
    });
  }

  const splitWarnings = workspace.shared_sessions.filter((session) => {
    const splitLimit = Number(session.max_students_per_group || 0);
    return splitLimit > 0 && !session.allow_parallel_rooms;
  });
  if (splitWarnings.length > 0) {
    warnings.push({
      key: "split-warning",
      title: "Split sessions may need parallel-room review",
      detail: `${splitWarnings.length} session${
        splitWarnings.length === 1 ? "" : "s"
      } use max students per group without parallel rooms enabled.`,
    });
  }

  return {
    blocking,
    warnings,
    ready: blocking.length === 0 && workspace.shared_sessions.length > 0,
  };
}

function ToggleList({ title, items, selectedIds, onToggle, renderLabel, emptyMessage }) {
  return (
    <div className="schema-notes compact">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="helper-copy">{emptyMessage}</p>
      ) : (
        <div className="constraint-list">
          {items.map((item) => {
            const label = renderLabel(item);
            return (
              <label key={item.id} className="constraint-row">
                <input
                  type="checkbox"
                  checked={selectedIds.includes(item.id)}
                  onChange={() => onToggle(item.id)}
                />
                <div>
                  <strong>{label.title}</strong>
                  <span>{label.detail}</span>
                </div>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SetupStudio() {
  const navigate = useNavigate();
  const [activeImportRunId, setActiveImportRunId] = useState(null);
  const [workspace, setWorkspace] = useState(emptyWorkspace);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [useSampleCsv, setUseSampleCsv] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [projection, setProjection] = useState(null);
  const [bucketDecision, setBucketDecision] = useState("accept_exception");
  const [openForm, setOpenForm] = useState("");
  const [showUtilities, setShowUtilities] = useState(false);
  const [editingSharedSessionId, setEditingSharedSessionId] = useState(null);
  const [importTemplates, setImportTemplates] = useState([]);
  const [recentRuns, setRecentRuns] = useState([]);
  const [lecturerForm, setLecturerForm] = useState(emptyLecturerForm);
  const [roomForm, setRoomForm] = useState(emptyRoomForm);
  const [sessionForm, setSessionForm] = useState(emptySessionForm);

  const hasChosenImportSource = useSampleCsv || Boolean(selectedFile);
  const summaryCards = useMemo(() => buildWorkspaceSummary(workspace), [workspace]);
  const readiness = useMemo(
    () => workspace.readiness || buildReadiness(workspace),
    [workspace]
  );
  const readinessBlocking = useMemo(
    () =>
      readiness.blocking || [
        ...(readiness.import_needed || readiness.importNeeded || []),
        ...(readiness.repair_needed || readiness.repairNeeded || []),
      ],
    [readiness]
  );
  const sessionsNeedingRepair = useMemo(
    () =>
      workspace.shared_sessions.filter(
        (session) =>
          !session.lecturer_ids?.length ||
          !session.curriculum_module_ids?.length ||
          !session.attendance_group_ids?.length ||
          readinessBlocking.some((item) =>
            item.form === "session" &&
            (item.key === `room-mismatch-${session.id}` ||
              item.key === `lab-mismatch-${session.id}` ||
              item.key === `room-capacity-${session.id}`)
          )
      ),
    [workspace, readinessBlocking]
  );

  async function refreshRecentRuns() {
    try {
      const response = await timetableStudioService.listImportRuns(20);
      setRecentRuns(response?.runs || []);
    } catch {
      setRecentRuns([]);
    }
  }

  async function loadWorkspace(importRunId, nextStatus = "") {
    if (!importRunId) {
      setWorkspace(emptyWorkspace);
      return;
    }
    setLoadingWorkspace(true);
    setError("");
    try {
      const response = await timetableStudioService.getImportWorkspace(importRunId);
      setWorkspace(response || emptyWorkspace);
      setActiveImportRunId(importRunId);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(activeImportRunStorageKey, String(importRunId));
      }
      if (nextStatus) {
        setStatus(nextStatus);
      }
    } catch (err) {
      if (
        err?.message?.toLowerCase().includes("not found") &&
        typeof window !== "undefined"
      ) {
        window.localStorage.removeItem(activeImportRunStorageKey);
        setActiveImportRunId(null);
        setWorkspace(emptyWorkspace);
      }
      setError(err.message || "Failed to load the import workspace.");
    } finally {
      setLoadingWorkspace(false);
    }
  }

  useEffect(() => {
    timetableStudioService
      .listImportTemplates()
      .then((response) => setImportTemplates(response.templates || []))
      .catch(() => {});
    refreshRecentRuns();
  }, []);

  function selectedImportFile() {
    return useSampleCsv ? undefined : selectedFile;
  }

  function buildReviewRules() {
    return (analysis?.buckets || []).map((bucket) => ({
      bucket_type: bucket.bucket_type,
      bucket_key: bucket.bucket_key,
      action: bucketDecision,
      label: "Applied from Setup Studio review.",
    }));
  }

  async function handleAnalyze() {
    if (!hasChosenImportSource) {
      return;
    }
    setWorking(true);
    setError("");
    setStatus("");
    try {
      const response = await timetableStudioService.analyzeEnrollmentImport(
        selectedImportFile()
      );
      setAnalysis(response);
      setProjection(null);
      setStatus(`Analyzed ${response.source_file || "the selected CSV"}.`);
    } catch (err) {
      setError(err.message || "Failed to analyze the enrollment CSV.");
    } finally {
      setWorking(false);
    }
  }

  async function handleReviewImport() {
    if (!analysis) {
      return;
    }
    setWorking(true);
    setError("");
    setStatus("");
    try {
      const response = await timetableStudioService.previewEnrollmentImport(
        { rules: buildReviewRules() },
        selectedImportFile()
      );
      setProjection(response);
      setStatus(
        "Review result is ready. If it looks correct, materialize this import into a working snapshot."
      );
    } catch (err) {
      setError(err.message || "Failed to review the analyzed import.");
    } finally {
      setWorking(false);
    }
  }

  async function handleUseImport() {
    if (!analysis) {
      return;
    }
    setWorking(true);
    setError("");
    setStatus("");
    try {
      const response = await timetableStudioService.materializeEnrollmentImport(
        { rules: buildReviewRules() },
        selectedImportFile()
      );
      setAnalysis(null);
      setProjection(null);
      setSelectedFile(null);
      setUseSampleCsv(false);
      await loadWorkspace(
        response.import_run_id,
        `The CSV import has been materialized into snapshot #${response.import_run_id}.`
      );
    } catch (err) {
      setError(err.message || "Failed to materialize the import into a working snapshot.");
    } finally {
      setWorking(false);
    }
  }

  async function handleDownloadTemplate(templateName) {
    setError("");
    try {
      const localTemplate =
        importTemplates.find((item) => item.name === templateName) ||
        localImportTemplates[templateName];
      if (localTemplate?.columns?.length) {
        downloadTextFile(
          localTemplate.filename || `${templateName}_template.csv`,
          buildLocalTemplateCsv(localTemplate)
        );
        setStatus(`Downloaded ${localTemplate.label || templateName} template.`);
        return;
      }
      const response = await timetableStudioService.downloadImportTemplate(templateName);
      downloadTextFile(response.filename, response.content);
      setStatus(`Downloaded ${templateName} template.`);
    } catch (err) {
      setError(err.message || "Failed to download the CSV template.");
    }
  }

  async function handleSupportCsvUpload(definition, file) {
    if (!activeImportRunId || !file) {
      return;
    }
    setWorking(true);
    setError("");
    setStatus("");
    try {
      const response = await timetableStudioService[definition.upload](activeImportRunId, file);
      const warningCount = response.warnings?.length || 0;
      await loadWorkspace(
        activeImportRunId,
        `${definition.title} CSV imported into snapshot #${activeImportRunId}. Created ${response.created_count || 0}, updated ${response.updated_count || 0}${warningCount ? `, warnings ${warningCount}` : ""}.`
      );
      await refreshRecentRuns();
    } catch (err) {
      setError(err.message || `Failed to import ${definition.title.toLowerCase()} CSV.`);
    } finally {
      setWorking(false);
    }
  }

  async function handleImportDemoBundle() {
    if (!activeImportRunId) {
      return;
    }
    setWorking(true);
    setError("");
    setStatus("");
    try {
      const response = await timetableStudioService.importDemoBundle(activeImportRunId);
      await loadWorkspace(
        activeImportRunId,
        `Imported demo bundle into snapshot #${activeImportRunId}: ${response.lecturers_created} lecturers, ${response.rooms_created} rooms, ${response.shared_sessions_created} shared sessions.`
      );
      await refreshRecentRuns();
    } catch (err) {
      setError(err.message || "Failed to import the demo bundle.");
    } finally {
      setWorking(false);
    }
  }

  async function handleOpenSnapshot(importRunId) {
    setAnalysis(null);
    setProjection(null);
    setSelectedFile(null);
    setUseSampleCsv(false);
    await loadWorkspace(importRunId, `Opened snapshot #${importRunId}.`);
  }

  function handleStartFresh() {
    setActiveImportRunId(null);
    setWorkspace(emptyWorkspace);
    setAnalysis(null);
    setProjection(null);
    setSelectedFile(null);
    setUseSampleCsv(false);
    setOpenForm("");
    setError("");
    setStatus("Starting a fresh setup session. Import student enrolments to create a new snapshot.");
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(activeImportRunStorageKey);
    }
  }

  async function handleAddLecturer(event) {
    event.preventDefault();
    setWorking(true);
    setError("");
    try {
      await timetableStudioService.createSnapshotLecturersBatch(activeImportRunId, [
        {
          name: lecturerForm.name.trim(),
          email: lecturerForm.email.trim() || null,
          notes: lecturerForm.notes.trim() || null,
        },
      ]);
      setLecturerForm(emptyLecturerForm);
      setOpenForm("");
      await loadWorkspace(activeImportRunId, "Lecturer added to the current snapshot.");
    } catch (err) {
      setError(err.message || "Failed to add the lecturer.");
    } finally {
      setWorking(false);
    }
  }

  async function handleAddRoom(event) {
    event.preventDefault();
    setWorking(true);
    setError("");
    try {
      await timetableStudioService.createSnapshotRoomsBatch(activeImportRunId, [
        {
          name: roomForm.name.trim(),
          capacity: Number(roomForm.capacity),
          room_type: roomForm.room_type,
          lab_type: roomForm.lab_type.trim() || null,
          location: roomForm.location.trim(),
          year_restriction: roomForm.year_restriction
            ? Number(roomForm.year_restriction)
            : null,
          notes: roomForm.notes.trim() || null,
        },
      ]);
      setRoomForm(emptyRoomForm);
      setOpenForm("");
      await loadWorkspace(activeImportRunId, "Room added to the current snapshot.");
    } catch (err) {
      setError(err.message || "Failed to add the room.");
    } finally {
      setWorking(false);
    }
  }

  async function handleAddSession(event) {
    event.preventDefault();
    setWorking(true);
    setError("");
    const payload = {
      name: sessionForm.name.trim(),
      session_type: sessionForm.session_type,
      duration_minutes: Number(sessionForm.duration_minutes),
      occurrences_per_week: Number(sessionForm.occurrences_per_week),
      required_room_type: sessionForm.required_room_type || null,
      required_lab_type: sessionForm.required_lab_type.trim() || null,
      specific_room_id: sessionForm.specific_room_id
        ? Number(sessionForm.specific_room_id)
        : null,
      max_students_per_group: sessionForm.max_students_per_group
        ? Number(sessionForm.max_students_per_group)
        : null,
      allow_parallel_rooms: Boolean(sessionForm.allow_parallel_rooms),
      notes: sessionForm.notes.trim() || null,
      lecturer_ids: sessionForm.lecturer_ids,
      curriculum_module_ids: sessionForm.curriculum_module_ids,
      attendance_group_ids: sessionForm.attendance_group_ids,
    };
    try {
      if (editingSharedSessionId) {
        await timetableStudioService.updateSnapshotSharedSession(
          activeImportRunId,
          editingSharedSessionId,
          payload
        );
      } else {
        await timetableStudioService.createSnapshotSharedSessionsBatch(activeImportRunId, [payload]);
      }
      setSessionForm(emptySessionForm);
      setEditingSharedSessionId(null);
      setOpenForm("");
      await loadWorkspace(
        activeImportRunId,
        editingSharedSessionId
          ? "Shared session repaired in the current snapshot."
          : "Shared session added to the current snapshot."
      );
    } catch (err) {
      setError(err.message || "Failed to save the shared session.");
    } finally {
      setWorking(false);
    }
  }

  function toggleSessionValue(field, id) {
    setSessionForm((current) => ({
      ...current,
      [field]: current[field].includes(id)
        ? current[field].filter((value) => value !== id)
        : [...current[field], id],
    }));
  }

  function handleEditSharedSession(session) {
    setEditingSharedSessionId(session.id);
    setSessionForm(buildSessionFormFromWorkspaceSession(session));
    setOpenForm("session");
    setError("");
    setStatus(`Repairing shared session: ${session.name}.`);
  }

  function handleCancelSessionEdit() {
    setEditingSharedSessionId(null);
    setSessionForm(emptySessionForm);
    setOpenForm("");
  }

  return (
    <div className="page-shell">
      <div className="panel studio-panel">
        <div className="studio-header">
          <div>
            <h1 className="section-title">Setup Studio</h1>
            <p className="section-subtitle">
              Start from student enrolments, then enrich the snapshot with support CSVs and repair
              only the missing local issues.
            </p>
            {activeImportRunId ? (
              <p className="helper-copy setup-context-chip">
                Active snapshot #{activeImportRunId}
                {workspace.selected_academic_year
                  ? ` for ${workspace.selected_academic_year}`
                  : ""}
              </p>
            ) : (
              <p className="helper-copy">
                Start with student enrolments. Everything else should be added only when the
                readiness list asks for it.
              </p>
            )}
          </div>
          <div className="studio-actions">
            <button
              type="button"
              className="ghost-btn"
              onClick={() => setShowUtilities((current) => !current)}
            >
              {showUtilities ? "Hide Utilities" : "Utilities"}
            </button>
            <button
              className="primary-btn"
              type="button"
              onClick={() => navigate("/generate")}
              disabled={!readiness.ready}
            >
              Continue to Generate
            </button>
          </div>
        </div>

        {status && <div className="info-banner valid">{status}</div>}
        {error && <div className="error-banner">{error}</div>}
        {loadingWorkspace && <div className="info-banner">Loading the current import snapshot...</div>}

        {showUtilities && (
          <section className="studio-card setup-utilities-card">
            <div className="studio-header compact">
              <div>
                <h2>Utilities</h2>
                <p className="helper-copy">
                  Keep the main flow simple. Use this area only when you intentionally want an older
                  snapshot or demo data.
                </p>
              </div>
              <div className="studio-actions">
                <button type="button" className="ghost-btn" onClick={handleStartFresh}>
                  Start Fresh
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={handleImportDemoBundle}
                  disabled={!activeImportRunId || working}
                >
                  Import Demo Bundle
                </button>
              </div>
            </div>
            <div className="constraint-list">
              {recentRuns.length === 0 ? (
                <div className="constraint-row static">
                  <div>
                    <strong>No previous snapshots</strong>
                    <span>Create one by materializing a student enrolment import.</span>
                  </div>
                </div>
              ) : (
                recentRuns.map((run) => (
                  <div key={run.import_run_id} className="constraint-row static">
                    <div>
                      <strong>Snapshot #{run.import_run_id}</strong>
                      <span>
                        {run.source_file} · {run.status}
                        {run.selected_academic_year ? ` · ${run.selected_academic_year}` : ""}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={() => handleOpenSnapshot(run.import_run_id)}
                    >
                      Open
                    </button>
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        <section className="studio-card setup-import-section">
          <h2>Import Files</h2>
          <p className="helper-copy">
            Start with student enrolments, then add whichever support CSVs the admin can export
            from the main system. Anything still missing can be repaired locally below.
          </p>
          <div className="summary-grid setup-import-grid">
            <article className="summary-item setup-import-card setup-import-card-primary">
              <span>Student Enrolments</span>
              <strong className="setup-card-status">
                {activeImportRunId ? "Snapshot available" : "Creates the snapshot"}
              </strong>
              <p>
                Import the registration CSV that tells the system which students take which modules.
              </p>
              <div className="studio-actions">
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() => handleDownloadTemplate("student_enrollments")}
                >
                  Download Template
                </button>
                <label className="ghost-btn file-picker-btn">
                  Import CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    hidden
                    onChange={(event) => {
                      const nextFile = event.target.files?.[0] || null;
                      setSelectedFile(nextFile);
                      setUseSampleCsv(false);
                      setAnalysis(null);
                      setProjection(null);
                      setStatus("");
                      setError("");
                    }}
                  />
                </label>
                <button
                  type="button"
                  className={useSampleCsv ? "primary-btn" : "ghost-btn"}
                  onClick={() => {
                    setUseSampleCsv(true);
                    setSelectedFile(null);
                    setAnalysis(null);
                    setProjection(null);
                    setStatus("Using the bundled sample enrollment CSV.");
                    setError("");
                  }}
                >
                  Use Sample CSV
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  onClick={handleAnalyze}
                  disabled={!hasChosenImportSource || working}
                >
                  {working ? "Working..." : "Analyze Import"}
                </button>
              </div>
              <p className="helper-copy setup-inline-note">
                {selectedFile
                  ? `Selected file: ${selectedFile.name}`
                  : useSampleCsv
                    ? "Using the bundled sample CSV."
                    : "No CSV selected yet."}
              </p>

              {analysis && (
                <div className="schema-notes compact">
                  <h3>Review</h3>
                  <div className="summary-grid">
                    <div className="summary-item">
                      <span>Total rows</span>
                      <strong>{analysis.summary?.total_rows ?? 0}</strong>
                    </div>
                    <div className="summary-item">
                      <span>Unique students</span>
                      <strong>{analysis.summary?.unique_students ?? 0}</strong>
                    </div>
                    <div className="summary-item">
                      <span>Review buckets</span>
                      <strong>{analysis.buckets?.length ?? 0}</strong>
                    </div>
                  </div>

                  {(analysis.buckets || []).length > 0 ? (
                    <>
                      <label>
                        <span>Apply this decision to all current review buckets</span>
                        <select
                          value={bucketDecision}
                          onChange={(event) => setBucketDecision(event.target.value)}
                        >
                          <option value="accept_exception">Accept As Exception</option>
                          <option value="exclude">Exclude From Timetable Demand</option>
                          <option value="treat_as_common">Treat As Common Teaching</option>
                        </select>
                      </label>
                      <div className="constraint-list">
                        {analysis.buckets.slice(0, 6).map((bucket) => (
                          <div
                            key={`${bucket.bucket_type}-${bucket.bucket_key}`}
                            className="constraint-row static"
                          >
                            <div>
                              <strong>{bucket.description}</strong>
                              <span>{bucket.row_count} rows</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="helper-copy">No review buckets were created for this import.</p>
                  )}

                  <div className="studio-actions">
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={handleReviewImport}
                      disabled={working}
                    >
                      Review Import
                    </button>
                    <button
                      type="button"
                      className="primary-btn"
                      onClick={handleUseImport}
                      disabled={working}
                    >
                      Use This Import
                    </button>
                  </div>
                </div>
              )}

              {projection && (
                <div className="info-banner setup-inline-banner">
                  Review result: {projection.projection_summary?.projected_rows ?? 0} projected
                  rows are ready to materialize into a working snapshot.
                </div>
              )}
            </article>

            {supportCsvDefinitions.map((definition) => {
              const template = importTemplates.find((item) => item.name === definition.templateName);
              return (
                <article key={definition.key} className="summary-item setup-import-card">
                  <span>{definition.title}</span>
                  <strong className="setup-card-status">
                    {activeImportRunId
                      ? definition.statusFromWorkspace(workspace)
                      : "Waiting for student enrolments"}
                  </strong>
                  <p>{template?.description || definition.detail}</p>
                  <div className="studio-actions">
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={() => handleDownloadTemplate(definition.templateName)}
                    >
                      Download Template
                    </button>
                    <label className="ghost-btn file-picker-btn">
                      Import CSV
                      <input
                        type="file"
                        accept=".csv,text/csv"
                        hidden
                        disabled={!activeImportRunId}
                        onChange={(event) =>
                          handleSupportCsvUpload(definition, event.target.files?.[0] || null)
                        }
                      />
                    </label>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="studio-card setup-summary-section">
          <h2>What The System Understood</h2>
          <p className="helper-copy">
            This section confirms the interpreted structure. It is intentionally summary-first
            rather than a giant editor.
          </p>
          <div className="summary-grid">
            {summaryCards.map((item) => (
              <div key={item.label} className="summary-item">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
          {!activeImportRunId && (
            <p className="empty-state">
              Materialize an enrollment import first to create a working snapshot.
            </p>
          )}
        </section>

        <section className="studio-card setup-readiness-section">
          <div className="studio-header compact">
            <div>
              <h2>Missing For Generation</h2>
              <p className="helper-copy">
                Separate missing imports from local repairs. Generation should block only on real
                solver requirements.
              </p>
            </div>
          </div>

          {readiness.ready ? (
            <div className="info-banner valid">This snapshot is currently generation-ready.</div>
          ) : (
            <div className="summary-grid">
              <div className="summary-item">
                <span>Import needed</span>
                <strong>
                  {
                    readinessBlocking.filter((item) =>
                      ["rooms-empty", "lecturers-empty", "sessions-empty"].includes(item.key)
                    ).length
                  }
                </strong>
              </div>
              <div className="summary-item">
                <span>Repair needed</span>
                <strong>
                  {
                    readinessBlocking.filter(
                      (item) =>
                        !["rooms-empty", "lecturers-empty", "sessions-empty"].includes(item.key)
                    ).length
                  }
                </strong>
              </div>
              <div className="summary-item">
                <span>Warnings</span>
                <strong>{readiness.warnings.length}</strong>
              </div>
            </div>
          )}

          {readinessBlocking.length > 0 && (
            <div className="constraint-list">
              {readinessBlocking.map((item) => (
                <div key={item.key} className="constraint-row static">
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.detail}</span>
                  </div>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => setOpenForm(item.form)}
                  >
                    {item.action}
                  </button>
                </div>
              ))}
            </div>
          )}

          {sessionsNeedingRepair.length > 0 && (
            <div className="schema-notes compact setup-repair-queue">
              <h3>Repair Queue</h3>
              <div className="constraint-list">
                {sessionsNeedingRepair.map((session) => {
                  const missing = describeSessionRepairNeeds(session, readinessBlocking);
                  return (
                    <div key={session.id} className="constraint-row static">
                      <div>
                        <strong>{session.name}</strong>
                        <span>Missing {missing.join(", ")}.</span>
                      </div>
                      <button
                        type="button"
                        className="ghost-btn"
                        onClick={() => handleEditSharedSession(session)}
                      >
                        Repair Session
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {readiness.warnings.length > 0 && (
            <div className="schema-notes compact">
              <h3>Warnings</h3>
              <div className="constraint-list">
                {readiness.warnings.map((item) => (
                  <div key={item.key} className="constraint-row static">
                    <div>
                      <strong>{item.title}</strong>
                      <span>{item.detail}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="studio-card setup-continue-section">
          <h2>Continue</h2>
          <p className="helper-copy">
            Move to generation only when the blocking list is empty. Warnings can remain if you are
            comfortable with them.
          </p>
          <div className="studio-actions">
            <button
              type="button"
              className="primary-btn"
              onClick={() => navigate("/generate")}
              disabled={!readiness.ready}
            >
              Open Generate
            </button>
          </div>
        </section>

        {activeImportRunId && (
          <section className="studio-card">
            <div className="studio-header compact">
              <div>
                <h2>Repair Missing Data</h2>
                <p className="helper-copy">
                  Use these forms only for small local fixes. Bulk source-data problems should still
                  be corrected in CSV and reimported.
                </p>
              </div>
              <div className="studio-actions">
                <button
                  type="button"
                  className={openForm === "lecturer" ? "primary-btn" : "ghost-btn"}
                  onClick={() => setOpenForm(openForm === "lecturer" ? "" : "lecturer")}
                >
                  Add Lecturer
                </button>
                <button
                  type="button"
                  className={openForm === "room" ? "primary-btn" : "ghost-btn"}
                  onClick={() => setOpenForm(openForm === "room" ? "" : "room")}
                >
                  Add Room
                </button>
                <button
                  type="button"
                  className={openForm === "session" ? "primary-btn" : "ghost-btn"}
                  onClick={() => {
                    if (openForm === "session") {
                      handleCancelSessionEdit();
                      return;
                    }
                    setEditingSharedSessionId(null);
                    setSessionForm(emptySessionForm);
                    setOpenForm("session");
                  }}
                >
                  {editingSharedSessionId ? "Editing Shared Session" : "Add Shared Session"}
                </button>
              </div>
            </div>

            {openForm === "lecturer" && (
              <form onSubmit={handleAddLecturer}>
                <div className="form-grid two-column">
                  <label>
                    <span>Name</span>
                    <input
                      value={lecturerForm.name}
                      onChange={(event) =>
                        setLecturerForm({ ...lecturerForm, name: event.target.value })
                      }
                      required
                    />
                  </label>
                  <label>
                    <span>Email</span>
                    <input
                      value={lecturerForm.email}
                      onChange={(event) =>
                        setLecturerForm({ ...lecturerForm, email: event.target.value })
                      }
                    />
                  </label>
                  <label className="full-span">
                    <span>Notes</span>
                    <textarea
                      rows="3"
                      value={lecturerForm.notes}
                      onChange={(event) =>
                        setLecturerForm({ ...lecturerForm, notes: event.target.value })
                      }
                    />
                  </label>
                </div>
                <div className="studio-actions">
                  <button type="submit" className="primary-btn" disabled={working}>
                    Save Lecturer
                  </button>
                </div>
              </form>
            )}

            {openForm === "room" && (
              <form onSubmit={handleAddRoom}>
                <div className="form-grid two-column">
                  <label>
                    <span>Room name</span>
                    <input
                      value={roomForm.name}
                      onChange={(event) => setRoomForm({ ...roomForm, name: event.target.value })}
                      required
                    />
                  </label>
                  <label>
                    <span>Capacity</span>
                    <input
                      type="number"
                      min="1"
                      value={roomForm.capacity}
                      onChange={(event) =>
                        setRoomForm({ ...roomForm, capacity: event.target.value })
                      }
                      required
                    />
                  </label>
                  <label>
                    <span>Room type</span>
                    <select
                      value={roomForm.room_type}
                      onChange={(event) =>
                        setRoomForm({ ...roomForm, room_type: event.target.value })
                      }
                    >
                      <option value="lecture">Lecture</option>
                      <option value="lab">Lab</option>
                      <option value="seminar">Seminar</option>
                      <option value="any">Any</option>
                    </select>
                  </label>
                  <label>
                    <span>Location</span>
                    <input
                      value={roomForm.location}
                      onChange={(event) =>
                        setRoomForm({ ...roomForm, location: event.target.value })
                      }
                      required
                    />
                  </label>
                  <label>
                    <span>Lab type</span>
                    <input
                      value={roomForm.lab_type}
                      onChange={(event) =>
                        setRoomForm({ ...roomForm, lab_type: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    <span>Year restriction</span>
                    <input
                      type="number"
                      min="1"
                      max="6"
                      value={roomForm.year_restriction}
                      onChange={(event) =>
                        setRoomForm({ ...roomForm, year_restriction: event.target.value })
                      }
                    />
                  </label>
                  <label className="full-span">
                    <span>Notes</span>
                    <textarea
                      rows="3"
                      value={roomForm.notes}
                      onChange={(event) =>
                        setRoomForm({ ...roomForm, notes: event.target.value })
                      }
                    />
                  </label>
                </div>
                <div className="studio-actions">
                  <button type="submit" className="primary-btn" disabled={working}>
                    Save Room
                  </button>
                </div>
              </form>
            )}

            {openForm === "session" && (
              <form onSubmit={handleAddSession}>
                {editingSharedSessionId && (
                  <div className="info-banner">
                    Repairing shared session #{editingSharedSessionId}. Update the missing links or
                    fields, then save.
                  </div>
                )}
                <div className="form-grid two-column">
                  <label>
                    <span>Session name</span>
                    <input
                      value={sessionForm.name}
                      onChange={(event) =>
                        setSessionForm({ ...sessionForm, name: event.target.value })
                      }
                      required
                    />
                  </label>
                  <label>
                    <span>Session type</span>
                    <select
                      value={sessionForm.session_type}
                      onChange={(event) =>
                        setSessionForm({ ...sessionForm, session_type: event.target.value })
                      }
                    >
                      <option value="lecture">Lecture</option>
                      <option value="tutorial">Tutorial</option>
                      <option value="lab">Lab</option>
                      <option value="practical">Practical</option>
                    </select>
                  </label>
                  <label>
                    <span>Duration (minutes)</span>
                    <input
                      type="number"
                      min="30"
                      step="30"
                      value={sessionForm.duration_minutes}
                      onChange={(event) =>
                        setSessionForm({
                          ...sessionForm,
                          duration_minutes: Number(event.target.value),
                        })
                      }
                      required
                    />
                  </label>
                  <label>
                    <span>Occurrences per week</span>
                    <input
                      type="number"
                      min="1"
                      max="10"
                      value={sessionForm.occurrences_per_week}
                      onChange={(event) =>
                        setSessionForm({
                          ...sessionForm,
                          occurrences_per_week: Number(event.target.value),
                        })
                      }
                      required
                    />
                  </label>
                  <label>
                    <span>Required room type</span>
                    <select
                      value={sessionForm.required_room_type}
                      onChange={(event) =>
                        setSessionForm({
                          ...sessionForm,
                          required_room_type: event.target.value,
                        })
                      }
                    >
                      <option value="lecture">Lecture</option>
                      <option value="lab">Lab</option>
                      <option value="seminar">Seminar</option>
                      <option value="any">Any</option>
                    </select>
                  </label>
                  <label>
                    <span>Required lab type</span>
                    <input
                      value={sessionForm.required_lab_type}
                      onChange={(event) =>
                        setSessionForm({
                          ...sessionForm,
                          required_lab_type: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label>
                    <span>Specific room</span>
                    <select
                      value={sessionForm.specific_room_id}
                      onChange={(event) =>
                        setSessionForm({
                          ...sessionForm,
                          specific_room_id: event.target.value,
                        })
                      }
                    >
                      <option value="">Any room</option>
                      {workspace.rooms.map((room) => (
                        <option key={room.id} value={room.id}>
                          {room.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Max students per group</span>
                    <input
                      type="number"
                      min="1"
                      value={sessionForm.max_students_per_group}
                      onChange={(event) =>
                        setSessionForm({
                          ...sessionForm,
                          max_students_per_group: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="checkbox-field full-span">
                    <span>Allow same-time parallel rooms</span>
                    <input
                      type="checkbox"
                      checked={sessionForm.allow_parallel_rooms}
                      onChange={(event) =>
                        setSessionForm({
                          ...sessionForm,
                          allow_parallel_rooms: event.target.checked,
                        })
                      }
                    />
                  </label>
                  <label className="full-span">
                    <span>Notes</span>
                    <textarea
                      rows="3"
                      value={sessionForm.notes}
                      onChange={(event) =>
                        setSessionForm({ ...sessionForm, notes: event.target.value })
                      }
                    />
                  </label>
                </div>

                <ToggleList
                  title="Link modules"
                  items={workspace.curriculum_modules}
                  selectedIds={sessionForm.curriculum_module_ids}
                  onToggle={(id) => toggleSessionValue("curriculum_module_ids", id)}
                  renderLabel={(item) => ({ title: item.code, detail: item.name })}
                  emptyMessage="No modules are available in this snapshot yet."
                />

                <ToggleList
                  title="Link attendance groups"
                  items={workspace.attendance_groups}
                  selectedIds={sessionForm.attendance_group_ids}
                  onToggle={(id) => toggleSessionValue("attendance_group_ids", id)}
                  renderLabel={(item) => ({
                    title: item.label,
                    detail: `${item.student_count} students`,
                  })}
                  emptyMessage="No attendance groups are available in this snapshot yet."
                />

                <ToggleList
                  title="Link lecturers"
                  items={workspace.lecturers}
                  selectedIds={sessionForm.lecturer_ids}
                  onToggle={(id) => toggleSessionValue("lecturer_ids", id)}
                  renderLabel={(item) => ({
                    title: item.name,
                    detail: item.email || "No email",
                  })}
                  emptyMessage="No lecturers are available in this snapshot yet."
                />

                <div className="studio-actions">
                  <button type="submit" className="primary-btn" disabled={working}>
                    {editingSharedSessionId ? "Save Shared Session Repair" : "Save Shared Session"}
                  </button>
                  {editingSharedSessionId && (
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={handleCancelSessionEdit}
                    >
                      Cancel Repair
                    </button>
                  )}
                </div>
              </form>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

export default SetupStudio;
