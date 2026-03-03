import React, { useEffect, useMemo, useState } from "react";
import "../styles/DatabaseDashboard.css";
import { dataStatusService } from "../services/dataStatusService";
import { subjectService } from "../services/subjectService";
import { pathwayService } from "../services/pathwayService";
import { moduleService } from "../services/moduleService";
import { sessionService } from "../services/sessionService";
import { lecturerService } from "../services/lecturerService";
import { roomService } from "../services/roomServiceNew";

const tabs = [
  "Subjects",
  "Pathways",
  "Modules",
  "Sessions",
  "Lecturers",
  "Rooms",
];

const emptyModal = {
  open: false,
  mode: "create",
  payload: null,
};

function DatabaseDashboard() {
  const [activeTab, setActiveTab] = useState("Subjects");
  const [status, setStatus] = useState({ ready: false, issues: [], warnings: [] });
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [modal, setModal] = useState(emptyModal);
  const [error, setError] = useState("");

  const [subjects, setSubjects] = useState([]);
  const [pathways, setPathways] = useState([]);
  const [modules, setModules] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [lecturers, setLecturers] = useState([]);
  const [rooms, setRooms] = useState([]);

  const [form, setForm] = useState({});

  const refreshStatus = async () => {
    setLoadingStatus(true);
    try {
      const data = await dataStatusService.get();
      setStatus(data);
    } catch (err) {
      setStatus({ ready: false, issues: [err.message], warnings: [] });
    } finally {
      setLoadingStatus(false);
    }
  };

  const fetchAll = async () => {
    try {
      const [subj, path, mod, sess, lect, room] = await Promise.all([
        subjectService.list(),
        pathwayService.list(),
        moduleService.list(),
        sessionService.list(),
        lecturerService.list(),
        roomService.list(),
      ]);
      setSubjects(subj || []);
      setPathways(path || []);
      setModules(mod || []);
      setSessions(sess || []);
      setLecturers(lect || []);
      setRooms(room || []);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchAll();
    refreshStatus();
  }, []);

  useEffect(() => {
    if (modal.open && modal.payload) {
      setForm(modal.payload);
    } else if (!modal.open) {
      setForm({});
    }
  }, [modal]);

  const handleOpenCreate = () => {
    setModal({ open: true, mode: "create", payload: {} });
  };

  const handleOpenEdit = (payload) => {
    setModal({ open: true, mode: "edit", payload });
  };

  const handleClose = () => {
    setModal(emptyModal);
    setError("");
  };

  const handleDelete = async (entity, id) => {
    try {
      if (entity === "Subjects") await subjectService.remove(id);
      if (entity === "Pathways") await pathwayService.remove(id);
      if (entity === "Modules") await moduleService.remove(id);
      if (entity === "Sessions") await sessionService.remove(id);
      if (entity === "Lecturers") await lecturerService.remove(id);
      if (entity === "Rooms") await roomService.remove(id);
      await fetchAll();
      await refreshStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSave = async () => {
    try {
      if (activeTab === "Subjects") {
        if (modal.mode === "create") await subjectService.create(form);
        else await subjectService.update(form.id, form);
      }
      if (activeTab === "Pathways") {
        if (modal.mode === "create") await pathwayService.create(form);
        else await pathwayService.update(form.id, form);
      }
      if (activeTab === "Modules") {
        if (modal.mode === "create") await moduleService.create(form);
        else await moduleService.update(form.id, form);
      }
      if (activeTab === "Sessions") {
        if (modal.mode === "create") await sessionService.create(form);
        else await sessionService.update(form.id, form);
      }
      if (activeTab === "Lecturers") {
        if (modal.mode === "create") await lecturerService.create(form);
        else await lecturerService.update(form.id, form);
      }
      if (activeTab === "Rooms") {
        if (modal.mode === "create") await roomService.create(form);
        else await roomService.update(form.id, form);
      }
      await fetchAll();
      await refreshStatus();
      handleClose();
    } catch (err) {
      setError(err.message);
    }
  };

  const tableRows = useMemo(() => {
    if (activeTab === "Subjects") return subjects;
    if (activeTab === "Pathways") return pathways;
    if (activeTab === "Modules") return modules;
    if (activeTab === "Sessions") return sessions;
    if (activeTab === "Lecturers") return lecturers;
    if (activeTab === "Rooms") return rooms;
    return [];
  }, [activeTab, subjects, pathways, modules, sessions, lecturers, rooms]);

  const renderColumns = () => {
    switch (activeTab) {
      case "Subjects":
        return ["id", "name", "code", "department_id"];
      case "Pathways":
        return ["id", "name", "department_id", "year", "subject_ids"];
      case "Modules":
        return ["id", "code", "name", "subject_id", "year", "semester"];
      case "Sessions":
        return [
          "id",
          "module_id",
          "session_type",
          "duration_hours",
          "frequency_per_week",
          "student_count",
          "max_students_per_group",
          "concurrent_split",
          "lecturer_ids",
        ];
      case "Lecturers":
        return ["id", "name", "email", "max_hours_per_week"];
      case "Rooms":
        return ["id", "name", "capacity", "room_type", "lab_type", "location", "year_restriction"];
      default:
        return [];
    }
  };

  const columns = renderColumns();

  return (
    <div className="page-shell">
      <div className="panel">
        <header className="db-header">
          <div>
            <h1 className="section-title">Database Management</h1>
            <p className="section-subtitle">Enter faculty data to unlock generation.</p>
          </div>
          <button className="primary-btn" onClick={handleOpenCreate}>Add New</button>
        </header>

        <section className={`status-banner ${status.ready ? "ready" : "blocked"}`}>
          {loadingStatus ? (
            <span>Checking data readiness...</span>
          ) : status.ready ? (
            <span>Ready to generate. All required data is present.</span>
          ) : (
            <div>
              <strong>Missing requirements:</strong>
              <ul>
                {status.issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {status.warnings.length > 0 && (
            <div className="status-warnings">
              <strong>Warnings:</strong>
              <ul>
                {status.warnings.map((warning, idx) => (
                  <li key={idx}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <nav className="db-tabs">
          {tabs.map((tab) => (
            <button
              key={tab}
              className={`db-tab ${activeTab === tab ? "active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>

        {error && <div className="error-banner">{error}</div>}

        <div className="db-table-wrapper">
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column.replace(/_/g, " ")}</th>
                ))}
                <th>actions</th>
              </tr>
            </thead>
            <tbody>
              {tableRows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 1} className="empty-state">
                    No records yet.
                  </td>
                </tr>
              ) : (
                tableRows.map((row) => (
                  <tr key={row.id}>
                    {columns.map((column) => (
                      <td key={`${row.id}-${column}`}>
                        {Array.isArray(row[column]) ? row[column].join(", ") : String(row[column] ?? "-")}
                      </td>
                    ))}
                    <td className="row-actions">
                      <button className="ghost-btn" onClick={() => handleOpenEdit(row)}>Edit</button>
                      <button className="danger-btn" onClick={() => handleDelete(activeTab, row.id)}>Delete</button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {modal.open && (
        <div className="modal-backdrop" onClick={handleClose}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>{modal.mode === "create" ? "Add" : "Edit"} {activeTab.slice(0, -1)}</h2>
              <button className="ghost-btn" onClick={handleClose}>Close</button>
            </div>
            <div className="modal-body">
              {columns.filter((col) => col !== "id").map((column) => (
                <label key={column}>
                  <span>{column.replace(/_/g, " ")}</span>
                  <input
                    value={form[column] ?? ""}
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        [column]: column.endsWith("_ids")
                          ? event.target.value.split(",").map((v) => Number(v.trim())).filter(Boolean)
                          : column.includes("count") || column.includes("year") || column.includes("semester") || column.includes("hours") || column.includes("capacity")
                          ? Number(event.target.value)
                          : event.target.value,
                      }))
                    }
                    placeholder={column.endsWith("_ids") ? "comma separated IDs" : ""}
                  />
                </label>
              ))}
            </div>
            {error && <div className="error-banner">{error}</div>}
            <div className="modal-footer">
              <button className="ghost-btn" onClick={handleClose}>Cancel</button>
              <button className="primary-btn" onClick={handleSave}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DatabaseDashboard;
