import React from "react";
import { findRecordIssue, invalidClass, makeId } from "./setupHelpers";
import { ConfirmDelete } from "./ConfirmDelete";

export function ModulesStep({
  draft,
  validation,
  touched,
  touchField,
  updateRecord,
  removeRecord,
  duplicateRecord,
  addRecord,
  addModuleShellsForSemester,
}) {
  const baseCohorts = draft.cohorts.filter((c) => c.kind === "base");

  // Build a map: moduleId → session count
  const sessionCountByModule = React.useMemo(() => {
    const counts = new Map();
    draft.sessions.forEach((s) => {
      if (s.moduleId) counts.set(s.moduleId, (counts.get(s.moduleId) || 0) + 1);
    });
    return counts;
  }, [draft.sessions]);

  return (
    <section className="studio-card">
      <div className="section-row">
        <div>
          <h2>Modules</h2>
          <p>
            Define the semester or full-year modules that sessions belong to. Sessions are scheduled
            later, but every session must point to a module first.
          </p>
        </div>
        <div className="record-actions">
          <button
            className="ghost-btn"
            onClick={() => addModuleShellsForSemester(1)}
            disabled={baseCohorts.length === 0}
          >
            Create Semester 1 Module Shells
          </button>
          <button
            className="ghost-btn"
            onClick={() => addModuleShellsForSemester(2)}
            disabled={baseCohorts.length === 0}
          >
            Create Semester 2 Module Shells
          </button>
          <button
            className="primary-btn"
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
          <div className="empty-state-with-action">
            <p className="empty-state">No modules added yet.</p>
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
              Add your first module
            </button>
          </div>
        ) : (
          draft.modules.map((module, index) => {
            const moduleIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Module ${index + 1} is missing code, name, or subject\\.$`)
            );
            const tk = (field) => touched.has(`modules.${module.id}.${field}`);
            const touch = (field) => touchField(`modules.${module.id}.${field}`);
            const sessionCount = sessionCountByModule.get(module.id) || 0;

            return (
              <div key={module.id} className="editor-card">
                <div className="editor-card-header">
                  <span className="editor-card-label">
                    {module.code || "New module"}
                  </span>
                  {sessionCount > 0 && (
                    <span
                      className="tag-chip tag-chip-count"
                      title={`${sessionCount} session${sessionCount !== 1 ? "s" : ""} linked to this module`}
                    >
                      {sessionCount} session{sessionCount !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>

                <div className="form-grid four-column">
                  <label>
                    <span>Code</span>
                    <input
                      className={invalidClass(moduleIssue, tk("code"))}
                      value={module.code}
                      onChange={(e) => updateRecord("modules", module.id, "code", e.target.value)}
                      onBlur={() => touch("code")}
                    />
                    {moduleIssue && tk("code") && (
                      <small className="field-hint invalid">{moduleIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Name</span>
                    <input
                      className={invalidClass(moduleIssue, tk("name"))}
                      value={module.name}
                      onChange={(e) => updateRecord("modules", module.id, "name", e.target.value)}
                      onBlur={() => touch("name")}
                    />
                    {moduleIssue && tk("name") && (
                      <small className="field-hint invalid">{moduleIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Subject</span>
                    <input
                      className={invalidClass(moduleIssue, tk("subject_name"))}
                      value={module.subject_name}
                      onChange={(e) => updateRecord("modules", module.id, "subject_name", e.target.value)}
                      onBlur={() => touch("subject_name")}
                    />
                    {moduleIssue && tk("subject_name") && (
                      <small className="field-hint invalid">{moduleIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Year</span>
                    <input
                      type="number"
                      min="1"
                      max="6"
                      value={module.year}
                      onChange={(e) => updateRecord("modules", module.id, "year", e.target.value)}
                    />
                  </label>
                  <label>
                    <span>Semester</span>
                    <select
                      value={module.semester}
                      onChange={(e) => updateRecord("modules", module.id, "semester", e.target.value)}
                    >
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                    </select>
                  </label>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={module.is_full_year}
                      onChange={(e) =>
                        updateRecord("modules", module.id, "is_full_year", e.target.checked)
                      }
                    />
                    <span>Full-year module</span>
                  </label>
                </div>

                <div className="record-actions">
                  <button className="ghost-btn" onClick={() => duplicateRecord("modules", module.id)}>
                    Duplicate Module
                  </button>
                  <ConfirmDelete
                    label="Remove Module"
                    confirmMessage={`Remove "${module.code || module.name || "this module"}"?`}
                    cascadeNote={
                      sessionCount > 0
                        ? `This will also remove ${sessionCount} linked session${sessionCount !== 1 ? "s" : ""}.`
                        : undefined
                    }
                    onConfirm={() => removeRecord("modules", module.id)}
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
