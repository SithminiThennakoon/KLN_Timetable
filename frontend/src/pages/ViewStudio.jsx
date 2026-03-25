import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const startMinutes = [480, 540, 600, 660, 780, 840, 900, 960, 1020];
const calendarStartMinute = 8 * 60;
const calendarEndMinute = 18 * 60;
const calendarTopInset = 0;
const densityModes = {
  compact: { label: "Compact", minuteHeight: 0.72 },
  comfortable: { label: "Comfortable", minuteHeight: 1.0 },
  expanded: { label: "Expanded", minuteHeight: 1.35 },
};
const activeImportRunStorageKey = "kln_active_import_run_id";

// ─── Pure helpers ──────────────────────────────────────────────────────────────

function formatMinute(minute) {
  const hour = Math.floor(minute / 60);
  const mins = String(minute % 60).padStart(2, "0");
  return `${String(hour).padStart(2, "0")}:${mins}`;
}

function formatDuration(minutes) {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

function studentPathValue(item) {
  if (!item) return "";
  return item.id ? `path-${item.id}` : `general-${item.year}`;
}

function compactSessionName(moduleCode, sessionName) {
  if (!sessionName) return "";
  const normalizedModuleCode = (moduleCode || "").trim();
  const normalizedSessionName = sessionName.trim();
  if (normalizedModuleCode && normalizedSessionName.startsWith(normalizedModuleCode)) {
    return normalizedSessionName.slice(normalizedModuleCode.length).trim() || normalizedSessionName;
  }
  return normalizedSessionName;
}

function compactLecturerNames(names = []) {
  if (names.length === 0) return "Unassigned";
  if (names.length === 1) return names[0];
  return `${names[0]} +${names.length - 1}`;
}

function compactAudienceLabels(labels = []) {
  if (labels.length <= 2) return labels.join(", ");
  return `${labels.slice(0, 2).join(", ")} +${labels.length - 2} more`;
}

function getEntryToneClass(entry) {
  const label = `${entry.session_name || ""} ${entry.module_name || ""}`.toLowerCase();
  if (label.includes("lab") || label.includes("laboratory")) return "is-lab";
  return "is-lecture";
}

// Group overlapping entries in a single day column into slot-groups.
// Each group has one primary entry (shown as the card) and extras (shown in popover).
// A slot-group spans the union of all its members' time ranges.
function groupOverlappingEntries(dayEntries, minuteHeight) {
  const visible = dayEntries
    .filter(
      (e) => e.start_minute >= calendarStartMinute && e.start_minute < calendarEndMinute
    )
    .slice()
    .sort((a, b) =>
      a.start_minute !== b.start_minute
        ? a.start_minute - b.start_minute
        : b.duration_minutes - a.duration_minutes
    );

  const groups = []; // [{ primary, extras, groupStart, groupEnd }]

  visible.forEach((entry) => {
    const start = entry.start_minute;
    const end = entry.start_minute + entry.duration_minutes;
    // Find an existing group that overlaps with this entry
    const overlap = groups.find(
      (g) => start < g.groupEnd && end > g.groupStart
    );
    if (overlap) {
      overlap.extras.push(entry);
      overlap.groupStart = Math.min(overlap.groupStart, start);
      overlap.groupEnd = Math.max(overlap.groupEnd, end);
    } else {
      groups.push({ primary: entry, extras: [], groupStart: start, groupEnd: end });
    }
  });

  // Build placement map: primary entry → { top, height, extraCount, allEntries }
  const placements = new Map();
  groups.forEach(({ primary, extras, groupStart, groupEnd }) => {
    const spanMinutes = groupEnd - groupStart;
    placements.set(primary, {
      top: (groupStart - calendarStartMinute) * minuteHeight,
      height: Math.max(32, spanMinutes * minuteHeight),
      extraCount: extras.length,
      allEntries: [primary, ...extras],
    });
  });

  return placements;
}

// Assign each entry in a day to a lane (column) so that no two entries in the
// same lane overlap in time. Returns a Map<entry, { top, height, lane, laneCount }>.
// laneCount is the total number of lanes used for the day (set after all entries placed).
function buildLanePlacements(dayEntries, minuteHeight) {
  const visible = dayEntries
    .filter((e) => e.start_minute >= calendarStartMinute && e.start_minute < calendarEndMinute)
    .slice()
    .sort((a, b) =>
      a.start_minute !== b.start_minute
        ? a.start_minute - b.start_minute
        : b.duration_minutes - a.duration_minutes
    );

  // lanes[i] = end_minute of the last entry placed in lane i
  const laneEnds = [];
  const assignments = []; // { entry, lane }

  visible.forEach((entry) => {
    const start = entry.start_minute;
    const end = entry.start_minute + entry.duration_minutes;
    // Find the first lane whose last entry has already ended
    let lane = laneEnds.findIndex((laneEnd) => laneEnd <= start);
    if (lane === -1) {
      lane = laneEnds.length; // open a new lane
      laneEnds.push(end);
    } else {
      laneEnds[lane] = end;
    }
    assignments.push({ entry, lane });
  });

  const laneCount = Math.max(1, laneEnds.length);
  const placements = new Map();
  assignments.forEach(({ entry, lane }) => {
    placements.set(entry, {
      top: (entry.start_minute - calendarStartMinute) * minuteHeight,
      height: Math.max(28, entry.duration_minutes * minuteHeight - 4),
      lane,
      laneCount,
    });
  });
  return placements;
}

function buildDayLoad(entries = []) {
  return days.map((day) => {
    const dayEntries = entries.filter((e) => e.day === day);
    const labCount = dayEntries.filter((e) => getEntryToneClass(e) === "is-lab").length;
    return { day, total: dayEntries.length, labCount, lectureCount: dayEntries.length - labCount };
  });
}

function buildAgendaDays(entries = []) {
  return days
    .map((day) => ({
      day,
      entries: entries
        .filter((e) => e.day === day)
        .slice()
        .sort((a, b) => a.start_minute - b.start_minute || b.duration_minutes - a.duration_minutes),
    }))
    .filter((d) => d.entries.length > 0);
}

function getEntryKey(entry, index) {
  return `${entry.session_id}-${entry.occurrence_index ?? 1}-${index}`;
}

function findEntryIndex(entries, target) {
  return entries.findIndex(
    (e) =>
      e.session_id === target.session_id &&
      (e.occurrence_index ?? 1) === (target.occurrence_index ?? 1) &&
      e.day === target.day &&
      e.start_minute === target.start_minute
  );
}

function downloadBase64(filename, contentType, content) {
  const bytes = atob(content);
  const array = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) array[i] = bytes.charCodeAt(i);
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

function collectActiveDays(entries = []) {
  return days.filter((day) => entries.some((entry) => entry.day === day));
}

function buildExportFilename(mode, suffix, extension) {
  return `${mode}-timetable-${suffix}.${extension}`;
}

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight) {
  const words = String(text || "").split(/\s+/).filter(Boolean);
  let line = "";
  let cursorY = y;
  words.forEach((word) => {
    const candidate = line ? `${line} ${word}` : word;
    if (ctx.measureText(candidate).width > maxWidth && line) {
      ctx.fillText(line, x, cursorY);
      line = word;
      cursorY += lineHeight;
    } else {
      line = candidate;
    }
  });
  if (line) {
    ctx.fillText(line, x, cursorY);
    cursorY += lineHeight;
  }
  return cursorY;
}

