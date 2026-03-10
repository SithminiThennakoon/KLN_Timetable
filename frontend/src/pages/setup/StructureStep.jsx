import React from "react";
import { findRecordIssue, invalidClass, makeId } from "./setupHelpers";
import { ConfirmDelete } from "./ConfirmDelete";

export function StructureStep({
  draft,
  validation,
  touched,
  touchField,
  updateRecord,
  removeRecord,
  addRecord,
  addScienceStructureTemplates,
}) {
  const degreeOptions = draft.degrees;

  // Count paths/cohorts per degree for cascade warnings
  function cascadeNoteForDegree(degreeId) {
    const pathCount = draft.paths.filter((p) => p.degreeId === degreeId).length;
    const cohortCount = draft.cohorts.filter((c) => c.degreeId === degreeId).length;
    const parts = [];
    if (pathCount > 0) parts.push(`${pathCount} path${pathCount > 1 ? "s" : ""}`);
    if (cohortCount > 0) parts.push(`${cohortCount} cohort${cohortCount > 1 ? "s" : ""}`);
    return parts.length > 0 ? `This will also remove ${parts.join(" and ")}.` : undefined;
  }

  return (
    <div className="studio-grid">
      {/* ── Degrees ── */}
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
            <div className="empty-state-with-action">
              <p className="empty-state">No degrees added yet.</p>
              <button
                className="ghost-btn"
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
                Add your first degree
              </button>
            </div>
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
              const tk = (field) => touched.has(`degrees.${degree.id}.${field}`);
              const touch = (field) => touchField(`degrees.${degree.id}.${field}`);

              return (
                <div key={degree.id} className="editor-card">
                  <div className="editor-card-header">
                    <span className="editor-card-label">
                      {degree.code || degree.name || `Degree ${index + 1}`}
                    </span>
                    {draft.paths.filter((p) => p.degreeId === degree.id).length > 0 && (
                      <span className="tag-chip tag-chip-count">
                        {draft.paths.filter((p) => p.degreeId === degree.id).length} path
                        {draft.paths.filter((p) => p.degreeId === degree.id).length > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  <div className="form-grid degree-row degree-row-actions">
                    <label>
                      <span>Code</span>
                      <input
                        className={invalidClass(degreeIssue, tk("code"))}
                        value={degree.code}
                        onChange={(e) => updateRecord("degrees", degree.id, "code", e.target.value)}
                        onBlur={() => touch("code")}
                      />
                      {degreeIssue && tk("code") && <small className="field-hint invalid">{degreeIssue}</small>}
                    </label>
                    <label>
                      <span>Name</span>
                      <input
                        className={invalidClass(degreeIssue, tk("name"))}
                        value={degree.name}
                        onChange={(e) => updateRecord("degrees", degree.id, "name", e.target.value)}
                        onBlur={() => touch("name")}
                      />
                      {degreeIssue && tk("name") && <small className="field-hint invalid">{degreeIssue}</small>}
                    </label>
                    <label>
                      <span>Duration</span>
                      <input
                        className={invalidClass(degreeDurationIssue, tk("duration_years"))}
                        type="number"
                        min="1"
                        max="6"
                        value={degree.duration_years}
                        onChange={(e) => updateRecord("degrees", degree.id, "duration_years", e.target.value)}
                        onBlur={() => touch("duration_years")}
                      />
                      {degreeDurationIssue && tk("duration_years") && (
                        <small className="field-hint invalid">{degreeDurationIssue}</small>
                      )}
                    </label>
                    <label>
                      <span>Intake label</span>
                      <input
                        className={invalidClass(degreeIssue, tk("intake_label"))}
                        value={degree.intake_label}
                        onChange={(e) => updateRecord("degrees", degree.id, "intake_label", e.target.value)}
                        onBlur={() => touch("intake_label")}
                      />
                      {degreeIssue && tk("intake_label") && (
                        <small className="field-hint invalid">{degreeIssue}</small>
                      )}
                    </label>
                    <div className="inline-delete-wrap">
                      <ConfirmDelete
                        label="Delete"
                        className="danger-btn danger-icon-btn"
                        confirmMessage={`Delete ${degree.code || degree.name || "this degree"}?`}
                        cascadeNote={cascadeNoteForDegree(degree.id)}
                        onConfirm={() => removeRecord("degrees", degree.id)}
                      />
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* ── Paths ── */}
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
            <p className="empty-state">
              Direct-entry degrees can be left without paths — a general cohort will be created per year.
            </p>
          ) : (
            draft.paths.map((path, index) => {
              const pathIssue = findRecordIssue(
                validation.blocking,
                new RegExp(`^Path ${index + 1} is missing degree, code, or name\\.$`)
              );
              const tk = (field) => touched.has(`paths.${path.id}.${field}`);
              const touch = (field) => touchField(`paths.${path.id}.${field}`);

              return (
                <div key={path.id} className="editor-card">
                  <div className="form-grid four-column">
                    <label>
                      <span>Degree</span>
                      <select
                        className={invalidClass(pathIssue, tk("degreeId"))}
                        value={path.degreeId}
                        onChange={(e) => updateRecord("paths", path.id, "degreeId", e.target.value)}
                        onBlur={() => touch("degreeId")}
                      >
                        <option value="">Select degree</option>
                        {degreeOptions.map((d) => (
                          <option key={d.id} value={d.id}>{d.code}</option>
                        ))}
                      </select>
                      {pathIssue && tk("degreeId") && <small className="field-hint invalid">{pathIssue}</small>}
                    </label>
                    <label>
                      <span>Year</span>
                      <input
                        type="number"
                        min="1"
                        max="6"
                        value={path.year}
                        onChange={(e) => updateRecord("paths", path.id, "year", e.target.value)}
                      />
                    </label>
                    <label>
                      <span>Code</span>
                      <input
                        className={invalidClass(pathIssue, tk("code"))}
                        value={path.code}
                        onChange={(e) => updateRecord("paths", path.id, "code", e.target.value)}
                        onBlur={() => touch("code")}
                      />
                      {pathIssue && tk("code") && <small className="field-hint invalid">{pathIssue}</small>}
                    </label>
                    <label>
                      <span>Name</span>
                      <input
                        className={invalidClass(pathIssue, tk("name"))}
                        value={path.name}
                        onChange={(e) => updateRecord("paths", path.id, "name", e.target.value)}
                        onBlur={() => touch("name")}
                      />
                      {pathIssue && tk("name") && <small className="field-hint invalid">{pathIssue}</small>}
                    </label>
                  </div>
                  <div className="record-actions">
                    <ConfirmDelete
                      label="Remove Path"
                      confirmMessage={`Remove path "${path.code || path.name || "this path"}"?`}
                      onConfirm={() => removeRecord("paths", path.id)}
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}
