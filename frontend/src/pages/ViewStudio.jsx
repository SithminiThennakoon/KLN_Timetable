import React, { useEffect, useMemo, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const startMinutes = [480, 540, 600, 660, 780, 840, 900, 960, 1020];
const calendarStartMinute = 8 * 60;
const calendarEndMinute = 18 * 60;
const minuteHeight = 1.05;
const calendarTopInset = 12;
const maxCalendarLanes = 6;

function formatMinute(minute) {
  const hour = Math.floor(minute / 60);
  const mins = String(minute % 60).padStart(2, "0");
  return `${String(hour).padStart(2, "0")}:${mins}`;
}

function formatCalendarHour(minute) {
  const hour = Math.floor(minute / 60);
  const mins = String(minute % 60).padStart(2, "0");
  return { hour: String(hour), mins: `:${mins}` };
}

function compactSessionName(moduleCode, sessionName) {
  if (!sessionName) {
    return "";
  }
  const normalizedModuleCode = (moduleCode || "").trim();
  const normalizedSessionName = sessionName.trim();
  if (normalizedModuleCode && normalizedSessionName.startsWith(normalizedModuleCode)) {
    return normalizedSessionName.slice(normalizedModuleCode.length).trim() || normalizedSessionName;
  }
  return normalizedSessionName;
}

function compactLecturerNames(names = []) {
  if (names.length <= 1) {
    return names[0] || "";
  }
  return `${names[0]} +${names.length - 1}`;
}

function compactAudienceLabels(labels = []) {
  if (labels.length <= 2) {
    return labels.join(" | ");
  }
  return `${labels.slice(0, 2).join(" | ")} +${labels.length - 2} more`;
}

function getEntryToneClass(entry) {
  const label = `${entry.session_name || ""} ${entry.module_name || ""}`.toLowerCase();
  if (label.includes("lab") || label.includes("laboratory")) {
    return "is-lab";
  }
  return "is-lecture";
}

function buildCalendarPlacements(entries = []) {
  const placements = new Map();

  days.forEach((day) => {
    const dayEntries = entries
      .filter(
        (entry) =>
          entry.day === day &&
          entry.start_minute >= calendarStartMinute &&
          entry.start_minute < calendarEndMinute
      )
      .slice()
      .sort((left, right) => {
        if (left.start_minute !== right.start_minute) {
          return left.start_minute - right.start_minute;
        }
        return right.duration_minutes - left.duration_minutes;
      });

    const laneEnds = [];
    const laneByEntry = new Map();
    dayEntries.forEach((entry) => {
      const endMinute = entry.start_minute + entry.duration_minutes;
      let lane = laneEnds.findIndex((laneEnd) => entry.start_minute >= laneEnd);
      if (lane === -1) {
        if (laneEnds.length < maxCalendarLanes) {
          lane = laneEnds.length;
          laneEnds.push(endMinute);
        } else {
          let earliestLane = 0;
          for (let index = 1; index < laneEnds.length; index += 1) {
            if (laneEnds[index] < laneEnds[earliestLane]) {
              earliestLane = index;
            }
          }
          lane = earliestLane;
          laneEnds[lane] = endMinute;
        }
      } else {
        laneEnds[lane] = endMinute;
      }
      laneByEntry.set(entry, lane);
    });

    const laneCount = maxCalendarLanes;
    dayEntries.forEach((entry) => {
      placements.set(entry, {
        lane: laneByEntry.get(entry) || 0,
        laneCount,
        top: Math.max(0, calendarTopInset + (entry.start_minute - calendarStartMinute) * minuteHeight),
        height: Math.max(56, entry.duration_minutes * minuteHeight),
      });
    });
  });

  return placements;
}

function entryCalendarStyle(placement) {
  const gapPx = 10;
  const laneWidth = 100 / placement.laneCount;
  return {
    top: `${placement.top + 5}px`,
    height: `${Math.max(placement.height - 10, 48)}px`,
    left: `calc(${laneWidth * placement.lane}% + ${placement.lane * gapPx}px)`,
    width: `calc(${laneWidth}% - ${gapPx * (placement.laneCount - 1) / placement.laneCount}px)`,
    boxSizing: "border-box",
  };
}

function buildAgendaDays(entries = []) {
  return days
    .map((day) => ({
      day,
      entries: entries
        .filter((entry) => entry.day === day)
        .slice()
        .sort((left, right) => left.start_minute - right.start_minute || right.duration_minutes - left.duration_minutes),
    }))
    .filter((item) => item.entries.length > 0);
}

function formatEntrySummary(entry) {
  return `${entry.day} ${formatMinute(entry.start_minute)} for ${entry.duration_minutes} minutes`;
}

function getEntryKey(entry, index) {
  return `${entry.session_id}-${entry.occurrence_index ?? 1}-${index}`;
}

function findEntryIndex(entries, target) {
  return entries.findIndex(
    (entry) =>
      entry.session_id === target.session_id &&
      (entry.occurrence_index ?? 1) === (target.occurrence_index ?? 1) &&
      entry.day === target.day &&
      entry.start_minute === target.start_minute
  );
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

function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function exportWorkbook(view, entryMap) {
  const XLSX = await import("xlsx");
  const workbook = XLSX.utils.book_new();

  const gridRows = startMinutes.map((minute) => {
    const row = { Time: formatMinute(minute) };
    days.forEach((day) => {
      const entries = entryMap.get(`${day}-${minute}`) || [];
      row[day] = entries
        .map(
          (entry) =>
            `${entry.module_code} ${entry.session_name}\n${entry.room_name}\n${entry.lecturer_names.join(", ")}\n${entry.total_students} students`
        )
        .join("\n\n");
    });
    return row;
  });

  const detailRows = view.solution.entries.map((entry) => ({
    Day: entry.day,
    Start: formatMinute(entry.start_minute),
    Duration: entry.duration_minutes,
    ModuleCode: entry.module_code,
    ModuleName: entry.module_name,
    Session: entry.session_name,
    Room: entry.room_name,
    Location: entry.room_location,
    Lecturers: entry.lecturer_names.join(", "),
    StudentGroups: entry.student_group_names.join(", "),
    DegreePaths: entry.degree_path_labels.join(" | "),
    Students: entry.total_students,
  }));

  const summaryRows = [
    { Field: "Title", Value: view.title },
    { Field: "Subtitle", Value: view.subtitle },
    { Field: "Mode", Value: view.mode },
    { Field: "Entry count", Value: view.solution.entries.length },
    { Field: "Exported at", Value: new Date().toISOString() },
  ];

  const gridSheet = XLSX.utils.json_to_sheet(gridRows);
  const detailSheet = XLSX.utils.json_to_sheet(detailRows);
  const summarySheet = XLSX.utils.json_to_sheet(summaryRows);

  gridSheet["!cols"] = [{ wch: 10 }, ...days.map(() => ({ wch: 34 }))];
  detailSheet["!cols"] = [
    { wch: 12 },
    { wch: 8 },
    { wch: 10 },
    { wch: 14 },
    { wch: 28 },
    { wch: 26 },
    { wch: 18 },
    { wch: 18 },
    { wch: 26 },
    { wch: 26 },
    { wch: 28 },
    { wch: 10 },
  ];
  summarySheet["!cols"] = [{ wch: 18 }, { wch: 48 }];

  XLSX.utils.book_append_sheet(workbook, summarySheet, "Summary");
  XLSX.utils.book_append_sheet(workbook, gridSheet, "Timetable");
  XLSX.utils.book_append_sheet(workbook, detailSheet, "Session Details");

  XLSX.writeFile(workbook, `${view.mode}-timetable.xlsx`);
}

async function exportPdf(view, entryMap) {
  const [{ default: jsPDF }] = await Promise.all([
    import("jspdf"),
    import("jspdf-autotable"),
  ]);
  const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
  doc.setFontSize(18);
  doc.text(view.title, 40, 36);
  doc.setFontSize(10);
  doc.text(view.subtitle, 40, 54);

  const header = ["Time", ...days];
  const body = startMinutes.map((minute) => [
    formatMinute(minute),
    ...days.map((day) => {
      const entries = entryMap.get(`${day}-${minute}`) || [];
      return entries
        .map(
          (entry) =>
            `${entry.module_code} ${entry.session_name}\n${entry.room_name}\n${entry.lecturer_names.join(", ")}`
        )
        .join("\n\n");
    }),
  ]);

  doc.autoTable({
    head: [header],
    body,
    startY: 72,
    styles: { fontSize: 7, cellPadding: 4, overflow: "linebreak", valign: "middle" },
    columnStyles: { 0: { cellWidth: 52, fontStyle: "bold" } },
    headStyles: { fillColor: [146, 64, 14] },
    margin: { left: 28, right: 28 },
  });

  const detailRows = view.solution.entries.map((entry) => [
    entry.day,
    formatMinute(entry.start_minute),
    `${entry.module_code} ${entry.session_name}`,
    entry.room_name,
    entry.lecturer_names.join(", "),
    String(entry.total_students),
  ]);

  doc.text("Session Details", 40, doc.lastAutoTable.finalY + 24);
  doc.autoTable({
    head: [["Day", "Start", "Session", "Room", "Lecturers", "Students"]],
    body: detailRows,
    startY: doc.lastAutoTable.finalY + 32,
    styles: { fontSize: 8, cellPadding: 4, overflow: "linebreak" },
    headStyles: { fillColor: [22, 101, 52] },
    margin: { left: 28, right: 28 },
  });

  doc.save(`${view.mode}-timetable.pdf`);
}

async function exportPng(view, entryMap) {
  const cellWidth = 220;
  const timeWidth = 90;
  const headerHeight = 42;
  const rowHeight = 130;
  const detailHeight = Math.max(180, view.solution.entries.length * 22 + 48);
  const width = timeWidth + days.length * cellWidth;
  const height = 96 + headerHeight + startMinutes.length * rowHeight + detailHeight;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    throw new Error("Canvas export is not supported in this browser.");
  }

  ctx.fillStyle = "#f7efe3";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#201a13";
  ctx.font = "bold 28px Georgia";
  ctx.fillText(view.title, 30, 40);
  ctx.font = "16px sans-serif";
  ctx.fillStyle = "#847867";
  ctx.fillText(view.subtitle, 30, 66);

  const top = 96;
  ctx.font = "bold 15px sans-serif";
  ctx.fillStyle = "#f2eadc";
  ctx.fillRect(0, top, width, headerHeight);
  ctx.strokeStyle = "#d7cfc3";
  ctx.strokeRect(0, top, width, headerHeight);
  ctx.fillStyle = "#3f362a";
  ctx.fillText("Time", 24, top + 26);
  days.forEach((day, dayIndex) => {
    ctx.fillText(day, timeWidth + dayIndex * cellWidth + 16, top + 26);
  });

  startMinutes.forEach((minute, rowIndex) => {
    const y = top + headerHeight + rowIndex * rowHeight;
    ctx.fillStyle = "#fffaf2";
    ctx.fillRect(0, y, width, rowHeight);
    ctx.strokeStyle = "#d7cfc3";
    ctx.strokeRect(0, y, width, rowHeight);
    ctx.fillStyle = "#3f362a";
    ctx.font = "bold 14px sans-serif";
    ctx.fillText(formatMinute(minute), 18, y + 28);

    days.forEach((day, dayIndex) => {
      const x = timeWidth + dayIndex * cellWidth;
      ctx.strokeRect(x, y, cellWidth, rowHeight);
      const entries = entryMap.get(`${day}-${minute}`) || [];
      let cursorY = y + 22;
      entries.forEach((entry) => {
        ctx.fillStyle = "#fbeedc";
        ctx.fillRect(x + 8, cursorY - 14, cellWidth - 16, 44);
        ctx.strokeStyle = "#d9b186";
        ctx.strokeRect(x + 8, cursorY - 14, cellWidth - 16, 44);
        ctx.fillStyle = "#201a13";
        ctx.font = "bold 11px sans-serif";
        ctx.fillText(entry.module_code, x + 14, cursorY);
        ctx.font = "10px sans-serif";
        ctx.fillText(entry.room_name, x + 14, cursorY + 14);
        ctx.fillText(`${entry.total_students} students`, x + 14, cursorY + 28);
        cursorY += 52;
      });
    });
  });

  const detailTop = top + headerHeight + startMinutes.length * rowHeight + 24;
  ctx.fillStyle = "#201a13";
  ctx.font = "bold 18px Georgia";
  ctx.fillText("Session Details", 30, detailTop);
  ctx.font = "12px sans-serif";
  ctx.fillStyle = "#3f362a";
  view.solution.entries.forEach((entry, index) => {
    const y = detailTop + 28 + index * 22;
    const line = `${entry.day} ${formatMinute(entry.start_minute)}  |  ${entry.module_code} ${entry.session_name}  |  ${entry.room_name}  |  ${entry.lecturer_names.join(", ")}`;
    ctx.fillText(line.slice(0, 150), 30, y);
  });

  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob((nextBlob) => {
      if (!nextBlob) {
        reject(new Error("Failed to render PNG export."));
        return;
      }
      resolve(nextBlob);
    }, "image/png");
  });
  downloadBlob(`${view.mode}-timetable.png`, blob);
}