function createCanvas(width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Canvas export is not supported in this browser.");
  }
  return { canvas, ctx };
}

async function canvasToBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error("Failed to render image export."));
      }
    }, "image/png");
  });
}

function drawDayGrid(ctx, x, y, width, height, minuteHeight, dayLabel) {
  ctx.fillStyle = "#11161a";
  ctx.fillRect(x, y, width, height);
  ctx.fillStyle = "#465462";
  ctx.fillRect(x, y, width, 36);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 16px Georgia, serif";
  ctx.fillText(dayLabel, x + 16, y + 23);

  ctx.strokeStyle = "rgba(255,255,255,0.1)";
  for (let minute = calendarStartMinute; minute <= calendarEndMinute; minute += 60) {
    const lineY = y + 36 + (minute - calendarStartMinute) * minuteHeight;
    ctx.beginPath();
    ctx.moveTo(x, lineY);
    ctx.lineTo(x + width, lineY);
    ctx.stroke();
  }
}

function drawEntryCard(ctx, entry, x, y, width, height) {
  const toneClass = getEntryToneClass(entry);
  const sessionShort = compactSessionName(entry.module_code, entry.session_name);
  ctx.fillStyle = toneClass === "is-lab" ? "#2f7c82" : "#3d6f9e";
  ctx.beginPath();
  ctx.roundRect(x, y, width, height, 10);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.16)";
  ctx.stroke();

  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 13px Georgia, serif";
  ctx.fillText(entry.module_code, x + 10, y + 18);

  ctx.font = "11px Arial";
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.fillText(`${formatMinute(entry.start_minute)}-${formatMinute(entry.start_minute + entry.duration_minutes)}`, x + 10, y + 34);
  ctx.fillText(entry.room_name, x + 10, y + 48);

  if (height >= 66 && sessionShort) {
    drawWrappedText(ctx, sessionShort, x + 10, y + 64, width - 20, 12);
  }
  if (height >= 90) {
    ctx.fillStyle = "rgba(255,255,255,0.86)";
    drawWrappedText(ctx, compactLecturerNames(entry.lecturer_names), x + 10, y + 80, width - 20, 12);
  }
}

function renderDailyCanvas(view, day, { detailed = false } = {}) {
  const minuteHeight = 0.9;
  const timeWidth = 78;
  const bodyWidth = 960;
  const headerHeight = 112;
  const gridHeaderHeight = 36;
  const calendarHeight = (calendarEndMinute - calendarStartMinute) * minuteHeight + gridHeaderHeight;
  const detailRows = detailed
    ? view.solution.entries.filter((entry) => entry.day === day).sort((a, b) => a.start_minute - b.start_minute)
    : [];
  const detailHeight = detailRows.length > 0 ? Math.max(140, detailRows.length * 22 + 44) : 0;
  const width = timeWidth + bodyWidth + 48;
  const height = headerHeight + calendarHeight + detailHeight + 40;
  const { canvas, ctx } = createCanvas(width, height);

  ctx.fillStyle = "#f4efe7";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#101826";
  ctx.font = "bold 28px Georgia, serif";
  ctx.fillText(view.title, 24, 40);
  ctx.font = "16px Arial";
  ctx.fillStyle = "#4e6376";
  ctx.fillText(`${view.subtitle} — ${day}`, 24, 68);

  const gridTop = headerHeight;
  ctx.fillStyle = "#11161a";
  ctx.fillRect(0, gridTop, timeWidth, calendarHeight);
  ctx.strokeStyle = "rgba(255,255,255,0.1)";
  ctx.beginPath();
  ctx.moveTo(timeWidth, gridTop);
  ctx.lineTo(timeWidth, gridTop + calendarHeight);
  ctx.stroke();

  for (let minute = calendarStartMinute; minute <= calendarEndMinute; minute += 60) {
    const lineY = gridTop + gridHeaderHeight + (minute - calendarStartMinute) * minuteHeight;
    ctx.beginPath();
    ctx.moveTo(0, lineY);
    ctx.lineTo(width - 24, lineY);
    ctx.stroke();
    ctx.fillStyle = "#cad3dc";
    ctx.font = "bold 12px Arial";
    ctx.fillText(formatMinute(minute), 10, lineY + 4);
  }

  drawDayGrid(ctx, timeWidth, gridTop, bodyWidth, calendarHeight, minuteHeight, day);

  const dayEntries = view.solution.entries.filter((entry) => entry.day === day);
  if (view.mode === "admin") {
    const placements = buildLanePlacements(dayEntries, minuteHeight);
    const laneCount = Math.max(
      1,
      ...Array.from(placements.values()).map((placement) => placement.lane + 1),
      1
    );
    const laneWidth = (bodyWidth - 16) / laneCount;
    dayEntries.forEach((entry) => {
      const placement = placements.get(entry);
      if (!placement) return;
      drawEntryCard(
        ctx,
        entry,
        timeWidth + 8 + placement.lane * laneWidth,
        gridTop + gridHeaderHeight + placement.top + 4,
        laneWidth - 10,
        Math.max(placement.height - 8, 24)
      );
    });
  } else {
    const placements = groupOverlappingEntries(dayEntries, minuteHeight);
    dayEntries.forEach((entry) => {
      const placement = placements.get(entry);
      if (!placement) return;
      drawEntryCard(
        ctx,
        entry,
        timeWidth + 12,
        gridTop + gridHeaderHeight + placement.top + 4,
        bodyWidth - 24,
        Math.max(placement.height - 8, 24)
      );
    });
  }

  if (detailRows.length > 0) {
    const detailTop = gridTop + calendarHeight + 28;
    ctx.fillStyle = "#101826";
    ctx.font = "bold 20px Georgia, serif";
    ctx.fillText("Session list", 24, detailTop);
    ctx.font = "13px Arial";
    ctx.fillStyle = "#35506a";
    detailRows.forEach((entry, index) => {
      ctx.fillText(
        `${formatMinute(entry.start_minute)} | ${entry.module_code} | ${entry.room_name} | ${compactLecturerNames(entry.lecturer_names)}`,
        24,
        detailTop + 28 + index * 22
      );
    });
  }

  return canvas;
}

