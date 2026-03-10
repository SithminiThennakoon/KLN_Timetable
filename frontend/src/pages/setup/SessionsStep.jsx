import React from "react";
import {
  SESSION_TYPE_OPTIONS,
  SESSION_TYPE_VALUES,
  findRecordIssue,
  invalidClass,
  isLabLikeSession,
  makeId,
} from "./setupHelpers";
import { ConfirmDelete } from "./ConfirmDelete";

// ── helpers ──────────────────────────────────────────────────────────────────

/**
 * Returns true if any advanced field is non-default.
 * Used to auto-open the accordion when a session already has advanced data.
 */
function hasAdvancedData(session) {
  return (
    Boolean(session.specific_room_id) ||
    Boolean((session.required_lab_type || "").trim()) ||
    Boolean(session.max_students_per_group) ||
    session.allow_parallel_rooms ||
    Boolean((session.notes || "").trim())
  );
}

/** Group cohorts by degree + year for display in the attending-cohorts checklist. */
function groupCohortsByDegreeYear(cohorts, degrees) {
  const groups = new Map(); // key: "degreeCode Y{year}" → { label, cohorts[] }
  cohorts.forEach((cohort) => {
    const degree = degrees.find((d) => d.id === cohort.degreeId);
    const degreeCode = degree?.code || "Unknown";
    const key = `${cohort.degreeId}::${cohort.year}`;
    if (!groups.has(key)) {
      groups.set(key, { label: `${degreeCode} — Year ${cohort.year}`, cohorts: [] });
    }
    groups.get(key).cohorts.push(cohort);
  });
  return Array.from(groups.values());
}

// ── Session accent colour helper ──────────────────────────────────────────────

function sessionAccentClass(sessionType) {
  const t = (sessionType || "").trim().toLowerCase();
  if (t === "lecture") return "session-accent-lecture";
  if (t === "tutorial") return "session-accent-tutorial";
  if (t === "seminar") return "session-accent-seminar";
  if (t === "practical") return "session-accent-practical";
  if (t === "lab" || t === "laboratory") return "session-accent-lab";
  return "session-accent-other";
}

// ── AdvancedPanel ─────────────────────────────────────────────────────────────

