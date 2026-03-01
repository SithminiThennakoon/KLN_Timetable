import React, { useEffect, useMemo, useState } from "react";
import "../styles/ViewTimetable.css";
import { timetableViewService } from "../services/timetableViewService";
import { pathwayService } from "../services/pathwayService";
import { lecturerService } from "../services/lecturerService";
import { roomService } from "../services/roomServiceNew";
import { sessionService } from "../services/sessionService";
import { moduleService } from "../services/moduleService";

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const times = [
  "08:00-09:00",
  "09:00-10:00",
  "10:00-11:00",
  "11:00-12:00",
  "12:00-13:00",
  "13:00-14:00",
  "14:00-15:00",
  "15:00-16:00",
  "16:00-17:00",
  "17:00-18:00",
];

function ViewTimetable() {
  const [entries, setEntries] = useState([]);
  const [manualEntries, setManualEntries] = useState([]);
  const [pathways, setPathways] = useState([]);
  const [lecturers, setLecturers] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [filters, setFilters] = useState({ pathway: "", lecturer: "", room: "" });
  const [selectedSession, setSelectedSession] = useState(null);
  const [validation, setValidation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [unscheduled, setUnscheduled] = useState([]);
  const [modules, setModules] = useState([]);
  const [sessionsInEntries, setSessionsInEntries] = useState([]);

  const loadAll = async () => {
    const [entriesData, pathwaysData, lecturersData, roomsData, unscheduledData, modulesData, expandedData] = await Promise.all([
      timetableViewService.listEntries(),
      pathwayService.list(),
      lecturerService.list(),
      roomService.list(),
      sessionService.listUnscheduled(),
      moduleService.list(),
      sessionService.listExpanded(),
    ]);
    setEntries(entriesData || []);
    setPathways(pathwaysData || []);
    setLecturers(lecturersData || []);
    setRooms(roomsData || []);
    setUnscheduled(unscheduledData || []);
    setModules(modulesData || []);
    setSessionsInEntries(expandedData || []);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleDrop = (dayIndex, timeIndex) => {
    if (!selectedSession) return;
    if (!filters.room) return;
    const timeslotId = dayIndex * times.length + timeIndex + 1;
    if (!rooms[0]?.id) return;
    const entry = {
      session_id: selectedSession.session_id,
      room_id: Number(filters.room),
      timeslot_id: timeslotId,
      group_number: selectedSession.group_number || 1,
    };
    setManualEntries((prev) => [...prev, entry]);
    setSelectedSession(null);
  };

  const handleValidate = async () => {
    setLoading(true);
    try {
      const result = await timetableViewService.validate(manualEntries);
      setValidation(result);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async () => {
    setLoading(true);
    try {
      const result = await timetableViewService.resolve(manualEntries);
      setValidation(result);
    } finally {
      setLoading(false);
    }
  };

  const handlePersistManual = async () => {
    setLoading(true);
    try {
      for (const entry of manualEntries) {
        await timetableViewService.createEntry({
          version: "manual",
          session_id: entry.session_id,
          room_id: entry.room_id,
          timeslot_id: entry.timeslot_id,
          group_number: entry.group_number,
          is_manual: true,
        });
      }
      setManualEntries([]);
      await loadAll();
    } finally {
      setLoading(false);
    }
  };

  const filteredEntries = useMemo(() => {
    return entries.filter((entry) => {
      if (filters.room && entry.room_id !== Number(filters.room)) return false;
      if (filters.lecturer) {
        const match = sessionsInEntries.find((s) => s.session_id === entry.session_id);
        if (!match || !match.lecturer_ids.includes(Number(filters.lecturer))) return false;
      }
      if (filters.pathway) {
        const match = sessionsInEntries.find((s) => s.session_id === entry.session_id);
        if (!match || !match.pathway_ids.includes(Number(filters.pathway))) return false;
      }
      return true;
    });
  }, [entries, filters, sessionsInEntries]);

  const filteredUnscheduled = useMemo(() => {
    return unscheduled.filter((session) => {
      if (filters.lecturer && !session.lecturer_ids.includes(Number(filters.lecturer))) return false;
      if (filters.pathway && !session.pathway_ids.includes(Number(filters.pathway))) return false;
      return true;
    });
  }, [unscheduled, filters]);

  const moduleLookup = useMemo(() => {
    const map = new Map();
    modules.forEach((mod) => map.set(mod.id, mod));
    return map;
  }, [modules]);

  return (
    <div className="page-shell">
      <div className="panel timetable-panel">
        <div className="timetable-header">
          <div>
            <h1 className="section-title">Timetable View</h1>
            <p className="section-subtitle">Drag unscheduled sessions into the grid.</p>
          </div>
          <div className="timetable-actions">
            <button className="ghost-btn" onClick={handleValidate} disabled={loading}>
              Validate
            </button>
            <button className="primary-btn" onClick={handleResolve} disabled={loading}>
              Resolve
            </button>
            <button className="ghost-btn" onClick={handlePersistManual} disabled={loading || manualEntries.length === 0}>
              Save Manual
            </button>
          </div>
        </div>

        <div className="filter-row">
          <select value={filters.pathway} onChange={(e) => setFilters((f) => ({ ...f, pathway: e.target.value }))}>
            <option value="">All Pathways</option>
            {pathways.map((p) => (
              <option key={p.id} value={p.id}>{p.name} (Y{p.year})</option>
            ))}
          </select>
          <select value={filters.lecturer} onChange={(e) => setFilters((f) => ({ ...f, lecturer: e.target.value }))}>
            <option value="">All Lecturers</option>
            {lecturers.map((l) => (
              <option key={l.id} value={l.id}>{l.name}</option>
            ))}
          </select>
          <select value={filters.room} onChange={(e) => setFilters((f) => ({ ...f, room: e.target.value }))}>
            <option value="">Select Room for Manual</option>
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
        </div>

        {validation && (
          <div className={`info-banner ${validation.valid ? "valid" : "invalid"}`}>
            {validation.valid ? "No conflicts found." : "Conflicts detected. Check details below."}
          </div>
        )}

        <div className="timetable-grid">
          <div className="grid-header" />
          {days.map((day) => (
            <div key={day} className="grid-header">{day}</div>
          ))}

          {times.map((time, timeIndex) => (
            <React.Fragment key={time}>
              <div className="grid-time">{time}</div>
              {days.map((day, dayIndex) => (
                <div
                  key={`${day}-${time}`}
                  className="grid-cell"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDrop(dayIndex, timeIndex)}
                >
                  {filteredEntries
                    .filter((e) => e.timeslot_id === dayIndex * times.length + timeIndex + 1)
                    .map((entry) => (
                      <div key={entry.id} className="entry-card">
                        Session {entry.session_id} / Room {entry.room_id}
                      </div>
                    ))}
                </div>
              ))}
            </React.Fragment>
          ))}
        </div>

        <aside className="unscheduled-panel">
          <h2>Unscheduled Sessions</h2>
          {!filters.room && (
            <p className="empty-state">Select a room to enable drag-and-drop.</p>
          )}
          {filteredUnscheduled.length === 0 && (
            <p className="empty-state">No unscheduled sessions.</p>
          )}
          {filteredUnscheduled.map((s) => (
            <div
              key={`${s.session_id}-${s.group_number}`}
              className="entry-card draggable"
              draggable
              onDragStart={() => setSelectedSession(s)}
            >
              {moduleLookup.get(s.module_id)?.code || `Module ${s.module_id}`} •
              Session {s.session_id} • Group {s.group_number}
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}
export default ViewTimetable;
