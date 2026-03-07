import React, { useEffect, useMemo, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";

const steps = [
  { key: "structure", label: "Structure" },
  { key: "lecturers", label: "Lecturers" },
  { key: "rooms", label: "Rooms" },
  { key: "cohorts", label: "Student Cohorts" },
  { key: "modules", label: "Modules" },
  { key: "sessions", label: "Sessions" },
  { key: "review", label: "Review & Save" },
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
    "Use this review step before saving. Blocking issues must be fixed first. Warnings are allowed, but they usually indicate incomplete staffing or unusual delivery choices.",
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

function validateDraft(draft) {
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
    if (!Number(cohort.size) || Number(cohort.size) <= 0) {
      blocking.push(`Base cohort ${index + 1} needs a positive student count.`);
    }
  });

  draft.cohorts
    .filter((cohort) => cohort.kind === "override")
    .forEach((cohort, index) => {
      if (!cohort.degreeId || !cohort.name.trim()) {
        blocking.push(`Override group ${index + 1} is missing degree or name.`);
      }
      if (!Number(cohort.size) || Number(cohort.size) <= 0) {
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
      warnings.push(`Session "${session.name || `#${index + 1}`}" has no lecturer assigned.`);
    }
    if (session.cohortIds.length === 0) {
      blocking.push(`Session ${index + 1} must target at least one cohort.`);
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

function StepChecks({ stepKey, validation }) {
  if (stepKey === "review") {
    return null;
  }

  const feedback = currentStepFeedback(stepKey, validation);
  if (feedback.blocking.length === 0 && feedback.warnings.length === 0) {
    return (
      <section className="studio-card">
        <div className="info-banner">No current issues detected for this step.</div>
      </section>
    );
  }

  return (
    <section className="studio-card">
      <h2>Current Step Checks</h2>
      {feedback.blocking.length > 0 && (
        <div className="error-banner">
          <strong>Fix these on this step:</strong>
          <ul>
            {feedback.blocking.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
      {feedback.warnings.length > 0 && (
        <div className="schema-notes">
          <h3>Warnings for this step</h3>
          <ul>
            {feedback.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
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

function SetupStudio() {
  const [draft, setDraft] = useState(emptyDraft);
  const [summary, setSummary] = useState(toSummary(emptyDraft));
  const [activeStep, setActiveStep] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const validation = useMemo(() => validateDraft(draft), [draft]);

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

  const loadDataset = async (nextStatus = "") => {
    setLoading(true);
    setError("");
    try {
      const dataset = await timetableStudioService.getFullDataset();
      const normalized = normalizeDataset(dataset);
      setDraft(normalized);
      setSummary(toSummary(normalized));
      setStatus(nextStatus);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDataset();
  }, []);

  const updateDraft = (updater) => {
    setDraft((current) => {
      const next = typeof updater === "function" ? updater(current) : updater;
      const synced = syncBaseCohorts(next);
      setSummary(toSummary(synced));
      return synced;
    });
  };

  const goToStep = (index) => {
    if (blockedSteps[steps[index].key]) {
      return;
    }
    setActiveStep(index);
  };

  const nextStep = () => {
    const nextIndex = Math.min(activeStep + 1, steps.length - 1);
    if (!blockedSteps[steps[nextIndex].key]) {
      setActiveStep(nextIndex);
    }
  };

  const prevStep = () => {
    setActiveStep((current) => Math.max(current - 1, 0));
  };

  const handleLoadDemo = async (profile) => {
    setSaving(true);
    setError("");
    try {
      await timetableStudioService.loadDemoDataset(profile);
      await loadDataset(
        profile === "tuned"
          ? "Tuned demo dataset loaded into the guided setup wizard."
          : "Realistic demo dataset loaded from the real enrollment baseline into the guided setup wizard."
      );
      setActiveStep(steps.length - 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const payload = buildPayload(draft);
      const response = await timetableStudioService.saveDataset(payload);
      await loadDataset("Dataset saved. The new setup flow is now ready for generation.");
      setSummary(response.summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const addRecord = (collection, record) => {
    updateDraft((current) => ({
      ...current,
      [collection]: [...current[collection], record],
    }));
  };

  const duplicateRecord = (collection, id) => {
    updateDraft((current) => {
      const source = current[collection].find((record) => record.id === id);
      if (!source) {
        return current;
      }
      return {
        ...current,
        [collection]: [
          ...current[collection],
          {
            ...source,
            id: makeId(collection.slice(0, -1) || "item"),
          },
        ],
      };
    });
  };

  const addStarterSessionsFromModules = () => {
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
          cohortIds: [],
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

  const addSessionPatternFromModules = (patternKey) => {
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
            cohortIds: [],
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

  const addRoomTemplateBatch = (templateKey) => {
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

  const addLecturerTemplateBatch = () => {
    const templates = [
      { name: "Dr. Perera", email: "dr.perera@science.kln.ac.lk" },
      { name: "Dr. Silva", email: "dr.silva@science.kln.ac.lk" },
      { name: "Prof. Fernando", email: "prof.fernando@science.kln.ac.lk" },
      { name: "Ms. Jayasinghe", email: "ms.jayasinghe@science.kln.ac.lk" },
    ];

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

  const removeRecord = (collection, id) => {
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

  const currentStep = steps[activeStep].key;

  return (
    <div className="page-shell">
      <div className="panel studio-panel">
        <div className="studio-header">
          <div>
            <h1 className="section-title">Setup Studio</h1>
            <p className="section-subtitle">
              Build the v2 timetable dataset through guided steps, then save one validated draft for generation.
            </p>
          </div>
          <div className="studio-actions wrap">
            <button
              className="ghost-btn"
              onClick={() => handleLoadDemo("realistic")}
              disabled={saving || loading}
            >
              Load Realistic Demo
            </button>
            <button
              className="ghost-btn"
              onClick={() => handleLoadDemo("tuned")}
              disabled={saving || loading}
            >
              Load Tuned Demo
            </button>
            <button
              className="primary-btn"
              onClick={handleSave}
              disabled={saving || loading || validation.blocking.length > 0}
            >
              {saving ? "Saving..." : "Save Dataset"}
            </button>
          </div>
        </div>

        {status && <div className="info-banner valid">{status}</div>}
        {error && <div className="error-banner">{error}</div>}
        {loading && <div className="info-banner">Loading existing v2 dataset...</div>}

        <div className="wizard-steps">
          {steps.map((step, index) => (
            <StepBadge
              key={step.key}
              label={`${index + 1}. ${step.label}`}
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

        <StepChecks stepKey={currentStep} validation={validation} />

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
                  <button className="ghost-btn" onClick={addScienceStructureTemplates}>
                    Load Science Structure Templates
                  </button>
                  <button
                    className="primary-btn"
                    onClick={() =>
                      addRecord("degrees", {
                        id: makeId("degree"),
                        code: "",
                        name: "",
                        duration_years: 3,
                        intake_label: "",
                      })
                    }
                  >
                    Add Degree
                  </button>
                </div>
              </div>
              <div className="editor-list">
                {draft.degrees.length === 0 ? (
                  <p className="empty-state">No degrees added yet.</p>
                ) : (
                  draft.degrees.map((degree, index) => {
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
                  onClick={() =>
                    addRecord("paths", {
                      id: makeId("path"),
                      degreeId: degreeOptions[0]?.id || "",
                      year: 1,
                      code: "",
                      name: "",
                    })
                  }
                  disabled={degreeOptions.length === 0}
                >
                  Add Path
                </button>
              </div>
              <div className="editor-list">
                {draft.paths.length === 0 ? (
                  <p className="empty-state">Direct-entry degrees can be left without paths.</p>
                ) : (
                  draft.paths.map((path, index) => {
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
                              onChange={(event) =>
                                updateRecord("paths", path.id, "name", event.target.value)
                              }
                            />
                            {pathIssue && <small className="field-hint invalid">{pathIssue}</small>}
                          </label>
                        </div>
                        <button className="danger-btn" onClick={() => removeRecord("paths", path.id)}>
                          Remove Path
                        </button>
                      </div>
                    );
                  })
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
                  <button className="ghost-btn" onClick={addLecturerTemplateBatch}>
                    Add Lecturer Templates
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() =>
                      addRecord("lecturers", {
                        id: makeId("lecturer"),
                        name: "",
                        email: "",
                      })
                    }
                  >
                    Add Lecturer
                  </button>
                </div>
              </div>
              <div className="editor-list">
                {draft.lecturers.length === 0 ? (
                  <p className="empty-state">No lecturers added yet.</p>
                ) : (
                  draft.lecturers.map((lecturer) => (
                    <div key={lecturer.id} className="editor-card">
                      <div className="form-grid two-column">
                        <label>
                          <span>Name</span>
                          <input
                            value={lecturer.name}
                            onChange={(event) =>
                              updateRecord("lecturers", lecturer.id, "name", event.target.value)
                            }
                          />
                        </label>
                        <label>
                          <span>Email</span>
                          <input
                            value={lecturer.email}
                            onChange={(event) =>
                              updateRecord("lecturers", lecturer.id, "email", event.target.value)
                            }
                          />
                        </label>
                      </div>
                      <button className="danger-btn" onClick={() => removeRecord("lecturers", lecturer.id)}>
                        Remove Lecturer
                      </button>
                    </div>
                  ))
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
                    onClick={() => addRoomTemplateBatch("lectureHalls")}
                  >
                    Add Lecture Hall Templates
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => addRoomTemplateBatch("labs")}
                  >
                    Add Lab Templates
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() =>
                      addRecord("rooms", {
                        id: makeId("room"),
                        name: "",
                        capacity: "",
                        room_type: "lecture",
                        lab_type: "",
                        location: "",
                        year_restriction: "",
                      })
                    }
                  >
                    Add Room
                  </button>
                </div>
              </div>
              <div className="editor-list">
              {draft.rooms.length === 0 ? (
                <p className="empty-state">No rooms added yet.</p>
              ) : (
                draft.rooms.map((room) => (
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
                        />
                      </label>
                    </div>
                      );
                    })()}
                    <div className="record-actions">
                      <button className="ghost-btn" onClick={() => duplicateRecord("rooms", room.id)}>
                        Duplicate Room
                      </button>
                      <button className="danger-btn" onClick={() => removeRecord("rooms", room.id)}>
                        Remove Room
                      </button>
                    </div>
                  </div>
                ))
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
              </div>
              <div className="editor-list">
                {draft.cohorts.filter((cohort) => cohort.kind === "base").length === 0 ? (
                  <p className="empty-state">Add degrees and paths first.</p>
                ) : (
                  draft.cohorts
                    .filter((cohort) => cohort.kind === "base")
                    .map((cohort) => {
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
                            <span className="tag-chip">{path?.code || "General"}</span>
                          </div>
                          <div className="form-grid two-column">
                            <label>
                              <span>Cohort name</span>
                              <input
                                className={invalidClass(cohortNameIssue)}
                                value={cohort.name}
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
                    disabled={draft.cohorts.filter((cohort) => cohort.kind === "base").length === 0}
                  >
                    Create Override Templates
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() =>
                      addRecord("cohorts", {
                        id: makeId("cohort"),
                        kind: "override",
                        degreeId: degreeOptions[0]?.id || "",
                        year: 1,
                        pathId: "",
                        name: "",
                        size: "",
                      })
                    }
                    disabled={degreeOptions.length === 0}
                  >
                    Add Override
                  </button>
                </div>
              </div>
              <div className="editor-list">
                {draft.cohorts.filter((cohort) => cohort.kind === "override").length === 0 ? (
                  <p className="empty-state">No override groups added.</p>
                ) : (
                  draft.cohorts
                    .filter((cohort) => cohort.kind === "override")
                    .map((cohort, index) => {
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
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "year", event.target.value)
                                }
                              />
                            </label>
                            <label>
                              <span>Path</span>
                              <select
                                value={cohort.pathId}
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
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "size", event.target.value)
                                }
                              />
                              {overrideSizeIssue && <small className="field-hint invalid">{overrideSizeIssue}</small>}
                            </label>
                            <label className="full-span">
                              <span>Override name</span>
                              <input
                                className={invalidClass(overrideIdentityIssue)}
                                value={cohort.name}
                                onChange={(event) =>
                                  updateRecord("cohorts", cohort.id, "name", event.target.value)
                                }
                              />
                              {overrideIdentityIssue && <small className="field-hint invalid">{overrideIdentityIssue}</small>}
                            </label>
                          </div>
                          <div className="record-actions">
                            <button className="ghost-btn" onClick={() => duplicateRecord("cohorts", cohort.id)}>
                              Duplicate Override
                            </button>
                            <button className="danger-btn" onClick={() => removeRecord("cohorts", cohort.id)}>
                              Remove Override
                            </button>
                          </div>
                        </div>
                      );
                    })
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
                    disabled={draft.cohorts.filter((cohort) => cohort.kind === "base").length === 0}
                  >
                    Create Semester 1 Module Shells
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => addModuleShellsForSemester(2)}
                    disabled={draft.cohorts.filter((cohort) => cohort.kind === "base").length === 0}
                  >
                    Create Semester 2 Module Shells
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() =>
                      addRecord("modules", {
                        id: makeId("module"),
                        code: "",
                        name: "",
                        subject_name: "",
                        year: 1,
                        semester: 1,
                        is_full_year: false,
                      })
                    }
                  >
                    Add Module
                  </button>
                </div>
              </div>
              <div className="editor-list">
              {draft.modules.length === 0 ? (
                <p className="empty-state">No modules added yet.</p>
              ) : (
                draft.modules.map((module, index) => {
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
                            onChange={(event) =>
                              updateRecord("modules", module.id, "year", event.target.value)
                            }
                          />
                        </label>
                        <label>
                          <span>Semester</span>
                          <select
                            value={module.semester}
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
                            onChange={(event) =>
                              updateRecord("modules", module.id, "is_full_year", event.target.checked)
                            }
                          />
                          <span>Full-year module</span>
                        </label>
                      </div>
                      <div className="record-actions">
                        <button className="ghost-btn" onClick={() => duplicateRecord("modules", module.id)}>
                          Duplicate Module
                        </button>
                        <button className="danger-btn" onClick={() => removeRecord("modules", module.id)}>
                          Remove Module
                        </button>
                      </div>
                    </div>
                  );
                })
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
                    onClick={addStarterSessionsFromModules}
                    disabled={moduleOptions.length === 0}
                  >
                    Create Starter Sessions
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => addSessionPatternFromModules("lectureTutorial")}
                    disabled={moduleOptions.length === 0}
                  >
                    Create Lecture + Tutorial Set
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() => addSessionPatternFromModules("scienceSet")}
                    disabled={moduleOptions.length === 0}
                  >
                    Create Science Session Set
                  </button>
                  <button
                    className="ghost-btn"
                    onClick={() =>
                      addRecord("sessions", {
                        id: makeId("session"),
                        moduleId: moduleOptions[0]?.id || "",
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
                      })
                    }
                    disabled={moduleOptions.length === 0}
                  >
                    Add Session
                  </button>
                </div>
              </div>
              <div className="editor-list">
              {draft.sessions.length === 0 ? (
                <p className="empty-state">No sessions added yet.</p>
              ) : (
                draft.sessions.map((session) => {
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
                          onChange={(event) =>
                            updateRecord("sessions", session.id, "moduleId", event.target.value)
                          }
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
                        />
                        {sessionOccurrenceIssue && (
                          <small className="field-hint invalid">{sessionOccurrenceIssue}</small>
                        )}
                      </label>
                      <label>
                        <span>Required room type</span>
                        <select
                          value={session.required_room_type}
                          onChange={(event) =>
                            updateRecord("sessions", session.id, "required_room_type", event.target.value)
                          }
                        >
                          <option value="">Any</option>
                          <option value="lecture">Lecture</option>
                          <option value="lab">Lab</option>
                          <option value="seminar">Seminar</option>
                        </select>
                      </label>
                      <label>
                        <span>Also counts as modules</span>
                        <select
                          multiple
                          value={session.linkedModuleIds || []}
                          onChange={(event) =>
                            updateRecord(
                              "sessions",
                              session.id,
                              "linkedModuleIds",
                              Array.from(event.target.selectedOptions, (option) => option.value)
                            )
                          }
                        >
                          {moduleOptions
                            .filter((module) => module.id !== session.moduleId)
                            .map((module) => (
                              <option key={module.id} value={module.id}>
                                {module.code} - {module.name}
                              </option>
                            ))}
                        </select>
                      </label>
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
                            onChange={(event) =>
                              updateRecord("sessions", session.id, "specific_room_id", event.target.value)
                            }
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
                          />
                        </label>
                        <label className="checkbox-field">
                          <input
                            type="checkbox"
                            checked={session.allow_parallel_rooms}
                            onChange={(event) =>
                              updateRecord(
                                "sessions",
                                session.id,
                                "allow_parallel_rooms",
                                event.target.checked
                              )
                            }
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
                          />
                        </label>
                      </div>
                    </div>

                    <div className="selection-grid">
                      <div>
                        <h3>Lecturers</h3>
                        <div className="check-grid">
                          {lecturerOptions.map((lecturer) => (
                            <label key={lecturer.id} className="check-chip">
                              <input
                                type="checkbox"
                                checked={session.lecturerIds.includes(lecturer.id)}
                                onChange={() => toggleSessionLink(session.id, "lecturerIds", lecturer.id)}
                              />
                              <span>{lecturer.name}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                      <div>
                        <h3>Attending cohorts</h3>
                        {sessionCohortIssue && <p className="field-hint invalid">{sessionCohortIssue}</p>}
                        <div className="check-grid">
                          {cohortOptions.map((cohort) => (
                            <label key={cohort.id} className="check-chip">
                              <input
                                type="checkbox"
                                checked={session.cohortIds.includes(cohort.id)}
                                onChange={() => toggleSessionLink(session.id, "cohortIds", cohort.id)}
                              />
                              <span>{cohort.name || "Unnamed cohort"}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="record-actions">
                      <button
                        className="ghost-btn"
                        onClick={() => copySessionAudienceToModuleSet(session.id)}
                        disabled={!session.moduleId}
                      >
                        Copy Lecturers + Cohorts To Module Set
                      </button>
                      <button className="ghost-btn" onClick={() => duplicateRecord("sessions", session.id)}>
                        Duplicate Session
                      </button>
                      <button className="danger-btn" onClick={() => removeRecord("sessions", session.id)}>
                        Remove Session
                      </button>
                    </div>
                  </div>
                );
                })
              )}
              </div>
            </section>
          </>
        )}

        {currentStep === "review" && (
          <div className="studio-grid two-column">
            <StepIntro stepKey="review" />
            <section className="studio-card">
              <h2>Readiness Review</h2>
              {validation.blocking.length === 0 ? (
                <div className="info-banner">The setup draft is complete enough to save and use for timetable generation.</div>
              ) : (
                <div className="error-banner">
                  <strong>Fix these blocking issues before saving:</strong>
                  <ul>
                    {validation.blocking.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}

              {validation.warnings.length > 0 && (
                <div className="schema-notes">
                  <h3>Warnings you may still want to review</h3>
                  <ul>
                    {validation.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="schema-notes">
                <h3>What this save action will write</h3>
                <ul>
                  <li>Degrees and year-specific paths</li>
                  <li>Rooms and lecturers used by the timetable views</li>
                  <li>Derived base cohorts plus any override groups</li>
                  <li>Modules and weekly sessions with advanced delivery options</li>
                  <li>Split limits that can auto-create internal session parts during generation</li>
                </ul>
              </div>
            </section>

            <section className="studio-card">
              <h2>Manual Entry First</h2>
              <p>
                CSV import will come later once the exact university source format is confirmed.
              </p>
              <div className="schema-notes">
                <h3>Split behavior</h3>
                <ul>
                  <li>Use `Split limit per room` when one room cannot fit an entire cohort.</li>
                  <li>The generator can divide a single cohort into internal parts automatically.</li>
                  <li>Create override groups only when attendance itself is different, such as electives.</li>
                </ul>
              </div>
              <div className="future-card">
                <strong>Future CSV import</strong>
                <span>Disabled for now. This wizard remains the supported path for setup data.</span>
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
            disabled={activeStep === steps.length - 1 || blockedSteps[steps[Math.min(activeStep + 1, steps.length - 1)].key]}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

export default SetupStudio;