function renderWeeklyCanvas(view) {
  const minuteHeight = 0.82;
  const activeDays = collectActiveDays(view.solution.entries);
  const timeWidth = 72;
  const dayWidth = 248;
  const headerHeight = 112;
  const gridHeaderHeight = 40;
  const calendarHeight = (calendarEndMinute - calendarStartMinute) * minuteHeight + gridHeaderHeight;
  const width = timeWidth + activeDays.length * dayWidth + 32;
  const height = headerHeight + calendarHeight + 28;
  const { canvas, ctx } = createCanvas(width, height);

  ctx.fillStyle = "#f4efe7";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#101826";
  ctx.font = "bold 30px Georgia, serif";
  ctx.fillText(view.title, 24, 42);
  ctx.font = "16px Arial";
  ctx.fillStyle = "#4e6376";
  ctx.fillText(view.subtitle, 24, 70);

  const gridTop = headerHeight;
  ctx.fillStyle = "#11161a";
  ctx.fillRect(0, gridTop, timeWidth, calendarHeight);

  for (let minute = calendarStartMinute; minute <= calendarEndMinute; minute += 60) {
    const lineY = gridTop + gridHeaderHeight + (minute - calendarStartMinute) * minuteHeight;
    ctx.strokeStyle = "rgba(255,255,255,0.1)";
    ctx.beginPath();
    ctx.moveTo(0, lineY);
    ctx.lineTo(width - 16, lineY);
    ctx.stroke();
    ctx.fillStyle = "#cad3dc";
    ctx.font = "bold 12px Arial";
    ctx.fillText(formatMinute(minute), 8, lineY + 4);
  }

  activeDays.forEach((day, index) => {
    const columnX = timeWidth + index * dayWidth;
    drawDayGrid(ctx, columnX, gridTop, dayWidth, calendarHeight, minuteHeight, day);
    const dayEntries = view.solution.entries.filter((entry) => entry.day === day);
    const placements = groupOverlappingEntries(dayEntries, minuteHeight);
    dayEntries.forEach((entry) => {
      const placement = placements.get(entry);
      if (!placement) return;
      drawEntryCard(
        ctx,
        entry,
        columnX + 8,
        gridTop + gridHeaderHeight + placement.top + 4,
        dayWidth - 16,
        Math.max(placement.height - 8, 24)
      );
    });
  });

  return canvas;
}

function combineCanvasesVertical(canvases, title) {
  const width = Math.max(...canvases.map((canvas) => canvas.width));
  const gap = 24;
  const headerHeight = 88;
  const height = headerHeight + canvases.reduce((sum, canvas) => sum + canvas.height, 0) + gap * (canvases.length - 1) + 24;
  const { canvas, ctx } = createCanvas(width, height);
  ctx.fillStyle = "#f4efe7";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#101826";
  ctx.font = "bold 28px Georgia, serif";
  ctx.fillText(title, 24, 42);
  ctx.font = "15px Arial";
  ctx.fillStyle = "#4e6376";
  ctx.fillText("Whole-week visual export", 24, 66);
  let offsetY = headerHeight;
  canvases.forEach((part) => {
    ctx.drawImage(part, 0, offsetY);
    offsetY += part.height + gap;
  });
  return canvas;
}

async function blobToUint8Array(blob) {
  return new Uint8Array(await blob.arrayBuffer());
}

