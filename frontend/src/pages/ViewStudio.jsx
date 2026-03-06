import React, { useEffect, useMemo, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const startMinutes = [480, 540, 600, 660, 780, 840, 900, 960, 1020];

function formatMinute(minute) {
  const hour = Math.floor(minute / 60);
  const mins = String(minute % 60).padStart(2, "0");
  return `${String(hour).padStart(2, "0")}:${mins}`;
}

function downloadBase64(filename, contentType, content) {
  const bytes = atob(content);
  const array = new Uint8Array(bytes.length);
  for (let index = 0; index < bytes.length; index += 1) {
    array[index] = bytes.charCodeAt(index);
  }
  const blob = new Blob([array], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function ViewStudio() {
  const [mode, setMode] = useState("admin");
  const [view, setView] = useState(null);
  const [lookups, setLookups] = useState({ lecturers: [], student_groups: [] });
  const [selectedLecturerId, setSelectedLecturerId] = useState("");
  const [selectedStudentGroupId, setSelectedStudentGroupId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadView = async (nextMode = mode) => {
    setLoading(true);
    setError("");
    try {
      const response = await timetableStudioService.view({
        mode: nextMode,
        lecturerId: nextMode === "lecturer" ? selectedLecturerId : undefined,
        studentGroupId: nextMode === "student" ? selectedStudentGroupId : undefined,
      });
      setView(response);
    } catch (err) {
      setError(err.message);
      setView(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadView();
    timetableStudioService.getLookups().then(setLookups).catch(() => {});
  }, []);

  const entryMap = useMemo(() => {
    const map = new Map();
    (view?.solution?.entries || []).forEach((entry) => {
      const key = `${entry.day}-${entry.start_minute}`;
      const items = map.get(key) || [];
      items.push(entry);
      map.set(key, items);
    });
    return map;
  }, [view]);

  const handleModeChange = async (nextMode) => {
    setMode(nextMode);
    await loadView(nextMode);
  };

  const handleApplyFilters = async () => {
    await loadView(mode);
  };

  const handleExport = async (format) => {
    try {
      const response = await timetableStudioService.exportView({ mode, format });
      downloadBase64(response.filename, response.content_type, response.content);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="page-shell">
      <div className="panel studio-panel">
        <div className="studio-header">
          <div>
            <h1 className="section-title">Timetable Views</h1>
            <p className="section-subtitle">
              Review the default timetable in admin, lecturer, or student mode and export the current view.
            </p>
          </div>
          <div className="studio-actions wrap">
            <select value={mode} onChange={(event) => handleModeChange(event.target.value)}>
              <option value="admin">Admin View</option>
              <option value="lecturer">Lecturer View</option>
              <option value="student">Student View</option>
            </select>
            {mode === "lecturer" && (
              <select value={selectedLecturerId} onChange={(event) => setSelectedLecturerId(event.target.value)}>
                <option value="">Select Lecturer</option>
                {lookups.lecturers.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            )}
            {mode === "student" && (
              <select value={selectedStudentGroupId} onChange={(event) => setSelectedStudentGroupId(event.target.value)}>
                <option value="">Select Student Group</option>
                {lookups.student_groups.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            )}
            {mode !== "admin" && <button className="ghost-btn" onClick={handleApplyFilters}>Apply</button>}
            <button className="ghost-btn" onClick={() => handleExport("pdf")}>PDF</button>
            <button className="ghost-btn" onClick={() => handleExport("csv")}>CSV</button>
            <button className="ghost-btn" onClick={() => handleExport("xls")}>XLS</button>
            <button className="ghost-btn" onClick={() => handleExport("png")}>PNG</button>
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {loading && <div className="info-banner">Loading timetable view...</div>}

        {view && (
          <>
            <section className="studio-card">
              <h2>{view.title}</h2>
              <p>{view.subtitle}</p>
            </section>

            <section className="studio-card timetable-grid-card">
              <div className="v2-grid">
                <div className="grid-header">Time</div>
                {days.map((day) => (
                  <div key={day} className="grid-header">{day}</div>
                ))}
                {startMinutes.map((minute) => (
                  <React.Fragment key={minute}>
                    <div className="grid-time">{formatMinute(minute)}</div>
                    {days.map((day) => (
                      <div key={`${day}-${minute}`} className="grid-cell tall">
                        {(entryMap.get(`${day}-${minute}`) || []).map((entry, index) => (
                          <article key={`${day}-${minute}-${index}`} className="entry-card detailed">
                            <strong>{entry.module_code}</strong>
                            <span>{entry.session_name}</span>
                            <span>{entry.room_name}</span>
                            <span>{entry.lecturer_names.join(", ")}</span>
                            <span>{entry.degree_path_labels.join(" | ")}</span>
                            <span>{entry.total_students} students</span>
                          </article>
                        ))}
                      </div>
                    ))}
                  </React.Fragment>
                ))}
              </div>
            </section>

            <section className="studio-card">
              <h2>Session Detail List</h2>
              <div className="entry-list">
                {view.solution.entries.map((entry, index) => (
                  <div key={`${entry.session_id}-${index}`} className="entry-row">
                    <div>
                      <strong>{entry.module_code} - {entry.session_name}</strong>
                      <p>{entry.day} {formatMinute(entry.start_minute)} for {entry.duration_minutes} minutes</p>
                    </div>
                    <div>
                      <span>{entry.room_name}</span>
                      <span>{entry.total_students} students</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default ViewStudio;
