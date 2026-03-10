import React from "react";
import { findRecordIssue, invalidClass, makeId } from "./setupHelpers";
import { ConfirmDelete } from "./ConfirmDelete";

export function CohortsStep({
  draft,
  validation,
  touched,
  touchField,
  updateRecord,
  removeRecord,
  duplicateRecord,
  addRecord,
  addOverrideTemplatesFromBaseCohorts,
}) {
  const degreeOptions = draft.degrees;
  const pathOptions = draft.paths;
  const baseCohorts = draft.cohorts.filter((c) => c.kind === "base");
  const overrideCohorts = draft.cohorts.filter((c) => c.kind === "override");

  return (
    <div className="studio-grid">
      {/* ── Base Cohorts ── */}
      <section className="studio-card">
        <div className="section-row">
          <div>
            <h2>Base Cohorts</h2>
            <p>
              Derived from degree, year, and path structure. Enter student counts here — these
              drive room capacity checks and session audience sizes.
            </p>
          </div>
        </div>

        <div className="editor-list">
          {baseCohorts.length === 0 ? (
            <p className="empty-state">Add degrees and paths first — cohorts are auto-created from structure.</p>
          ) : (
            baseCohorts.map((cohort, index) => {
              const degree = degreeOptions.find((d) => d.id === cohort.degreeId);
              const path = pathOptions.find((p) => p.id === cohort.pathId);
              const cohortNameIssue = findRecordIssue(
                validation.blocking,
                new RegExp(`^Base cohort ${index + 1} is missing a name\\.$`)
              );
              const cohortSizeIssue = findRecordIssue(
                validation.blocking,
                new RegExp(`^Base cohort ${index + 1} needs a positive student count\\.$`)
              );
              const tk = (field) => touched.has(`cohorts.${cohort.id}.${field}`);
              const touch = (field) => touchField(`cohorts.${cohort.id}.${field}`);

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
                        className={invalidClass(cohortNameIssue, tk("name"))}
                        value={cohort.name}
                        onChange={(e) => updateRecord("cohorts", cohort.id, "name", e.target.value)}
                        onBlur={() => touch("name")}
                      />
                      {cohortNameIssue && tk("name") && (
                        <small className="field-hint invalid">{cohortNameIssue}</small>
                      )}
                    </label>
                    <label>
                      <span>Student count</span>
                      <input
                        className={invalidClass(cohortSizeIssue, tk("size"))}
                        type="number"
                        min="1"
                        value={cohort.size}
                        onChange={(e) => updateRecord("cohorts", cohort.id, "size", e.target.value)}
                        onBlur={() => touch("size")}
                      />
                      {cohortSizeIssue && tk("size") && (
                        <small className="field-hint invalid">{cohortSizeIssue}</small>
                      )}
                    </label>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* ── Override Groups ── */}
      <section className="studio-card">
        <div className="section-row">
          <div>
            <h2>Override Groups</h2>
            <p>
              Add elective or special attendance groups only when attendance itself differs from the
              base cohort — e.g. students from multiple years taking one elective together.
            </p>
          </div>
          <div className="record-actions">
            <button
              className="ghost-btn"
              onClick={addOverrideTemplatesFromBaseCohorts}
              disabled={baseCohorts.length === 0}
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
          {overrideCohorts.length === 0 ? (
            <p className="empty-state">No override groups added.</p>
          ) : (
            overrideCohorts.map((cohort, index) => {
              const overrideIdentityIssue = findRecordIssue(
                validation.blocking,
                new RegExp(`^Override group ${index + 1} is missing degree or name\\.$`)
              );
              const overrideSizeIssue = findRecordIssue(
                validation.blocking,
                new RegExp(`^Override group ${index + 1} needs a positive student count\\.$`)
              );
              const tk = (field) => touched.has(`cohorts.${cohort.id}.${field}`);
              const touch = (field) => touchField(`cohorts.${cohort.id}.${field}`);

              return (
                <div key={cohort.id} className="editor-card">
                  <div className="form-grid four-column">
                    <label>
                      <span>Degree</span>
                      <select
                        className={invalidClass(overrideIdentityIssue, tk("degreeId"))}
                        value={cohort.degreeId}
                        onChange={(e) => updateRecord("cohorts", cohort.id, "degreeId", e.target.value)}
                        onBlur={() => touch("degreeId")}
                      >
                        <option value="">Select degree</option>
                        {degreeOptions.map((d) => (
                          <option key={d.id} value={d.id}>{d.code}</option>
                        ))}
                      </select>
                      {overrideIdentityIssue && tk("degreeId") && (
                        <small className="field-hint invalid">{overrideIdentityIssue}</small>
                      )}
                    </label>
                    <label>
                      <span>Year</span>
                      <input
                        type="number"
                        min="1"
                        max="6"
                        value={cohort.year}
                        onChange={(e) => updateRecord("cohorts", cohort.id, "year", e.target.value)}
                      />
                    </label>
                    <label>
                      <span>Path</span>
                      <select
                        value={cohort.pathId}
                        onChange={(e) => updateRecord("cohorts", cohort.id, "pathId", e.target.value)}
                      >
                        <option value="">General</option>
                        {pathOptions
                          .filter((p) => p.degreeId === cohort.degreeId)
                          .map((p) => (
                            <option key={p.id} value={p.id}>{p.code}</option>
                          ))}
                      </select>
                    </label>
                    <label>
                      <span>Student count</span>
                      <input
                        className={invalidClass(overrideSizeIssue, tk("size"))}
                        type="number"
                        min="1"
                        value={cohort.size}
                        onChange={(e) => updateRecord("cohorts", cohort.id, "size", e.target.value)}
                        onBlur={() => touch("size")}
                      />
                      {overrideSizeIssue && tk("size") && (
                        <small className="field-hint invalid">{overrideSizeIssue}</small>
                      )}
                    </label>
                    <label className="full-span">
                      <span>Override group name</span>
                      <input
                        className={invalidClass(overrideIdentityIssue, tk("name"))}
                        value={cohort.name}
                        onChange={(e) => updateRecord("cohorts", cohort.id, "name", e.target.value)}
                        onBlur={() => touch("name")}
                      />
                      {overrideIdentityIssue && tk("name") && (
                        <small className="field-hint invalid">{overrideIdentityIssue}</small>
                      )}
                    </label>
                  </div>
                  <div className="record-actions">
                    <button className="ghost-btn" onClick={() => duplicateRecord("cohorts", cohort.id)}>
                      Duplicate Override
                    </button>
                    <ConfirmDelete
                      label="Remove Override"
                      confirmMessage={`Remove "${cohort.name || "this override group"}"?`}
                      onConfirm={() => removeRecord("cohorts", cohort.id)}
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