function ViewStudio() {
  const [mode, setMode] = useState("admin");
  const [view, setView] = useState(null);
  const [lookups, setLookups] = useState({ lecturers: [], degrees: [], student_paths: [] });
  const [selectedLecturerId, setSelectedLecturerId] = useState("");
  const [selectedDegreeId, setSelectedDegreeId] = useState("");
  const [selectedPathId, setSelectedPathId] = useState("");
  const [layoutMode, setLayoutMode] = useState("agenda");
  const [selectedCalendarDay, setSelectedCalendarDay] = useState(days[0]);
  const [selectedEntryKey, setSelectedEntryKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const availableStudentPaths = useMemo(
    () =>
      lookups.student_paths.filter(
        (item) => String(item.degree_id) === String(selectedDegreeId || "")
      ),
    [lookups.student_paths, selectedDegreeId]
  );

  const loadView = async (nextMode = mode) => {
    setLoading(true);
    setError("");
    try {
      const response = await timetableStudioService.view({
        mode: nextMode,
        lecturerId: nextMode === "lecturer" ? selectedLecturerId : undefined,
        degreeId: nextMode === "student" ? selectedDegreeId : undefined,
        pathId: nextMode === "student" && selectedPathId !== "general" ? selectedPathId : undefined,
      });
      setView(response);
      setSelectedEntryKey("");
    } catch (err) {
      if (
        nextMode === "admin" &&
        typeof err.message === "string" &&
        err.message.toLowerCase().includes("no default solution")
      ) {
        setError("");
      } else {
        setError(err.message);
      }
      setView(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    timetableStudioService.getLookups().then(setLookups).catch(() => {});
    loadView();
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

  const calendarPlacements = useMemo(
    () => buildCalendarPlacements(view?.solution?.entries || []),
    [view]
  );

  const agendaDays = useMemo(
    () => buildAgendaDays(view?.solution?.entries || []),
    [view]
  );

  const selectedEntry = useMemo(() => {
    const entries = view?.solution?.entries || [];
    if (entries.length === 0) {
      return null;
    }
    if (!selectedEntryKey) {
      return entries[0];
    }
    return entries.find((entry, index) => `${entry.session_id}-${entry.occurrence_index ?? 1}-${index}` === selectedEntryKey) || entries[0];
  }, [selectedEntryKey, view]);

  const resolvedSelectedEntryKey = useMemo(() => {
    const entries = view?.solution?.entries || [];
    if (!selectedEntry || entries.length === 0) {
      return "";
    }
    const index = findEntryIndex(entries, selectedEntry);
    if (index === -1) {
      return "";
    }
    return getEntryKey(selectedEntry, index);
  }, [selectedEntry, view]);

  const handleModeChange = async (nextMode) => {
    setMode(nextMode);
    setError("");
    setLayoutMode(nextMode === "admin" ? "agenda" : "calendar");
    if (nextMode === "admin") {
      await loadView(nextMode);
      return;
    }
    setView(null);
  };

  const handleApplyFilters = async () => {
    if (needsSelection) {
      return;
    }
    await loadView(mode);
  };

  const needsSelection =
    (mode === "lecturer" && !selectedLecturerId) ||
    (mode === "student" && (!selectedDegreeId || !selectedPathId));

  const handleExport = async (format) => {
    try {
      if (!view) {
        setError("Load a timetable before exporting.");
        return;
      }
      if (format === "pdf") {
        await exportPdf(view, entryMap);
        return;
      }
      if (format === "xls") {
        await exportWorkbook(view, entryMap);
        return;
      }
      if (format === "png") {
        await exportPng(view, entryMap);
        return;
      }
      const response = await timetableStudioService.exportView({
        mode,
        format,
        lecturerId: mode === "lecturer" ? selectedLecturerId : undefined,
        degreeId: mode === "student" ? selectedDegreeId : undefined,
        pathId: mode === "student" && selectedPathId !== "general" ? selectedPathId : undefined,
      });
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
              Review the current default timetable in admin, lecturer, or student mode and export the view that is on screen.
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
              <select value={selectedDegreeId} onChange={(event) => {
                setSelectedDegreeId(event.target.value);
                setSelectedPathId("");
              }}>
                <option value="">Select Degree</option>
                {lookups.degrees.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            )}
            {mode === "student" && (
              <select value={selectedPathId} onChange={(event) => setSelectedPathId(event.target.value)} disabled={!selectedDegreeId}>
                <option value="">Select Path</option>
                {availableStudentPaths.map((item) => (
                  <option key={`${item.degree_id}-${item.year}-${item.id ?? "general"}`} value={item.id ?? "general"}>
                    {item.label}
                  </option>
                ))}
              </select>
            )}
            <div className="view-layout-toggle" role="tablist" aria-label="View layout">
              <button
                type="button"
                className={layoutMode === "calendar" ? "ghost-btn active-layout" : "ghost-btn"}
                onClick={() => setLayoutMode("calendar")}
              >
                Calendar
              </button>
              <button
                type="button"
                className={layoutMode === "agenda" ? "ghost-btn active-layout" : "ghost-btn"}
                onClick={() => setLayoutMode("agenda")}
              >
                Agenda
              </button>
            </div>
            {mode !== "admin" && (
              <button
                className="ghost-btn"
                onClick={handleApplyFilters}
                disabled={needsSelection}
              >
                Apply
              </button>
            )}
            <button className="ghost-btn" onClick={() => handleExport("pdf")}>PDF</button>
            <button className="ghost-btn" onClick={() => handleExport("csv")}>CSV</button>
            <button className="ghost-btn" onClick={() => handleExport("xls")}>XLSX</button>
            <button className="ghost-btn" onClick={() => handleExport("png")}>PNG</button>
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {loading && <div className="info-banner">Loading timetable view...</div>}

        {!loading && mode === "lecturer" && !view && !error && !selectedLecturerId && (
          <section className="studio-card">
            <h2>Select a lecturer</h2>
            <p className="empty-state">
              Choose a lecturer, then apply the filter to load the timetable for the sessions they teach.
            </p>
          </section>
        )}

        {!loading && mode === "student" && !view && !error && (
          <section className="studio-card">
            <h2>Select a degree and path</h2>
            <p className="empty-state">
              Choose the degree first, then choose the relevant path or general cohort before loading the student timetable.
            </p>
          </section>
        )}

        {!loading && mode === "admin" && !view && !error && (
          <section className="studio-card">
            <h2>No default timetable available</h2>
            <p className="empty-state">
              Generate timetable solutions in the Generate page and mark one as the default timetable before using the Views page.
            </p>
          </section>
        )}

        {view && (
          <>
            <section className="studio-card">
              <h2>{view.title}</h2>
              <p>{view.subtitle}</p>
            </section>

            <section className="studio-grid two-column view-layout-grid">
            {layoutMode === "calendar" ? (
              <section className="studio-card timetable-grid-card">
                <div className="calendar-day-tabs" role="tablist" aria-label="Calendar day">
                  {days.map((day) => (
                    <button
                      key={day}
                      type="button"
                      className={selectedCalendarDay === day ? "ghost-btn active-layout" : "ghost-btn"}
                      onClick={() => setSelectedCalendarDay(day)}
                    >
                      {day}
                    </button>
                  ))}
                </div>
                <div
                  className="calendar-stage"
                  style={{ height: `${calendarTopInset + (calendarEndMinute - calendarStartMinute) * minuteHeight}px` }}
                >
                  {Array.from({ length: (calendarEndMinute - calendarStartMinute) / 60 }, (_, index) => {
                    const minute = calendarStartMinute + index * 60;
                    return (
                      <div
                        key={`stage-line-${minute}`}
                        className="calendar-hour-line stage-line"
                        style={{ top: `${calendarTopInset + (minute - calendarStartMinute) * minuteHeight}px` }}
                      />
                    );
                  })}
                  {Array.from({ length: (calendarEndMinute - calendarStartMinute) / 60 + 1 }, (_, index) => {
                    const minute = calendarStartMinute + index * 60;
                    return (
                      <div
                        key={`stage-label-${minute}`}
                        className="calendar-time-label stage-time-label"
                        style={{ top: `${calendarTopInset + (minute - calendarStartMinute) * minuteHeight}px` }}
                      >
                        <span className="calendar-time-hour">{formatCalendarHour(minute).hour}</span>
                        <span className="calendar-time-mins">{formatCalendarHour(minute).mins}</span>
                      </div>
                    );
                  })}
                  <div className="calendar-stage-divider" />
                  <div className="calendar-event-layer">
                    {(view.solution.entries || [])
                      .filter((entry) => entry.day === selectedCalendarDay)
                      .map((entry, index) => {
                        const placement = calendarPlacements.get(entry);
                        if (!placement) {
                          return null;
                        }
                        const entryKey = getEntryKey(entry, index);
                        return (
                          <article
                            key={entryKey}
                            className={
                              resolvedSelectedEntryKey === entryKey
                                ? `entry-card detailed compact calendar-entry simplified ${getEntryToneClass(entry)} selected-entry`
                                : `entry-card detailed compact calendar-entry simplified ${getEntryToneClass(entry)}`
                            }
                            style={entryCalendarStyle(placement)}
                            onClick={() => setSelectedEntryKey(entryKey)}
                            title={[
                              `${entry.module_code} ${entry.session_name}`,
                              entry.room_name,
                              entry.lecturer_names.join(", "),
                              entry.degree_path_labels.join(" | "),
                              `${entry.total_students} students`,
                            ].filter(Boolean).join("\n")}
                          >
                            <strong>{entry.module_code}</strong>
                            <span className="entry-meta-line">{entry.room_name}</span>
                          </article>
                        );
                      })}
                  </div>
                </div>
              </section>
            ) : (
              <section className="studio-card agenda-card">
                <div className="agenda-days">
                  {agendaDays.map(({ day, entries }) => (
                    <section key={day} className="agenda-day-section">
                      <h3>{day}</h3>
                      <div className="agenda-day-list">
                        {entries.map((entry, index) => {
                          const entryKey = getEntryKey(entry, index);
                          return (
                          <article
                            key={entryKey}
                            className={
                              resolvedSelectedEntryKey === entryKey
                                ? `agenda-entry ${getEntryToneClass(entry)} selected-entry`
                                : `agenda-entry ${getEntryToneClass(entry)}`
                            }
                            onClick={() => setSelectedEntryKey(entryKey)}
                          >
                            <div className="agenda-entry-time">
                              <strong>{formatMinute(entry.start_minute)}</strong>
                              <span>{entry.duration_minutes} min</span>
                            </div>
                            <div className="agenda-entry-body">
                              <strong>{entry.module_code} {compactSessionName(entry.module_code, entry.session_name)}</strong>
                              <span>{entry.room_name} | {compactLecturerNames(entry.lecturer_names)}</span>
                              <span>{compactAudienceLabels(entry.degree_path_labels)}</span>
                              <span>{entry.total_students} students</span>
                            </div>
                          </article>
                        )})}
                      </div>
                    </section>
                  ))}
                </div>
              </section>
            )}
              <aside className="studio-card detail-drawer">
                <h2>Session Details</h2>
                {!selectedEntry ? (
                  <p className="empty-state">Select a session to inspect its details.</p>
                ) : (
                  <div className="detail-drawer-body">
                    <strong className="detail-title">
                      {selectedEntry.module_code} {compactSessionName(selectedEntry.module_code, selectedEntry.session_name)}
                    </strong>
                    <p className="detail-summary">{formatEntrySummary(selectedEntry)}</p>
                    <div className="detail-pairs">
                      <span>Room</span>
                      <strong>{selectedEntry.room_name}</strong>
                      <span>Lecturers</span>
                      <strong>{selectedEntry.lecturer_names.join(", ") || "Unassigned"}</strong>
                      <span>Student groups</span>
                      <strong>{selectedEntry.student_group_names.join(", ") || "None"}</strong>
                      <span>Degree paths</span>
                      <strong>{selectedEntry.degree_path_labels.join(" | ") || "None"}</strong>
                      <span>Students</span>
                      <strong>{selectedEntry.total_students}</strong>
                    </div>
                  </div>
                )}
              </aside>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default ViewStudio;
