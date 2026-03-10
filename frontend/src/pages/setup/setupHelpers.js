// ─── Shared pure helpers used by SetupStudio and all step components ──────────

export const SESSION_TYPE_OPTIONS = [
  { value: "lecture", label: "Lecture" },
  { value: "tutorial", label: "Tutorial" },
  { value: "seminar", label: "Seminar" },
  { value: "practical", label: "Practical" },
  { value: "lab", label: "Lab" },
  { value: "laboratory", label: "Laboratory" },
];

export const SESSION_TYPE_VALUES = new Set(SESSION_TYPE_OPTIONS.map((o) => o.value));

export function makeId(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

export function makeBaseCohortName(degree, year, path) {
  if (!degree) return "";
  const base = `${degree.code || degree.name || "Degree"} Y${year}`;
  return path ? `${base} ${path.code || path.name}` : `${base} General`;
}

export function numericSize(value) {
  const parsed = Number(value);
  return parsed > 0 ? parsed : 0;
}

export function isLabLikeSession(session) {
  const t = (session.session_type || "").trim().toLowerCase();
  return (
    t === "lab" ||
    t === "laboratory" ||
    (session.required_room_type || "").trim().toLowerCase() === "lab" ||
    Boolean((session.required_lab_type || "").trim())
  );
}

export function sessionAudienceSize(session, draft) {
  return (session.cohortIds || []).reduce((total, cohortId) => {
    const cohort = draft.cohorts.find((c) => c.id === cohortId);
    return total + numericSize(cohort?.size);
  }, 0);
}

export function roomStructureMatchesSession(room, session) {
  if (session.required_room_type && room.room_type !== session.required_room_type) return false;
  if (session.required_lab_type && (room.lab_type || "").trim() !== session.required_lab_type.trim()) return false;
  if (session.specific_room_id && room.id !== session.specific_room_id) return false;
  return true;
}

export function roomMatchesSession(room, session, audienceSize) {
  return roomStructureMatchesSession(room, session) && numericSize(room.capacity) >= audienceSize;
}

export function toSummary(draft) {
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

export function syncBaseCohorts(draft) {
  const expected = [];
  draft.degrees.forEach((degree) => {
    for (let year = 1; year <= Number(degree.duration_years || 0); year += 1) {
      const matchingPaths = draft.paths.filter(
        (p) => p.degreeId === degree.id && Number(p.year) === year
      );
      if (matchingPaths.length === 0) {
        expected.push({ degreeId: degree.id, year, pathId: "" });
        continue;
      }
      matchingPaths.forEach((path) => {
        expected.push({ degreeId: degree.id, year, pathId: path.id });
      });
    }
  });

  const expectedKeySet = new Set(
    expected.map((item) => `${item.degreeId}::${item.year}::${item.pathId || "general"}`)
  );
  const existingBaseByKey = new Map(
    draft.cohorts
      .filter((c) => c.kind === "base")
      .map((c) => [`${c.degreeId}::${c.year}::${c.pathId || "general"}`, c])
  );

  const baseCohorts = expected.map((item) => {
    const degree = draft.degrees.find((d) => d.id === item.degreeId);
    const path = draft.paths.find((p) => p.id === item.pathId);
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

  const overrideCohorts = draft.cohorts.filter((c) => {
    if (c.kind !== "base") return true;
    const key = `${c.degreeId}::${c.year}::${c.pathId || "general"}`;
    return !expectedKeySet.has(key);
  });

  return { ...draft, cohorts: [...baseCohorts, ...overrideCohorts] };
}

export function validateDraft(draft) {
  const blocking = [];
  const warnings = [];

  if (draft.degrees.length === 0) blocking.push("Add at least one degree before continuing.");
  draft.degrees.forEach((degree, i) => {
    if (!degree.code.trim() || !degree.name.trim() || !degree.intake_label.trim())
      blocking.push(`Degree ${i + 1} is missing code, name, or intake label.`);
    if (!Number.isInteger(Number(degree.duration_years)) || Number(degree.duration_years) < 1)
      blocking.push(`Degree ${i + 1} needs a valid duration in years.`);
  });

  draft.paths.forEach((path, i) => {
    if (!path.degreeId || !path.code.trim() || !path.name.trim())
      blocking.push(`Path ${i + 1} is missing degree, code, or name.`);
  });

  if (draft.lecturers.length === 0) warnings.push("No lecturers entered yet.");

  if (draft.rooms.length === 0) blocking.push("Add at least one room before generating timetables.");
  draft.rooms.forEach((room, i) => {
    if (!room.name.trim() || !room.location.trim())
      blocking.push(`Room ${i + 1} is missing name or location.`);
    if (!Number(room.capacity) || Number(room.capacity) <= 0)
      blocking.push(`Room ${i + 1} needs a positive capacity.`);
  });

  const baseCohorts = draft.cohorts.filter((c) => c.kind === "base");
  if (baseCohorts.length === 0) blocking.push("Define structure first so base student cohorts can be created.");
  baseCohorts.forEach((cohort, i) => {
    if (!cohort.name.trim()) blocking.push(`Base cohort ${i + 1} is missing a name.`);
    if (!Number(cohort.size) || Number(cohort.size) <= 0)
      blocking.push(`Base cohort ${i + 1} needs a positive student count.`);
  });

  draft.cohorts.filter((c) => c.kind === "override").forEach((cohort, i) => {
    if (!cohort.degreeId || !cohort.name.trim())
      blocking.push(`Override group ${i + 1} is missing degree or name.`);
    if (!Number(cohort.size) || Number(cohort.size) <= 0)
      blocking.push(`Override group ${i + 1} needs a positive student count.`);
  });

  draft.modules.forEach((module, i) => {
    if (!module.code.trim() || !module.name.trim() || !module.subject_name.trim())
      blocking.push(`Module ${i + 1} is missing code, name, or subject.`);
  });
  if (draft.modules.length === 0) blocking.push("Add at least one module.");

  draft.sessions.forEach((session, i) => {
    const audienceSize = sessionAudienceSize(session, draft);
    const selectedRoom = session.specific_room_id
      ? draft.rooms.find((r) => r.id === session.specific_room_id)
      : null;
    const structurallyCompatibleRooms = draft.rooms.filter((r) =>
      roomStructureMatchesSession(r, session)
    );
    const matchingRooms = draft.rooms.filter((r) =>
      roomMatchesSession(
        r,
        session,
        session.max_students_per_group ? Number(session.max_students_per_group) : audienceSize
      )
    );

    if (!session.moduleId || !session.name.trim() || !session.session_type.trim())
      blocking.push(`Session ${i + 1} is missing module, name, or type.`);
    if (session.session_type.trim() && !SESSION_TYPE_VALUES.has(session.session_type.trim().toLowerCase()))
      blocking.push(`Session ${i + 1} type must be one of: lecture, tutorial, seminar, practical, lab, laboratory.`);
    if (!Number(session.duration_minutes) || Number(session.duration_minutes) % 30 !== 0)
      blocking.push(`Session ${i + 1} duration must be a positive multiple of 30.`);
    if (!Number(session.occurrences_per_week) || Number(session.occurrences_per_week) <= 0 || Number(session.occurrences_per_week) > 10)
      blocking.push(`Session ${i + 1} weekly occurrence count must be between 1 and 10.`);
    if (isLabLikeSession(session) && Number(session.duration_minutes) !== 180)
      blocking.push(`Session ${i + 1} is treated as a lab and must be 180 minutes.`);
    if (session.required_room_type === "lab" && !session.required_lab_type.trim())
      warnings.push(`Session "${session.name || `#${i + 1}`}" uses room type lab but has no lab type, so it may match the wrong lab pool.`);
    if (session.required_lab_type.trim() && session.required_room_type !== "lab")
      warnings.push(`Session "${session.name || `#${i + 1}`}" has a lab type, so the solver will still treat it as lab-style delivery.`);
    if (session.lecturerIds.length === 0)
      warnings.push(`Session "${session.name || `#${i + 1}`}" has no lecturer assigned.`);
    if (session.cohortIds.length === 0)
      blocking.push(`Session ${i + 1} must target at least one cohort.`);
    if (
      session.cohortIds.length > 0 &&
      draft.rooms.length > 0 &&
      !session.max_students_per_group &&
      audienceSize > 0 &&
      structurallyCompatibleRooms.length > 0 &&
      structurallyCompatibleRooms.every((r) => numericSize(r.capacity) < audienceSize)
    ) {
      blocking.push(`Session ${i + 1} exceeds every matching room capacity for ${audienceSize} students, so add a split limit or expand the room pool.`);
    } else if (session.cohortIds.length > 0 && draft.rooms.length > 0 && matchingRooms.length === 0) {
      blocking.push(`Session ${i + 1} has no matching room pool for ${audienceSize || "its"} students with the current room, lab, and split settings.`);
    }
    if (selectedRoom && session.required_room_type && selectedRoom.room_type !== session.required_room_type)
      blocking.push(`Session ${i + 1} pins room "${selectedRoom.name}" but its room type does not match the selected requirement.`);
    if (selectedRoom && session.required_lab_type.trim() && (selectedRoom.lab_type || "").trim() !== session.required_lab_type.trim())
      blocking.push(`Session ${i + 1} pins room "${selectedRoom.name}" but its lab type does not match the selected requirement.`);
    if (selectedRoom && !session.max_students_per_group && audienceSize > 0 && numericSize(selectedRoom.capacity) < audienceSize)
      blocking.push(`Session ${i + 1} pins room "${selectedRoom.name}" but the room cannot hold all ${audienceSize} students without a split limit.`);
    if (session.allow_parallel_rooms && session.lecturerIds.length < 2)
      warnings.push(`Session "${session.name || `#${i + 1}`}" uses parallel rooms but has fewer than two lecturers assigned.`);
  });

  if (draft.sessions.length === 0) blocking.push("Add at least one session.");

  return {
    blocking: [...new Set(blocking)],
    warnings: [...new Set(warnings)],
  };
}

export function findRecordIssue(messages, pattern) {
  return messages.find((m) => pattern.test(m)) || "";
}

// invalidClass gated by touched state.
// touchKey is a string like "degrees.id123.code" or undefined to always show.
export function invalidClass(message, isTouched = true) {
  return message && isTouched ? "field-invalid" : "";
}

export function currentStepFeedback(stepKey, validation) {
  const matchesStep = (msg) => {
    const lower = msg.toLowerCase();
    if (stepKey === "structure") return lower.includes("degree") || lower.includes("path");
    if (stepKey === "lecturers") return lower.includes("lecturer");
    if (stepKey === "rooms") return lower.includes("room");
    if (stepKey === "cohorts") return lower.includes("cohort") || lower.includes("student count") || lower.includes("structure first") || lower.includes("override group") || lower.includes("degree or name");
    if (stepKey === "modules") return lower.includes("module");
    if (stepKey === "sessions") return lower.includes("session");
    return true;
  };
  return {
    blocking: validation.blocking.filter(matchesStep),
    warnings: validation.warnings.filter(matchesStep),
  };
}

// Returns the keys that belong to a given step (for touchAll).
// Format: "collection.recordId.field"
export const STEP_COLLECTIONS = {
  structure: ["degrees", "paths"],
  lecturers: ["lecturers"],
  rooms: ["rooms"],
  cohorts: ["cohorts"],
  modules: ["modules"],
  sessions: ["sessions"],
  review: [],
};

export const BLOCKED_STEP_REASONS = {
  lecturers: "Add at least one degree first",
  rooms: "Add at least one degree first",
  cohorts: "Add at least one degree first",
  modules: "Add base cohorts first (complete Structure step)",
  sessions: "Add modules and rooms first",
};
