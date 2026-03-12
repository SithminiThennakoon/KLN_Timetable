import React from "react";
import { findRecordIssue, invalidClass, makeId } from "./setupHelpers";
import { ConfirmDelete } from "./ConfirmDelete";

export function RoomsStep({
  draft,
  validation,
  touched,
  touchField,
  updateRecord,
  removeRecord,
  duplicateRecord,
  addRecord,
  addRoomTemplateBatch,
}) {
  return (
    <section className="studio-card">
      <div className="section-row">
        <div>
          <h2>Rooms</h2>
          <p>
            Capture lecture halls, labs, capacities, and lab types. Under-entering the real room
            pool can cause generation to fail even when sessions are correct.
          </p>
          <p className="helper-copy" style={{ marginTop: 6 }}>
            <strong>Year restriction</strong> is stored with the dataset, but not currently enforced
            during timetable generation — use it as reference data only.
          </p>
        </div>
        <div className="record-actions">
          <button className="ghost-btn" onClick={() => addRoomTemplateBatch("lectureHalls")}>
            Add Lecture Hall Templates
          </button>
          <button className="ghost-btn" onClick={() => addRoomTemplateBatch("labs")}>
            Add Lab Templates
          </button>
          <button
            className="primary-btn"
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
          <div className="empty-state-with-action">
            <p className="empty-state">No rooms added yet.</p>
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
              Add your first room
            </button>
          </div>
        ) : (
          draft.rooms.map((room, roomIndex) => {
            const roomNameIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Room ${roomIndex + 1} is missing name or location\\.$`)
            );
            const roomCapacityIssue = findRecordIssue(
              validation.blocking,
              new RegExp(`^Room ${roomIndex + 1} needs a positive capacity\\.$`)
            );
            const tk = (field) => touched.has(`rooms.${room.id}.${field}`);
            const touch = (field) => touchField(`rooms.${room.id}.${field}`);

            return (
              <div key={room.id} className="editor-card">
                {/* Row 1: core identity */}
                <div className="form-grid rooms-primary-row">
                  <label>
                    <span>Name</span>
                    <input
                      className={invalidClass(roomNameIssue, tk("name"))}
                      value={room.name}
                      onChange={(e) => updateRecord("rooms", room.id, "name", e.target.value)}
                      onBlur={() => touch("name")}
                    />
                    {roomNameIssue && tk("name") && (
                      <small className="field-hint invalid">{roomNameIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Location</span>
                    <input
                      className={invalidClass(roomNameIssue, tk("location"))}
                      value={room.location}
                      onChange={(e) => updateRecord("rooms", room.id, "location", e.target.value)}
                      onBlur={() => touch("location")}
                    />
                    {roomNameIssue && tk("location") && (
                      <small className="field-hint invalid">{roomNameIssue}</small>
                    )}
                  </label>
                  <label>
                    <span>Capacity</span>
                    <input
                      className={invalidClass(roomCapacityIssue, tk("capacity"))}
                      type="number"
                      min="1"
                      value={room.capacity}
                      onChange={(e) => updateRecord("rooms", room.id, "capacity", e.target.value)}
                      onBlur={() => touch("capacity")}
                    />
                    {roomCapacityIssue && tk("capacity") && (
                      <small className="field-hint invalid">{roomCapacityIssue}</small>
                    )}
                  </label>
                </div>
                {/* Row 2: type details */}
                <div className="form-grid rooms-secondary-row">
                  <label>
                    <span>Room type</span>
                    <select
                      value={room.room_type}
                      onChange={(e) => updateRecord("rooms", room.id, "room_type", e.target.value)}
                    >
                      <option value="lecture">Lecture hall</option>
                      <option value="lab">Lab</option>
                      <option value="seminar">Seminar room</option>
                    </select>
                  </label>
                  <label>
                    <span>Lab type</span>
                    <input
                      placeholder={room.room_type === "lab" ? "e.g. physics, chemistry" : "Only for labs"}
                      value={room.lab_type}
                      onChange={(e) => updateRecord("rooms", room.id, "lab_type", e.target.value)}
                    />
                  </label>
                  <label>
                    <span>Year restriction</span>
                    <input
                      type="number"
                      min="1"
                      max="6"
                      placeholder="Optional"
                      value={room.year_restriction}
                      onChange={(e) => updateRecord("rooms", room.id, "year_restriction", e.target.value)}
                    />
                  </label>
                </div>
                <div className="record-actions">
                  <button className="ghost-btn" onClick={() => duplicateRecord("rooms", room.id)}>
                    Duplicate Room
                  </button>
                  <ConfirmDelete
                    label="Remove Room"
                    confirmMessage={`Remove "${room.name || "this room"}"?`}
                    onConfirm={() => removeRecord("rooms", room.id)}
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