const crcTable = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let c = i;
    for (let j = 0; j < 8; j += 1) {
      c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    }
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) {
    crc = crcTable[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function toDosDateTime(date = new Date()) {
  const year = Math.max(1980, date.getFullYear());
  const dosTime = ((date.getHours() & 0x1f) << 11) | ((date.getMinutes() & 0x3f) << 5) | (Math.floor(date.getSeconds() / 2) & 0x1f);
  const dosDate = (((year - 1980) & 0x7f) << 9) | (((date.getMonth() + 1) & 0xf) << 5) | (date.getDate() & 0x1f);
  return { dosDate, dosTime };
}

function writeUint16(view, offset, value) {
  view.setUint16(offset, value, true);
}

function writeUint32(view, offset, value) {
  view.setUint32(offset, value, true);
}

async function buildZipBlob(files) {
  const encoder = new TextEncoder();
  const prepared = await Promise.all(files.map(async (file) => {
    const data = file.blob instanceof Blob ? await blobToUint8Array(file.blob) : file.data;
    return {
      name: file.name,
      nameBytes: encoder.encode(file.name),
      data,
      crc: crc32(data),
    };
  }));

  const localParts = [];
  const centralParts = [];
  let offset = 0;
  const { dosDate, dosTime } = toDosDateTime();

  prepared.forEach((file) => {
    const localHeader = new Uint8Array(30 + file.nameBytes.length);
    const localView = new DataView(localHeader.buffer);
    writeUint32(localView, 0, 0x04034b50);
    writeUint16(localView, 4, 20);
    writeUint16(localView, 6, 0);
    writeUint16(localView, 8, 0);
    writeUint16(localView, 10, dosTime);
    writeUint16(localView, 12, dosDate);
    writeUint32(localView, 14, file.crc);
    writeUint32(localView, 18, file.data.length);
    writeUint32(localView, 22, file.data.length);
    writeUint16(localView, 26, file.nameBytes.length);
    writeUint16(localView, 28, 0);
    localHeader.set(file.nameBytes, 30);
    localParts.push(localHeader, file.data);

    const centralHeader = new Uint8Array(46 + file.nameBytes.length);
    const centralView = new DataView(centralHeader.buffer);
    writeUint32(centralView, 0, 0x02014b50);
    writeUint16(centralView, 4, 20);
    writeUint16(centralView, 6, 20);
    writeUint16(centralView, 8, 0);
    writeUint16(centralView, 10, 0);
    writeUint16(centralView, 12, dosTime);
    writeUint16(centralView, 14, dosDate);
    writeUint32(centralView, 16, file.crc);
    writeUint32(centralView, 20, file.data.length);
    writeUint32(centralView, 24, file.data.length);
    writeUint16(centralView, 28, file.nameBytes.length);
    writeUint16(centralView, 30, 0);
    writeUint16(centralView, 32, 0);
    writeUint16(centralView, 34, 0);
    writeUint16(centralView, 36, 0);
    writeUint32(centralView, 38, 0);
    writeUint32(centralView, 42, offset);
    centralHeader.set(file.nameBytes, 46);
    centralParts.push(centralHeader);

    offset += localHeader.length + file.data.length;
  });

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  writeUint32(endView, 0, 0x06054b50);
  writeUint16(endView, 8, prepared.length);
  writeUint16(endView, 10, prepared.length);
  writeUint32(endView, 12, centralSize);
  writeUint32(endView, 16, offset);
  writeUint16(endView, 20, 0);

  return new Blob([...localParts, ...centralParts, end], { type: "application/zip" });
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
          (e) =>
            `${e.module_code} ${e.session_name}\n${e.room_name}\n${e.lecturer_names.join(", ")}\n${e.total_students} students`
        )
        .join("\n\n");
    });
    return row;
  });
  const detailRows = view.solution.entries.map((e) => ({
    Day: e.day,
    Start: formatMinute(e.start_minute),
    Duration: e.duration_minutes,
    ModuleCode: e.module_code,
    ModuleName: e.module_name,
    Session: e.session_name,
    Room: e.room_name,
    Location: e.room_location,
    Lecturers: e.lecturer_names.join(", "),
    StudentGroups: e.student_group_names.join(", "),
    DegreePaths: e.degree_path_labels.join(" | "),
    Students: e.total_students,
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
    { wch: 12 }, { wch: 8 }, { wch: 10 }, { wch: 14 }, { wch: 28 }, { wch: 26 },
    { wch: 18 }, { wch: 18 }, { wch: 26 }, { wch: 26 }, { wch: 28 }, { wch: 10 },
  ];
  summarySheet["!cols"] = [{ wch: 18 }, { wch: 48 }];
  XLSX.utils.book_append_sheet(workbook, summarySheet, "Summary");
  XLSX.utils.book_append_sheet(workbook, gridSheet, "Timetable");
  XLSX.utils.book_append_sheet(workbook, detailSheet, "Session Details");
  XLSX.writeFile(workbook, buildExportFilename(view.mode, "week", "xlsx"));
}

async function exportPdf(view, scope) {
  const [{ default: jsPDF }] = await Promise.all([import("jspdf")]);
  const renderPdf = async (canvases, filename) => {
    const first = canvases[0];
    const doc = new jsPDF({
      orientation: first.width >= first.height ? "landscape" : "portrait",
      unit: "px",
      format: [first.width, first.height],
    });
    canvases.forEach((canvas, index) => {
      if (index > 0) {
        doc.addPage([canvas.width, canvas.height], canvas.width >= canvas.height ? "landscape" : "portrait");
      }
      doc.addImage(canvas.toDataURL("image/png"), "PNG", 0, 0, canvas.width, canvas.height);
    });
    doc.save(filename);
  };

  const activeDays = collectActiveDays(view.solution.entries);
  if (view.mode === "admin" && scope === "daily_bundle") {
    const files = [];
    for (const day of activeDays) {
      const canvas = renderDailyCanvas(view, day, { detailed: true });
      const doc = new jsPDF({
        orientation: canvas.width >= canvas.height ? "landscape" : "portrait",
        unit: "px",
        format: [canvas.width, canvas.height],
      });
      doc.addImage(canvas.toDataURL("image/png"), "PNG", 0, 0, canvas.width, canvas.height);
      files.push({
        name: buildExportFilename(view.mode, day.toLowerCase(), "pdf"),
        blob: doc.output("blob"),
      });
    }
    const zipBlob = await buildZipBlob(files);
    downloadBlob(buildExportFilename(view.mode, "daily-bundle", "zip"), zipBlob);
    return;
  }

  if (view.mode === "admin") {
    const canvases = activeDays.map((day) => renderDailyCanvas(view, day, { detailed: true }));
    await renderPdf(canvases, buildExportFilename(view.mode, "week", "pdf"));
    return;
  }

  const canvas = renderWeeklyCanvas(view);
  await renderPdf([canvas], buildExportFilename(view.mode, "week", "pdf"));
}

async function exportPng(view, scope) {
  const activeDays = collectActiveDays(view.solution.entries);
  if (view.mode === "admin" && scope === "daily_bundle") {
    const files = [];
    for (const day of activeDays) {
      const canvas = renderDailyCanvas(view, day, { detailed: true });
      files.push({
        name: buildExportFilename(view.mode, day.toLowerCase(), "png"),
        blob: await canvasToBlob(canvas),
      });
    }
    const zipBlob = await buildZipBlob(files);
    downloadBlob(buildExportFilename(view.mode, "daily-bundle", "zip"), zipBlob);
    return;
  }

  const canvas = view.mode === "admin"
    ? combineCanvasesVertical(activeDays.map((day) => renderDailyCanvas(view, day, { detailed: true })), view.title)
    : renderWeeklyCanvas(view);
  const blob = await canvasToBlob(canvas);
  downloadBlob(buildExportFilename(view.mode, "week", "png"), blob);
}

// ─── Session Detail Modal ──────────────────────────────────────────────────────

function SessionModalInner({ entry, onClose }) {
  const overlayRef = useRef(null);

  useEffect(() => {
    const handleKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  useEffect(() => {
    if (!import.meta.env.DEV || typeof window === "undefined") return;
    const startedAt = window.__viewStudioSessionClickStartedAt;
    if (!startedAt) return;
    const elapsed = performance.now() - startedAt;
    console.debug(`[ViewStudio] Session modal visible in ${elapsed.toFixed(1)}ms`);
    window.__viewStudioSessionClickStartedAt = 0;
  }, []);

  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) onClose();
  };

  if (!entry) return null;

  const toneClass = getEntryToneClass(entry);
  const sessionLabel = compactSessionName(entry.module_code, entry.session_name);

  return (
    <div className="modal-overlay" ref={overlayRef} onClick={handleOverlayClick} role="dialog" aria-modal="true" aria-label="Session details">
      <div className={`modal-card ${toneClass}`}>
        <div className="modal-header">
          <div className="modal-title-block">
            <span className={`modal-tone-badge ${toneClass}`}>
              {toneClass === "is-lab" ? "Lab" : "Lecture"}
            </span>
            <h2 className="modal-module-code">{entry.module_code}</h2>
            {sessionLabel && <p className="modal-session-name">{sessionLabel}</p>}
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5 5L15 15M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
        <div className="modal-body">
          <div className="modal-time-row">
            <div className="modal-time-chip">
              <span className="modal-chip-label">Day</span>
              <strong>{entry.day}</strong>
            </div>
            <div className="modal-time-chip">
              <span className="modal-chip-label">Time</span>
              <strong>{formatMinute(entry.start_minute)} – {formatMinute(entry.start_minute + entry.duration_minutes)}</strong>
            </div>
            <div className="modal-time-chip">
              <span className="modal-chip-label">Duration</span>
              <strong>{formatDuration(entry.duration_minutes)}</strong>
            </div>
          </div>
          <div className="modal-detail-grid">
            <div className="modal-detail-row">
              <span className="modal-detail-label">Module</span>
              <span className="modal-detail-value">{entry.module_name || entry.module_code}</span>
            </div>
            <div className="modal-detail-row">
              <span className="modal-detail-label">Room</span>
              <span className="modal-detail-value">
                <strong>{entry.room_name}</strong>
                {entry.room_location && <em className="modal-location"> · {entry.room_location}</em>}
              </span>
            </div>
            <div className="modal-detail-row">
              <span className="modal-detail-label">Lecturer{entry.lecturer_names.length !== 1 ? "s" : ""}</span>
              <span className="modal-detail-value">{entry.lecturer_names.join(", ") || "Unassigned"}</span>
            </div>
            {entry.student_group_names.length > 0 && (
              <div className="modal-detail-row">
                <span className="modal-detail-label">Groups</span>
                <span className="modal-detail-value">{entry.student_group_names.join(", ")}</span>
              </div>
            )}
            {entry.degree_path_labels.length > 0 && (
              <div className="modal-detail-row">
                <span className="modal-detail-label">Degree paths</span>
                <span className="modal-detail-value">{entry.degree_path_labels.join(" | ")}</span>
              </div>
            )}
            <div className="modal-detail-row">
              <span className="modal-detail-label">Students</span>
              <span className="modal-detail-value modal-students-count">{entry.total_students}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const SessionModal = memo(SessionModalInner);

// ─── Slot Popover ──────────────────────────────────────────────────────────────

function SlotPopoverInner({ entries, anchorStyle, onSelectEntry, onClose }) {
  const popoverRef = useRef(null);

  useEffect(() => {
    const handleKey = (e) => { if (e.key === "Escape") onClose(); };
    const handleClick = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) onClose();
    };
    document.addEventListener("keydown", handleKey);
    // Delay outside-click listener so the opening click doesn't immediately close it
    const tid = setTimeout(() => document.addEventListener("mousedown", handleClick), 0);
    return () => {
      document.removeEventListener("keydown", handleKey);
      clearTimeout(tid);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [onClose]);

  return (
    <div
      className="slot-popover"
      ref={popoverRef}
      style={anchorStyle}
      role="listbox"
      aria-label={`${entries.length} sessions at this time`}
    >
      <div className="slot-popover-header">
        <span>{entries.length} sessions</span>
        <button type="button" className="slot-popover-close" onClick={onClose} aria-label="Close">×</button>
      </div>
      {entries.map((entry, idx) => {
        const toneClass = getEntryToneClass(entry);
        const sessionShort = compactSessionName(entry.module_code, entry.session_name);
        return (
          <button
            key={getEntryKey(entry, idx)}
            type="button"
            className={`slot-popover-row ${toneClass}`}
            onClick={() => { onSelectEntry(entry); onClose(); }}
          >
            <span className="spr-code">{entry.module_code}</span>
            <span className="spr-body">
              <span className="spr-session">{sessionShort || entry.session_name}</span>
              <span className="spr-meta">{entry.room_name} · {compactLecturerNames(entry.lecturer_names)} · {entry.total_students} students</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

const SlotPopover = memo(SlotPopoverInner);

// ─── Admin Day Calendar (multi-lane, horizontally scrollable) ─────────────────

function AdminDayCalendarInner({ entries, selectedDay, minuteHeight, onEntryClick }) {
  const hourCount = (calendarEndMinute - calendarStartMinute) / 60;
  const totalHeight = (calendarEndMinute - calendarStartMinute) * minuteHeight;
  const timeColWidth = 52;
  const laneMinWidth = 240;

  const [modalEntry, setModalEntry] = useState(null);
  const wrapperRef = useRef(null);

  const { placements, laneCount } = useMemo(() => {
    const dayEntries = entries.filter((e) => e.day === selectedDay);
    const p = buildLanePlacements(dayEntries, minuteHeight);
    const lc = dayEntries.length === 0 ? 1 : (p.size === 0 ? 1 : Math.max(...[...p.values()].map((v) => v.lane)) + 1);
    return { placements: p, laneCount: lc };
  }, [entries, selectedDay, minuteHeight]);

  // Group placements by lane
  const laneEntries = useMemo(() => {
    const lanes = Array.from({ length: laneCount }, () => []);
    placements.forEach((placement, entry) => {
      lanes[placement.lane].push({ entry, placement });
    });
    return lanes;
  }, [placements, laneCount]);

  const handleCardClick = useCallback((entry) => {
    onEntryClick(entry);
  }, [onEntryClick]);

  const hourLines = Array.from({ length: hourCount }, (_, i) => i);
  const halfLines = Array.from({ length: hourCount }, (_, i) => i);

  return (
    <div className="admin-cal-wrapper" ref={wrapperRef}>
      <div
        className="admin-cal-body"
        style={{ gridTemplateColumns: `${timeColWidth}px repeat(${laneCount}, minmax(${laneMinWidth}px, 1fr))` }}
      >
        {/* Time gutter */}
        <div className="week-cal-time-col" style={{ height: `${totalHeight}px` }}>
          {Array.from({ length: hourCount + 1 }, (_, i) => {
            const minute = calendarStartMinute + i * 60;
            return (
              <div
                key={minute}
                className="week-cal-time-label"
                style={{ top: `${i * 60 * minuteHeight}px` }}
              >
                {formatMinute(minute)}
              </div>
            );
          })}
        </div>

        {/* Lane columns */}
        {laneEntries.map((lane, laneIdx) => (
          <div
            key={laneIdx}
            className="week-cal-day-col admin-cal-lane-col"
            style={{ height: `${totalHeight}px` }}
          >
            {/* Hour lines */}
            {hourLines.map((i) => (
              <div key={i} className="week-cal-hour-line" style={{ top: `${i * 60 * minuteHeight}px` }} />
            ))}
            {/* Half-hour lines */}
            {halfLines.map((i) => (
              <div key={`h-${i}`} className="week-cal-halfhour-line" style={{ top: `${(i * 60 + 30) * minuteHeight}px` }} />
            ))}

            {/* Entry cards */}
            {lane.map(({ entry, placement }, idx) => {
              const toneClass = getEntryToneClass(entry);
              const sessionShort = compactSessionName(entry.module_code, entry.session_name);
              const h = placement.height;
              const isTiny = h < 28;
              const isShort = h < 52;

              return (
                <button
                  key={`${entry.session_id}-${entry.occurrence_index ?? 1}-${idx}`}
                  type="button"
                className={`week-cal-entry ${toneClass}`}
                style={{
                  top: `${placement.top + 4}px`,
                  height: `${Math.max(h - 8, 22)}px`,
                  left: "6px",
                  right: "6px",
                }}
                  onClick={() => handleCardClick(entry)}
                  title={[
                    `${entry.module_code} ${entry.session_name}`,
                    `${formatMinute(entry.start_minute)} – ${formatMinute(entry.start_minute + entry.duration_minutes)}`,
                    entry.room_name,
                    entry.lecturer_names.join(", "),
                  ].filter(Boolean).join("\n")}
                >
                  {isTiny ? (
                    <span className="wce-code-only">{entry.module_code}</span>
                  ) : isShort ? (
                    <>
                      <span className="wce-top-line">
                        <span className="wce-code">{entry.module_code}</span>
                      </span>
                      <span className="wce-room">{entry.room_name}</span>
                    </>
                  ) : (
                    <>
                      <span className="wce-top-line">
                        <span className="wce-code">{entry.module_code}</span>
                      </span>
                      <span className="wce-type-room">
                        <span className={`wce-type-dot ${toneClass}`} />
                        {toneClass === "is-lab" ? "Lab" : "Lecture"} · {entry.room_name}
                      </span>
                      {sessionShort && (
                        <span className="wce-session">{sessionShort}</span>
                      )}
                      {h >= 72 && (
                        <span className="wce-time">
                          {formatMinute(entry.start_minute)} – {formatMinute(entry.start_minute + entry.duration_minutes)}
                        </span>
                      )}
                      {h >= 100 && entry.lecturer_names.length > 0 && (
                        <span className="wce-lecturer-line">
                          {compactLecturerNames(entry.lecturer_names)}
                        </span>
                      )}
                      {h >= 130 && (
                        <span className="wce-students-line">
                          {entry.total_students} students
                          {entry.student_group_names.length > 0 && (
                            <> · {compactAudienceLabels(entry.student_group_names)}</>
                          )}
                        </span>
                      )}
                    </>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

const AdminDayCalendar = memo(AdminDayCalendarInner);

// ─── Day Picker ────────────────────────────────────────────────────────────────

function DayPickerInner({ selectedDay, onSelectDay, dayLoad }) {
  return (
    <div className="day-picker" role="tablist" aria-label="Select day" data-tour="views-day-picker">
      {days.map((day) => {
        const load = dayLoad.find((d) => d.day === day);
        const isActive = day === selectedDay;
        return (
          <button
            key={day}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`day-picker-btn${isActive ? " active" : ""}`}
            onClick={() => onSelectDay(day)}
          >
            <span className="dp-day-name">{day.slice(0, 3).toUpperCase()}</span>
            {load && load.total > 0 && (
              <span className="dp-count">{load.total}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

const DayPicker = memo(DayPickerInner);

// ─── Day Calendar Component ────────────────────────────────────────────────────

function DayCalendarInner({ entries, selectedDay, minuteHeight, onEntryClick }) {
  const hourCount = (calendarEndMinute - calendarStartMinute) / 60;
  const totalHeight = (calendarEndMinute - calendarStartMinute) * minuteHeight;
  const timeColWidth = 52;

  const [popover, setPopover] = useState(null);
  const wrapperRef = useRef(null);

  const groupMap = useMemo(() => {
    const dayEntries = entries.filter((e) => e.day === selectedDay);
    return groupOverlappingEntries(dayEntries, minuteHeight);
  }, [entries, selectedDay, minuteHeight]);

  // Close popover when the day changes
  useEffect(() => { setPopover(null); }, [selectedDay]);

  const handleCardClick = useCallback((e, primary, placement) => {
    if (placement.extraCount === 0) {
      onEntryClick(primary);
      return;
    }
    e.stopPropagation();
    const wrapperRect = wrapperRef.current?.getBoundingClientRect() ?? { top: 0, left: 0 };
    const cardRect = e.currentTarget.getBoundingClientRect();
    setPopover({
      allEntries: placement.allEntries,
      top: cardRect.bottom - wrapperRect.top + 4,
      left: cardRect.left - wrapperRect.left,
    });
  }, [onEntryClick]);

  const closePopover = useCallback(() => setPopover(null), []);

  return (
    <div className="week-cal-wrapper" ref={wrapperRef}>
      {/* Body: time gutter + single day column */}
      <div className="week-cal-body" style={{ gridTemplateColumns: `${timeColWidth}px 1fr` }}>
        {/* Time gutter */}
        <div className="week-cal-time-col" style={{ height: `${totalHeight}px` }}>
          {Array.from({ length: hourCount + 1 }, (_, i) => {
            const minute = calendarStartMinute + i * 60;
            return (
              <div
                key={minute}
                className="week-cal-time-label"
                style={{ top: `${i * 60 * minuteHeight}px` }}
              >
                {formatMinute(minute)}
              </div>
            );
          })}
        </div>

        {/* Single day column */}
        <div className="week-cal-day-col" style={{ height: `${totalHeight}px` }}>
          {/* Hour lines */}
          {Array.from({ length: hourCount }, (_, i) => (
            <div
              key={i}
              className="week-cal-hour-line"
              style={{ top: `${i * 60 * minuteHeight}px` }}
            />
          ))}
          {/* Half-hour lines */}
          {Array.from({ length: hourCount }, (_, i) => (
            <div
              key={`half-${i}`}
              className="week-cal-halfhour-line"
              style={{ top: `${(i * 60 + 30) * minuteHeight}px` }}
            />
          ))}

          {/* Entry blocks — one per group (primary only) */}
          {[...groupMap.entries()].map(([primary, placement], idx) => {
            const toneClass = getEntryToneClass(primary);
            const sessionShort = compactSessionName(primary.module_code, primary.session_name);
            const blockHeight = placement.height;
            const isShort = blockHeight < 48;
            const isTiny = blockHeight < 28;
            const hasExtras = placement.extraCount > 0;

            return (
              <button
                key={`${selectedDay}-${primary.session_id}-${primary.occurrence_index ?? 1}-${idx}`}
                type="button"
                className={`week-cal-entry ${toneClass}${hasExtras ? " has-extras" : ""}`}
                style={{
                  top: `${placement.top + 4}px`,
                  height: `${Math.max(blockHeight - 8, 22)}px`,
                  left: "8px",
                  right: "8px",
                }}
                onClick={(e) => handleCardClick(e, primary, placement)}
                title={hasExtras
                  ? `${placement.allEntries.length} sessions at ${formatMinute(primary.start_minute)} — click to see all`
                  : [
                      `${primary.module_code} ${primary.session_name}`,
                      `${formatMinute(primary.start_minute)} – ${formatMinute(primary.start_minute + primary.duration_minutes)}`,
                      primary.room_name,
                      primary.lecturer_names.join(", "),
                    ].filter(Boolean).join("\n")
                }
              >
                {isTiny ? (
                  <span className="wce-code-only">{primary.module_code}{hasExtras ? ` +${placement.extraCount}` : ""}</span>
                ) : isShort ? (
                  <>
                    <span className="wce-top-line">
                      <span className="wce-code">{primary.module_code}</span>
                      {hasExtras && <span className="wce-extras-badge">+{placement.extraCount}</span>}
                    </span>
                    <span className="wce-room">{primary.room_name}</span>
                  </>
                ) : (
                  <>
                    <span className="wce-top-line">
                      <span className="wce-code">{primary.module_code}</span>
                      {hasExtras && <span className="wce-extras-badge">+{placement.extraCount}</span>}
                    </span>
                    <span className="wce-type-room">
                      <span className={`wce-type-dot ${toneClass}`} />
                      {toneClass === "is-lab" ? "Lab" : "Lecture"} · {primary.room_name}
                    </span>
                    {sessionShort && (
                      <span className="wce-session">{sessionShort}</span>
                    )}
                    {blockHeight >= 72 && (
                      <span className="wce-time">
                        {formatMinute(primary.start_minute)} – {formatMinute(primary.start_minute + primary.duration_minutes)}
                      </span>
                    )}
                    {blockHeight >= 100 && primary.lecturer_names.length > 0 && (
                      <span className="wce-lecturer-line">
                        {compactLecturerNames(primary.lecturer_names)}
                      </span>
                    )}
                    {blockHeight >= 130 && (
                      <span className="wce-students-line">
                        {primary.total_students} students
                        {primary.student_group_names.length > 0 && (
                          <> · {compactAudienceLabels(primary.student_group_names)}</>
                        )}
                      </span>
                    )}
                  </>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Slot popover */}
      {popover && (
        <SlotPopover
          entries={popover.allEntries}
          anchorStyle={{ top: popover.top, left: popover.left }}
          onSelectEntry={onEntryClick}
          onClose={closePopover}
        />
      )}
    </div>
  );
}

const DayCalendar = memo(DayCalendarInner);

// ─── Agenda Component ──────────────────────────────────────────────────────────

function AgendaViewInner({ agendaDays, onEntryClick }) {
  return (
    <div className="agenda-view">
      {agendaDays.map(({ day, entries }) => (
        <section key={day} className="agenda-day-section">
          <div className="agenda-day-header">
            <h3 className="agenda-day-name">{day}</h3>
            <span className="agenda-day-count">{entries.length} sessions</span>
          </div>
          <div className="agenda-table">
            <div className="agenda-table-head">
              <span>Time</span>
              <span>Module</span>
              <span>Session</span>
              <span>Room</span>
              <span>Lecturer</span>
              <span>Students</span>
            </div>
            {entries.map((entry, idx) => {
              const toneClass = getEntryToneClass(entry);
              const sessionShort = compactSessionName(entry.module_code, entry.session_name);
              const endMinute = entry.start_minute + entry.duration_minutes;
              const audienceCompact = compactAudienceLabels(entry.degree_path_labels || []);
              const allLecturers = (entry.lecturer_names || []).join(", ") || "Unassigned";
              return (
                <button
                  key={getEntryKey(entry, idx)}
                  type="button"
                  className={`agenda-table-row ${toneClass}`}
                  onClick={() => onEntryClick(entry)}
                >
                  <span className="at-time">
                    <strong>{formatMinute(entry.start_minute)}</strong>
                    <small>{formatMinute(endMinute)}</small>
                  </span>
                  <span className="at-code">
                    <span className="at-type-dot" />
                    {entry.module_code}
                  </span>
                  <span className="at-session">{sessionShort || entry.session_name}</span>
                  <span className="at-room">
                    <span className="at-room-name">{entry.room_name}</span>
                    {entry.room_location && (
                      <small className="at-room-loc">{entry.room_location}</small>
                    )}
                  </span>
                  <span className="at-lecturer" title={allLecturers}>
                    {compactLecturerNames(entry.lecturer_names)}
                  </span>
                  <span className="at-students">
                    <strong>{entry.total_students}</strong>
                    {audienceCompact && (
                      <small className="at-groups">{audienceCompact}</small>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

const AgendaView = memo(AgendaViewInner);

// ─── Main Page Component ───────────────────────────────────────────────────────

function ViewStudio() {
  const [mode, setMode] = useState("admin");
  const [activeImportRunId] = useState(() => {
    if (typeof window === "undefined") {
      return null;
    }
    const raw = window.localStorage.getItem(activeImportRunStorageKey);
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  });
  const [view, setView] = useState(null);
  const [lookups, setLookups] = useState({ lecturers: [], degrees: [], student_paths: [] });
  const [selectedLecturerId, setSelectedLecturerId] = useState("");
  const [selectedDegreeId, setSelectedDegreeId] = useState("");
  const [selectedPathId, setSelectedPathId] = useState("");
  const [layoutMode, setLayoutMode] = useState("calendar");
  const [densityMode, setDensityMode] = useState("comfortable");
  const [modalEntry, setModalEntry] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [selectedDay, setSelectedDay] = useState(days[0]);
  const [visualExportScope, setVisualExportScope] = useState("whole_week");

  const minuteHeight = densityModes[densityMode].minuteHeight;

  const availableStudentPaths = useMemo(
    () => lookups.student_paths.filter((p) => String(p.degree_id) === String(selectedDegreeId || "")),
    [lookups.student_paths, selectedDegreeId]
  );
  const selectedStudentPath = useMemo(
    () =>
      availableStudentPaths.find(
        (item) => studentPathValue(item) === String(selectedPathId || "")
      ) || null,
    [availableStudentPaths, selectedPathId]
  );

  const loadView = useCallback(
    async (nextMode = mode) => {
      setLoading(true);
      setError("");
      try {
        const response = await timetableStudioService.view({
          mode: nextMode,
          importRunId: activeImportRunId,
          lecturerId: nextMode === "lecturer" ? selectedLecturerId : undefined,
          degreeId: nextMode === "student" ? selectedDegreeId : undefined,
          studyYear: nextMode === "student" ? selectedStudentPath?.year : undefined,
          pathId:
            nextMode === "student" && selectedStudentPath?.id
              ? selectedStudentPath.id
              : undefined,
        });
        setView(response);
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
    },
    [activeImportRunId, mode, selectedLecturerId, selectedDegreeId, selectedPathId, selectedStudentPath]
  );

  useEffect(() => {
    timetableStudioService.getLookups(activeImportRunId).then(setLookups).catch(() => {});
    loadView();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeImportRunId]);

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

  const agendaDays = useMemo(() => buildAgendaDays(view?.solution?.entries || []), [view]);
  const dayLoad = useMemo(() => buildDayLoad(view?.solution?.entries || []), [view]);

  // Sync selectedDay to first day that has entries
  useEffect(() => {
    if (view?.solution?.entries?.length) {
      const firstDay = days.find((d) => view.solution.entries.some((e) => e.day === d));
      if (firstDay) setSelectedDay(firstDay);
    }
  }, [view]);

  const handleModeChange = async (nextMode) => {
    setMode(nextMode);
    setError("");
    if (nextMode === "admin") {
      await loadView(nextMode);
      return;
    }
    setView(null);
  };

  const needsSelection =
    (mode === "lecturer" && !selectedLecturerId) ||
    (mode === "student" && (!selectedDegreeId || !selectedPathId));

  useEffect(() => {
    if (mode === "admin") {
      return;
    }
    if (needsSelection) {
      setView(null);
      return;
    }
    loadView(mode);
  }, [mode, needsSelection, selectedLecturerId, selectedDegreeId, selectedPathId, loadView]);

  const handleExport = async (format) => {
    setError("");
    setExporting(true);
    try {
      if (!view) { setError("Load a timetable before exporting."); return; }
      const exportScope =
        mode === "admin" && (format === "pdf" || format === "png")
          ? visualExportScope
          : "whole_week";
      if (format === "pdf") { await exportPdf(view, exportScope); return; }
      if (format === "xls") { await exportWorkbook(view, entryMap); return; }
      if (format === "png") { await exportPng(view, exportScope); return; }
      const response = await timetableStudioService.exportView({
        mode,
        format,
        scope: exportScope,
        importRunId: activeImportRunId,
        lecturerId: mode === "lecturer" ? selectedLecturerId : undefined,
        degreeId: mode === "student" ? selectedDegreeId : undefined,
        studyYear: mode === "student" ? selectedStudentPath?.year : undefined,
        pathId:
          mode === "student" && selectedStudentPath?.id
            ? selectedStudentPath.id
            : undefined,
      });
      downloadBase64(response.filename, response.content_type, response.content);
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  };

  const handleEntryClick = useCallback((entry) => {
    if (import.meta.env.DEV && typeof window !== "undefined") {
      window.__viewStudioSessionClickStartedAt = performance.now();
      console.debug(`[ViewStudio] Session click received for ${entry.module_code} ${entry.session_name}`);
    }
    setModalEntry(entry);
  }, []);

  const handleModalClose = useCallback(() => {
    setModalEntry(null);
  }, []);

  return (
    <div className="page-shell">
      {exporting ? (
        <div className="setup-blocking-overlay" role="status" aria-live="polite" aria-busy="true">
          <div className="setup-blocking-dialog">
            <div className="setup-blocking-spinner" aria-hidden="true" />
            <strong>Exporting timetable</strong>
            <p>The file is being prepared for download.</p>
            <span>Please wait until the export finishes.</span>
          </div>
        </div>
      ) : null}
      <div className="panel studio-panel">

        {/* ── Toolbar Row 1: Title + Mode + Filters ── */}
        <div className="vs-toolbar-row vs-toolbar-row-1">
          <div className="vs-title-block">
            <h1 className="section-title">Timetable Views</h1>
            <p className="section-subtitle">
              Start with the default timetable. Switch to lecturer or student mode only when you need a filtered view.
            </p>
            {activeImportRunId && (
              <p className="helper-copy">
                Using import snapshot #{activeImportRunId} for lookups and timetable views.
              </p>
            )}
          </div>
          <div className="vs-filter-controls" data-tour="views-mode-controls">
            <div className="vs-mode-group">
              {["admin", "lecturer", "student"].map((m) => (
                <button
                  key={m}
                  type="button"
                  className={mode === m ? "ghost-btn active-layout" : "ghost-btn"}
                  onClick={() => handleModeChange(m)}
                >
                  {m.charAt(0).toUpperCase() + m.slice(1)}
                </button>
              ))}
            </div>
            {mode === "lecturer" && (
              <select
                value={selectedLecturerId}
                onChange={(e) => setSelectedLecturerId(e.target.value)}
                className="vs-filter-select"
              >
                <option value="">Select Lecturer</option>
                {lookups.lecturers.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            )}
            {mode === "student" && (
              <>
                <select
                  value={selectedDegreeId}
                  onChange={(e) => { setSelectedDegreeId(e.target.value); setSelectedPathId(""); }}
                  className="vs-filter-select"
                >
                  <option value="">Select Degree</option>
                  {lookups.degrees.map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </select>
                <select
                  value={selectedPathId}
                  onChange={(e) => setSelectedPathId(e.target.value)}
                  disabled={!selectedDegreeId}
                  className="vs-filter-select"
                >
                  <option value="">Select Path</option>
                  {availableStudentPaths.map((item) => (
                    <option
                      key={`${item.degree_id}-${item.year}-${item.id ?? "general"}`}
                      value={studentPathValue(item)}
                    >
                      {item.label}
                    </option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>

        {/* ── Toolbar Row 2: Layout + Density + Export ── */}
        <div className="vs-toolbar-row vs-toolbar-row-2">
          <div className="vs-control-group" data-tour="views-layout-controls">
            <span className="vs-control-label">View</span>
            <div className="vs-toggle-group" role="tablist" aria-label="Layout mode">
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
          </div>
          <div className="vs-control-group" data-tour="views-density-controls">
            <span className="vs-control-label">Density</span>
            <div className="vs-toggle-group" role="tablist" aria-label="Density mode">
              {Object.entries(densityModes).map(([key, opt]) => (
                <button
                  key={key}
                  type="button"
                  className={densityMode === key ? "ghost-btn active-layout" : "ghost-btn"}
                  onClick={() => setDensityMode(key)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="vs-control-group vs-export-group" data-tour="views-export-controls">
            <span className="vs-control-label">Export</span>
            {mode === "admin" && (
              <select
                value={visualExportScope}
                onChange={(e) => setVisualExportScope(e.target.value)}
                className="vs-filter-select"
                aria-label="Admin visual export scope"
              >
                <option value="whole_week">Visual: Whole week</option>
                <option value="daily_bundle">Visual: Daily bundle</option>
              </select>
            )}
            <div className="vs-export-buttons">
              <button type="button" className="ghost-btn vs-export-btn" onClick={() => handleExport("pdf")} disabled={exporting}>PDF</button>
              <button type="button" className="ghost-btn vs-export-btn" onClick={() => handleExport("csv")} disabled={exporting}>CSV</button>
              <button type="button" className="ghost-btn vs-export-btn" onClick={() => handleExport("xls")} disabled={exporting}>XLSX</button>
              <button type="button" className="ghost-btn vs-export-btn" onClick={() => handleExport("png")} disabled={exporting}>PNG</button>
            </div>
          </div>
        </div>

        {/* ── Status banners ── */}
        {error && <div className="error-banner">{error}</div>}
        {loading && <div className="info-banner">Loading timetable view...</div>}

        {/* ── Empty states ── */}
        {!loading && mode === "lecturer" && !view && !error && !selectedLecturerId && (
          <section className="studio-card vs-empty-state">
            <h2>Select a lecturer</h2>
            <p>Choose a lecturer above to load their timetable automatically.</p>
          </section>
        )}
        {!loading && mode === "student" && !view && !error && (
          <section className="studio-card vs-empty-state">
            <h2>Select a degree and path</h2>
            <p>Choose the degree and path above to load the student timetable automatically.</p>
          </section>
        )}
        {!loading && mode === "admin" && !view && !error && (
          <section className="studio-card vs-empty-state">
            <h2>No default timetable available</h2>
            <p>Generate timetable solutions in the Generate page and mark one as the default before using Views.</p>
          </section>
        )}

        {/* ── Main timetable content ── */}
        {view && (
          <>
            {/* View info bar */}
            <div className="vs-view-info-bar">
              <div>
                <span className="vs-view-title">{view.title}</span>
                <span className="vs-view-subtitle">{view.subtitle}</span>
              </div>
              <span className="vs-entry-count">{view.solution.entries.length} sessions total</span>
            </div>

            {/* Calendar or Agenda */}
            {layoutMode === "calendar" ? (
              <>
                <DayPicker
                  selectedDay={selectedDay}
                  onSelectDay={setSelectedDay}
                  dayLoad={dayLoad}
                />
                <section className="studio-card vs-calendar-card" data-tour="views-calendar-surface">
                  {mode === "admin" ? (
                    <AdminDayCalendar
                      entries={view.solution.entries}
                      selectedDay={selectedDay}
                      minuteHeight={minuteHeight}
                      onEntryClick={handleEntryClick}
                    />
                  ) : (
                    <DayCalendar
                      entries={view.solution.entries}
                      selectedDay={selectedDay}
                      minuteHeight={minuteHeight}
                      onEntryClick={handleEntryClick}
                    />
                  )}
                </section>
              </>
            ) : (
              <section className="studio-card vs-agenda-card">
                <AgendaView
                  agendaDays={agendaDays}
                  onEntryClick={handleEntryClick}
                />
              </section>
            )}
          </>
        )}
      </div>

      {/* ── Session detail modal ── */}
      {modalEntry && <SessionModal entry={modalEntry} onClose={handleModalClose} />}
    </div>
  );
}

export default ViewStudio;
