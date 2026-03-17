import React from "react";
import { makeId } from "./setupHelpers";
import { ConfirmDelete } from "./ConfirmDelete";

export function LecturersStep({
  draft,
  updateRecord,
  removeRecord,
  addRecord,
  addLecturerTemplateBatch,
  onEdit,
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

      <div className="lecturer-table-wrap">
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
          <table className="lecturer-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th className="lecturer-actions-header">Action</th>
              </tr>
            </thead>
            <tbody>
              {draft.lecturers.map((lecturer) => (
                <tr key={lecturer.id}>
                  <td>{lecturer.name}</td>
                  <td>{lecturer.email}</td>
                  <td className="lecturer-actions-cell">
                    <button
                      className="ghost-btn lecturer-edit-btn"
                      onClick={() => onEdit && onEdit(lecturer)}
                    >
                      Edit
                    </button>
                    <ConfirmDelete
                      label="Remove"
                      confirmMessage={`Remove "${lecturer.name || "this lecturer"}"?`}
                      onConfirm={() => removeRecord("lecturers", lecturer.id)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
