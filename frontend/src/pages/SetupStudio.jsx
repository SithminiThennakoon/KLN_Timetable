import React, { useCallback, useEffect, useMemo, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";
import {
  makeId,
  syncBaseCohorts,
  toSummary,
  validateDraft,
  currentStepFeedback,
  BLOCKED_STEP_REASONS,
} from "./setup/setupHelpers";
import { StructureStep } from "./setup/StructureStep";
import { LecturersStep } from "./setup/LecturersStep";
import { RoomsStep } from "./setup/RoomsStep";
import { CohortsStep } from "./setup/CohortsStep";
import { ModulesStep } from "./setup/ModulesStep";
import { SessionsStep } from "./setup/SessionsStep";
import { ReviewStep } from "./setup/ReviewStep";

// ── Step config ────────────────────────────────────────────────────────────────

const steps = [
  { key: "structure", label: "Structure" },
  { key: "lecturers", label: "Lecturers" },
  { key: "rooms", label: "Rooms" },
  { key: "cohorts", label: "Student Cohorts" },
  { key: "modules", label: "Modules" },
  { key: "sessions", label: "Sessions" },
  { key: "review", label: "Review & Save" },
];

const stepGuidance = {
  structure:
    "Start by defining each degree and any allowed year-specific paths. Direct-entry degrees can stay without paths and will use a general cohort.",
  lecturers:
    "Enter the lecturers who may be assigned to weekly sessions. These names are also used in lecturer timetable views.",
  rooms:
    "Add every teaching room the solver may use, including lecture halls, labs, capacities, locations, and lab types. Under-entering the real room pool can make generation fail even when sessions are correct. Year restrictions are stored, but the current solver does not enforce them.",
  cohorts:
    "Base cohorts are created from degree, year, and path structure. Add student counts there first, then create override groups only when attendance itself differs, such as electives or special attendance patterns.",
  modules:
    "Enter the semester or full-year modules that sessions belong to. Sessions are scheduled later, but every session must point to a module first.",
  sessions:
    "Create the actual weekly teaching activities here. Link each session to its lecturers and attending cohorts, then use advanced options only when delivery needs extra rules such as split groups, lab typing, or fixed rooms.",
  review:
    "Use this review step before saving. Blocking issues must be fixed first. Warnings are allowed, but they usually indicate incomplete staffing or unusual delivery choices.",
};

// ── Empty draft ────────────────────────────────────────────────────────────────

const emptyDraft = {
  degrees: [],
  paths: [],
  lecturers: [],
  rooms: [],
  cohorts: [],
  modules: [],
  sessions: [],
};

// ── normalizeDataset (keeps local IDs stable across load) ─────────────────────

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
    const existing = groupedStudentGroups.get(key) || [];
    existing.push(group);
    groupedStudentGroups.set(key, existing);
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

  return syncBaseCohorts({ degrees, paths, lecturers, rooms, cohorts, modules, sessions });
}

// ── buildPayload ───────────────────────────────────────────────────────────────

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

  return { degrees, paths, lecturers, rooms, student_groups, modules, sessions };
}

// ── Step nav sub-components ────────────────────────────────────────────────────

