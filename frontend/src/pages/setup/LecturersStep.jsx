import React from "react";
import { makeId } from "./setupHelpers";
import { ConfirmDelete } from "./ConfirmDelete";

export function LecturersStep({
  draft,
  updateRecord,
  removeRecord,
  addRecord,
  addLecturerTemplateBatch,
}) {
  return (
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
            className="primary-btn"
            onClick={() =>
              addRecord("lecturers", { id: makeId("lecturer"), name: "", email: "" })
            }
          >
            Add Lecturer
          </button>
        </div>
      </div>

      <div className="editor-list">
        {draft.lecturers.length === 0 ? (
          <div className="empty-state-with-action">
            <p className="empty-state">No lecturers added yet.</p>
            <button
              className="ghost-btn"
              onClick={() =>
                addRecord("lecturers", { id: makeId("lecturer"), name: "", email: "" })
              }
            >
              Add your first lecturer
            </button>
          </div>
        ) : (
          draft.lecturers.map((lecturer) => (
            <div key={lecturer.id} className="editor-card">
              <div className="form-grid two-column">
                <label>
                  <span>Name</span>
                  <input
                    value={lecturer.name}
                    onChange={(e) => updateRecord("lecturers", lecturer.id, "name", e.target.value)}
                  />
                </label>
                <label>
                  <span>Email</span>
                  <input
                    type="email"
                    value={lecturer.email}
                    onChange={(e) => updateRecord("lecturers", lecturer.id, "email", e.target.value)}
                  />
                </label>
              </div>
              <div className="record-actions">
                <ConfirmDelete
                  label="Remove Lecturer"
                  confirmMessage={`Remove "${lecturer.name || "this lecturer"}"?`}
                  onConfirm={() => removeRecord("lecturers", lecturer.id)}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
