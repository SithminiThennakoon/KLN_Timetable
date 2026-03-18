import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { timetableStudioService } from "../services/timetableStudioService";
import SearchableMultiSelect from "../components/SearchableMultiSelect";

const activeImportRunStorageKey = "kln_active_import_run_id";

const steps = [
  { key: "structure", label: "Structure" },
  { key: "lecturers", label: "Lecturers" },
  { key: "rooms", label: "Rooms" },
  { key: "cohorts", label: "Student Cohorts" },
  { key: "modules", label: "Modules" },
  { key: "sessions", label: "Sessions" },
  { key: "review", label: "Review & Generate" },
];

const emptyDraft = {
  degrees: [],
  paths: [],
  lecturers: [],
  rooms: [],
  cohorts: [],
  modules: [],
  sessions: [],
};

const stepGuidance = {
  structure:
    "Start by defining each degree and any allowed year-specific paths. Direct-entry degrees can stay without paths and will use a general cohort.",
  lecturers:
    "Enter the lecturers who may be assigned to weekly sessions. These names are also used in lecturer timetable views.",
  rooms:
    "Add every teaching room that the solver may use, including lecture halls, labs, capacities, locations, and any year restrictions.",
  cohorts:
    "Base cohorts are created from degree, year, and path structure. Add student counts there first, then create override groups only for electives or special attendance patterns.",
  modules:
    "Enter the semester or full-year modules that sessions belong to. Sessions are scheduled later, but every session must point to a module first.",
  sessions:
    "Create the actual weekly teaching activities here. Link each session to its lecturers and attending cohorts, then use advanced options only when delivery needs extra rules.",
  review:
    "Use this review step before generation. Blocking issues must be fixed first. Warnings are allowed, but they usually indicate incomplete staffing or unusual delivery choices.",
};