function StepBadge({ active, complete, blocked, blockedReason, label, onClick }) {
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
      title={blocked ? (blockedReason || "Complete earlier steps first") : "Jump to this step"}
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

function StepChecks({ stepKey, validation }) {
  if (stepKey === "review") return null;

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

// ── Template batches (kept in orchestrator — not needed by step components) ───

function buildRoomTemplates() {
  return {
    lectureHalls: [
      { name: "A7 Hall 1", capacity: 180, room_type: "lecture", lab_type: "", location: "A7 Building", year_restriction: "" },
      { name: "A7 Hall 2", capacity: 140, room_type: "lecture", lab_type: "", location: "A7 Building", year_restriction: "" },
    ],
    labs: [
      { name: "Physics Lab 1", capacity: 40, room_type: "lab", lab_type: "physics", location: "Science Labs Block", year_restriction: "" },
      { name: "Chemistry Lab 1", capacity: 36, room_type: "lab", lab_type: "chemistry", location: "Science Labs Block", year_restriction: "" },
    ],
  };
}

function buildLecturerTemplates() {
  return [
    { name: "Dr. Perera", email: "dr.perera@science.kln.ac.lk" },
    { name: "Dr. Silva", email: "dr.silva@science.kln.ac.lk" },
    { name: "Prof. Fernando", email: "prof.fernando@science.kln.ac.lk" },
    { name: "Ms. Jayasinghe", email: "ms.jayasinghe@science.kln.ac.lk" },
  ];
}

function buildScienceStructureTemplates() {
  return {
    degrees: [
      { code: "PS", name: "Physical Science", duration_years: 3, intake_label: "PS Intake" },
      { code: "BS", name: "Biological Science", duration_years: 3, intake_label: "BS Intake" },
      { code: "ENCM", name: "Environmental Conservation and Management", duration_years: 4, intake_label: "ENCM Intake" },
      { code: "AC", name: "Applied Chemistry", duration_years: 4, intake_label: "AC Intake" },
      { code: "ECS", name: "Electronics and Computer Science", duration_years: 4, intake_label: "ECS Intake" },
      { code: "PE", name: "Physical Education", duration_years: 4, intake_label: "PE Intake" },
    ],
    paths: [
      { degreeCode: "PS", year: 1, code: "PHY-CHEM-MATH", name: "Physics Chemistry Mathematics" },
      { degreeCode: "PS", year: 2, code: "PHY-MATH-STAT", name: "Physics Mathematics Statistics" },
      { degreeCode: "BS", year: 1, code: "BOT-ZOO-CHEM", name: "Botany Zoology Chemistry" },
      { degreeCode: "BS", year: 2, code: "MICRO-BCH-GEN", name: "Microbiology Biochemistry Genetics" },
      { degreeCode: "ECS", year: 1, code: "ECS-GENERAL", name: "Electronics and Computer Science General" },
      { degreeCode: "AC", year: 1, code: "AC-GENERAL", name: "Applied Chemistry General" },
    ],
  };
}

// ── Main component ─────────────────────────────────────────────────────────────

function SetupStudio() {
  const [draft, setDraft] = useState(emptyDraft);
  const [summary, setSummary] = useState(toSummary(emptyDraft));
  const [activeStep, setActiveStep] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // touched: Set of "collection.id.field" keys
  const [touched, setTouched] = useState(new Set());
  // nextBlocked flash: show a banner when Next is clicked but the target step is blocked
  const [nextBlockedMsg, setNextBlockedMsg] = useState("");

  const validation = useMemo(() => validateDraft(draft), [draft]);

  const blockedSteps = useMemo(() => {
    const hasStructure = draft.degrees.length > 0;
    const hasCohorts = draft.cohorts.some((c) => c.kind === "base");
    const hasModules = draft.modules.length > 0;
    const hasRooms = draft.rooms.length > 0;
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

  // ── Load ────────────────────────────────────────────────────────────────────

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

  useEffect(() => { loadDataset(); }, []);

  // ── Draft mutations ──────────────────────────────────────────────────────────

  const updateDraft = useCallback((updater) => {
    setDraft((current) => {
      const next = typeof updater === "function" ? updater(current) : updater;
      const synced = syncBaseCohorts(next);
      setSummary(toSummary(synced));
      return synced;
    });
  }, []);

  // ── Touched state helpers ────────────────────────────────────────────────────

  const touchField = useCallback((key) => {
    setTouched((prev) => new Set([...prev, key]));
  }, []);

  const touchAll = useCallback((stepKey) => {
    // Touch all fields for all records in the collections owned by this step
    const collections = {
      structure: ["degrees", "paths"],
      lecturers: ["lecturers"],
      rooms: ["rooms"],
      cohorts: ["cohorts"],
      modules: ["modules"],
      sessions: ["sessions"],
    }[stepKey] || [];

    setTouched((prev) => {
      const next = new Set(prev);
      const fieldsByCollection = {
        degrees: ["code", "name", "duration_years", "intake_label"],
        paths: ["degreeId", "code", "name"],
        lecturers: ["name", "email"],
        rooms: ["name", "location", "capacity"],
        cohorts: ["name", "size", "degreeId"],
        modules: ["code", "name", "subject_name"],
        sessions: ["moduleId", "name", "session_type", "duration_minutes", "occurrences_per_week", "cohortIds"],
      };
      collections.forEach((col) => {
        const fields = fieldsByCollection[col] || [];
        draft[col].forEach((record) => {
          fields.forEach((field) => {
            next.add(`${col}.${record.id}.${field}`);
          });
        });
      });
      return next;
    });
  }, [draft]);

  // ── Navigation ───────────────────────────────────────────────────────────────

  const goToStep = (index) => {
    if (blockedSteps[steps[index].key]) return;
    setNextBlockedMsg("");
    setActiveStep(index);
  };

  const nextStep = () => {
    // Touch all fields on the current step so validation shows
    touchAll(steps[activeStep].key);
    const nextIndex = Math.min(activeStep + 1, steps.length - 1);
    if (blockedSteps[steps[nextIndex].key]) {
      setNextBlockedMsg(BLOCKED_STEP_REASONS[steps[nextIndex].key] || "Complete this step first.");
      return;
    }
    setNextBlockedMsg("");
    setActiveStep(nextIndex);
  };

  const prevStep = () => {
    setNextBlockedMsg("");
    setActiveStep((current) => Math.max(current - 1, 0));
  };

  // ── Demo / save ──────────────────────────────────────────────────────────────

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

  // ── Record CRUD helpers ───────────────────────────────────────────────────────

  const addRecord = useCallback((collection, record) => {
    updateDraft((current) => ({
      ...current,
      [collection]: [...current[collection], record],
    }));
  }, [updateDraft]);

  const duplicateRecord = useCallback((collection, id) => {
    updateDraft((current) => {
      const source = current[collection].find((r) => r.id === id);
      if (!source) return current;
      return {
        ...current,
        [collection]: [
          ...current[collection],
          { ...source, id: makeId(collection.slice(0, -1) || "item") },
        ],
      };
    });
  }, [updateDraft]);

  const updateRecord = useCallback((collection, id, field, value) => {
    updateDraft((current) => ({
      ...current,
      [collection]: current[collection].map((r) =>
        r.id === id ? { ...r, [field]: value } : r
      ),
    }));
  }, [updateDraft]);

  const removeRecord = useCallback((collection, id) => {
    updateDraft((current) => {
      const next = { ...current, [collection]: current[collection].filter((r) => r.id !== id) };
      if (collection === "degrees") {
        next.paths = next.paths.filter((p) => p.degreeId !== id);
        next.cohorts = next.cohorts.filter((c) => c.degreeId !== id);
      }
      if (collection === "paths") {
        next.cohorts = next.cohorts.filter((c) => c.pathId !== id);
      }
      if (collection === "modules") {
        next.sessions = next.sessions.filter((s) => s.moduleId !== id);
      }
      if (collection === "lecturers") {
        next.sessions = next.sessions.map((s) => ({
          ...s,
          lecturerIds: s.lecturerIds.filter((lid) => lid !== id),
        }));
      }
      if (collection === "rooms") {
        next.sessions = next.sessions.map((s) => ({
          ...s,
          specific_room_id: s.specific_room_id === id ? "" : s.specific_room_id,
        }));
      }
      if (collection === "cohorts") {
        next.sessions = next.sessions.map((s) => ({
          ...s,
          cohortIds: s.cohortIds.filter((cid) => cid !== id),
        }));
      }
      return next;
    });
  }, [updateDraft]);

  const toggleSessionLink = useCallback((sessionId, field, value) => {
    updateDraft((current) => ({
      ...current,
      sessions: current.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        const items = s[field];
        const next = items.includes(value)
          ? items.filter((item) => item !== value)
          : [...items, value];
        return { ...s, [field]: next };
      }),
    }));
  }, [updateDraft]);

  const copySessionAudienceToModuleSet = useCallback((sessionId) => {
    updateDraft((current) => {
      const source = current.sessions.find((s) => s.id === sessionId);
      if (!source || !source.moduleId) return current;
      return {
        ...current,
        sessions: current.sessions.map((s) => {
          if (s.id === sessionId || s.moduleId !== source.moduleId) return s;
          return { ...s, lecturerIds: [...source.lecturerIds], cohortIds: [...source.cohortIds] };
        }),
      };
    });
  }, [updateDraft]);

  // ── Bulk generators ──────────────────────────────────────────────────────────

  const addStarterSessionsFromModules = useCallback(() => {
    updateDraft((current) => {
      const moduleIdsWithSessions = new Set(current.sessions.map((s) => s.moduleId));
      const starterSessions = current.modules
        .filter((m) => m.id && !moduleIdsWithSessions.has(m.id))
        .map((m) => ({
          id: makeId("session"),
          moduleId: m.id,
          linkedModuleIds: [],
          name: `${m.name || m.code || "Module"} Session`,
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
        }));
      if (starterSessions.length === 0) return current;
      return { ...current, sessions: [...current.sessions, ...starterSessions] };
    });
  }, [updateDraft]);

  const addSessionPatternFromModules = useCallback((patternKey) => {
    const patterns = {
      lectureTutorial: [
        { suffix: "Lecture", session_type: "lecture", duration_minutes: 120, occurrences_per_week: 1, required_room_type: "lecture" },
        { suffix: "Tutorial", session_type: "tutorial", duration_minutes: 60, occurrences_per_week: 1, required_room_type: "seminar" },
      ],
      scienceSet: [
        { suffix: "Lecture", session_type: "lecture", duration_minutes: 120, occurrences_per_week: 1, required_room_type: "lecture" },
        { suffix: "Tutorial", session_type: "tutorial", duration_minutes: 60, occurrences_per_week: 1, required_room_type: "seminar" },
        { suffix: "Lab", session_type: "lab", duration_minutes: 180, occurrences_per_week: 1, required_room_type: "lab" },
      ],
    };
    const selectedPattern = patterns[patternKey] || [];
    if (selectedPattern.length === 0) return;

    updateDraft((current) => {
      const moduleIdsWithSessions = new Set(current.sessions.map((s) => s.moduleId));
      const generated = current.modules
        .filter((m) => m.id && !moduleIdsWithSessions.has(m.id))
        .flatMap((m) =>
          selectedPattern.map((tpl) => ({
            id: makeId("session"),
            moduleId: m.id,
            linkedModuleIds: [],
            name: `${m.name || m.code || "Module"} ${tpl.suffix}`,
            session_type: tpl.session_type,
            duration_minutes: tpl.duration_minutes,
            occurrences_per_week: tpl.occurrences_per_week,
            required_room_type: tpl.required_room_type,
            required_lab_type: "",
            specific_room_id: "",
            max_students_per_group: "",
            allow_parallel_rooms: false,
            notes: "",
            lecturerIds: [],
            cohortIds: [],
          }))
        );
      if (generated.length === 0) return current;
      return { ...current, sessions: [...current.sessions, ...generated] };
    });
  }, [updateDraft]);

  const addModuleShellsForSemester = useCallback((semester) => {
    updateDraft((current) => {
      const yearCombos = Array.from(
        new Map(
          current.cohorts
            .filter((c) => c.kind === "base" && c.degreeId && Number(c.year) > 0)
            .map((c) => [`${c.degreeId}::${c.year}`, { degreeId: c.degreeId, year: Number(c.year) }])
        ).values()
      );
      const existingByYearSemester = new Set(
        current.modules.map((m) => `${Number(m.year)}::${Number(m.semester)}`)
      );
      const moduleShells = yearCombos
        .filter((combo) => !existingByYearSemester.has(`${combo.year}::${semester}`))
        .map((combo, i) => {
          const degree = current.degrees.find((d) => d.id === combo.degreeId);
          const degreeCode = degree?.code?.trim() || "DEG";
          return {
            id: makeId("module"),
            code: `${degreeCode}${combo.year}${semester}0${i + 1}`,
            name: `${degreeCode} Year ${combo.year} Semester ${semester} Module`,
            subject_name: `${degreeCode} Year ${combo.year}`,
            year: combo.year,
            semester,
            is_full_year: false,
          };
        });
      if (moduleShells.length === 0) return current;
      return { ...current, modules: [...current.modules, ...moduleShells] };
    });
  }, [updateDraft]);

  const addRoomTemplateBatch = useCallback((templateKey) => {
    const templates = buildRoomTemplates();
    const selected = templates[templateKey] || [];
    if (selected.length === 0) return;
    updateDraft((current) => {
      const existingNames = new Set(
        current.rooms.map((r) => r.name.trim().toLowerCase()).filter(Boolean)
      );
      const roomsToAdd = selected
        .filter((r) => !existingNames.has(r.name.trim().toLowerCase()))
        .map((r) => ({ id: makeId("room"), ...r }));
      if (roomsToAdd.length === 0) return current;
      return { ...current, rooms: [...current.rooms, ...roomsToAdd] };
    });
  }, [updateDraft]);

  const addLecturerTemplateBatch = useCallback(() => {
    const templates = buildLecturerTemplates();
    updateDraft((current) => {
      const existingNames = new Set(
        current.lecturers.map((l) => l.name.trim().toLowerCase()).filter(Boolean)
      );
      const toAdd = templates
        .filter((l) => !existingNames.has(l.name.trim().toLowerCase()))
        .map((l) => ({ id: makeId("lecturer"), ...l }));
      if (toAdd.length === 0) return current;
      return { ...current, lecturers: [...current.lecturers, ...toAdd] };
    });
  }, [updateDraft]);

  const addScienceStructureTemplates = useCallback(() => {
    const { degrees: degreeTpls, paths: pathTpls } = buildScienceStructureTemplates();
    updateDraft((current) => {
      const existingDegreeCodes = new Set(
        current.degrees.map((d) => d.code.trim().toUpperCase()).filter(Boolean)
      );
      const degreesToAdd = degreeTpls
        .filter((d) => !existingDegreeCodes.has(d.code))
        .map((d) => ({ id: makeId("degree"), ...d }));
      const allDegrees = [...current.degrees, ...degreesToAdd];
      const degreeIdByCode = new Map(allDegrees.map((d) => [d.code.trim().toUpperCase(), d.id]));
      const existingPathKeys = new Set(
        current.paths
          .map((p) => {
            const deg = allDegrees.find((d) => d.id === p.degreeId);
            return deg ? `${deg.code.trim().toUpperCase()}::${Number(p.year)}::${p.code.trim().toUpperCase()}` : "";
          })
          .filter(Boolean)
      );
      const pathsToAdd = pathTpls
        .filter((p) => !existingPathKeys.has(`${p.degreeCode}::${p.year}::${p.code}`))
        .map((p) => ({
          id: makeId("path"),
          degreeId: degreeIdByCode.get(p.degreeCode) || "",
          year: p.year,
          code: p.code,
          name: p.name,
        }))
        .filter((p) => p.degreeId);
      if (degreesToAdd.length === 0 && pathsToAdd.length === 0) return current;
      return { ...current, degrees: allDegrees, paths: [...current.paths, ...pathsToAdd] };
    });
  }, [updateDraft]);

  const addOverrideTemplatesFromBaseCohorts = useCallback(() => {
    updateDraft((current) => {
      const overrideTemplates = current.cohorts
        .filter((c) => c.kind === "base")
        .map((c) => ({
          id: makeId("cohort"),
          kind: "override",
          degreeId: c.degreeId,
          year: c.year,
          pathId: c.pathId,
          name: `${c.name || "Cohort"} Override`,
          size: "",
        }));
      if (overrideTemplates.length === 0) return current;
      return { ...current, cohorts: [...current.cohorts, ...overrideTemplates] };
    });
  }, [updateDraft]);

  // ── Shared props ──────────────────────────────────────────────────────────────

  const commonProps = {
    draft,
    validation,
    touched,
    touchField,
    updateRecord,
    removeRecord,
    duplicateRecord,
    addRecord,
  };

  const currentStep = steps[activeStep].key;

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="page-shell">
      <div className="panel studio-panel">
        {/* Header */}
        <div className="studio-header">
          <div>
            <h1 className="section-title">Setup Studio</h1>
            <p className="section-subtitle">
              Build the v2 timetable dataset through guided steps, then save one validated draft for
              generation.
            </p>
          </div>
          <div className="studio-actions wrap">
            <button className="ghost-btn" onClick={() => handleLoadDemo("realistic")} disabled={saving || loading}>
              Load Realistic Demo
            </button>
            <button className="ghost-btn" onClick={() => handleLoadDemo("tuned")} disabled={saving || loading}>
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

        {/* Step nav */}
        <div className="wizard-steps">
          {steps.map((step, index) => (
            <StepBadge
              key={step.key}
              label={`${index + 1}. ${step.label}`}
              active={index === activeStep}
              complete={!blockedSteps[step.key] && index < activeStep}
              blocked={blockedSteps[step.key]}
              blockedReason={BLOCKED_STEP_REASONS[step.key]}
              onClick={() => goToStep(index)}
            />
          ))}
        </div>

        {/* Summary bar */}
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

        {/* ── Step panes ── */}
        {currentStep === "structure" && (
          <div className="studio-grid">
            <StepIntro stepKey="structure" />
            <StructureStep
              {...commonProps}
              addScienceStructureTemplates={addScienceStructureTemplates}
            />
          </div>
        )}

        {currentStep === "lecturers" && (
          <>
            <StepIntro stepKey="lecturers" />
            <LecturersStep
              {...commonProps}
              addLecturerTemplateBatch={addLecturerTemplateBatch}
            />
          </>
        )}

        {currentStep === "rooms" && (
          <>
            <StepIntro stepKey="rooms" />
            <RoomsStep
              {...commonProps}
              addRoomTemplateBatch={addRoomTemplateBatch}
            />
          </>
        )}

        {currentStep === "cohorts" && (
          <div className="studio-grid">
            <StepIntro stepKey="cohorts" />
            <CohortsStep
              {...commonProps}
              addOverrideTemplatesFromBaseCohorts={addOverrideTemplatesFromBaseCohorts}
            />
          </div>
        )}

        {currentStep === "modules" && (
          <>
            <StepIntro stepKey="modules" />
            <ModulesStep
              {...commonProps}
              addModuleShellsForSemester={addModuleShellsForSemester}
            />
          </>
        )}

        {currentStep === "sessions" && (
          <>
            <StepIntro stepKey="sessions" />
            <SessionsStep
              {...commonProps}
              toggleSessionLink={toggleSessionLink}
              copySessionAudienceToModuleSet={copySessionAudienceToModuleSet}
              addStarterSessionsFromModules={addStarterSessionsFromModules}
              addSessionPatternFromModules={addSessionPatternFromModules}
            />
          </>
        )}

        {currentStep === "review" && (
          <ReviewStep validation={validation} summary={summary} />
        )}

        {/* Blocked-next flash */}
        {nextBlockedMsg && (
          <div className="error-banner" style={{ marginTop: 8 }}>
            {nextBlockedMsg}
          </div>
        )}

        {/* Footer nav */}
        <div className="wizard-footer">
          <button className="ghost-btn" onClick={prevStep} disabled={activeStep === 0}>
            Back
          </button>
          <button
            className="primary-btn"
            onClick={nextStep}
            disabled={activeStep === steps.length - 1}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

export default SetupStudio;