function AdvancedPanel({ session, roomOptions, updateRecord }) {
  const [open, setOpen] = React.useState(() => hasAdvancedData(session));

  return (
    <div className="advanced-session">
      <button
        type="button"
        className="advanced-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>{open ? "▾" : "▸"} Advanced options</span>
        {!open && hasAdvancedData(session) && (
          <span className="tag-chip tag-chip-count" style={{ marginLeft: 8 }}>
            set
          </span>
        )}
      </button>

      {open && (
        <>
          <p className="helper-copy" style={{ marginTop: 8 }}>
            A split limit lets the generator divide one large cohort into internal parts when a
            single room cannot hold everyone — you do not need to create manual override groups for
            that case. Lab-style sessions must run as one 180-minute block, and room type plus lab
            type should reflect the real room pool you expect the solver to use.
          </p>
          <div className="form-grid four-column">
            <label>
              <span>Specific room</span>
              <select
                value={session.specific_room_id}
                onChange={(e) =>
                  updateRecord("sessions", session.id, "specific_room_id", e.target.value)
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
                onChange={(e) =>
                  updateRecord("sessions", session.id, "required_lab_type", e.target.value)
                }
              />
            </label>
            <label>
              <span>Split limit per room</span>
              <input
                type="number"
                min="1"
                value={session.max_students_per_group}
                onChange={(e) =>
                  updateRecord("sessions", session.id, "max_students_per_group", e.target.value)
                }
              />
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={session.allow_parallel_rooms}
                onChange={(e) =>
                  updateRecord("sessions", session.id, "allow_parallel_rooms", e.target.checked)
                }
              />
              <span>Same-time parallel rooms for all split parts</span>
            </label>
            <label className="full-span">
              <span>Notes</span>
              <textarea
                className="compact-textarea"
                value={session.notes}
                onChange={(e) =>
                  updateRecord("sessions", session.id, "notes", e.target.value)
                }
              />
            </label>
          </div>
        </>
      )}
    </div>
  );
}

// ── CopyAudienceButton ────────────────────────────────────────────────────────

function CopyAudienceButton({ session, moduleOptions, onCopy }) {
  const [pending, setPending] = React.useState(false);

  const mod = moduleOptions.find((m) => m.id === session.moduleId);
  const modLabel = mod ? `${mod.code} — ${mod.name}` : "this module";

  if (!pending) {
    return (
      <button
        type="button"
        className="ghost-btn"
        onClick={() => setPending(true)}
        disabled={!session.moduleId}
        title="Copy the lecturers and cohorts assigned to this session to all other sessions under the same module"
      >
        Copy Lecturers + Cohorts To Module Set
      </button>
    );
  }

  return (
    <span className="confirm-strip">
      <span className="confirm-strip-msg">
        Overwrite lecturers &amp; cohorts on all other sessions in{" "}
        <em>{modLabel}</em>?
        <span className="confirm-strip-note"> This cannot be undone.</span>
      </span>
      <button
        type="button"
        className="danger-btn confirm-strip-yes"
        onClick={() => { setPending(false); onCopy(); }}
      >
        Overwrite
      </button>
      <button
        type="button"
        className="ghost-btn confirm-strip-cancel"
        onClick={() => setPending(false)}
      >
        Cancel
      </button>
    </span>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function SessionsStep({
  draft,
  validation,
  touched,
  touchField,
  updateRecord,
  removeRecord,
  duplicateRecord,
  addRecord,
  toggleSessionLink,
  copySessionAudienceToModuleSet,
  addStarterSessionsFromModules,
  addSessionPatternFromModules,
}) {
  const moduleOptions = draft.modules;
  const lecturerOptions = draft.lecturers;
  const roomOptions = draft.rooms;
  const cohortOptions = draft.cohorts;

  const cohortGroups = React.useMemo(
    () => groupCohortsByDegreeYear(cohortOptions, draft.degrees),
    [cohortOptions, draft.degrees]
  );

  return (
    <section className="studio-card">
      <div className="section-row">
        <div>
          <h2>Sessions</h2>
          <p>
            Create the actual weekly teaching activities. Link each session to its lecturers and
            attending cohorts, then use advanced options only when delivery needs extra rules such
            as split groups, lab typing, or fixed rooms.
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
            Science Session Set
          </button>
          <button
            className="primary-btn"
            onClick={() =>
              addRecord("sessions", {
                id: makeId("session"),
                moduleId: moduleOptions[0]?.id || "",
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
          <div className="empty-state-with-action">
            <p className="empty-state">No sessions added yet.</p>
            {moduleOptions.length > 0 && (
              <button
                className="ghost-btn"
                onClick={addStarterSessionsFromModules}
              >
                Create starter sessions from modules
              </button>
            )}
          </div>
        ) : (
          draft.sessions.map((session, index) => {
            const sessionIndex = index + 1;

            const sessionIdentityIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Session ${sessionIndex} is missing module, name, or type\\.$`)
            );
            const sessionTypeRuleIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Session ${sessionIndex} type must be one of:`)
            );
            const sessionDurationIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Session ${sessionIndex} duration must be a positive multiple of 30\\.$`)
            );
            const sessionLabDurationIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Session ${sessionIndex} is treated as a lab and must be 180 minutes\\.$`)
            );
            const sessionOccurrenceIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Session ${sessionIndex} weekly occurrence count must be between 1 and 10\\.$`)
            );
            const sessionCohortIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Session ${sessionIndex} must target at least one cohort\\.$`)
            );

            const tk = (field) => touched.has(`sessions.${session.id}.${field}`);
            const touch = (field) => touchField(`sessions.${session.id}.${field}`);

            return (
              <div key={session.id} className={`editor-card session-type-accent ${sessionAccentClass(session.session_type)}`}>
                {/* ── Core fields ── */}
                <div className="form-grid four-column">
                  <label>
                    <span>Module</span>
                    <select
                      className={invalidClass(sessionIdentityIssue, tk("moduleId"))}
                      value={session.moduleId}
                      onChange={(e) =>
                        updateRecord("sessions", session.id, "moduleId", e.target.value)
                      }
                      onBlur={() => touch("moduleId")}
                    >
                      <option value="">Select module</option>
                      {moduleOptions.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.code} — {m.name}
                        </option>
                      ))}
                    </select>
                    {sessionIdentityIssue && tk("moduleId") && (
                      <small className="field-hint invalid">{sessionIdentityIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Name</span>
                    <input
                      className={invalidClass(sessionIdentityIssue, tk("name"))}
                      value={session.name}
                      onChange={(e) =>
                        updateRecord("sessions", session.id, "name", e.target.value)
                      }
                      onBlur={() => touch("name")}
                    />
                    {sessionIdentityIssue && tk("name") && (
                      <small className="field-hint invalid">{sessionIdentityIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Type</span>
                    <select
                      className={invalidClass(
                        sessionIdentityIssue || sessionTypeRuleIssue,
                        tk("session_type")
                      )}
                      value={session.session_type}
                      onChange={(e) =>
                        updateRecord("sessions", session.id, "session_type", e.target.value)
                      }
                      onBlur={() => touch("session_type")}
                    >
                      <option value="">Select type</option>
                      {session.session_type &&
                        !SESSION_TYPE_VALUES.has(session.session_type.toLowerCase()) && (
                          <option value={session.session_type}>{session.session_type}</option>
                        )}
                      {SESSION_TYPE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    {(sessionIdentityIssue || sessionTypeRuleIssue) && tk("session_type") && (
                      <small className="field-hint invalid">
                        {sessionIdentityIssue || sessionTypeRuleIssue}
                      </small>
                    )}
                  </label>
                  <label>
                    <span>Duration (min)</span>
                    <input
                      className={invalidClass(
                        sessionDurationIssue || sessionLabDurationIssue,
                        tk("duration_minutes")
                      )}
                      type="number"
                      step="30"
                      min="30"
                      value={session.duration_minutes}
                      onChange={(e) =>
                        updateRecord("sessions", session.id, "duration_minutes", e.target.value)
                      }
                      onBlur={() => touch("duration_minutes")}
                    />
                    {(sessionDurationIssue || sessionLabDurationIssue) &&
                      tk("duration_minutes") && (
                        <small className="field-hint invalid">
                          {sessionDurationIssue || sessionLabDurationIssue}
                        </small>
                      )}
                  </label>
                  <label>
                    <span>Occurrences / week</span>
                    <input
                      className={invalidClass(sessionOccurrenceIssue, tk("occurrences_per_week"))}
                      type="number"
                      min="1"
                      max="10"
                      value={session.occurrences_per_week}
                      onChange={(e) =>
                        updateRecord(
                          "sessions",
                          session.id,
                          "occurrences_per_week",
                          e.target.value
                        )
                      }
                      onBlur={() => touch("occurrences_per_week")}
                    />
                    {sessionOccurrenceIssue && tk("occurrences_per_week") && (
                      <small className="field-hint invalid">{sessionOccurrenceIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Required room type</span>
                    <select
                      value={session.required_room_type}
                      onChange={(e) =>
                        updateRecord("sessions", session.id, "required_room_type", e.target.value)
                      }
                    >
                      <option value="">Any</option>
                      <option value="lecture">Lecture hall</option>
                      <option value="lab">Lab</option>
                      <option value="seminar">Seminar room</option>
                    </select>
                  </label>
                </div>

                {/* ── Also counts as modules — check-chip grid ── */}
                {moduleOptions.filter((m) => m.id !== session.moduleId).length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <h4 style={{ marginBottom: 6, fontWeight: 600, fontSize: "0.85rem" }}>
                      Also counts as modules
                    </h4>
                    <div className="check-grid">
                      {moduleOptions
                        .filter((m) => m.id !== session.moduleId)
                        .map((m) => (
                          <label key={m.id} className="check-chip">
                            <input
                              type="checkbox"
                              checked={(session.linkedModuleIds || []).includes(m.id)}
                              onChange={() =>
                                toggleSessionLink(session.id, "linkedModuleIds", m.id)
                              }
                            />
                            <span>
                              {m.code} — {m.name}
                            </span>
                          </label>
                        ))}
                    </div>
                  </div>
                )}

                {/* ── Advanced options accordion ── */}
                <AdvancedPanel
                  session={session}
                  roomOptions={roomOptions}
                  updateRecord={updateRecord}
                />

                {/* ── Lecturer + Cohort selection ── */}
                <div className="selection-grid">
                  {/* Lecturers */}
                  <div>
                    <h3>Lecturers</h3>
                    {lecturerOptions.length === 0 ? (
                      <p className="empty-state" style={{ fontSize: "0.85rem" }}>
                        No lecturers defined.
                      </p>
                    ) : (
                      <div className="check-grid">
                        {lecturerOptions.map((l) => (
                          <label key={l.id} className="check-chip">
                            <input
                              type="checkbox"
                              checked={session.lecturerIds.includes(l.id)}
                              onChange={() =>
                                toggleSessionLink(session.id, "lecturerIds", l.id)
                              }
                            />
                            <span>{l.name}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Attending cohorts — grouped by degree + year */}
                  <div>
                    <h3>Attending cohorts</h3>
                    {sessionCohortIssue && tk("cohortIds") && (
                      <p className="field-hint invalid" style={{ marginBottom: 6 }}>
                        {sessionCohortIssue}
                      </p>
                    )}
                    {cohortOptions.length === 0 ? (
                      <p className="empty-state" style={{ fontSize: "0.85rem" }}>
                        No cohorts defined.
                      </p>
                    ) : (
                      cohortGroups.map((group) => (
                        <div key={group.label} style={{ marginBottom: 8 }}>
                          <div className="group-header-chip">{group.label}</div>
                          <div className="check-grid" style={{ marginTop: 4 }}>
                            {group.cohorts.map((cohort) => (
                              <label
                                key={cohort.id}
                                className="check-chip"
                                onClick={() => touch("cohortIds")}
                              >
                                <input
                                  type="checkbox"
                                  checked={session.cohortIds.includes(cohort.id)}
                                  onChange={() =>
                                    toggleSessionLink(session.id, "cohortIds", cohort.id)
                                  }
                                />
                                <span>{cohort.name || "Unnamed cohort"}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* ── Actions ── */}
                <div className="record-actions">
                  <CopyAudienceButton
                    session={session}
                    moduleOptions={moduleOptions}
                    onCopy={() => copySessionAudienceToModuleSet(session.id)}
                  />
                  <button
                    className="ghost-btn"
                    onClick={() => duplicateRecord("sessions", session.id)}
                  >
                    Duplicate Session
                  </button>
                  <ConfirmDelete
                    label="Remove Session"
                    confirmMessage={`Remove "${session.name || "this session"}"?`}
                    onConfirm={() => removeRecord("sessions", session.id)}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