function makeId(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function makeBaseCohortName(degree, year, path) {
  if (!degree) {
    return "";
  }
  const base = `${degree.code || degree.name || "Degree"} Y${year}`;
  return path ? `${base} ${path.code || path.name}` : `${base} General`;
}

function syncBaseCohorts(draft) {
  const currentYear = new Date().getFullYear();
  const expected = [];

  draft.degrees.forEach((degree) => {
    for (let year = 1; year <= Number(degree.duration_years || 0); year += 1) {
      const matchingPaths = draft.paths.filter(
        (path) => path.degreeId === degree.id && Number(path.year) === year
      );

      if (matchingPaths.length === 0) {
        expected.push({
          degreeId: degree.id,
          year,
          pathId: "",
        });
        continue;
      }

      matchingPaths.forEach((path) => {
        expected.push({
          degreeId: degree.id,
          year,
          pathId: path.id,
        });
      });
    }
  });

  const expectedKeySet = new Set(
    expected.map((item) => `${item.degreeId}::${item.year}::${item.pathId || "general"}`)
  );

  const existingBaseByKey = new Map(
    draft.cohorts
      .filter((cohort) => cohort.kind === "base")
      .map((cohort) => [
        `${cohort.degreeId}::${cohort.year}::${cohort.pathId || "general"}`,
        cohort,
      ])
  );

  const baseCohorts = expected.map((item) => {
    const degree = draft.degrees.find((entry) => entry.id === item.degreeId);
    const path = draft.paths.find((entry) => entry.id === item.pathId);
    const key = `${item.degreeId}::${item.year}::${item.pathId || "general"}`;
    const existing = existingBaseByKey.get(key);

    return {
      id: existing?.id || makeId("cohort"),
      kind: "base",
      degreeId: item.degreeId,
      year: item.year,
      pathId: item.pathId || "",
      name: existing?.name || makeBaseCohortName(degree, item.year, path),
      size: existing?.size ?? "",
      cohort_year: existing?.cohort_year ?? currentYear,
    };
  });

  const overrideCohorts = draft.cohorts.filter((cohort) => {
    if (cohort.kind !== "base") {
      return true;
    }
    const key = `${cohort.degreeId}::${cohort.year}::${cohort.pathId || "general"}`;
    return !expectedKeySet.has(key);
  });

  return {
    ...draft,
    cohorts: [...baseCohorts, ...overrideCohorts],
  };
}

function toSummary(draft) {
  return {
    degrees: draft.degrees.length,
    paths: draft.paths.length,
    lecturers: draft.lecturers.length,
    rooms: draft.rooms.length,
    student_groups: draft.cohorts.length,
    modules: draft.modules.length,
    sessions: draft.sessions.length,
  };
}

function academicYearStart(academicYear) {
  const match = String(academicYear || "").match(/^(\d{4})/);
  return match ? Number(match[1]) : new Date().getFullYear();
}

function normalizeDataset(dataset) {
  const degreeIdByKey = new Map();
  const pathIdByKey = new Map();
  const lecturerIdByKey = new Map();
  const roomIdByKey = new Map();
  const cohortIdByKey = new Map();
  const moduleIdByKey = new Map();

  const degrees = (dataset.degrees || []).map((degree) => {
    const id = makeId("degree");
    degreeIdByKey.set(degree.client_key, id);
    return {
      id,
      code: degree.code || "",
      name: degree.name || "",
      duration_years: degree.duration_years || 3,
      intake_label: degree.intake_label || "",
    };
  });

  const paths = (dataset.paths || []).map((path) => {
    const id = makeId("path");
    pathIdByKey.set(path.client_key, id);
    return {
      id,
      degreeId: degreeIdByKey.get(path.degree_client_key) || "",
      year: path.year || 1,
      code: path.code || "",
      name: path.name || "",
    };
  });

  const lecturers = (dataset.lecturers || []).map((lecturer) => {
    const id = makeId("lecturer");
    lecturerIdByKey.set(lecturer.client_key, id);
    return {
      id,
      name: lecturer.name || "",
      email: lecturer.email || "",
    };
  });

  const rooms = (dataset.rooms || []).map((room) => {
    const id = makeId("room");
    roomIdByKey.set(room.client_key, id);
    return {
      id,
      name: room.name || "",
      capacity: room.capacity || "",
      room_type: room.room_type || "lecture",
      lab_type: room.lab_type || "",
      location: room.location || "",
      year_restriction: room.year_restriction || "",
    };
  });

  const groupedStudentGroups = new Map();
  (dataset.student_groups || []).forEach((group) => {
    const key = [
      degreeIdByKey.get(group.degree_client_key) || "",
      group.year || 1,
      pathIdByKey.get(group.path_client_key) || "",
    ].join("::");
    const next = groupedStudentGroups.get(key) || [];
    next.push(group);
    groupedStudentGroups.set(key, next);
  });

  const cohorts = [];
  groupedStudentGroups.forEach((groups, compositeKey) => {
    groups.forEach((group, index) => {
      const id = makeId("cohort");
      cohortIdByKey.set(group.client_key, id);
      const [degreeId, year, pathId] = compositeKey.split("::");
      cohorts.push({
        id,
        kind: index === 0 ? "base" : "override",
        degreeId,
        year: Number(year) || 1,
        pathId: pathId || "",
        name: group.name || "",
        size: group.size || "",
        cohort_year: group.cohort_year || new Date().getFullYear(),
      });
    });
  });

  const modules = (dataset.modules || []).map((module) => {
    const id = makeId("module");
    moduleIdByKey.set(module.client_key, id);
    return {
      id,
      code: module.code || "",
      name: module.name || "",
      subject_name: module.subject_name || "",
      year: module.year || 1,
      semester: module.semester || 1,
      is_full_year: Boolean(module.is_full_year),
    };
  });

  const sessions = (dataset.sessions || []).map((session) => ({
    id: makeId("session"),
    moduleId: moduleIdByKey.get(session.module_client_key) || "",
    linkedModuleIds: (session.linked_module_client_keys || [])
      .map((key) => moduleIdByKey.get(key))
      .filter(Boolean),
    name: session.name || "",
    session_type: session.session_type || "lecture",
    duration_minutes: session.duration_minutes || 60,
    occurrences_per_week: session.occurrences_per_week || 1,
    required_room_type: session.required_room_type || "",
    required_lab_type: session.required_lab_type || "",
    specific_room_id: roomIdByKey.get(session.specific_room_client_key) || "",
    max_students_per_group: session.max_students_per_group || "",
    allow_parallel_rooms: Boolean(session.allow_parallel_rooms),
    notes: session.notes || "",
    lecturerIds: (session.lecturer_client_keys || [])
      .map((key) => lecturerIdByKey.get(key))
      .filter(Boolean),
    cohortIds: (session.student_group_client_keys || [])
      .map((key) => cohortIdByKey.get(key))
      .filter(Boolean),
  }));

  return syncBaseCohorts({
    degrees,
    paths,
    lecturers,
    rooms,
    cohorts,
    modules,
    sessions,
  });
}

function normalizeImportWorkspace(workspace) {
  const degreeIdBySource = new Map();
  const pathIdBySource = new Map();
  const lecturerIdBySource = new Map();
  const roomIdBySource = new Map();
  const cohortIdBySource = new Map();
  const moduleIdBySource = new Map();
  const groupedAttendanceGroups = new Map();
  const defaultCohortYear = academicYearStart(workspace.selected_academic_year);

  const degrees = (workspace.programmes || []).map((programme) => {
    const id = makeId("degree");
    degreeIdBySource.set(programme.id, id);
    return {
      id,
      sourceProgrammeId: programme.id,
      code: programme.code || "",
      name: programme.name || "",
      duration_years: programme.duration_years || 3,
      intake_label: programme.intake_label || `${programme.code || "Programme"} Intake`,
    };
  });

  const paths = (workspace.programme_paths || []).map((path) => {
    const id = makeId("path");
    pathIdBySource.set(path.id, id);
    return {
      id,
      sourcePathId: path.id,
      degreeId: degreeIdBySource.get(path.programme_id) || "",
      year: path.study_year || 1,
      code: path.code || "",
      name: path.name || "",
      is_common: Boolean(path.is_common),
    };
  });

  const lecturers = (workspace.lecturers || []).map((lecturer) => {
    const id = makeId("lecturer");
    lecturerIdBySource.set(lecturer.id, id);
    return {
      id,
      snapshotId: lecturer.id,
      name: lecturer.name || "",
      email: lecturer.email || "",
      notes: lecturer.notes || "",
    };
  });

  const rooms = (workspace.rooms || []).map((room) => {
    const id = makeId("room");
    roomIdBySource.set(room.id, id);
    return {
      id,
      snapshotId: room.id,
      name: room.name || "",
      capacity: room.capacity || "",
      room_type: room.room_type || "lecture",
      lab_type: room.lab_type || "",
      location: room.location || "",
      year_restriction: room.year_restriction || "",
      notes: room.notes || "",
    };
  });

  (workspace.attendance_groups || []).forEach((group) => {
    const key = [
      degreeIdBySource.get(group.programme_id) || "",
      group.study_year || 1,
      pathIdBySource.get(group.programme_path_id) || "",
    ].join("::");
    const next = groupedAttendanceGroups.get(key) || [];
    next.push(group);
    groupedAttendanceGroups.set(key, next);
  });

  const cohorts = [];
  groupedAttendanceGroups.forEach((groups, compositeKey) => {
    groups.forEach((group, index) => {
      const id = makeId("cohort");
      cohortIdBySource.set(group.id, id);
      const [degreeId, year, pathId] = compositeKey.split("::");
      cohorts.push({
        id,
        sourceAttendanceGroupId: group.id,
        kind: index === 0 ? "base" : "override",
        degreeId,
        year: Number(year) || 1,
        pathId: pathId || "",
        name: group.label || "",
        size: group.student_count || "",
        cohort_year: defaultCohortYear,
      });
    });
  });

  const modules = (workspace.curriculum_modules || []).map((module) => {
    const id = makeId("module");
    moduleIdBySource.set(module.id, id);
    return {
      id,
      sourceModuleId: module.id,
      code: module.code || "",
      name: module.name || "",
      subject_name: module.subject_name || "",
      year: module.nominal_year || 1,
      semester: module.semester_bucket || 1,
      is_full_year: Boolean(module.is_full_year),
      defaultCohortIds: (module.attendance_group_ids || [])
        .map((attendanceGroupId) => cohortIdBySource.get(attendanceGroupId))
        .filter(Boolean),
    };
  });

  const sessions = (workspace.shared_sessions || []).map((session) => {
    const moduleIds = (session.curriculum_module_ids || [])
      .map((id) => moduleIdBySource.get(id))
      .filter(Boolean);
    return {
      id: makeId("session"),
      sourceSharedSessionId: session.id,
      moduleId: moduleIds[0] || "",
      linkedModuleIds: moduleIds.slice(1),
      name: session.name || "",
      session_type: session.session_type || "lecture",
      duration_minutes: session.duration_minutes || 60,
      occurrences_per_week: session.occurrences_per_week || 1,
      required_room_type: session.required_room_type || "",
      required_lab_type: session.required_lab_type || "",
      specific_room_id: roomIdBySource.get(session.specific_room_id) || "",
      max_students_per_group: session.max_students_per_group || "",
      allow_parallel_rooms: Boolean(session.allow_parallel_rooms),
      notes: session.notes || "",
      lecturerIds: (session.lecturer_ids || [])
        .map((id) => lecturerIdBySource.get(id))
        .filter(Boolean),
      cohortIds: (session.attendance_group_ids || [])
        .map((id) => cohortIdBySource.get(id))
        .filter(Boolean),
    };
  });

  return {
    degrees,
    paths,
    lecturers,
    rooms,
    cohorts,
    modules,
    sessions,
  };
}

function buildPayload(draft) {
  const degreeKeyById = new Map();
  const pathKeyById = new Map();
  const lecturerKeyById = new Map();
  const roomKeyById = new Map();
  const cohortKeyById = new Map();
  const moduleKeyById = new Map();

  const degrees = draft.degrees.map((degree) => {
    const clientKey = `degree_${degree.id}`;
    degreeKeyById.set(degree.id, clientKey);
    return {
      client_key: clientKey,
      code: degree.code.trim(),
      name: degree.name.trim(),
      duration_years: Number(degree.duration_years),
      intake_label: degree.intake_label.trim(),
    };
  });

  const paths = draft.paths.map((path) => {
    const clientKey = `path_${path.id}`;
    pathKeyById.set(path.id, clientKey);
    return {
      client_key: clientKey,
      degree_client_key: degreeKeyById.get(path.degreeId),
      year: Number(path.year),
      code: path.code.trim(),
      name: path.name.trim(),
    };
  });

  const lecturers = draft.lecturers.map((lecturer) => {
    const clientKey = `lecturer_${lecturer.id}`;
    lecturerKeyById.set(lecturer.id, clientKey);
    return {
      client_key: clientKey,
      name: lecturer.name.trim(),
      email: lecturer.email.trim() || null,
    };
  });

  const rooms = draft.rooms.map((room) => {
    const clientKey = `room_${room.id}`;
    roomKeyById.set(room.id, clientKey);
    return {
      client_key: clientKey,
      name: room.name.trim(),
      capacity: Number(room.capacity),
      room_type: room.room_type || "lecture",
      lab_type: room.lab_type.trim() || null,
      location: room.location.trim(),
      year_restriction: room.year_restriction ? Number(room.year_restriction) : null,
    };
  });

  const student_groups = draft.cohorts.map((cohort) => {
    const clientKey = `group_${cohort.id}`;
    cohortKeyById.set(cohort.id, clientKey);
    return {
      client_key: clientKey,
      degree_client_key: degreeKeyById.get(cohort.degreeId),
      path_client_key: cohort.pathId ? pathKeyById.get(cohort.pathId) : null,
      year: Number(cohort.year),
      name: cohort.name.trim(),
      size: Number(cohort.size),
      cohort_year: cohort.cohort_year ? Number(cohort.cohort_year) : null,
    };
  });

  const modules = draft.modules.map((module) => {
    const clientKey = `module_${module.id}`;
    moduleKeyById.set(module.id, clientKey);
    return {
      client_key: clientKey,
      code: module.code.trim(),
      name: module.name.trim(),
      subject_name: module.subject_name.trim(),
      year: Number(module.year),
      semester: Number(module.semester),
      is_full_year: Boolean(module.is_full_year),
    };
  });

  const sessions = draft.sessions.map((session) => ({
    client_key: `session_${session.id}`,
    module_client_key: moduleKeyById.get(session.moduleId),
    linked_module_client_keys: (session.linkedModuleIds || [])
      .filter((id) => id && id !== session.moduleId)
      .map((id) => moduleKeyById.get(id))
      .filter(Boolean),
    name: session.name.trim(),
    session_type: session.session_type.trim(),
    duration_minutes: Number(session.duration_minutes),
    occurrences_per_week: Number(session.occurrences_per_week),
    required_room_type: session.required_room_type.trim() || null,
    required_lab_type: session.required_lab_type.trim() || null,
    specific_room_client_key: session.specific_room_id
      ? roomKeyById.get(session.specific_room_id)
      : null,
    max_students_per_group: session.max_students_per_group
      ? Number(session.max_students_per_group)
      : null,
    allow_parallel_rooms: Boolean(session.allow_parallel_rooms),
    notes: session.notes.trim() || null,
    lecturer_client_keys: session.lecturerIds
      .map((id) => lecturerKeyById.get(id))
      .filter(Boolean),
    student_group_client_keys: session.cohortIds
      .map((id) => cohortKeyById.get(id))
      .filter(Boolean),
  }));

  return {
    degrees,
    paths,
    lecturers,
    rooms,
    student_groups,
    modules,
    sessions,
  };
}

function validateDraft(draft, { snapshotMode = false } = {}) {
  const blocking = [];
  const warnings = [];

  if (draft.degrees.length === 0) {
    blocking.push("Add at least one degree before continuing.");
  }

  draft.degrees.forEach((degree, index) => {
    if (!degree.code.trim() || !degree.name.trim() || !degree.intake_label.trim()) {
      blocking.push(`Degree ${index + 1} is missing code, name, or intake label.`);
    }
    if (!Number.isInteger(Number(degree.duration_years)) || Number(degree.duration_years) < 1) {
      blocking.push(`Degree ${index + 1} needs a valid duration in years.`);
    }
  });

  draft.paths.forEach((path, index) => {
    if (!path.degreeId || !path.code.trim() || !path.name.trim()) {
      blocking.push(`Path ${index + 1} is missing degree, code, or name.`);
    }
  });

  if (draft.lecturers.length === 0) {
    warnings.push("No lecturers entered yet.");
  }

  if (draft.rooms.length === 0) {
    blocking.push("Add at least one room before generating timetables.");
  }

  draft.rooms.forEach((room, index) => {
    if (!room.name.trim() || !room.location.trim()) {
      blocking.push(`Room ${index + 1} is missing name or location.`);
    }
    if (!Number(room.capacity) || Number(room.capacity) <= 0) {
      blocking.push(`Room ${index + 1} needs a positive capacity.`);
    }
  });

  const baseCohorts = draft.cohorts.filter((cohort) => cohort.kind === "base");
  if (baseCohorts.length === 0) {
    blocking.push("Define structure first so base student cohorts can be created.");
  }

  baseCohorts.forEach((cohort, index) => {
    if (!cohort.name.trim()) {
      blocking.push(`Base cohort ${index + 1} is missing a name.`);
    }
    if (!snapshotMode && (!Number(cohort.size) || Number(cohort.size) <= 0)) {
      blocking.push(`Base cohort ${index + 1} needs a positive student count.`);
    }
  });

  draft.cohorts
    .filter((cohort) => cohort.kind === "override")
    .forEach((cohort, index) => {
      if (!cohort.degreeId || !cohort.name.trim()) {
        blocking.push(`Override group ${index + 1} is missing degree or name.`);
      }
      if (!snapshotMode && (!Number(cohort.size) || Number(cohort.size) <= 0)) {
        blocking.push(`Override group ${index + 1} needs a positive student count.`);
      }
    });

  draft.modules.forEach((module, index) => {
    if (!module.code.trim() || !module.name.trim() || !module.subject_name.trim()) {
      blocking.push(`Module ${index + 1} is missing code, name, or subject.`);
    }
  });

  if (draft.modules.length === 0) {
    blocking.push("Add at least one module.");
  }

  draft.sessions.forEach((session, index) => {
    if (!session.moduleId || !session.name.trim() || !session.session_type.trim()) {
      blocking.push(`Session ${index + 1} is missing module, name, or type.`);
    }
    if (!Number(session.duration_minutes) || Number(session.duration_minutes) % 30 !== 0) {
      blocking.push(`Session ${index + 1} duration must be a positive multiple of 30.`);
    }
    if (!Number(session.occurrences_per_week) || Number(session.occurrences_per_week) <= 0) {
      blocking.push(`Session ${index + 1} needs a valid weekly occurrence count.`);
    }
    if (session.lecturerIds.length === 0) {
      blocking.push(
        `Session "${session.name || `#${index + 1}`}" must have at least one lecturer assigned.`
      );
    }
    if (session.cohortIds.length === 0) {
      if (snapshotMode) {
        warnings.push(`Session "${session.name || `#${index + 1}`}" has no attendance group assigned yet.`);
      } else {
        blocking.push(`Session ${index + 1} must target at least one cohort.`);
      }
    }
    if (session.allow_parallel_rooms && session.lecturerIds.length < 2) {
      warnings.push(
        `Session "${session.name || `#${index + 1}`}" uses parallel rooms but has fewer than two lecturers assigned.`
      );
    }
  });

  if (draft.sessions.length === 0) {
    blocking.push("Add at least one session.");
  }

  return {
    blocking: [...new Set(blocking)],
    warnings: [...new Set(warnings)],
  };
}

function StepBadge({ active, complete, blocked, label, onClick }) {
  let className = "wizard-step";
  if (active) className += " active";
  else if (complete) className += " complete";
  else if (blocked) className += " blocked";

  return (
    <button
      type="button"
      className={className}
      onClick={onClick}
      aria-current={active ? "step" : undefined}
      title={blocked ? "Complete earlier steps first" : "Jump to this step"}
    >
      {label}
    </button>
  );
}

function StepIntro({ stepKey }) {
  return (
    <p className="helper-copy step-intro step-inline-intro">{stepGuidance[stepKey]}</p>
  );
}

function currentStepFeedback(stepKey, validation) {
  const matchesStep = (message) => {
    const lower = message.toLowerCase();

    if (stepKey === "structure") {
      return lower.includes("degree") || lower.includes("path");
    }
    if (stepKey === "lecturers") {
      return lower.includes("lecturer");
    }
    if (stepKey === "rooms") {
      return lower.includes("room");
    }
    if (stepKey === "cohorts") {
      return lower.includes("cohort") || lower.includes("student count") || lower.includes("structure first");
    }
    if (stepKey === "modules") {
      return lower.includes("module");
    }
    if (stepKey === "sessions") {
      return lower.includes("session");
    }
    return true;
  };

  return {
    blocking: validation.blocking.filter(matchesStep),
    warnings: validation.warnings.filter(matchesStep),
  };
}

function summarizeValidationWarnings(warnings, { snapshotMode = false } = {}) {
  if (!snapshotMode) {
    return warnings;
  }

  const attendanceWarnings = warnings.filter((warning) =>
    /^Session ".*" has no attendance group assigned yet\.$/.test(warning)
  );
  const parallelWarnings = warnings.filter((warning) =>
    /^Session ".*" uses parallel rooms but has fewer than two lecturers assigned\.$/.test(warning)
  );
  const summarized = [];

  if (attendanceWarnings.length > 0) {
    summarized.push(
      `${attendanceWarnings.length} session${attendanceWarnings.length === 1 ? "" : "s"} still need attendance-group assignments.`
    );
  }
  if (parallelWarnings.length > 0) {
    summarized.push(
      `${parallelWarnings.length} parallel-room session${parallelWarnings.length === 1 ? "" : "s"} still need at least two lecturers.`
    );
  }

  const covered = new Set([
    ...attendanceWarnings,
    ...parallelWarnings,
  ]);
  return [...summarized, ...warnings.filter((warning) => !covered.has(warning))];
}

function StepChecks({ stepKey, validation, snapshotMode = false }) {
  if (stepKey === "review") {
    return null;
  }

  const feedback = currentStepFeedback(stepKey, validation);
  const warningMessages = summarizeValidationWarnings(feedback.warnings, {
    snapshotMode,
  });
  if (feedback.blocking.length === 0 && feedback.warnings.length === 0) {
    return null;
  }

  const visibleWarnings = warningMessages.slice(0, 5);

  return (
    <section className="studio-card">
      <h2>Step Check</h2>
      {feedback.blocking.length > 0 && (
        <div className="error-banner">
          <strong>
            {feedback.blocking.length} required issue{feedback.blocking.length === 1 ? "" : "s"} on this step
          </strong>
          <ul>
            {feedback.blocking.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
      {warningMessages.length > 0 && (
        <div className="schema-notes">
          <h3>
            {warningMessages.length} warning{warningMessages.length === 1 ? "" : "s"} to review
          </h3>
          <ul>
            {visibleWarnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
          {warningMessages.length > visibleWarnings.length && (
            <p className="helper-copy">
              {warningMessages.length - visibleWarnings.length} more warning
              {warningMessages.length - visibleWarnings.length === 1 ? "" : "s"} are hidden for now.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function findRecordIssue(messages, pattern) {
  return messages.find((message) => pattern.test(message)) || "";
}

function invalidClass(message) {
  return message ? "field-invalid" : "";
}

function buildImportRulePayload(bucketActions) {
  return Object.entries(bucketActions)
    .filter(([, action]) => action)
    .map(([compositeKey, action]) => {
      const [bucketType, bucketKey] = compositeKey.split("::", 2);
      return {
        bucket_type: bucketType,
        bucket_key: bucketKey,
        action,
      };
    });
}

function SetupStudio() {
  const navigate = useNavigate();
  const INITIAL_VISIBLE_RECORDS = 4;
  const currentYear = new Date().getFullYear();
  const [draft, setDraft] = useState(emptyDraft);
  const [summary, setSummary] = useState(toSummary(emptyDraft));
  const [activeStep, setActiveStep] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showDegreeModal, setShowDegreeModal] = useState(false);
  const [showPathModal, setShowPathModal] = useState(false);
  const [showLecturerModal, setShowLecturerModal] = useState(false);
  const [showRoomModal, setShowRoomModal] = useState(false);
  const [showModuleModal, setShowModuleModal] = useState(false);
  const [visibleDegreeCount, setVisibleDegreeCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [visiblePathCount, setVisiblePathCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [visibleLecturerCount, setVisibleLecturerCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [visibleRoomCount, setVisibleRoomCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [visibleModuleCount, setVisibleModuleCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [tempDegree, setTempDegree] = useState({ code: "", name: "", duration_years: 3, intake_label: "" });
  const [tempPath, setTempPath] = useState({ degreeId: "", year: 1, code: "", name: "" });
  const [tempLecturer, setTempLecturer] = useState({ name: "", email: "" });
  const [tempRoom, setTempRoom] = useState({
    name: "",
    capacity: "",
    room_type: "lecture",
    lab_type: "",
    location: "",
    year_restriction: "",
  });
  const [tempModule, setTempModule] = useState({
    code: "",
    name: "",
    subject_name: "",
    year: 1,
    semester: 1,
    is_full_year: false,
  });
  const [moduleSearchQuery, setModuleSearchQuery] = useState("");
  const [visibleBaseCohortCount, setVisibleBaseCohortCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [visibleOverrideCohortCount, setVisibleOverrideCohortCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [cohortYearFilter, setCohortYearFilter] = useState("all");
  const [showOverrideCohortModal, setShowOverrideCohortModal] = useState(false);
  const [tempOverrideCohort, setTempOverrideCohort] = useState({
    degreeId: "",
    year: 1,
    pathId: "",
    name: "",
    size: "",
    cohort_year: currentYear,
  });
  const [sessionYearFilter, setSessionYearFilter] = useState("all");
  const [visibleSessionCount, setVisibleSessionCount] = useState(INITIAL_VISIBLE_RECORDS);
  const [showSessionModal, setShowSessionModal] = useState(false);
  const [sessionCohortYearFilter, setSessionCohortYearFilter] = useState(currentYear);
  const [tempSession, setTempSession] = useState({
    moduleId: "",
    linkedModuleIds: [],
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
    lecturerIds: [],
    cohortIds: [],
  });
  const [importAnalysis, setImportAnalysis] = useState(null);
  const [importProjection, setImportProjection] = useState(null);
  const [materializedImport, setMaterializedImport] = useState(null);
  const [importAction, setImportAction] = useState("");
  const [selectedImportFile, setSelectedImportFile] = useState(null);
  const [useBundledImportSample, setUseBundledImportSample] = useState(false);
  const [importRuleActions, setImportRuleActions] = useState({});
  const [importLoading, setImportLoading] = useState(false);
  const activeImportRunId = materializedImport?.import_run_id || null;
  const snapshotDerivedEditingDisabled = Boolean(activeImportRunId);
  const showSetupWizard = Boolean(activeImportRunId);

  const filteredModules = useMemo(() => {
    if (!moduleSearchQuery.trim()) {
      return draft.modules;
    }
    const query = moduleSearchQuery.toLowerCase();
    return draft.modules.filter(
      (m) =>
        m.name.toLowerCase().includes(query) ||
        m.code.toLowerCase().includes(query) ||
        m.subject_name.toLowerCase().includes(query)
    );
  }, [draft.modules, moduleSearchQuery]);

  const filteredBaseCohorts = useMemo(() => {
    const baseCohorts = draft.cohorts.filter((c) => c.kind === "base");
    if (cohortYearFilter === "all") {
      return baseCohorts;
    }
    return baseCohorts.filter((c) => String(c.year) === cohortYearFilter);
  }, [draft.cohorts, cohortYearFilter]);

  const filteredOverrideCohorts = useMemo(() => {
    const overrideCohorts = draft.cohorts.filter((c) => c.kind === "override");
    if (cohortYearFilter === "all") {
      return overrideCohorts;
    }
    return overrideCohorts.filter((c) => String(c.year) === cohortYearFilter);
  }, [draft.cohorts, cohortYearFilter]);

  const filteredSessions = useMemo(() => {
    const moduleYear = (m) => {
      const mod = draft.modules.find((mod) => mod.id === m.moduleId);
      return mod ? mod.year : null;
    };
    if (sessionYearFilter === "all") {
      return draft.sessions;
    }
    return draft.sessions.filter((s) => String(moduleYear(s)) === sessionYearFilter);
  }, [draft.sessions, draft.modules, sessionYearFilter]);

  const importBuckets = useMemo(() => importAnalysis?.buckets || [], [importAnalysis]);

  const filteredCohortsByYear = useMemo(() => {
    return draft.cohorts.filter((c) => String(c.cohort_year) === String(sessionCohortYearFilter));
  }, [draft.cohorts, sessionCohortYearFilter]);

  const validation = useMemo(
    () => validateDraft(draft, { snapshotMode: Boolean(activeImportRunId) }),
    [draft, activeImportRunId]
  );

  const blockedSteps = useMemo(() => {
    const hasStructure = draft.degrees.length > 0;
    const hasLecturers = draft.lecturers.length > 0;
    const hasRooms = draft.rooms.length > 0;
    const hasCohorts = draft.cohorts.some((cohort) => cohort.kind === "base");
    const hasModules = draft.modules.length > 0;
    const hasSessions = draft.sessions.length > 0;

    return {
      structure: false,
      lecturers: !hasStructure,
      rooms: !hasStructure,
      cohorts: !hasStructure,
      modules: !hasCohorts,
      sessions: !hasModules || !hasRooms,
      review: false,
    };
  }, [draft]);

  const loadImportWorkspace = async (importRunId, nextStatus = "") => {
    setLoading(true);
    setError("");
    try {
      if (typeof window !== "undefined") {
        window.localStorage.setItem(
          activeImportRunStorageKey,
          String(importRunId)
        );
      }
      const workspace = await timetableStudioService.getImportWorkspace(importRunId);
      const normalized = normalizeImportWorkspace(workspace);
      setDraft(normalized);
      setSummary(toSummary(normalized));
      setVisibleDegreeCount(INITIAL_VISIBLE_RECORDS);
      setVisiblePathCount(INITIAL_VISIBLE_RECORDS);
      setVisibleLecturerCount(INITIAL_VISIBLE_RECORDS);
      setVisibleBaseCohortCount(INITIAL_VISIBLE_RECORDS);
      setVisibleOverrideCohortCount(INITIAL_VISIBLE_RECORDS);
      setCohortYearFilter("all");
      setVisibleRoomCount(INITIAL_VISIBLE_RECORDS);
      setVisibleModuleCount(INITIAL_VISIBLE_RECORDS);
      setSessionYearFilter("all");
      setVisibleSessionCount(INITIAL_VISIBLE_RECORDS);
      setStatus(nextStatus);
      return normalized;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const buildSnapshotSharedSessionPayload = (session, sourceDraft = draft) => {
    const lecturerSourceIds = (session.lecturerIds || [])
      .map((id) => sourceDraft.lecturers.find((entry) => entry.id === id)?.snapshotId)
      .filter(Boolean);
    const roomSourceId = session.specific_room_id
      ? sourceDraft.rooms.find((entry) => entry.id === session.specific_room_id)?.snapshotId
      : null;
    const moduleSourceIds = [session.moduleId, ...(session.linkedModuleIds || [])]
      .map((id) => sourceDraft.modules.find((entry) => entry.id === id)?.sourceModuleId)
      .filter(Boolean);
    const attendanceGroupSourceIds = (session.cohortIds || [])
      .map((id) => sourceDraft.cohorts.find((entry) => entry.id === id)?.sourceAttendanceGroupId)
      .filter(Boolean);

    if (!moduleSourceIds.length) {
      throw new Error(
        "Imported shared sessions must point to modules loaded from the materialized import snapshot."
      );
    }
    return {
      client_key: `session_${session.id}`,
      name: session.name.trim(),
      session_type: session.session_type.trim(),
      duration_minutes: Number(session.duration_minutes),
      occurrences_per_week: Number(session.occurrences_per_week),
      required_room_type: session.required_room_type.trim() || null,
      required_lab_type: session.required_lab_type.trim() || null,
      specific_room_id: roomSourceId || null,
      max_students_per_group: session.max_students_per_group
        ? Number(session.max_students_per_group)
        : null,
      allow_parallel_rooms: Boolean(session.allow_parallel_rooms),
      notes: session.notes.trim() || null,
      lecturer_ids: lecturerSourceIds,
      curriculum_module_ids: moduleSourceIds,
      attendance_group_ids: attendanceGroupSourceIds,
    };
  };

  const buildSnapshotLecturerPayload = (record) => ({
    client_key: `lecturer_${record.id}`,
    name: record.name.trim(),
    email: record.email.trim() || null,
    notes: record.notes?.trim() || null,
  });

  const buildSnapshotRoomPayload = (record) => ({
    client_key: `room_${record.id}`,
    name: record.name.trim(),
    capacity: Number(record.capacity),
    room_type: record.room_type || "lecture",
    lab_type: record.lab_type?.trim() || null,
    location: record.location.trim(),
    year_restriction: record.year_restriction ? Number(record.year_restriction) : null,
    notes: record.notes?.trim() || null,
  });

  const persistSnapshotBatch = async (collection, records, successMessage) => {
    if (!activeImportRunId || records.length === 0) {
      return false;
    }

    setSaving(true);
    setError("");
    setStatus("");

    try {
      if (collection === "lecturers") {
        await timetableStudioService.createSnapshotLecturersBatch(
          activeImportRunId,
          records.map(buildSnapshotLecturerPayload)
        );
      } else if (collection === "rooms") {
        await timetableStudioService.createSnapshotRoomsBatch(
          activeImportRunId,
          records.map(buildSnapshotRoomPayload)
        );
      } else if (collection === "sessions") {
        await timetableStudioService.createSnapshotSharedSessionsBatch(
          activeImportRunId,
          records.map((record) => buildSnapshotSharedSessionPayload(record))
        );
      }
      await loadImportWorkspace(activeImportRunId, successMessage);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const persistSnapshotRecordUpdate = async (collection, record) => {
    if (!activeImportRunId) {
      return;
    }

    try {
      if (collection === "lecturers" && record.snapshotId) {
        await timetableStudioService.updateSnapshotLecturer(
          activeImportRunId,
          record.snapshotId,
          {
            client_key: `lecturer_${record.id}`,
            name: record.name.trim(),
            email: record.email.trim() || null,
            notes: record.notes?.trim() || null,
          }
        );
      } else if (collection === "rooms" && record.snapshotId) {
        await timetableStudioService.updateSnapshotRoom(activeImportRunId, record.snapshotId, {
          client_key: `room_${record.id}`,
          name: record.name.trim(),
          capacity: Number(record.capacity),
          room_type: record.room_type || "lecture",
          lab_type: record.lab_type?.trim() || null,
          location: record.location.trim(),
          year_restriction: record.year_restriction ? Number(record.year_restriction) : null,
          notes: record.notes?.trim() || null,
        });
      } else if (collection === "sessions" && record.sourceSharedSessionId) {
        await timetableStudioService.updateSnapshotSharedSession(
          activeImportRunId,
          record.sourceSharedSessionId,
          buildSnapshotSharedSessionPayload(record)
        );
      } else {
        return;
      }
      setStatus(`Saved ${collection.slice(0, -1)} changes to import snapshot #${activeImportRunId}.`);
    } catch (err) {
      await loadImportWorkspace(activeImportRunId);
      setError(err.message);
    }
  };

  const assignDefaultCohortsToSnapshotSessions = async (sourceDraft = draft) => {
    if (!activeImportRunId) {
      return 0;
    }

    const sessionsNeedingDefaults = sourceDraft.sessions.filter((session) => {
      if (!session.sourceSharedSessionId || (session.cohortIds || []).length > 0) {
        return false;
      }
      const module = sourceDraft.modules.find((entry) => entry.id === session.moduleId);
      return Boolean(module && (module.defaultCohortIds || []).length > 0);
    });

    if (sessionsNeedingDefaults.length === 0) {
      return 0;
    }

    for (const session of sessionsNeedingDefaults) {
      const module = sourceDraft.modules.find((entry) => entry.id === session.moduleId);
      if (!module || !module.defaultCohortIds?.length) {
        continue;
      }
      await timetableStudioService.updateSnapshotSharedSession(
        activeImportRunId,
        session.sourceSharedSessionId,
        buildSnapshotSharedSessionPayload(
          {
            ...session,
            cohortIds: module.defaultCohortIds,
          },
          sourceDraft
        )
      );
    }

    return sessionsNeedingDefaults.length;
  };

  const deleteSnapshotRecord = async (collection, record) => {
    if (!activeImportRunId) {
      return false;
    }

    try {
      if (collection === "lecturers" && record.snapshotId) {
        await timetableStudioService.deleteSnapshotLecturer(activeImportRunId, record.snapshotId);
      } else if (collection === "rooms" && record.snapshotId) {
        await timetableStudioService.deleteSnapshotRoom(activeImportRunId, record.snapshotId);
      } else if (collection === "sessions" && record.sourceSharedSessionId) {
        await timetableStudioService.deleteSnapshotSharedSession(
          activeImportRunId,
          record.sourceSharedSessionId
        );
      } else {
        return false;
      }
      setStatus(`Removed ${collection.slice(0, -1)} from import snapshot #${activeImportRunId}.`);
      return true;
    } catch (err) {
      await loadImportWorkspace(activeImportRunId);
      setError(err.message);
      return false;
    }
  };

  useEffect(() => {
    const restoreActiveImportWorkspace = async () => {
      const savedImportRunId =
        typeof window !== "undefined"
          ? window.localStorage.getItem(activeImportRunStorageKey)
          : null;

      if (!savedImportRunId) {
        setDraft(emptyDraft);
        setSummary(toSummary(emptyDraft));
        setLoading(false);
        return;
      }

      const importRunId = Number(savedImportRunId);
      if (!Number.isFinite(importRunId) || importRunId <= 0) {
        if (typeof window !== "undefined") {
          window.localStorage.removeItem(activeImportRunStorageKey);
        }
        setDraft(emptyDraft);
        setSummary(toSummary(emptyDraft));
        setLoading(false);
        return;
      }

      setMaterializedImport({ import_run_id: importRunId, counts: {} });
      await loadImportWorkspace(
        importRunId,
        `Restored snapshot #${importRunId}. Continue completing the missing teaching details.`
      );
    };

    restoreActiveImportWorkspace();
  }, []);

  const updateDraft = (updater) => {
    setDraft((current) => {
      const next = typeof updater === "function" ? updater(current) : updater;
      const synced = activeImportRunId ? next : syncBaseCohorts(next);
      setSummary(toSummary(synced));
      return synced;
    });
  };

  const goToStep = (index) => {
    if (blockedSteps[visibleSteps[index].key]) {
      return;
    }
    setActiveStep(index);
  };

  const nextStep = () => {
    const nextIndex = Math.min(activeStep + 1, visibleSteps.length - 1);
    if (!blockedSteps[visibleSteps[nextIndex].key]) {
      setActiveStep(nextIndex);
    }
  };

  const prevStep = () => {
    setActiveStep((current) => Math.max(current - 1, 0));
  };

  const handleOpenGenerate = () => {
    if (!activeImportRunId) {
      return;
    }
    if (validation.blocking.length > 0) {
      const reviewIndex = visibleSteps.findIndex((step) => step.key === "review");
      if (reviewIndex >= 0) {
        setActiveStep(reviewIndex);
      }
      setStatus("");
      setError(
        `Fix ${validation.blocking.length} blocking issue${
          validation.blocking.length === 1 ? "" : "s"
        } before generation. Review & Generate shows the full list.`
      );
      return;
    }
    navigate("/generate");
  };

  const persistAddedRecord = async (collection, record, successMessage) => {
    setSaving(true);
    setError("");
    setStatus("");

    try {
      if (activeImportRunId && ["lecturers", "rooms", "sessions"].includes(collection)) {
        await createSnapshotRecord(collection, record);
        await loadImportWorkspace(activeImportRunId, successMessage);
        return true;
      }

      setError("This action only makes sense after a CSV import has been materialized.");
      return false;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleAnalyzeEnrollmentImport = async () => {
    setImportAction("analyze");
    setImportLoading(true);
    setError("");
    setStatus("");
    try {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(activeImportRunStorageKey);
      }
      const response = await timetableStudioService.analyzeEnrollmentImport(selectedImportFile);
      setImportAnalysis(response);
      setImportProjection(null);
      setMaterializedImport(null);
      setImportRuleActions({});
      setStatus(
        selectedImportFile
          ? `Loaded ${selectedImportFile.name}. Review the flagged items before continuing.`
          : "Enrollment CSV analyzed. Review the flagged items before continuing."
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setImportAction("");
      setImportLoading(false);
    }
  };

  const handlePreviewEnrollmentImport = async () => {
    setImportAction("review");
    setImportLoading(true);
    setError("");
    setStatus("");
    try {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(activeImportRunStorageKey);
      }
      const rules = buildImportRulePayload(importRuleActions);
      const response = await timetableStudioService.previewEnrollmentImport(
        {
          rules,
        },
        selectedImportFile
      );
      setImportProjection(response);
      setMaterializedImport(null);
      setStatus("Import review is ready. Check the projected counts before using this import.");
    } catch (err) {
      setError(err.message);
    } finally {
      setImportAction("");
      setImportLoading(false);
    }
  };

  const handleLoadEnrollmentImport = async () => {
    setImportAction("materialize");
    setImportLoading(true);
    setSaving(true);
    setError("");
    setStatus("Using this import. This can take a while for the full sample CSV.");
    try {
      const rules = buildImportRulePayload(importRuleActions);
      const response = await timetableStudioService.materializeEnrollmentImport(
        {
          rules,
        },
        selectedImportFile
      );
      setMaterializedImport(response);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(
          activeImportRunStorageKey,
          String(response.import_run_id)
        );
      }
      await loadImportWorkspace(
        response.import_run_id,
        `Import loaded. Snapshot #${response.import_run_id} is ready for manual completion.`
      );
      setActiveStep(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setImportAction("");
      setImportLoading(false);
      setSaving(false);
    }
  };

  const runGuidedDemoSetup = async () => {
    setSelectedImportFile(null);
    setUseBundledImportSample(true);
    setImportAnalysis(null);
    setImportProjection(null);
    setMaterializedImport(null);
    setImportRuleActions({});
    setImportAction("demo");
    setImportLoading(true);
    setSaving(true);
    setError("");
    setStatus("Preparing the guided demo flow. This will load sample student data and fill the missing teaching details automatically.");
    try {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(activeImportRunStorageKey);
      }
      const analysis = await timetableStudioService.analyzeEnrollmentImport(null);
      setImportAnalysis(analysis);
      const projection = await timetableStudioService.previewEnrollmentImport({ rules: [] }, null);
      setImportProjection(projection);
      const response = await timetableStudioService.materializeEnrollmentImport(
        { rules: [] },
        null
      );
      setMaterializedImport(response);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(activeImportRunStorageKey, String(response.import_run_id));
      }
      await loadImportWorkspace(response.import_run_id);
      const summary = await timetableStudioService.seedRealisticSnapshotMissingData(
        response.import_run_id
      );
      await loadImportWorkspace(
        response.import_run_id,
        `Demo setup ready. Snapshot #${response.import_run_id} now includes ${summary.lecturers_created} lecturers, ${summary.rooms_created} rooms, and ${summary.shared_sessions_created} teaching sessions.`
      );
      setActiveStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setImportAction("");
      setImportLoading(false);
      setSaving(false);
    }
  };

  const handleTempSessionModuleChange = (moduleId) => {
    const selectedModule = draft.modules.find((module) => module.id === moduleId);
    setTempSession((current) => ({
      ...current,
      moduleId,
      cohortIds:
        current.cohortIds.length > 0
          ? current.cohortIds
          : selectedModule?.defaultCohortIds || current.cohortIds,
      name:
        current.name.trim().length > 0
          ? current.name
          : selectedModule
            ? `${selectedModule.code} Session`
            : current.name,
    }));
  };

  const addRecord = (collection, record) => {
    updateDraft((current) => ({
      ...current,
      [collection]: [...current[collection], record],
    }));
  };

  const duplicateRecord = async (collection, id) => {
    const source = draft[collection].find((record) => record.id === id);
    if (!source) {
      return;
    }

    const duplicate = {
      ...source,
      id: makeId(collection.slice(0, -1) || "item"),
    };

    if (activeImportRunId && ["lecturers", "rooms", "sessions"].includes(collection)) {
      await persistAddedRecord(
        collection,
        duplicate,
        `${collection.slice(0, -1)} duplicated into import snapshot #${activeImportRunId}.`
      );
      return;
    }

    updateDraft((current) => {
      return {
        ...current,
        [collection]: [
          ...current[collection],
          duplicate,
        ],
      };
    });
  };

  const addStarterSessionsFromModules = async () => {
    const moduleIdsWithSessions = new Set(draft.sessions.map((session) => session.moduleId));
    const starterSessions = draft.modules
      .filter((module) => module.id && !moduleIdsWithSessions.has(module.id))
      .map((module) => ({
        id: makeId("session"),
        moduleId: module.id,
        name: `${module.name || module.code || "Module"} Session`,
        session_type: "lecture",
        duration_minutes: 60,
        occurrences_per_week: 1,
        linkedModuleIds: [],
        required_room_type: "lecture",
        required_lab_type: "",
        specific_room_id: "",
        max_students_per_group: "",
        allow_parallel_rooms: false,
        notes: "",
        lecturerIds: [],
        cohortIds: module.defaultCohortIds || [],
      }));

    if (starterSessions.length === 0) {
      return;
    }

    if (activeImportRunId) {
      await persistSnapshotBatch(
        "sessions",
        starterSessions,
        `Starter sessions saved into import snapshot #${activeImportRunId}.`
      );
      return;
    }

    updateDraft((current) => {
      const moduleIdsWithSessions = new Set(current.sessions.map((session) => session.moduleId));
      const starterSessions = current.modules
        .filter((module) => module.id && !moduleIdsWithSessions.has(module.id))
          .map((module) => ({
            id: makeId("session"),
            moduleId: module.id,
            name: `${module.name || module.code || "Module"} Session`,
          session_type: "lecture",
          duration_minutes: 60,
          occurrences_per_week: 1,
          linkedModuleIds: [],
          required_room_type: "lecture",
          required_lab_type: "",
          specific_room_id: "",
            max_students_per_group: "",
            allow_parallel_rooms: false,
            notes: "",
            lecturerIds: [],
            cohortIds: module.defaultCohortIds || [],
          }));

      if (starterSessions.length === 0) {
        return current;
      }

      return {
        ...current,
        sessions: [...current.sessions, ...starterSessions],
      };
    });
  };

  const addSessionPatternFromModules = async (patternKey) => {
    const patterns = {
      lectureTutorial: [
        {
          suffix: "Lecture",
          session_type: "lecture",
          duration_minutes: 120,
          occurrences_per_week: 1,
          required_room_type: "lecture",
        },
        {
          suffix: "Tutorial",
          session_type: "tutorial",
          duration_minutes: 60,
          occurrences_per_week: 1,
          required_room_type: "seminar",
        },
      ],
      scienceSet: [
        {
          suffix: "Lecture",
          session_type: "lecture",
          duration_minutes: 120,
          occurrences_per_week: 1,
          required_room_type: "lecture",
        },
        {
          suffix: "Tutorial",
          session_type: "tutorial",
          duration_minutes: 60,
          occurrences_per_week: 1,
          required_room_type: "seminar",
        },
        {
          suffix: "Lab",
          session_type: "lab",
          duration_minutes: 120,
          occurrences_per_week: 1,
          required_room_type: "lab",
        },
      ],
    };

    const selectedPattern = patterns[patternKey] || [];
    if (selectedPattern.length === 0) {
      return;
    }

    const moduleIdsWithSessions = new Set(draft.sessions.map((session) => session.moduleId));
    const generatedSessions = draft.modules
      .filter((module) => module.id && !moduleIdsWithSessions.has(module.id))
      .flatMap((module) =>
        selectedPattern.map((template) => ({
          id: makeId("session"),
          moduleId: module.id,
          name: `${module.name || module.code || "Module"} ${template.suffix}`,
          session_type: template.session_type,
          duration_minutes: template.duration_minutes,
          occurrences_per_week: template.occurrences_per_week,
          linkedModuleIds: [],
          required_room_type: template.required_room_type,
          required_lab_type: "",
          specific_room_id: "",
          max_students_per_group: "",
          allow_parallel_rooms: false,
          notes: "",
          lecturerIds: [],
          cohortIds: module.defaultCohortIds || [],
        }))
      );

    if (generatedSessions.length === 0) {
      return;
    }

    if (activeImportRunId) {
      await persistSnapshotBatch(
        "sessions",
        generatedSessions,
        `Session pattern saved into import snapshot #${activeImportRunId}.`
      );
      return;
    }

    updateDraft((current) => {
      const moduleIdsWithSessions = new Set(current.sessions.map((session) => session.moduleId));
      const generatedSessions = current.modules
        .filter((module) => module.id && !moduleIdsWithSessions.has(module.id))
        .flatMap((module) =>
          selectedPattern.map((template) => ({
            id: makeId("session"),
            moduleId: module.id,
            name: `${module.name || module.code || "Module"} ${template.suffix}`,
            session_type: template.session_type,
            duration_minutes: template.duration_minutes,
            occurrences_per_week: template.occurrences_per_week,
            linkedModuleIds: [],
            required_room_type: template.required_room_type,
            required_lab_type: "",
            specific_room_id: "",
            max_students_per_group: "",
            allow_parallel_rooms: false,
            notes: "",
            lecturerIds: [],
            cohortIds: module.defaultCohortIds || [],
          }))
        );

      if (generatedSessions.length === 0) {
        return current;
      }

      return {
        ...current,
        sessions: [...current.sessions, ...generatedSessions],
      };
    });
  };

  const addModuleShellsForSemester = (semester) => {
    updateDraft((current) => {
      const yearCombos = Array.from(
        new Map(
          current.cohorts
            .filter((cohort) => cohort.kind === "base" && cohort.degreeId && Number(cohort.year) > 0)
            .map((cohort) => [`${cohort.degreeId}::${cohort.year}`, { degreeId: cohort.degreeId, year: Number(cohort.year) }])
        ).values()
      );

      const existingByYearSemester = new Set(
        current.modules.map((module) => `${Number(module.year)}::${Number(module.semester)}`)
      );

      const moduleShells = yearCombos
        .filter((combo) => !existingByYearSemester.has(`${combo.year}::${semester}`))
        .map((combo, index) => {
          const degree = current.degrees.find((entry) => entry.id === combo.degreeId);
          const degreeCode = degree?.code?.trim() || "DEG";
          return {
            id: makeId("module"),
            code: `${degreeCode}${combo.year}${semester}0${index + 1}`,
            name: `${degreeCode} Year ${combo.year} Semester ${semester} Module`,
            subject_name: `${degreeCode} Year ${combo.year}`,
            year: combo.year,
            semester,
            is_full_year: false,
          };
        });

      if (moduleShells.length === 0) {
        return current;
      }

      return {
        ...current,
        modules: [...current.modules, ...moduleShells],
      };
    });
  };

  const addRoomTemplateBatch = async (templateKey) => {
    const templates = {
      lectureHalls: [
        {
          name: "A7 Hall 1",
          capacity: 180,
          room_type: "lecture",
          lab_type: "",
          location: "A7 Building",
          year_restriction: "",
        },
        {
          name: "A7 Hall 2",
          capacity: 140,
          room_type: "lecture",
          lab_type: "",
          location: "A7 Building",
          year_restriction: "",
        },
      ],
      labs: [
        {
          name: "Physics Lab 1",
          capacity: 40,
          room_type: "lab",
          lab_type: "physics",
          location: "Science Labs Block",
          year_restriction: "",
        },
        {
          name: "Chemistry Lab 1",
          capacity: 36,
          room_type: "lab",
          lab_type: "chemistry",
          location: "Science Labs Block",
          year_restriction: "",
        },
      ],
    };

    const selectedTemplate = templates[templateKey] || [];
    if (selectedTemplate.length === 0) {
      return;
    }

    const existingRoomNames = new Set(
      draft.rooms.map((room) => room.name.trim().toLowerCase()).filter(Boolean)
    );
    const roomsToAdd = selectedTemplate
      .filter((room) => !existingRoomNames.has(room.name.trim().toLowerCase()))
      .map((room) => ({
        id: makeId("room"),
        ...room,
      }));

    if (roomsToAdd.length === 0) {
      return;
    }

    if (activeImportRunId) {
      await persistSnapshotBatch(
        "rooms",
        roomsToAdd,
        `Room templates saved into import snapshot #${activeImportRunId}.`
      );
      return;
    }

    updateDraft((current) => {
      const existingRoomNames = new Set(
        current.rooms.map((room) => room.name.trim().toLowerCase()).filter(Boolean)
      );

      const roomsToAdd = selectedTemplate
        .filter((room) => !existingRoomNames.has(room.name.trim().toLowerCase()))
        .map((room) => ({
          id: makeId("room"),
          ...room,
        }));

      if (roomsToAdd.length === 0) {
        return current;
      }

      return {
        ...current,
        rooms: [...current.rooms, ...roomsToAdd],
      };
    });
  };

  const addLecturerTemplateBatch = async () => {
    const templates = [
      { name: "Dr. Perera", email: "dr.perera@science.kln.ac.lk" },
      { name: "Dr. Silva", email: "dr.silva@science.kln.ac.lk" },
      { name: "Prof. Fernando", email: "prof.fernando@science.kln.ac.lk" },
      { name: "Ms. Jayasinghe", email: "ms.jayasinghe@science.kln.ac.lk" },
    ];

    const existingNames = new Set(
      draft.lecturers.map((lecturer) => lecturer.name.trim().toLowerCase()).filter(Boolean)
    );

    const lecturersToAdd = templates
      .filter((lecturer) => !existingNames.has(lecturer.name.trim().toLowerCase()))
      .map((lecturer) => ({
        id: makeId("lecturer"),
        ...lecturer,
      }));

    if (lecturersToAdd.length === 0) {
      return;
    }

    if (activeImportRunId) {
      await persistSnapshotBatch(
        "lecturers",
        lecturersToAdd,
        `Lecturer templates saved into import snapshot #${activeImportRunId}.`
      );
      return;
    }

    updateDraft((current) => {
      const existingNames = new Set(
        current.lecturers.map((lecturer) => lecturer.name.trim().toLowerCase()).filter(Boolean)
      );

      const lecturersToAdd = templates
        .filter((lecturer) => !existingNames.has(lecturer.name.trim().toLowerCase()))
        .map((lecturer) => ({
          id: makeId("lecturer"),
          ...lecturer,
        }));

      if (lecturersToAdd.length === 0) {
        return current;
      }

      return {
        ...current,
        lecturers: [...current.lecturers, ...lecturersToAdd],
      };
    });
  };

  const loadSampleManualCompletionData = async () => {
    if (!activeImportRunId) {
      setError("Import a CSV first. Sample missing-data helpers only work after the student data is loaded.");
      return;
    }

    setSaving(true);
    setError("");
    setStatus("");
    try {
      const summary = await timetableStudioService.seedRealisticSnapshotMissingData(
        activeImportRunId
      );
      await loadImportWorkspace(activeImportRunId);
      setActiveStep(3);
      setStatus(
        `Teaching details added for the demo. Snapshot #${activeImportRunId} now includes ${summary.rooms_created} rooms, ${summary.lecturers_created} lecturers, and ${summary.shared_sessions_created} realistic starter sessions.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const addScienceStructureTemplates = () => {
    const degreeTemplates = [
      { code: "PS", name: "Physical Science", duration_years: 3, intake_label: "PS Intake" },
      { code: "BS", name: "Biological Science", duration_years: 3, intake_label: "BS Intake" },
      { code: "ENCM", name: "Environmental Conservation and Management", duration_years: 4, intake_label: "ENCM Intake" },
      { code: "AC", name: "Applied Chemistry", duration_years: 4, intake_label: "AC Intake" },
      { code: "ECS", name: "Electronics and Computer Science", duration_years: 4, intake_label: "ECS Intake" },
      { code: "PE", name: "Physical Education", duration_years: 4, intake_label: "PE Intake" },
    ];

    const pathTemplates = [
      { degreeCode: "PS", year: 1, code: "PHY-CHEM-MATH", name: "Physics Chemistry Mathematics" },
      { degreeCode: "PS", year: 2, code: "PHY-MATH-STAT", name: "Physics Mathematics Statistics" },
      { degreeCode: "BS", year: 1, code: "BOT-ZOO-CHEM", name: "Botany Zoology Chemistry" },
      { degreeCode: "BS", year: 2, code: "MICRO-BCH-GEN", name: "Microbiology Biochemistry Genetics" },
      { degreeCode: "ECS", year: 1, code: "ECS-GENERAL", name: "Electronics and Computer Science General" },
      { degreeCode: "AC", year: 1, code: "AC-GENERAL", name: "Applied Chemistry General" },
    ];

    updateDraft((current) => {
      const existingDegreeCodes = new Set(
        current.degrees.map((degree) => degree.code.trim().toUpperCase()).filter(Boolean)
      );

      const degreesToAdd = degreeTemplates
        .filter((degree) => !existingDegreeCodes.has(degree.code))
        .map((degree) => ({
          id: makeId("degree"),
          ...degree,
        }));

      const allDegrees = [...current.degrees, ...degreesToAdd];
      const degreeIdByCode = new Map(allDegrees.map((degree) => [degree.code.trim().toUpperCase(), degree.id]));
      const existingPathKeys = new Set(
        current.paths
          .map((path) => {
            const degree = allDegrees.find((entry) => entry.id === path.degreeId);
            return degree ? `${degree.code.trim().toUpperCase()}::${Number(path.year)}::${path.code.trim().toUpperCase()}` : "";
          })
          .filter(Boolean)
      );

      const pathsToAdd = pathTemplates
        .filter(
          (path) => !existingPathKeys.has(`${path.degreeCode}::${path.year}::${path.code}`)
        )
        .map((path) => ({
          id: makeId("path"),
          degreeId: degreeIdByCode.get(path.degreeCode) || "",
          year: path.year,
          code: path.code,
          name: path.name,
        }))
        .filter((path) => path.degreeId);

      if (degreesToAdd.length === 0 && pathsToAdd.length === 0) {
        return current;
      }

      return {
        ...current,
        degrees: allDegrees,
        paths: [...current.paths, ...pathsToAdd],
      };
    });
  };

  const addOverrideTemplatesFromBaseCohorts = () => {
    updateDraft((current) => {
      const overrideTemplates = current.cohorts
        .filter((cohort) => cohort.kind === "base")
        .map((cohort) => ({
          id: makeId("cohort"),
          kind: "override",
          degreeId: cohort.degreeId,
          year: cohort.year,
          pathId: cohort.pathId,
          name: `${cohort.name || "Cohort"} Override`,
          size: "",
        }));

      if (overrideTemplates.length === 0) {
        return current;
      }

      return {
        ...current,
        cohorts: [...current.cohorts, ...overrideTemplates],
      };
    });
  };

  const updateRecord = (collection, id, field, value) => {
    updateDraft((current) => ({
      ...current,
      [collection]: current[collection].map((record) =>
        record.id === id ? { ...record, [field]: value } : record
      ),
    }));
  };

  const removeRecord = async (collection, id) => {
    const record = draft[collection]?.find((entry) => entry.id === id);
    if (record && ["lecturers", "rooms", "sessions"].includes(collection) && activeImportRunId) {
      const deleted = await deleteSnapshotRecord(collection, record);
      if (!deleted) {
        return;
      }
    }

    updateDraft((current) => {
      const next = { ...current, [collection]: current[collection].filter((record) => record.id !== id) };

      if (collection === "degrees") {
        next.paths = next.paths.filter((path) => path.degreeId !== id);
        next.cohorts = next.cohorts.filter((cohort) => cohort.degreeId !== id);
      }
      if (collection === "paths") {
        next.cohorts = next.cohorts.filter((cohort) => cohort.pathId !== id);
      }
      if (collection === "modules") {
        next.sessions = next.sessions.filter((session) => session.moduleId !== id);
      }
      if (collection === "lecturers") {
        next.sessions = next.sessions.map((session) => ({
          ...session,
          lecturerIds: session.lecturerIds.filter((lecturerId) => lecturerId !== id),
        }));
      }
      if (collection === "rooms") {
        next.sessions = next.sessions.map((session) => ({
          ...session,
          specific_room_id: session.specific_room_id === id ? "" : session.specific_room_id,
        }));
      }
      if (collection === "cohorts") {
        next.sessions = next.sessions.map((session) => ({
          ...session,
          cohortIds: session.cohortIds.filter((cohortId) => cohortId !== id),
        }));
      }

      return next;
    });
  };

  const toggleSessionLink = (sessionId, field, value) => {
    updateDraft((current) => ({
      ...current,
      sessions: current.sessions.map((session) => {
        if (session.id !== sessionId) {
          return session;
        }
        const items = session[field];
        const nextItems = items.includes(value)
          ? items.filter((item) => item !== value)
          : [...items, value];
        return { ...session, [field]: nextItems };
      }),
    }));
  };

  const copySessionAudienceToModuleSet = (sessionId) => {
    updateDraft((current) => {
      const source = current.sessions.find((session) => session.id === sessionId);
      if (!source || !source.moduleId) {
        return current;
      }

      return {
        ...current,
        sessions: current.sessions.map((session) => {
          if (session.id === sessionId || session.moduleId !== source.moduleId) {
            return session;
          }

          return {
            ...session,
            lecturerIds: [...source.lecturerIds],
            cohortIds: [...source.cohortIds],
          };
        }),
      };
    });
  };

  const degreeOptions = draft.degrees;
  const pathOptions = draft.paths;
  const cohortOptions = draft.cohorts;
  const moduleOptions = draft.modules;
  const lecturerOptions = draft.lecturers;
  const roomOptions = draft.rooms;

  const visibleSteps = activeImportRunId
    ? steps.filter((step) =>
        ["lecturers", "rooms", "sessions", "review"].includes(step.key)
      )
    : steps;
  const currentStep = visibleSteps[activeStep]?.key || visibleSteps[0].key;
  const hasChosenImportSource = Boolean(selectedImportFile || useBundledImportSample);
  const importSourceLabel = selectedImportFile
    ? selectedImportFile.name
    : useBundledImportSample
      ? "Built-in sample CSV"
      : "";
  const hasAnalyzedImport = Boolean(importAnalysis);
  const hasReviewedImport = Boolean(importProjection);
  const hasMaterializedImport = Boolean(activeImportRunId);
  const nextGuidedAction = !hasMaterializedImport
    ? {
        title: "Start with the easiest path",
        description:
          "For the demo, use the sample student data and let the app fill the missing teaching details automatically.",
        button: importAction === "demo" ? "Preparing Demo..." : "Start Demo with Sample Data",
        onClick: runGuidedDemoSetup,
        secondary: "If you want, you can still use your own CSV below.",
      }
    : summary.sessions === 0
      ? {
          title: "Add the teaching details",
          description:
            "The student data is ready. Fill lecturers, rooms, and teaching sessions next.",
          button: "Fill Demo Teaching Data",
          onClick: loadSampleManualCompletionData,
          secondary: "You can also add lecturers, rooms, and sessions manually in the sections below.",
        }
      : validation.blocking.length > 0
        ? {
            title: "Fix the final issues",
            description: `There are ${validation.blocking.length} required issue${
              validation.blocking.length === 1 ? "" : "s"
            } to review before generation.`,
            button: "Go to Ready to Generate",
            onClick: () => setActiveStep(3),
            secondary: "The final review step shows the shortest fix list.",
          }
        : {
            title: "Move to generation",
            description: "This setup looks ready. Open Generate and create timetable options.",
            button: "Open Generate",
            onClick: handleOpenGenerate,
            secondary: "You can always return here and adjust the teaching details later.",
          };
  const importStageSection = (
    <section className="studio-card">
      <div className="setup-flow-overview">
        <div className={`flow-card ${hasMaterializedImport ? "done" : "current"}`}>
          <span className="flow-card-step">1</span>
          <div>
            <strong>Import student enrolments</strong>
            <p>
              {!hasChosenImportSource
                ? "Choose a CSV file to begin."
                : hasMaterializedImport
                  ? "Student enrolments are loaded."
                  : "Analyze and review the selected CSV."}
            </p>
          </div>
        </div>
        <div className={`flow-card ${hasMaterializedImport ? "current" : ""}`}>
          <span className="flow-card-step">2</span>
          <div>
            <strong>Complete missing details</strong>
            <p>
              {hasMaterializedImport
                ? "Add rooms, lecturers, and teaching sessions."
                : "Unlocks after the import is used."}
            </p>
          </div>
        </div>
        <div className="flow-card">
          <span className="flow-card-step">3</span>
          <div>
            <strong>Generate timetable</strong>
            <p>Publish this setup and move to generation.</p>
          </div>
        </div>
      </div>

      <div className="future-card">
        <strong>{nextGuidedAction.title}</strong>
        <span>{nextGuidedAction.description}</span>
        <div className="record-actions">
          <button
            className="primary-btn"
            type="button"
            onClick={nextGuidedAction.onClick}
            disabled={importLoading || saving || loading}
          >
            {nextGuidedAction.button}
          </button>
        </div>
        <p className="helper-copy">{nextGuidedAction.secondary}</p>
      </div>

      <div className="section-row">
        <div>
          <h2>Import Student Enrolments</h2>
          <p>
            Use your own CSV if you want to test real enrolment data. The guided demo path above is the fastest route for a normal user.
          </p>
        </div>
        <div className="record-actions">
          <label className="ghost-btn file-picker-btn">
            <input
              type="file"
              accept=".csv,text/csv"
              className="visually-hidden"
              onChange={(event) => {
                const nextFile = event.target.files?.[0] || null;
                setSelectedImportFile(nextFile);
                setUseBundledImportSample(false);
                setImportAnalysis(null);
                setImportProjection(null);
                setMaterializedImport(null);
                setImportRuleActions({});
                if (typeof window !== "undefined") {
                  window.localStorage.removeItem(activeImportRunStorageKey);
                }
                setStatus(
                  nextFile
                    ? `${nextFile.name} selected. Analyze it to start the import flow.`
                    : ""
                );
              }}
            />
            Choose CSV File
          </label>
          <button
            className="ghost-btn"
            type="button"
            onClick={() => {
              setSelectedImportFile(null);
              setUseBundledImportSample(true);
              setImportAnalysis(null);
              setImportProjection(null);
              setMaterializedImport(null);
              setImportRuleActions({});
              if (typeof window !== "undefined") {
                window.localStorage.removeItem(activeImportRunStorageKey);
              }
              setStatus("Built-in sample CSV selected. Analyze it to start the import flow.");
            }}
            disabled={importLoading || saving || loading}
          >
            Use Sample CSV
          </button>
        </div>
      </div>

      <div className={`import-source-banner ${hasChosenImportSource ? "is-ready" : ""}`}>
        {hasChosenImportSource ? (
          <>
            <strong>Selected source</strong>
            <span>{importSourceLabel}</span>
          </>
        ) : (
          <>
            <strong>No CSV selected yet</strong>
            <span>Choose a file or use the guided demo action above.</span>
          </>
        )}
      </div>

      <div className="section-row">
        <div>
          <h3>Review The CSV</h3>
          <p>Analyze the file, review unclear groups, then use the cleaned import.</p>
        </div>
        <div className="record-actions">
          <button
            className={!hasAnalyzedImport && hasChosenImportSource ? "primary-btn" : "ghost-btn"}
            type="button"
            onClick={handleAnalyzeEnrollmentImport}
            disabled={importLoading || saving || loading || !hasChosenImportSource}
          >
            {importAction === "analyze" ? "Analyzing..." : "Analyze Enrollment CSV"}
          </button>
          <button
            className={!hasReviewedImport && hasAnalyzedImport ? "primary-btn" : "ghost-btn"}
            type="button"
            onClick={handlePreviewEnrollmentImport}
            disabled={importLoading || !hasAnalyzedImport}
          >
            {importAction === "review" ? "Reviewing..." : "Review Import"}
          </button>
          <button
            className="primary-btn"
            type="button"
            onClick={handleLoadEnrollmentImport}
            disabled={importLoading || saving || !hasReviewedImport}
          >
            {importAction === "materialize" ? "Using Import..." : "Use This Import"}
          </button>
        </div>
      </div>

      {!hasAnalyzedImport ? (
        <div className="future-card">
          <strong>Step 1: Analyze the CSV</strong>
          <span>
            After choosing a source, click `Analyze Enrollment CSV`. The system will scan the file
            and point out anything unclear.
          </span>
        </div>
      ) : hasMaterializedImport ? (
        <div className="info-banner">
          The CSV import has been materialized into snapshot #{activeImportRunId}. You can return to
          this section later, but the next step is to complete the missing teaching details below.
        </div>
      ) : (
        <>
          <div className="summary-grid">
            <div className="summary-item">
              <span>Rows scanned</span>
              <strong>{importAnalysis.summary?.total_rows || 0}</strong>
            </div>
            <div className="summary-item">
              <span>Students found</span>
              <strong>{importAnalysis.summary?.unique_students || 0}</strong>
            </div>
            <div className="summary-item">
              <span>Review buckets</span>
              <strong>{importBuckets.length}</strong>
            </div>
            {hasReviewedImport && (
              <div className="summary-item">
                <span>Rows kept for timetable building</span>
                <strong>{importProjection.projection_summary?.projected_rows || 0}</strong>
              </div>
            )}
          </div>

          <details className="schema-notes">
            <summary>See import details</summary>
            <h3>Things That Need Review</h3>
            {importBuckets.length === 0 ? (
              <p className="empty-state">This import looks clean. No review items were generated.</p>
            ) : (
              <div className="editor-list">
                {importBuckets.slice(0, 12).map((bucket) => {
                  const bucketId = `${bucket.bucket_type}::${bucket.bucket_key}`;
                  return (
                    <div key={bucketId} className="editor-card">
                      <div className="section-row">
                        <div>
                          <h3>{bucket.bucket_type.replace(/_/g, " ")}</h3>
                          <p>{bucket.description}</p>
                        </div>
                        <span className="tag-chip">{bucket.row_count} rows</span>
                      </div>
                      <label>
                        <span>How should this be treated?</span>
                        <select
                          value={importRuleActions[bucketId] || ""}
                          onChange={(event) =>
                            setImportRuleActions((current) => ({
                              ...current,
                              [bucketId]: event.target.value,
                            }))
                          }
                        >
                          <option value="">Leave unresolved</option>
                          <option value="accept_exception">Accept exception</option>
                          <option value="treat_as_common">Treat as common module</option>
                          <option value="exclude">Exclude bucket</option>
                        </select>
                      </label>
                    </div>
                  );
                })}
              </div>
            )}
          </details>

          {hasReviewedImport && (
            <div className="schema-notes">
              <h3>Review result</h3>
              <div className="summary-grid">
                {Object.entries(importProjection.projection_summary || {}).map(([key, value]) => (
                  <div key={key} className="summary-item">
                    <span>{key.replace(/_/g, " ")}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          {materializedImport && (
            <div className="schema-notes">
              <h3>Import Ready</h3>
              <div className="summary-grid">
                {Object.entries(materializedImport.counts || {}).map(([key, value]) => (
                  <div key={key} className="summary-item">
                    <span>{key.replace(/_/g, " ")}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="schema-notes">
            <h3>What happens next</h3>
            <ul>
              <li>The system keeps the student enrolments from the CSV.</li>
              <li>Unresolved items stay excluded until you decide otherwise.</li>
              <li>After `Use This Import`, you only complete the teaching details that the CSV cannot provide.</li>
            </ul>
          </div>
        </>
      )}
    </section>
  );

  return (
    <div className="page-shell">
      <div className="panel studio-panel">
        <div className="studio-header">
          <div>
            <h1 className="section-title">Setup Studio</h1>
            <p className="section-subtitle">
              {activeImportRunId
                ? `Student enrolments are loaded. Now complete the missing teaching details.`
                : "Start with the guided demo path or import your own student CSV."}
            </p>
          </div>
          {showSetupWizard && (
            <div className="studio-actions wrap">
              <button
                className="primary-btn"
                onClick={handleOpenGenerate}
                disabled={saving || loading}
                title={
                  validation.blocking.length > 0
                    ? `Fix ${validation.blocking.length} blocking issue${
                        validation.blocking.length === 1 ? "" : "s"
                      } before generation`
                    : "Open the generation workspace"
                }
              >
                {validation.blocking.length > 0 ? "Review Before Generate" : "Open Generate"}
              </button>
            </div>
          )}
        </div>

        {status && <div className="info-banner valid">{status}</div>}
        {error && <div className="error-banner">{error}</div>}
        {loading && (
          <div className="info-banner">
            {activeImportRunId
              ? `Loading normalized import workspace #${activeImportRunId}...`
              : "Preparing the CSV-first setup flow..."}
          </div>
        )}

        {importStageSection}

        {showSetupWizard ? (
          <>
        <section className="studio-card">
          <div className="section-row">
            <div>
              <h2>Complete Missing Details</h2>
              <p>
                Add only the teaching details that do not exist in the CSV: rooms, lecturers, and teaching sessions.
              </p>
            </div>
            {activeImportRunId && <span className="tag-chip">Snapshot #{activeImportRunId}</span>}
          </div>
          {activeImportRunId && (
            <div className="future-card">
              <strong>Fastest next step</strong>
              <span>Use the realistic demo teaching data if you want to reach generation quickly.</span>
              <div className="record-actions">
                <button
                  className="ghost-btn"
                  type="button"
                  onClick={loadSampleManualCompletionData}
                  disabled={saving || loading || importLoading}
                >
                  Fill Demo Teaching Data
                </button>
              </div>
            </div>
          )}
        </section>

        <div className="wizard-steps">
          {visibleSteps.map((step, index) => (
            <StepBadge
              key={step.key}
              label={`${index + 1}. ${step.key === "review" ? "Ready to Generate" : step.label}`}
              active={index === activeStep}
              complete={!blockedSteps[step.key] && index < activeStep}
              blocked={blockedSteps[step.key]}
              onClick={() => goToStep(index)}
            />
          ))}
        </div>

        <section className="studio-card">
          <div className="summary-grid">
            {Object.entries(summary).map(([key, value]) => (
              <div key={key} className="summary-item">
                <span>{key.replace(/_/g, " ")}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </section>

        <StepChecks
          stepKey={currentStep}
          validation={validation}
          snapshotMode={Boolean(activeImportRunId)}
        />

        {currentStep === "structure" && (
          <div className="studio-grid">
            <StepIntro stepKey="structure" />
            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Degrees</h2>
                  <p>Enter each Faculty of Science degree and its duration.</p>
                </div>
                <div className="record-actions">
                  <button
                    className="ghost-btn"
                    onClick={addScienceStructureTemplates}
                    disabled={snapshotDerivedEditingDisabled}
                  >
                    Load Science Structure Templates
                  </button>
                  <button
                    className="primary-btn"
                    onClick={() => {
                      setTempDegree({ code: "", name: "", duration_years: 3, intake_label: "" });
                      setShowDegreeModal(true);
                    }}
                    disabled={snapshotDerivedEditingDisabled}
                  >
                    Add Degree
                  </button>
                </div>
              </div>
              {snapshotDerivedEditingDisabled && (
                <div className="info-banner">
                  Degrees and paths are loaded from the import snapshot and are read-only in this bridge.
                </div>
              )}
              <div className="editor-list">
                {draft.degrees.length === 0 ? (
                  <p className="empty-state">No degrees added yet.</p>
                ) : (
                  draft.degrees.slice(0, visibleDegreeCount).map((degree, index) => {
                    const degreeIssue = findRecordIssue(
                      validation.blocking,
                      new RegExp(`^Degree ${index + 1} is missing code, name, or intake label\\.$`)
                    );
                    const degreeDurationIssue = findRecordIssue(
                      validation.blocking,
                      new RegExp(`^Degree ${index + 1} needs a valid duration in years\\.$`)
                    );

                    return (
                      <div key={degree.id} className="editor-card">
                        <div className="form-grid degree-row degree-row-actions">
                          <label>
                            <span>Code</span>
                            <input
                              className={invalidClass(degreeIssue)}
                              value={degree.code}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("degrees", degree.id, "code", event.target.value)
                              }
                            />
                            {degreeIssue && <small className="field-hint invalid">{degreeIssue}</small>}
                          </label>
                          <label>
                            <span>Name</span>
                            <input
                              className={invalidClass(degreeIssue)}
                              value={degree.name}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("degrees", degree.id, "name", event.target.value)
                              }
                            />
                            {degreeIssue && <small className="field-hint invalid">{degreeIssue}</small>}
                          </label>
                          <label>
                            <span>Duration</span>
                            <input
                              className={invalidClass(degreeDurationIssue)}
                              type="number"
                              min="1"
                              max="6"
                              value={degree.duration_years}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("degrees", degree.id, "duration_years", event.target.value)
                              }
                            />
                            {degreeDurationIssue && (
                              <small className="field-hint invalid">{degreeDurationIssue}</small>
                            )}
                          </label>
                          <label>
                            <span>Intake label</span>
                            <input
                              className={invalidClass(degreeIssue)}
                              value={degree.intake_label}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("degrees", degree.id, "intake_label", event.target.value)
                              }
                            />
                            {degreeIssue && <small className="field-hint invalid">{degreeIssue}</small>}
                          </label>
                          <div className="inline-delete-wrap">
                            <button
                              className="danger-btn danger-icon-btn"
                              onClick={() => removeRecord("degrees", degree.id)}
                              disabled={snapshotDerivedEditingDisabled}
                              aria-label={`Remove ${degree.code || degree.name || "degree"}`}
                              title="Remove degree"
                              type="button"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                {draft.degrees.length > INITIAL_VISIBLE_RECORDS && (
                  <div className="list-see-more-wrap">
                    <button
                      type="button"
                      className="list-see-more-btn"
                      onClick={() =>
                        setVisibleDegreeCount((current) =>
                          current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : draft.degrees.length
                        )
                      }
                    >
                      <span className={`list-see-more-arrow ${visibleDegreeCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`} aria-hidden="true" />
                      {visibleDegreeCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                    </button>
                  </div>
                )}
              </div>
            </section>

            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Paths</h2>
                  <p>Add year-specific subject combinations where a degree offers them.</p>
                </div>
                <button
                  className="ghost-btn"
                  onClick={() => {
                    setTempPath({ degreeId: degreeOptions[0]?.id || "", year: 1, code: "", name: "" });
                    setShowPathModal(true);
                  }}
                  disabled={degreeOptions.length === 0 || snapshotDerivedEditingDisabled}
                >
                  Add Path
                </button>
              </div>
              <div className="editor-list">
                {draft.paths.length === 0 ? (
                  <p className="empty-state">Direct-entry degrees can be left without paths.</p>
                ) : (
                  draft.paths.slice(0, visiblePathCount).map((path, index) => {
                    const pathIssue = findRecordIssue(
                      validation.blocking,
                      new RegExp(`^Path ${index + 1} is missing degree, code, or name\\.$`)
                    );

                    return (
                      <div key={path.id} className="editor-card">
                        <div className="form-grid four-column">
                          <label>
                            <span>Degree</span>
                            <select
                              className={invalidClass(pathIssue)}
                              value={path.degreeId}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("paths", path.id, "degreeId", event.target.value)
                              }
                            >
                              <option value="">Select degree</option>
                              {degreeOptions.map((degree) => (
                                <option key={degree.id} value={degree.id}>
                                  {degree.code}
                                </option>
                              ))}
                            </select>
                            {pathIssue && <small className="field-hint invalid">{pathIssue}</small>}
                          </label>
                          <label>
                            <span>Year</span>
                            <input
                              type="number"
                              min="1"
                              max="6"
                              value={path.year}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("paths", path.id, "year", event.target.value)
                              }
                            />
                          </label>
                          <label>
                            <span>Code</span>
                            <input
                              className={invalidClass(pathIssue)}
                              value={path.code}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("paths", path.id, "code", event.target.value)
                              }
                            />
                            {pathIssue && <small className="field-hint invalid">{pathIssue}</small>}
                          </label>
                          <label>
                            <span>Name</span>
                            <input
                              className={invalidClass(pathIssue)}
                              value={path.name}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("paths", path.id, "name", event.target.value)
                              }
                            />
                            {pathIssue && <small className="field-hint invalid">{pathIssue}</small>}
                          </label>
                        </div>
                        <button
                          className="danger-btn"
                          onClick={() => removeRecord("paths", path.id)}
                          disabled={snapshotDerivedEditingDisabled}
                        >
                          Remove Path
                        </button>
                      </div>
                    );
                  })
                )}
                {draft.paths.length > INITIAL_VISIBLE_RECORDS && (
                  <div className="list-see-more-wrap">
                    <button
                      type="button"
                      className="list-see-more-btn"
                      onClick={() =>
                        setVisiblePathCount((current) =>
                          current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : draft.paths.length
                        )
                      }
                    >
                      <span className={`list-see-more-arrow ${visiblePathCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`} aria-hidden="true" />
                      {visiblePathCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                    </button>
                  </div>
                )}
              </div>
            </section>
          </div>
        )}

        {currentStep === "lecturers" && (
          <>
            <StepIntro stepKey="lecturers" />
            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Lecturers</h2>
                  <p>These appear in session assignment and lecturer timetable views.</p>
                </div>
                <div className="record-actions">
                  <button
                    className="ghost-btn"
                    onClick={() => {
                      setTempLecturer({ name: "", email: "" });
                      setShowLecturerModal(true);
                    }}
                  >
                    Add Lecturer
                  </button>
                </div>
              </div>
              <div className="editor-list">
                {draft.lecturers.length === 0 ? (
                  <p className="empty-state">No lecturers added yet.</p>
                ) : (
                  draft.lecturers.slice(0, visibleLecturerCount).map((lecturer) => (
                    <div key={lecturer.id} className="editor-card">
                      <div className="form-grid two-column">
                        <label>
                          <span>Name</span>
                          <input
                            value={lecturer.name}
                            onChange={(event) =>
                              updateRecord("lecturers", lecturer.id, "name", event.target.value)
                            }
                            onBlur={() => persistSnapshotRecordUpdate("lecturers", lecturer)}
                          />
                        </label>
                        <label>
                          <span>Email</span>
                          <input
                            value={lecturer.email}
                            onChange={(event) =>
                              updateRecord("lecturers", lecturer.id, "email", event.target.value)
                            }
                            onBlur={() => persistSnapshotRecordUpdate("lecturers", lecturer)}
                          />
                        </label>
                      </div>
                      <button className="danger-btn" onClick={() => removeRecord("lecturers", lecturer.id)}>
                        Remove Lecturer
                      </button>
                    </div>
                  ))
                )}
                {draft.lecturers.length > INITIAL_VISIBLE_RECORDS && (
                  <div className="list-see-more-wrap">
                    <button
                      type="button"
                      className="list-see-more-btn"
                      onClick={() =>
                        setVisibleLecturerCount((current) =>
                          current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : draft.lecturers.length
                        )
                      }
                    >
                      <span
                        className={`list-see-more-arrow ${visibleLecturerCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`}
                        aria-hidden="true"
                      />
                      {visibleLecturerCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                    </button>
                  </div>
                )}
              </div>
            </section>
          </>
        )}

        {currentStep === "rooms" && (
          <>
            <StepIntro stepKey="rooms" />
            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Rooms</h2>
                  <p>Capture lecture halls, labs, and any year-specific restrictions.</p>
                </div>
                <div className="record-actions">
                  <button
                    className="ghost-btn"
                    onClick={() => {
                      setTempRoom({
                        name: "",
                        capacity: "",
                        room_type: "lecture",
                        lab_type: "",
                        location: "",
                        year_restriction: "",
                      });
                      setShowRoomModal(true);
                    }}
                  >
                    Add Room
                  </button>
                </div>
              </div>
              <div className="editor-list">
              {draft.rooms.length === 0 ? (
                <p className="empty-state">No rooms added yet.</p>
              ) : (
                draft.rooms.slice(0, visibleRoomCount).map((room) => (
                  <div key={room.id} className="editor-card">
                    {(() => {
                      const roomNameIssue = findRecordIssue(
                        validation.blocking,
                        new RegExp(`^Room ${draft.rooms.indexOf(room) + 1} is missing name or location\\.$`)
                      );
                      const roomCapacityIssue = findRecordIssue(
                        validation.blocking,
                        new RegExp(`^Room ${draft.rooms.indexOf(room) + 1} needs a positive capacity\\.$`)
                      );
                      return (
                    <div className="form-grid four-column">
                      <label>
                        <span>Name</span>
                        <input
                          className={invalidClass(roomNameIssue)}
                          value={room.name}
                          onChange={(event) =>
                            updateRecord("rooms", room.id, "name", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("rooms", room)}
                        />
                        {roomNameIssue && <small className="field-hint invalid">{roomNameIssue}</small>}
                      </label>
                      <label>
                        <span>Capacity</span>
                        <input
                          className={invalidClass(roomCapacityIssue)}
                          type="number"
                          min="1"
                          value={room.capacity}
                          onChange={(event) =>
                            updateRecord("rooms", room.id, "capacity", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("rooms", room)}
                        />
                        {roomCapacityIssue && <small className="field-hint invalid">{roomCapacityIssue}</small>}
                      </label>
                      <label>
                        <span>Room type</span>
                        <select
                          value={room.room_type}
                          onChange={(event) =>
                            updateRecord("rooms", room.id, "room_type", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("rooms", room)}
                        >
                          <option value="lecture">Lecture</option>
                          <option value="lab">Lab</option>
                          <option value="seminar">Seminar</option>
                        </select>
                      </label>
                      <label>
                        <span>Lab type</span>
                        <input
                          value={room.lab_type}
                          onChange={(event) =>
                            updateRecord("rooms", room.id, "lab_type", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("rooms", room)}
                        />
                      </label>
                      <label>
                        <span>Location</span>
                        <input
                          className={invalidClass(roomNameIssue)}
                          value={room.location}
                          onChange={(event) =>
                            updateRecord("rooms", room.id, "location", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("rooms", room)}
                        />
                        {roomNameIssue && <small className="field-hint invalid">{roomNameIssue}</small>}
                      </label>
                      <label>
                        <span>Year restriction</span>
                        <input
                          type="number"
                          min="1"
                          max="6"
                          value={room.year_restriction}
                          onChange={(event) =>
                            updateRecord("rooms", room.id, "year_restriction", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("rooms", room)}
                        />
                      </label>
                    </div>
                      );
                    })()}
                    <div className="record-actions">
                      <button className="danger-btn" onClick={() => removeRecord("rooms", room.id)}>
                        Remove Room
                      </button>
                    </div>
                  </div>
                ))
              )}
              {draft.rooms.length > INITIAL_VISIBLE_RECORDS && (
                <div className="list-see-more-wrap">
                  <button
                    type="button"
                    className="list-see-more-btn"
                    onClick={() =>
                      setVisibleRoomCount((current) =>
                        current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : draft.rooms.length
                      )
                    }
                  >
                    <span
                      className={`list-see-more-arrow ${visibleRoomCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`}
                      aria-hidden="true"
                    />
                    {visibleRoomCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                  </button>
                </div>
              )}
              </div>
            </section>
          </>
        )}

        {currentStep === "cohorts" && (
          <div className="studio-grid">
            <StepIntro stepKey="cohorts" />
            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Base Cohorts</h2>
                  <p>These are derived from degree, year, and path structure. Enter counts here first.</p>
                </div>
                <div className="record-actions">
                  <select
                    className="cohort-year-filter"
                    value={cohortYearFilter}
                    onChange={(e) => setCohortYearFilter(e.target.value)}
                  >
                    <option value="all">All Years</option>
                    {[1, 2, 3, 4, 5, 6].map((y) => (
                      <option key={y} value={y}>
                        Year {y}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {snapshotDerivedEditingDisabled && (
                <div className="info-banner">
                  Attendance groups are loaded from the import snapshot and are read-only in this bridge.
                </div>
              )}
              <div className="editor-list">
                {filteredBaseCohorts.length === 0 ? (
                  <p className="empty-state">
                    {cohortYearFilter !== "all"
                      ? `No base cohorts found for Year ${cohortYearFilter}.`
                      : "Add degrees and paths first."}
                  </p>
                ) : (
                  filteredBaseCohorts.slice(0, visibleBaseCohortCount).map((cohort) => {
                    const degree = degreeOptions.find((entry) => entry.id === cohort.degreeId);
                    const path = pathOptions.find((entry) => entry.id === cohort.pathId);
                    const baseIndex =
                      draft.cohorts.filter((entry) => entry.kind === "base").findIndex((entry) => entry.id === cohort.id) + 1;
                    const cohortNameIssue = findRecordIssue(
                      validation.blocking,
                      new RegExp(`^Base cohort ${baseIndex} is missing a name\\.$`)
                    );
                    const cohortSizeIssue = findRecordIssue(
                      validation.blocking,
                      new RegExp(`^Base cohort ${baseIndex} needs a positive student count\\.$`)
                    );
                    return (
                      <div key={cohort.id} className="editor-card">
                        <div className="chip-row">
                          <span className="tag-chip">{degree?.code || "Degree"}</span>
                          <span className="tag-chip">Year {cohort.year}</span>
                          <select
                            className="cohort-year-select"
                            value={cohort.cohort_year || currentYear}
                            disabled={snapshotDerivedEditingDisabled}
                            onChange={(event) =>
                              updateRecord("cohorts", cohort.id, "cohort_year", event.target.value)
                            }
                          >
                            {[2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015].map((y) => (
                              <option key={y} value={y}>
                                {y}
                              </option>
                            ))}
                          </select>
                          <span className="tag-chip">{path?.code || "General"}</span>
                        </div>
                        <div className="form-grid two-column">
                          <label>
                            <span>Cohort name</span>
                            <input
                              className={invalidClass(cohortNameIssue)}
                              value={cohort.name}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("cohorts", cohort.id, "name", event.target.value)
                              }
                            />
                            {cohortNameIssue && <small className="field-hint invalid">{cohortNameIssue}</small>}
                          </label>
                          <label>
                            <span>Student count</span>
                            <input
                              className={invalidClass(cohortSizeIssue)}
                              type="number"
                              min="1"
                              value={cohort.size}
                              disabled={snapshotDerivedEditingDisabled}
                              onChange={(event) =>
                                updateRecord("cohorts", cohort.id, "size", event.target.value)
                              }
                            />
                            {cohortSizeIssue && <small className="field-hint invalid">{cohortSizeIssue}</small>}
                          </label>
                        </div>
                      </div>
                    );
                  })
                )}
                {filteredBaseCohorts.length > INITIAL_VISIBLE_RECORDS && (
                  <div className="list-see-more-wrap">
                    <button
                      type="button"
                      className="list-see-more-btn"
                      onClick={() =>
                        setVisibleBaseCohortCount((current) =>
                          current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : filteredBaseCohorts.length
                        )
                      }
                    >
                      <span
                        className={`list-see-more-arrow ${visibleBaseCohortCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`}
                        aria-hidden="true"
                      />
                      {visibleBaseCohortCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                    </button>
                  </div>
                )}
              </div>
            </section>

            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Override Groups</h2>
                  <p>Add elective or special attendance groups when the base cohort is not enough.</p>
                </div>
                <div className="record-actions">
                  <button
                    className="ghost-btn"
                    onClick={addOverrideTemplatesFromBaseCohorts}
                    disabled={
                      draft.cohorts.filter((cohort) => cohort.kind === "base").length === 0 ||
                      snapshotDerivedEditingDisabled
                    }
                  >
                    Create Override Templates
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => {
                      setTempOverrideCohort({
                        degreeId: degreeOptions[0]?.id || "",
                        year: 1,
                        pathId: "",
                        name: "",
                        size: "",
                      });
                      setShowOverrideCohortModal(true);
                    }}
                    disabled={degreeOptions.length === 0 || snapshotDerivedEditingDisabled}
                  >
                    Add Override
                  </button>
                </div>
              </div>
              <div className="editor-list">
                {filteredOverrideCohorts.length === 0 ? (
                  <p className="empty-state">
                    {cohortYearFilter !== "all"
                      ? `No override groups found for Year ${cohortYearFilter}.`
                      : "No override groups added."}
                  </p>
                ) : (
                  filteredOverrideCohorts.slice(0, visibleOverrideCohortCount).map((cohort, index) => {
                      const overrideIdentityIssue = findRecordIssue(
                        validation.blocking,
                        new RegExp(`^Override group ${index + 1} is missing degree or name\\.$`)
                      );
                      const overrideSizeIssue = findRecordIssue(
                        validation.blocking,
                        new RegExp(`^Override group ${index + 1} needs a positive student count\\.$`)
                      );

                      return (
                        <div key={cohort.id} className="editor-card">
                          <div className="form-grid four-column">
                            <label>
                              <span>Degree</span>
                              <select
                                className={invalidClass(overrideIdentityIssue)}
                                value={cohort.degreeId}
                                disabled={snapshotDerivedEditingDisabled}
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "degreeId", event.target.value)
                                }
                              >
                                <option value="">Select degree</option>
                                {degreeOptions.map((degree) => (
                                  <option key={degree.id} value={degree.id}>
                                    {degree.code}
                                  </option>
                                ))}
                              </select>
                              {overrideIdentityIssue && <small className="field-hint invalid">{overrideIdentityIssue}</small>}
                            </label>
                            <label>
                              <span>Year</span>
                              <input
                                type="number"
                                min="1"
                                max="6"
                                value={cohort.year}
                                disabled={snapshotDerivedEditingDisabled}
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "year", event.target.value)
                                }
                              />
                            </label>
                            <label>
                              <span>Path</span>
                              <select
                                value={cohort.pathId}
                                disabled={snapshotDerivedEditingDisabled}
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "pathId", event.target.value)
                                }
                              >
                                <option value="">General</option>
                                {pathOptions
                                  .filter((path) => path.degreeId === cohort.degreeId)
                                  .map((path) => (
                                    <option key={path.id} value={path.id}>
                                      {path.code}
                                    </option>
                                  ))}
                              </select>
                            </label>
                            <label>
                              <span>Student count</span>
                              <input
                                className={invalidClass(overrideSizeIssue)}
                                type="number"
                                min="1"
                                value={cohort.size}
                                disabled={snapshotDerivedEditingDisabled}
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "size", event.target.value)
                                }
                              />
                              {overrideSizeIssue && <small className="field-hint invalid">{overrideSizeIssue}</small>}
                            </label>
                            <label>
                              <span>Calendar year</span>
                              <select
                                value={cohort.cohort_year || currentYear}
                                disabled={snapshotDerivedEditingDisabled}
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "cohort_year", event.target.value)
                                }
                              >
                                {[2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015].map((y) => (
                                  <option key={y} value={y}>
                                    {y}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label className="full-span">
                              <span>Override name</span>
                              <input
                                className={invalidClass(overrideIdentityIssue)}
                                value={cohort.name}
                                disabled={snapshotDerivedEditingDisabled}
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "name", event.target.value)
                                }
                              />
                              {overrideIdentityIssue && <small className="field-hint invalid">{overrideIdentityIssue}</small>}
                            </label>
                          </div>
                          <div className="record-actions">
                            <button
                              className="ghost-btn"
                              onClick={() => duplicateRecord("cohorts", cohort.id)}
                              disabled={snapshotDerivedEditingDisabled}
                            >
                              Duplicate Override
                            </button>
                            <button
                              className="danger-btn"
                              onClick={() => removeRecord("cohorts", cohort.id)}
                              disabled={snapshotDerivedEditingDisabled}
                            >
                              Remove Override
                            </button>
                          </div>
                        </div>
                      );
                    })
                )}
                {filteredOverrideCohorts.length > INITIAL_VISIBLE_RECORDS && (
                  <div className="list-see-more-wrap">
                    <button
                      type="button"
                      className="list-see-more-btn"
                      onClick={() =>
                        setVisibleOverrideCohortCount((current) =>
                          current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : filteredOverrideCohorts.length
                        )
                      }
                    >
                      <span
                        className={`list-see-more-arrow ${visibleOverrideCohortCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`}
                        aria-hidden="true"
                      />
                      {visibleOverrideCohortCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                    </button>
                  </div>
                )}
              </div>
            </section>
          </div>
        )}

        {currentStep === "modules" && (
          <>
            <StepIntro stepKey="modules" />
            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Modules</h2>
                  <p>Define the semester modules before attaching weekly sessions.</p>
                </div>
                <div className="record-actions">
                  <button
                    className="ghost-btn"
                    onClick={() => addModuleShellsForSemester(1)}
                    disabled={
                      draft.cohorts.filter((cohort) => cohort.kind === "base").length === 0 ||
                      snapshotDerivedEditingDisabled
                    }
                  >
                    Create Semester 1 Module Shells
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => addModuleShellsForSemester(2)}
                    disabled={
                      draft.cohorts.filter((cohort) => cohort.kind === "base").length === 0 ||
                      snapshotDerivedEditingDisabled
                    }
                  >
                    Create Semester 2 Module Shells
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => {
                      setTempModule({
                        code: "",
                        name: "",
                        subject_name: "",
                        year: 1,
                        semester: 1,
                        is_full_year: false,
                      });
                      setShowModuleModal(true);
                    }}
                    disabled={snapshotDerivedEditingDisabled}
                  >
                    Add Module
                  </button>
                </div>
              </div>
              {snapshotDerivedEditingDisabled && (
                <div className="info-banner">
                  Modules are loaded from the import snapshot and are read-only in this bridge.
                </div>
              )}
              <div className="module-search-wrap">
                <input
                  type="text"
                  className="module-search-input"
                  placeholder="Search modules by name, code, or subject..."
                  value={moduleSearchQuery}
                  onChange={(e) => setModuleSearchQuery(e.target.value)}
                />
              </div>
              <div className="editor-list">
              {draft.modules.length === 0 ? (
                <p className="empty-state">No modules added yet.</p>
              ) : filteredModules.length === 0 ? (
                <p className="empty-state">No modules found matching "{moduleSearchQuery}"</p>
              ) : (
                filteredModules.slice(0, visibleModuleCount).map((module, index) => {
                  const moduleIssue = findRecordIssue(
                    validation.blocking,
                    new RegExp(`^Module ${index + 1} is missing code, name, or subject\\.$`)
                  );

                  return (
                    <div key={module.id} className="editor-card">
                      <div className="form-grid four-column">
                        <label>
                          <span>Code</span>
                          <input
                            className={invalidClass(moduleIssue)}
                            value={module.code}
                            disabled={snapshotDerivedEditingDisabled}
                            onChange={(event) =>
                              updateRecord("modules", module.id, "code", event.target.value)
                            }
                          />
                          {moduleIssue && <small className="field-hint invalid">{moduleIssue}</small>}
                        </label>
                        <label>
                          <span>Name</span>
                          <input
                            className={invalidClass(moduleIssue)}
                            value={module.name}
                            disabled={snapshotDerivedEditingDisabled}
                            onChange={(event) =>
                              updateRecord("modules", module.id, "name", event.target.value)
                            }
                          />
                          {moduleIssue && <small className="field-hint invalid">{moduleIssue}</small>}
                        </label>
                        <label>
                          <span>Subject</span>
                          <input
                            className={invalidClass(moduleIssue)}
                            value={module.subject_name}
                            disabled={snapshotDerivedEditingDisabled}
                            onChange={(event) =>
                              updateRecord("modules", module.id, "subject_name", event.target.value)
                            }
                          />
                          {moduleIssue && <small className="field-hint invalid">{moduleIssue}</small>}
                        </label>
                        <label>
                          <span>Year</span>
                          <input
                            type="number"
                            min="1"
                            max="6"
                            value={module.year}
                            disabled={snapshotDerivedEditingDisabled}
                            onChange={(event) =>
                              updateRecord("modules", module.id, "year", event.target.value)
                            }
                          />
                        </label>
                        <label>
                          <span>Semester</span>
                          <select
                            value={module.semester}
                            disabled={snapshotDerivedEditingDisabled}
                            onChange={(event) =>
                              updateRecord("modules", module.id, "semester", event.target.value)
                            }
                          >
                            <option value={1}>1</option>
                            <option value={2}>2</option>
                          </select>
                        </label>
                        <label className="checkbox-field">
                          <input
                            type="checkbox"
                            checked={module.is_full_year}
                            disabled={snapshotDerivedEditingDisabled}
                            onChange={(event) =>
                              updateRecord("modules", module.id, "is_full_year", event.target.checked)
                            }
                          />
                          <span>Full-year module</span>
                        </label>
                      </div>
                      <div className="record-actions">
                        <button
                          className="ghost-btn"
                          onClick={() => duplicateRecord("modules", module.id)}
                          disabled={snapshotDerivedEditingDisabled}
                        >
                          Duplicate Module
                        </button>
                        <button
                          className="danger-btn"
                          onClick={() => removeRecord("modules", module.id)}
                          disabled={snapshotDerivedEditingDisabled}
                        >
                          Remove Module
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
              {filteredModules.length > INITIAL_VISIBLE_RECORDS && (
                <div className="list-see-more-wrap">
                  <button
                    type="button"
                    className="list-see-more-btn"
                    onClick={() =>
                      setVisibleModuleCount((current) =>
                        current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : filteredModules.length
                      )
                    }
                  >
                    <span
                      className={`list-see-more-arrow ${visibleModuleCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`}
                      aria-hidden="true"
                    />
                    {visibleModuleCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                  </button>
                </div>
              )}
              </div>
            </section>
          </>
        )}

        {currentStep === "sessions" && (
          <>
            <StepIntro stepKey="sessions" />
            <section className="studio-card">
              <div className="section-row">
                <div>
                  <h2>Sessions</h2>
                  <p>
                    Use advanced options for auto-splitting oversized cohorts, specific labs,
                    and same-time parallel delivery.
                  </p>
                </div>
                <div className="record-actions">
                  <button
                    className="ghost-btn"
                    onClick={() => {
                      const defaultModuleId = moduleOptions[0]?.id || "";
                      const defaultModule = moduleOptions.find((module) => module.id === defaultModuleId);
                      setTempSession({
                        moduleId: defaultModuleId,
                        linkedModuleIds: [],
                        name: defaultModule ? `${defaultModule.code} Session` : "",
                        session_type: "lecture",
                        duration_minutes: 60,
                        occurrences_per_week: 1,
                        required_room_type: "lecture",
                        required_lab_type: "",
                        specific_room_id: "",
                        max_students_per_group: "",
                        allow_parallel_rooms: false,
                        notes: "",
                        lecturerIds: [],
                        cohortIds: defaultModule?.defaultCohortIds || [],
                      });
                      setShowSessionModal(true);
                    }}
                    disabled={moduleOptions.length === 0}
                  >
                    Add Session
                  </button>
                </div>
              </div>
              <div className="section-row" style={{ borderBottom: 0, paddingBottom: 0, marginBottom: 0 }}>
                <div className="record-actions">
                  <select
                    className="cohort-year-filter"
                    value={sessionYearFilter}
                    onChange={(e) => setSessionYearFilter(e.target.value)}
                  >
                    <option value="all">All Years</option>
                    {[1, 2, 3, 4].map((y) => (
                      <option key={y} value={y}>
                        Year {y}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="editor-list">
              {filteredSessions.length === 0 ? (
                <p className="empty-state">
                  {sessionYearFilter !== "all"
                    ? `No sessions found for Year ${sessionYearFilter}.`
                    : "No sessions added yet."}
                </p>
              ) : (
                filteredSessions.slice(0, visibleSessionCount).map((session) => {
                  const sessionIndex = draft.sessions.findIndex((entry) => entry.id === session.id) + 1;
                  const sessionIdentityIssue = findRecordIssue(
                    validation.blocking,
                    new RegExp(`^Session ${sessionIndex} is missing module, name, or type\\.$`)
                  );
                  const sessionDurationIssue = findRecordIssue(
                    validation.blocking,
                    new RegExp(`^Session ${sessionIndex} duration must be a positive multiple of 30\\.$`)
                  );
                  const sessionOccurrenceIssue = findRecordIssue(
                    validation.blocking,
                    new RegExp(`^Session ${sessionIndex} needs a valid weekly occurrence count\\.$`)
                  );
                  const sessionCohortIssue = findRecordIssue(
                    validation.blocking,
                    new RegExp(`^Session ${sessionIndex} must target at least one cohort\\.$`)
                  );

                  return (
                  <div key={session.id} className="editor-card">
                    <div className="form-grid four-column">
                      <label>
                        <span>Module</span>
                        <select
                          className={invalidClass(sessionIdentityIssue)}
                          value={session.moduleId}
                          onChange={async (event) => {
                            updateRecord("sessions", session.id, "moduleId", event.target.value);
                            await persistSnapshotRecordUpdate("sessions", {
                              ...session,
                              moduleId: event.target.value,
                            });
                          }}
                        >
                          <option value="">Select module</option>
                          {moduleOptions.map((module) => (
                            <option key={module.id} value={module.id}>
                              {module.code} - {module.name}
                            </option>
                          ))}
                        </select>
                        {sessionIdentityIssue && <small className="field-hint invalid">{sessionIdentityIssue}</small>}
                      </label>
                      <label>
                        <span>Name</span>
                        <input
                          className={invalidClass(sessionIdentityIssue)}
                          value={session.name}
                          onChange={(event) =>
                            updateRecord("sessions", session.id, "name", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("sessions", session)}
                        />
                        {sessionIdentityIssue && <small className="field-hint invalid">{sessionIdentityIssue}</small>}
                      </label>
                      <label>
                        <span>Type</span>
                        <input
                          className={invalidClass(sessionIdentityIssue)}
                          value={session.session_type}
                          onChange={(event) =>
                            updateRecord("sessions", session.id, "session_type", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("sessions", session)}
                        />
                        {sessionIdentityIssue && <small className="field-hint invalid">{sessionIdentityIssue}</small>}
                      </label>
                      <label>
                        <span>Duration</span>
                        <input
                          className={invalidClass(sessionDurationIssue)}
                          type="number"
                          step="30"
                          min="30"
                          value={session.duration_minutes}
                          onChange={(event) =>
                            updateRecord("sessions", session.id, "duration_minutes", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("sessions", session)}
                        />
                        {sessionDurationIssue && (
                          <small className="field-hint invalid">{sessionDurationIssue}</small>
                        )}
                      </label>
                      <label>
                        <span>Occurrences / week</span>
                        <input
                          className={invalidClass(sessionOccurrenceIssue)}
                          type="number"
                          min="1"
                          value={session.occurrences_per_week}
                          onChange={(event) =>
                            updateRecord("sessions", session.id, "occurrences_per_week", event.target.value)
                          }
                          onBlur={() => persistSnapshotRecordUpdate("sessions", session)}
                        />
                        {sessionOccurrenceIssue && (
                          <small className="field-hint invalid">{sessionOccurrenceIssue}</small>
                        )}
                      </label>
                      <label>
                        <span>Required room type</span>
                        <select
                          value={session.required_room_type}
                          onChange={async (event) => {
                            updateRecord("sessions", session.id, "required_room_type", event.target.value);
                            await persistSnapshotRecordUpdate("sessions", {
                              ...session,
                              required_room_type: event.target.value,
                            });
                          }}
                        >
                          <option value="">Any</option>
                          <option value="lecture">Lecture</option>
                          <option value="lab">Lab</option>
                          <option value="seminar">Seminar</option>
                        </select>
                      </label>
                      <div className="full-span">
                        <label>
                          <span>Also counts as modules</span>
                          <SearchableMultiSelect
                            options={moduleOptions.filter(
                              (module) => module.id !== session.moduleId
                            )}
                            selectedIds={session.linkedModuleIds || []}
                            getLabel={(module) => `${module.code} - ${module.name}`}
                            placeholder="Search linked modules..."
                            onChange={async (linkedModuleIds) => {
                              updateRecord("sessions", session.id, "linkedModuleIds", linkedModuleIds);
                              await persistSnapshotRecordUpdate("sessions", {
                                ...session,
                                linkedModuleIds,
                              });
                            }}
                          />
                          <small className="field-hint">
                            Use this when one real lecture, tutorial, or lab should appear under
                            more than one module identity for different degree or path groups.
                          </small>
                        </label>
                      </div>
                    </div>

                    <div className="advanced-session">
                      <h3>Advanced options</h3>
                      <p className="helper-copy">
                        A split limit lets the generator divide one large cohort into internal parts
                        when a single room cannot hold everyone. You do not need to create manual
                        override groups for that case.
                      </p>
                      <div className="form-grid four-column">
                        <label>
                          <span>Specific room</span>
                          <select
                            value={session.specific_room_id}
                            onChange={async (event) => {
                              updateRecord("sessions", session.id, "specific_room_id", event.target.value);
                              await persistSnapshotRecordUpdate("sessions", {
                                ...session,
                                specific_room_id: event.target.value,
                              });
                            }}
                          >
                            <option value="">Any matching room</option>
                            {roomOptions.map((room) => (
                              <option key={room.id} value={room.id}>
                                {room.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          <span>Required lab type</span>
                          <input
                            value={session.required_lab_type}
                            onChange={(event) =>
                              updateRecord("sessions", session.id, "required_lab_type", event.target.value)
                            }
                            onBlur={() => persistSnapshotRecordUpdate("sessions", session)}
                          />
                        </label>
                        <label>
                          <span>Split limit per room</span>
                          <input
                            type="number"
                            min="1"
                            value={session.max_students_per_group}
                            onChange={(event) =>
                              updateRecord(
                                "sessions",
                                session.id,
                                "max_students_per_group",
                                event.target.value
                              )
                            }
                            onBlur={() => persistSnapshotRecordUpdate("sessions", session)}
                          />
                        </label>
                        <label className="checkbox-field">
                          <input
                            type="checkbox"
                            checked={session.allow_parallel_rooms}
                            onChange={async (event) => {
                              updateRecord(
                                "sessions",
                                session.id,
                                "allow_parallel_rooms",
                                event.target.checked
                              );
                              await persistSnapshotRecordUpdate("sessions", {
                                ...session,
                                allow_parallel_rooms: event.target.checked,
                              });
                            }}
                          />
                          <span>Same-time parallel rooms for all split parts</span>
                        </label>
                        <label className="full-span">
                          <span>Notes</span>
                          <textarea
                            className="compact-textarea"
                            value={session.notes}
                            onChange={(event) =>
                              updateRecord("sessions", session.id, "notes", event.target.value)
                            }
                            onBlur={() => persistSnapshotRecordUpdate("sessions", session)}
                          />
                        </label>
                      </div>
                    </div>

                    <div className="selection-grid">
                      <div>
                        <h3>Lecturers</h3>
                        <SearchableMultiSelect
                          options={lecturerOptions}
                          selectedIds={session.lecturerIds}
                          onChange={async (ids) => {
                            updateRecord("sessions", session.id, "lecturerIds", ids);
                            await persistSnapshotRecordUpdate("sessions", {
                              ...session,
                              lecturerIds: ids,
                            });
                          }}
                          getLabel={(l) => l.name}
                          placeholder="Search lecturers..."
                        />
                      </div>
                      <div>
                        <h3>Attending cohorts</h3>
                        <div className="session-cohort-year-filter">
                          <select
                            value={sessionCohortYearFilter}
                            onChange={(e) => setSessionCohortYearFilter(Number(e.target.value))}
                          >
                            {[2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015].map((y) => (
                              <option key={y} value={y}>
                                {y}
                              </option>
                            ))}
                          </select>
                        </div>
                        {sessionCohortIssue && <p className="field-hint invalid">{sessionCohortIssue}</p>}
                        <SearchableMultiSelect
                          options={filteredCohortsByYear}
                          selectedIds={session.cohortIds}
                          onChange={async (ids) => {
                            updateRecord("sessions", session.id, "cohortIds", ids);
                            await persistSnapshotRecordUpdate("sessions", {
                              ...session,
                              cohortIds: ids,
                            });
                          }}
                          getLabel={(c) => c.name || "Unnamed cohort"}
                          placeholder="Search cohorts..."
                        />
                      </div>
                    </div>

                    <div className="record-actions">
                      <button className="danger-btn" onClick={() => removeRecord("sessions", session.id)}>
                        Remove Session
                      </button>
                    </div>
                  </div>
                );
                })
              )}
              {filteredSessions.length > INITIAL_VISIBLE_RECORDS && (
                <div className="list-see-more-wrap">
                  <button
                    type="button"
                    className="list-see-more-btn"
                    onClick={() =>
                      setVisibleSessionCount((current) =>
                        current > INITIAL_VISIBLE_RECORDS ? INITIAL_VISIBLE_RECORDS : filteredSessions.length
                      )
                    }
                  >
                    <span
                      className={`list-see-more-arrow ${visibleSessionCount > INITIAL_VISIBLE_RECORDS ? "is-open" : ""}`}
                      aria-hidden="true"
                    />
                    {visibleSessionCount > INITIAL_VISIBLE_RECORDS ? "See less" : "See more"}
                  </button>
                </div>
              )}
              </div>
            </section>
          </>
        )}

        {currentStep === "review" && (
          <div className="studio-grid two-column">
            <StepIntro stepKey="review" />
            <section className="studio-card">
              <h2>Ready to Generate</h2>
              {validation.blocking.length === 0 ? (
                <div className="info-banner">This setup is ready for timetable generation.</div>
              ) : (
                <div className="error-banner">
                  <strong>Fix these blocking issues before generation:</strong>
                  <ul>
                    {validation.blocking.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}

              {validation.warnings.length > 0 && (
                <div className="schema-notes">
                  <h3>Warnings to review</h3>
                  <ul>
                    {summarizeValidationWarnings(validation.warnings, {
                      snapshotMode: Boolean(activeImportRunId),
                    }).map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="schema-notes">
                <h3>What this setup currently defines</h3>
                <ul>
                  <li>rooms and room capabilities</li>
                  <li>lecturers used by generation, views, and verification</li>
                  <li>shared teaching sessions linked to imported attendance groups</li>
                  <li>delivery rules such as split limits, parallel rooms, and specific-room requirements</li>
                </ul>
              </div>
            </section>

            <section className="studio-card">
              <h2>Where This Data Came From</h2>
              <div className="schema-notes">
                <h3>Imported student enrolments</h3>
                <div className="summary-grid">
                  {Object.entries(materializedImport?.counts || {}).map(([key, value]) => (
                    <div key={key} className="summary-item">
                      <span>{key.replace(/_/g, " ")}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
                <p>
                  The CSV import flow lives at the top of the page. This step is the final check
                  before moving to generation.
                </p>
              </div>
            </section>
          </div>
        )}

        <div className="wizard-footer">
          <button className="ghost-btn" onClick={prevStep} disabled={activeStep === 0}>
            Back
          </button>
          <button
            className="primary-btn"
            onClick={nextStep}
            disabled={
              activeStep === visibleSteps.length - 1 ||
              blockedSteps[visibleSteps[Math.min(activeStep + 1, visibleSteps.length - 1)].key]
            }
          >
            Continue
          </button>
        </div>
          </>
        ) : (
          <section className="studio-card">
            <h2>Next step</h2>
            <p>Use the import first. The manual completion wizard will appear after that.</p>
          </section>
        )}
      </div>

      {showDegreeModal && (
        <div className="modal-overlay" onClick={() => setShowDegreeModal(false)}>
          <div className="modal-card setup-add-modal" onClick={(e) => e.stopPropagation()}>
            <div className="setup-add-modal-header">
              <div className="setup-add-modal-title-block">
                <span className="setup-add-modal-kicker">Degree setup</span>
                <h3>Add New Degree</h3>
                <p>Enter the core details once, then save it into the structure list.</p>
              </div>
              <button type="button" className="setup-add-modal-close" onClick={() => setShowDegreeModal(false)}>
                Close
              </button>
            </div>

            <div className="setup-add-modal-body">
              <div className="form-grid two-column">
                <label>
                  <span>Code</span>
                  <input
                    type="text"
                    value={tempDegree.code}
                    onChange={(e) => setTempDegree({ ...tempDegree, code: e.target.value })}
                    placeholder="e.g., CS"
                  />
                </label>
                <label>
                  <span>Duration (years)</span>
                  <input
                    type="number"
                    min="1"
                    max="6"
                    value={tempDegree.duration_years}
                    onChange={(e) => setTempDegree({ ...tempDegree, duration_years: Number(e.target.value) })}
                  />
                </label>
                <label className="full-span">
                  <span>Name</span>
                  <input
                    type="text"
                    value={tempDegree.name}
                    onChange={(e) => setTempDegree({ ...tempDegree, name: e.target.value })}
                    placeholder="e.g., Computer Science"
                  />
                </label>
                <label className="full-span">
                  <span>Intake Label</span>
                  <input
                    type="text"
                    value={tempDegree.intake_label}
                    onChange={(e) => setTempDegree({ ...tempDegree, intake_label: e.target.value })}
                    placeholder="e.g., CS Intake"
                  />
                </label>
              </div>
            </div>

            <div className="setup-add-modal-footer">
              <p>Cancel closes this window without adding anything.</p>
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={() => setShowDegreeModal(false)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  onClick={() => {
                    addRecord("degrees", {
                      id: makeId("degree"),
                      code: tempDegree.code,
                      name: tempDegree.name,
                      duration_years: tempDegree.duration_years,
                      intake_label: tempDegree.intake_label,
                    });
                    setVisibleDegreeCount((current) => current + 1);
                    setShowDegreeModal(false);
                  }}
                >
                  Save Degree
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showPathModal && (
        <div className="modal-overlay" onClick={() => setShowPathModal(false)}>
          <div className="modal-card setup-add-modal" onClick={(e) => e.stopPropagation()}>
            <div className="setup-add-modal-header">
              <div className="setup-add-modal-title-block">
                <span className="setup-add-modal-kicker">Path setup</span>
                <h3>Add New Path</h3>
                <p>Choose the degree and year first, then add the path code and display name.</p>
              </div>
              <button type="button" className="setup-add-modal-close" onClick={() => setShowPathModal(false)}>
                Close
              </button>
            </div>

            <div className="setup-add-modal-body">
              <div className="form-grid two-column">
                <label>
                  <span>Degree</span>
                  <select
                    value={tempPath.degreeId}
                    onChange={(e) => setTempPath({ ...tempPath, degreeId: e.target.value })}
                  >
                    <option value="">Select degree</option>
                    {draft.degrees.map((degree) => (
                      <option key={degree.id} value={degree.id}>
                        {degree.code} - {degree.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Year</span>
                  <input
                    type="number"
                    min="1"
                    max="6"
                    value={tempPath.year}
                    onChange={(e) => setTempPath({ ...tempPath, year: Number(e.target.value) })}
                  />
                </label>
                <label>
                  <span>Code</span>
                  <input
                    type="text"
                    value={tempPath.code}
                    onChange={(e) => setTempPath({ ...tempPath, code: e.target.value })}
                    placeholder="e.g., CS-GENERAL"
                  />
                </label>
                <label>
                  <span>Name</span>
                  <input
                    type="text"
                    value={tempPath.name}
                    onChange={(e) => setTempPath({ ...tempPath, name: e.target.value })}
                    placeholder="e.g., Computer Science General"
                  />
                </label>
              </div>
            </div>

            <div className="setup-add-modal-footer">
              <p>Save adds the path to the draft, ready for the main dataset save.</p>
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={() => setShowPathModal(false)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  onClick={() => {
                    addRecord("paths", {
                      id: makeId("path"),
                      degreeId: tempPath.degreeId,
                      year: tempPath.year,
                      code: tempPath.code,
                      name: tempPath.name,
                    });
                    setVisiblePathCount((current) => current + 1);
                    setShowPathModal(false);
                  }}
                >
                  Save Path
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showLecturerModal && (
        <div className="modal-overlay" onClick={() => setShowLecturerModal(false)}>
          <div className="modal-card setup-add-modal" onClick={(e) => e.stopPropagation()}>
            <div className="setup-add-modal-header">
              <div className="setup-add-modal-title-block">
                <span className="setup-add-modal-kicker">Lecturer setup</span>
                <h3>Add New Lecturer</h3>
                <p>
                  {activeImportRunId
                    ? "Enter the lecturer details and save them into the active import snapshot."
                    : "Enter the lecturer details and save directly into the current setup dataset."}
                </p>
              </div>
              <button type="button" className="setup-add-modal-close" onClick={() => setShowLecturerModal(false)}>
                Close
              </button>
            </div>

            <div className="setup-add-modal-body">
              <div className="form-grid two-column">
                <label>
                  <span>Name</span>
                  <input
                    type="text"
                    value={tempLecturer.name}
                    onChange={(e) => setTempLecturer({ ...tempLecturer, name: e.target.value })}
                    placeholder="e.g., Dr. Perera"
                  />
                </label>
                <label>
                  <span>Email</span>
                  <input
                    type="email"
                    value={tempLecturer.email}
                    onChange={(e) => setTempLecturer({ ...tempLecturer, email: e.target.value })}
                    placeholder="e.g., lecturer@science.ac.lk"
                  />
                </label>
              </div>
            </div>

            <div className="setup-add-modal-footer">
              <p>
                {activeImportRunId
                  ? "Save writes the lecturer to the active import snapshot."
                  : "Save writes the lecturer to the current setup dataset."}
              </p>
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={() => setShowLecturerModal(false)} disabled={saving}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  disabled={saving}
                  onClick={async () => {
                    const lecturer = {
                      id: makeId("lecturer"),
                      name: tempLecturer.name,
                      email: tempLecturer.email,
                    };
                    const saved = await persistAddedRecord(
                      "lecturers",
                      lecturer,
                      "Lecturer saved to the setup dataset."
                    );
                    if (saved) {
                      setVisibleLecturerCount((current) => current + 1);
                      setShowLecturerModal(false);
                    }
                  }}
                >
                  {saving ? "Saving..." : "Save Lecturer"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showRoomModal && (
        <div className="modal-overlay" onClick={() => setShowRoomModal(false)}>
          <div className="modal-card setup-add-modal" onClick={(e) => e.stopPropagation()}>
            <div className="setup-add-modal-header">
              <div className="setup-add-modal-title-block">
                <span className="setup-add-modal-kicker">Room setup</span>
                <h3>Add New Room</h3>
                <p>
                  {activeImportRunId
                    ? "Capture the room details and save them into the active import snapshot."
                    : "Capture the room details and save them directly into the current setup dataset."}
                </p>
              </div>
              <button type="button" className="setup-add-modal-close" onClick={() => setShowRoomModal(false)}>
                Close
              </button>
            </div>

            <div className="setup-add-modal-body">
              <div className="form-grid two-column">
                <label>
                  <span>Name</span>
                  <input
                    type="text"
                    value={tempRoom.name}
                    onChange={(e) => setTempRoom({ ...tempRoom, name: e.target.value })}
                    placeholder="e.g., Hall A"
                  />
                </label>
                <label>
                  <span>Capacity</span>
                  <input
                    type="number"
                    min="1"
                    value={tempRoom.capacity}
                    onChange={(e) => setTempRoom({ ...tempRoom, capacity: e.target.value })}
                  />
                </label>
                <label>
                  <span>Room type</span>
                  <select
                    value={tempRoom.room_type}
                    onChange={(e) => setTempRoom({ ...tempRoom, room_type: e.target.value })}
                  >
                    <option value="lecture">Lecture</option>
                    <option value="lab">Lab</option>
                    <option value="seminar">Seminar</option>
                  </select>
                </label>
                <label>
                  <span>Lab type</span>
                  <input
                    type="text"
                    value={tempRoom.lab_type}
                    onChange={(e) => setTempRoom({ ...tempRoom, lab_type: e.target.value })}
                    placeholder="e.g., Chemistry"
                  />
                </label>
                <label>
                  <span>Location</span>
                  <input
                    type="text"
                    value={tempRoom.location}
                    onChange={(e) => setTempRoom({ ...tempRoom, location: e.target.value })}
                    placeholder="e.g., Science Building"
                  />
                </label>
                <label>
                  <span>Year restriction</span>
                  <input
                    type="number"
                    min="1"
                    max="6"
                    value={tempRoom.year_restriction}
                    onChange={(e) => setTempRoom({ ...tempRoom, year_restriction: e.target.value })}
                  />
                </label>
              </div>
            </div>

            <div className="setup-add-modal-footer">
              <p>
                {activeImportRunId
                  ? "Save writes the room to the active import snapshot."
                  : "Save writes the room to the current setup dataset."}
              </p>
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={() => setShowRoomModal(false)} disabled={saving}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  disabled={saving}
                  onClick={async () => {
                    const room = {
                      id: makeId("room"),
                      name: tempRoom.name,
                      capacity: tempRoom.capacity,
                      room_type: tempRoom.room_type,
                      lab_type: tempRoom.lab_type,
                      location: tempRoom.location,
                      year_restriction: tempRoom.year_restriction,
                    };
                    const saved = await persistAddedRecord(
                      "rooms",
                      room,
                      "Room saved to the setup dataset."
                    );
                    if (saved) {
                      setVisibleRoomCount((current) => current + 1);
                      setShowRoomModal(false);
                    }
                  }}
                >
                  {saving ? "Saving..." : "Save Room"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showModuleModal && (
        <div className="modal-overlay" onClick={() => setShowModuleModal(false)}>
          <div className="modal-card setup-add-modal" onClick={(e) => e.stopPropagation()}>
            <div className="setup-add-modal-header">
              <div className="setup-add-modal-title-block">
                <span className="setup-add-modal-kicker">Module setup</span>
                <h3>Add New Module</h3>
                <p>Enter the module details and save them directly into the current setup dataset.</p>
              </div>
              <button type="button" className="setup-add-modal-close" onClick={() => setShowModuleModal(false)}>
                Close
              </button>
            </div>

            <div className="setup-add-modal-body">
              <div className="form-grid two-column">
                <label>
                  <span>Code</span>
                  <input
                    type="text"
                    value={tempModule.code}
                    onChange={(e) => setTempModule({ ...tempModule, code: e.target.value })}
                    placeholder="e.g., CS101"
                  />
                </label>
                <label>
                  <span>Year</span>
                  <input
                    type="number"
                    min="1"
                    max="6"
                    value={tempModule.year}
                    onChange={(e) => setTempModule({ ...tempModule, year: Number(e.target.value) })}
                  />
                </label>
                <label>
                  <span>Name</span>
                  <input
                    type="text"
                    value={tempModule.name}
                    onChange={(e) => setTempModule({ ...tempModule, name: e.target.value })}
                    placeholder="e.g., Introduction to Programming"
                  />
                </label>
                <label>
                  <span>Semester</span>
                  <select
                    value={tempModule.semester}
                    onChange={(e) => setTempModule({ ...tempModule, semester: Number(e.target.value) })}
                  >
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                  </select>
                </label>
                <label>
                  <span>Subject</span>
                  <input
                    type="text"
                    value={tempModule.subject_name}
                    onChange={(e) => setTempModule({ ...tempModule, subject_name: e.target.value })}
                    placeholder="e.g., Computer Science"
                  />
                </label>
                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={tempModule.is_full_year}
                    onChange={(e) => setTempModule({ ...tempModule, is_full_year: e.target.checked })}
                  />
                  <span>Full-year module</span>
                </label>
              </div>
            </div>

            <div className="setup-add-modal-footer">
              <p>Save writes the module to the current setup dataset.</p>
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={() => setShowModuleModal(false)} disabled={saving}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  disabled={saving}
                  onClick={async () => {
                    const module = {
                      id: makeId("module"),
                      code: tempModule.code,
                      name: tempModule.name,
                      subject_name: tempModule.subject_name,
                      year: tempModule.year,
                      semester: tempModule.semester,
                      is_full_year: tempModule.is_full_year,
                    };
                    const saved = await persistAddedRecord(
                      "modules",
                      module,
                      "Module saved to the setup dataset."
                    );
                    if (saved) {
                      setVisibleModuleCount((current) => current + 1);
                      setShowModuleModal(false);
                    }
                  }}
                >
                  {saving ? "Saving..." : "Save Module"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showOverrideCohortModal && (
        <div className="modal-overlay" onClick={() => setShowOverrideCohortModal(false)}>
          <div className="modal-card setup-add-modal" onClick={(e) => e.stopPropagation()}>
            <div className="setup-add-modal-header">
              <div className="setup-add-modal-title-block">
                <span className="setup-add-modal-kicker">Cohort setup</span>
                <h3>Add New Override Group</h3>
                <p>Enter the override group details and save them directly into the current setup dataset.</p>
              </div>
              <button type="button" className="setup-add-modal-close" onClick={() => setShowOverrideCohortModal(false)}>
                Close
              </button>
            </div>

            <div className="setup-add-modal-body">
              <div className="form-grid two-column">
                <label>
                  <span>Degree</span>
                  <select
                    value={tempOverrideCohort.degreeId}
                    onChange={(e) => setTempOverrideCohort({ ...tempOverrideCohort, degreeId: e.target.value, pathId: "" })}
                  >
                    <option value="">Select degree</option>
                    {degreeOptions.map((degree) => (
                      <option key={degree.id} value={degree.id}>
                        {degree.code}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Year</span>
                  <input
                    type="number"
                    min="1"
                    max="6"
                    value={tempOverrideCohort.year}
                    onChange={(e) => setTempOverrideCohort({ ...tempOverrideCohort, year: Number(e.target.value) })}
                  />
                </label>
                <label>
                  <span>Path</span>
                  <select
                    value={tempOverrideCohort.pathId}
                    onChange={(e) => setTempOverrideCohort({ ...tempOverrideCohort, pathId: e.target.value })}
                  >
                    <option value="">General</option>
                    {pathOptions
                      .filter((path) => path.degreeId === tempOverrideCohort.degreeId)
                      .map((path) => (
                        <option key={path.id} value={path.id}>
                          {path.code}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  <span>Student count</span>
                  <input
                    type="number"
                    min="1"
                    value={tempOverrideCohort.size}
                    onChange={(e) => setTempOverrideCohort({ ...tempOverrideCohort, size: e.target.value })}
                  />
                </label>
                <label>
                  <span>Calendar year</span>
                  <select
                    value={tempOverrideCohort.cohort_year || currentYear}
                    onChange={(e) => setTempOverrideCohort({ ...tempOverrideCohort, cohort_year: Number(e.target.value) })}
                  >
                    {[2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015].map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="full-span">
                  <span>Override name</span>
                  <input
                    type="text"
                    value={tempOverrideCohort.name}
                    onChange={(e) => setTempOverrideCohort({ ...tempOverrideCohort, name: e.target.value })}
                    placeholder="e.g., Elective Group A"
                  />
                </label>
              </div>
            </div>

            <div className="setup-add-modal-footer">
              <p>Save writes the override group to the current setup dataset.</p>
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={() => setShowOverrideCohortModal(false)} disabled={saving}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  disabled={saving}
                  onClick={async () => {
                    const cohort = {
                      id: makeId("cohort"),
                      kind: "override",
                      degreeId: tempOverrideCohort.degreeId,
                      year: tempOverrideCohort.year,
                      pathId: tempOverrideCohort.pathId,
                      name: tempOverrideCohort.name,
                      size: tempOverrideCohort.size,
                      cohort_year: tempOverrideCohort.cohort_year || currentYear,
                    };
                    const saved = await persistAddedRecord(
                      "cohorts",
                      cohort,
                      "Override group saved to the setup dataset."
                    );
                    if (saved) {
                      setVisibleOverrideCohortCount((current) => current + 1);
                      setShowOverrideCohortModal(false);
                    }
                  }}
                >
                  {saving ? "Saving..." : "Save Override"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showSessionModal && (
        <div className="modal-overlay" onClick={() => setShowSessionModal(false)}>
          <div className="modal-card setup-add-modal" onClick={(e) => e.stopPropagation()}>
            <div className="setup-add-modal-header">
              <div className="setup-add-modal-title-block">
                <span className="setup-add-modal-kicker">Session setup</span>
                <h3>Add New Session</h3>
                <p>
                  {activeImportRunId
                    ? "Enter the shared session details and save them into the active import snapshot."
                    : "Enter the session details and save them directly into the current setup dataset."}
                </p>
              </div>
              <button type="button" className="setup-add-modal-close" onClick={() => setShowSessionModal(false)}>
                Close
              </button>
            </div>

            <div className="setup-add-modal-body">
              <div className="form-grid two-column">
                <label>
                  <span>Module</span>
                  <select
                    value={tempSession.moduleId}
                    onChange={(e) => handleTempSessionModuleChange(e.target.value)}
                  >
                    <option value="">Select module</option>
                    {moduleOptions.map((module) => (
                      <option key={module.id} value={module.id}>
                        {module.code} - {module.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Session name</span>
                  <input
                    type="text"
                    value={tempSession.name}
                    onChange={(e) => setTempSession({ ...tempSession, name: e.target.value })}
                    placeholder="e.g., Lecture 1"
                  />
                </label>
                <label>
                  <span>Session type</span>
                  <select
                    value={tempSession.session_type}
                    onChange={(e) => setTempSession({ ...tempSession, session_type: e.target.value })}
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
                    value={tempSession.duration_minutes}
                    onChange={(e) => setTempSession({ ...tempSession, duration_minutes: Number(e.target.value) })}
                  />
                </label>
                <label>
                  <span>Occurrences per week</span>
                  <input
                    type="number"
                    min="1"
                    value={tempSession.occurrences_per_week}
                    onChange={(e) => setTempSession({ ...tempSession, occurrences_per_week: Number(e.target.value) })}
                  />
                </label>
                <label>
                  <span>Required room type</span>
                  <select
                    value={tempSession.required_room_type}
                    onChange={(e) => setTempSession({ ...tempSession, required_room_type: e.target.value })}
                  >
                    <option value="lecture">Lecture Hall</option>
                    <option value="lab">Lab</option>
                    <option value="seminar">Seminar Room</option>
                    <option value="any">Any</option>
                  </select>
                </label>
                <label>
                  <span>Required lab type</span>
                  <input
                    type="text"
                    value={tempSession.required_lab_type}
                    onChange={(e) => setTempSession({ ...tempSession, required_lab_type: e.target.value })}
                    placeholder="e.g., Chemistry"
                  />
                </label>
                <label>
                  <span>Specific room</span>
                  <select
                    value={tempSession.specific_room_id}
                    onChange={(e) => setTempSession({ ...tempSession, specific_room_id: e.target.value })}
                  >
                    <option value="">Any room</option>
                    {roomOptions.map((room) => (
                      <option key={room.id} value={room.id}>
                        {room.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="schema-notes compact">
                <h3>Shared teaching and attendance</h3>
                <p>
                  Define the real teaching event once, then link any extra curriculum modules and
                  the attendance groups that actually attend it.
                </p>
              </div>

              <div className="form-grid two-column">
                <label>
                  <span>Linked modules</span>
                  <SearchableMultiSelect
                    items={moduleOptions
                      .filter((module) => module.id !== tempSession.moduleId)
                      .map((module) => ({
                        id: module.id,
                        label: `${module.code} - ${module.name}`,
                      }))}
                    selectedIds={tempSession.linkedModuleIds || []}
                    searchPlaceholder="Search linked modules"
                    emptyMessage="No additional modules"
                    onChange={(linkedModuleIds) =>
                      setTempSession({ ...tempSession, linkedModuleIds })
                    }
                  />
                  <small className="field-hint">
                    Use this when one real lecture, tutorial, or lab should appear under more than
                    one module identity.
                  </small>
                </label>
                <label>
                  <span>Lecturers</span>
                  <SearchableMultiSelect
                    items={lecturerOptions.map((lecturer) => ({
                      id: lecturer.id,
                      label: lecturer.name,
                    }))}
                    selectedIds={tempSession.lecturerIds || []}
                    searchPlaceholder="Search lecturers"
                    emptyMessage="No lecturers"
                    onChange={(lecturerIds) => setTempSession({ ...tempSession, lecturerIds })}
                  />
                </label>
                <label className="full-span">
                  <span>Attendance groups</span>
                  <SearchableMultiSelect
                    items={cohortOptions.map((cohort) => ({
                      id: cohort.id,
                      label: `${cohort.name} (${cohort.size || "?"} students)`,
                    }))}
                    selectedIds={tempSession.cohortIds || []}
                    searchPlaceholder="Search attendance groups"
                    emptyMessage="No attendance groups"
                    onChange={(cohortIds) => setTempSession({ ...tempSession, cohortIds })}
                  />
                </label>
              </div>

              <div className="schema-notes compact">
                <h3>Delivery options</h3>
                <p>
                  Use split groups when one cohort must attend at different times. Use parallel
                  rooms when the same session should run at the same time in multiple rooms with
                  multiple lecturers.
                </p>
              </div>

              <div className="form-grid two-column">
                <label>
                  <span>Max students per time-separated group</span>
                  <input
                    type="number"
                    min="1"
                    value={tempSession.max_students_per_group}
                    onChange={(e) =>
                      setTempSession({ ...tempSession, max_students_per_group: e.target.value })
                    }
                    placeholder="Leave blank for no split"
                  />
                  <small className="field-hint">
                    Example: set `24` to let the solver split one large lab into multiple smaller
                    lab groups at different times.
                  </small>
                </label>
                <label className="checkbox-field full-span">
                  <span>Same-time parallel rooms</span>
                  <input
                    type="checkbox"
                    checked={tempSession.allow_parallel_rooms}
                    onChange={(e) =>
                      setTempSession({ ...tempSession, allow_parallel_rooms: e.target.checked })
                    }
                  />
                  <small className="field-hint">
                    Turn this on only when the session may run at the same time in multiple rooms
                    with separate lecturers.
                  </small>
                </label>
                <label className="full-span">
                  <span>Notes</span>
                  <textarea
                    rows="3"
                    value={tempSession.notes}
                    onChange={(e) => setTempSession({ ...tempSession, notes: e.target.value })}
                    placeholder="Optional delivery notes or room guidance"
                  />
                </label>
              </div>
            </div>

            <div className="setup-add-modal-footer">
              <p>
                Save writes this shared teaching session into the active import snapshot.
              </p>
              <div className="modal-actions">
                <button type="button" className="ghost-btn" onClick={() => setShowSessionModal(false)} disabled={saving}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary-btn"
                  disabled={saving}
                  onClick={async () => {
                    const session = {
                      id: makeId("session"),
                      moduleId: tempSession.moduleId,
                      linkedModuleIds: tempSession.linkedModuleIds,
                      name: tempSession.name,
                      session_type: tempSession.session_type,
                      duration_minutes: tempSession.duration_minutes,
                      occurrences_per_week: tempSession.occurrences_per_week,
                      required_room_type: tempSession.required_room_type,
                      required_lab_type: tempSession.required_lab_type,
                      specific_room_id: tempSession.specific_room_id,
                      max_students_per_group: tempSession.max_students_per_group,
                      allow_parallel_rooms: tempSession.allow_parallel_rooms,
                      notes: tempSession.notes,
                      lecturerIds: tempSession.lecturerIds,
                      cohortIds: tempSession.cohortIds,
                    };
                    const saved = await persistAddedRecord(
                      "sessions",
                      session,
                      `Session saved to import snapshot #${activeImportRunId}.`
                    );
                    if (saved) {
                      setVisibleSessionCount((current) => current + 1);
                      setShowSessionModal(false);
                    }
                  }}
                >
                  {saving ? "Saving..." : "Save Session"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SetupStudio;
