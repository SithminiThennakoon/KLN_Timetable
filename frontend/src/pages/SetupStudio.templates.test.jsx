import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import SetupStudio from "./SetupStudio";
import { timetableStudioService } from "../services/timetableStudioService";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock("../services/timetableStudioService", () => ({
  timetableStudioService: {
    getImportWorkspace: vi.fn(),
    getImportReadiness: vi.fn(),
    importSnapshotRoomsCsv: vi.fn(),
    importSnapshotLecturersCsv: vi.fn(),
    importSnapshotModulesCsv: vi.fn(),
    importSnapshotSharedSessionsCsv: vi.fn(),
    importSnapshotSessionLecturersCsv: vi.fn(),
  },
}));

describe("SetupStudio CSV templates", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
  });

  it("shows the enrollment template link on the main import step", async () => {
    timetableStudioService.getImportReadiness.mockResolvedValue({
      import_run_id: 77,
      ready: false,
      counts: { modules: 0, rooms: 0, lecturers: 0, shared_sessions: 0 },
      blocking: [],
      warnings: [],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    const enrollmentTemplateLink = await screen.findByRole("link", {
      name: /Download the enrollment template/i,
    });
    expect(enrollmentTemplateLink.getAttribute("href")).toContain(
      "/api/v2/imports/templates/student_enrollments"
    );
  });

  it("shows support CSV import cards after an import workspace is active", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      selected_academic_year: "2022/2023",
      programmes: [],
      programme_paths: [],
      curriculum_modules: [],
      attendance_groups: [],
      lecturers: [],
      rooms: [],
      shared_sessions: [],
    });
    timetableStudioService.getImportReadiness.mockResolvedValue({
      import_run_id: 77,
      ready: false,
      counts: { modules: 12, rooms: 0, lecturers: 0, shared_sessions: 0 },
      blocking: ["Import rooms.csv or add rooms manually."],
      warnings: [],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByText("Step 2: Add Teaching Data")).toBeInTheDocument();
    expect(
      screen.getByText(/Re-import policy: CSV re-imports update existing records only when the original stable keys match/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Rooms CSV")).toBeInTheDocument();
    expect(screen.getByText("Modules CSV")).toBeInTheDocument();
    expect(screen.getByText("Session Lecturers CSV")).toBeInTheDocument();
  });

  it("shows import readiness guidance on the review step", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      selected_academic_year: "2022/2023",
      programmes: [],
      programme_paths: [],
      curriculum_modules: [],
      attendance_groups: [],
      lecturers: [],
      rooms: [],
      shared_sessions: [],
    });
    timetableStudioService.getImportReadiness.mockResolvedValue({
      import_run_id: 77,
      ready: false,
      counts: { modules: 12, rooms: 0, lecturers: 0, shared_sessions: 0 },
      blocking: [
        "Import rooms.csv or add rooms manually.",
        "Import sessions.csv or add teaching sessions manually.",
      ],
      warnings: [],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    await screen.findByText("Step 2: Add Teaching Data");
    fireEvent.click(screen.getByRole("button", { name: "4. Ready to Generate" }));

    expect(await screen.findByText("Import Readiness Checklist")).toBeInTheDocument();
    expect(screen.getByText(/Import rooms.csv or add rooms manually/i)).toBeInTheDocument();
    expect(screen.getByText(/Import sessions.csv or add teaching sessions manually/i)).toBeInTheDocument();
  });

  it("shows a clearer warning list after a support CSV import", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      selected_academic_year: "2022/2023",
      programmes: [],
      programme_paths: [],
      curriculum_modules: [],
      attendance_groups: [],
      lecturers: [],
      rooms: [],
      shared_sessions: [],
    });
    timetableStudioService.getImportReadiness.mockResolvedValue({
      import_run_id: 77,
      ready: false,
      counts: { modules: 12, rooms: 0, lecturers: 0, shared_sessions: 0 },
      blocking: [],
      warnings: [],
    });
    timetableStudioService.importSnapshotRoomsCsv.mockResolvedValue({
      created_count: 2,
      updated_count: 1,
      warnings: [
        { row_number: 3, message: "Lab room 'Chemistry Lab 1' has no lab_type" },
        { row_number: null, message: "Ignoring unknown columns: building_code" },
      ],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    await screen.findByText("Step 2: Add Teaching Data");
    const file = new File(["room_code,room_name,capacity,room_type\nR1,Room 1,30,lecture\n"], "rooms.csv", {
      type: "text/csv",
    });
    const roomCard = screen.getByText("Rooms CSV").closest(".editor-card");
    const fileInput = roomCard.querySelector('input[type="file"]');
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getAllByRole("button", { name: "Import CSV" })[0]);

    expect(await screen.findByText(/Rooms CSV: 2 created, 1 updated, 2 warnings./i)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Warnings from this import"));
    expect(screen.getByText(/Row 3: Lab room 'Chemistry Lab 1' has no lab_type/i)).toBeInTheDocument();
    expect(screen.getByText(/Ignoring unknown columns: building_code/i)).toBeInTheDocument();
  });

  it("blocks session lecturer import until sessions and lecturers exist", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      selected_academic_year: "2022/2023",
      programmes: [],
      programme_paths: [],
      curriculum_modules: [],
      attendance_groups: [],
      lecturers: [],
      rooms: [],
      shared_sessions: [],
    });
    timetableStudioService.getImportReadiness.mockResolvedValue({
      import_run_id: 77,
      ready: false,
      counts: { modules: 12, rooms: 0, lecturers: 0, shared_sessions: 0 },
      blocking: ["Import sessions.csv or add teaching sessions manually."],
      warnings: [],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    const card = (await screen.findByText("Session Lecturers CSV")).closest(".editor-card");
    expect(within(card).getByText("Import sessions.csv first.")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Import CSV" })).toBeDisabled();
  });

  it("shows backend readiness blockers and warnings on the review step", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      selected_academic_year: "2022/2023",
      programmes: [],
      programme_paths: [],
      curriculum_modules: [],
      attendance_groups: [],
      lecturers: [],
      rooms: [],
      shared_sessions: [],
    });
    timetableStudioService.getImportReadiness.mockResolvedValue({
      import_run_id: 77,
      ready: false,
      counts: { modules: 12, rooms: 4, lecturers: 6, shared_sessions: 2 },
      blocking: ["2 sessions still need lecturers."],
      warnings: [
        "Dr. Silva is assigned 50.0 weekly hours, which exceeds the timetable capacity of 45 hours.",
      ],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "4. Ready to Generate" }));
    expect(await screen.findByText("Import Readiness Checklist")).toBeInTheDocument();
    expect(screen.getByText("2 sessions still need lecturers.")).toBeInTheDocument();
    expect(screen.getByText("Backend Readiness Warnings")).toBeInTheDocument();
    expect(
      screen.getByText(
        /Dr. Silva is assigned 50.0 weekly hours, which exceeds the timetable capacity of 45 hours./i
      )
    ).toBeInTheDocument();
  });
});
