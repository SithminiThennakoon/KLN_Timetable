import React from "react";
import { render, screen } from "@testing-library/react";
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
    listImportFixtures: vi.fn(),
    listImportRuns: vi.fn(),
    listImportTemplates: vi.fn(),
    downloadImportTemplate: vi.fn(),
    downloadImportFixturePack: vi.fn(),
    analyzeEnrollmentImport: vi.fn(),
    previewEnrollmentImport: vi.fn(),
    materializeEnrollmentImport: vi.fn(),
    uploadModulesCsv: vi.fn(),
    uploadRoomsCsv: vi.fn(),
    uploadLecturersCsv: vi.fn(),
    uploadSessionsCsv: vi.fn(),
    uploadSessionLecturersCsv: vi.fn(),
    importDemoBundle: vi.fn(),
    seedRealisticSnapshotMissingData: vi.fn(),
    createSnapshotLecturersBatch: vi.fn(),
    createSnapshotRoomsBatch: vi.fn(),
    createSnapshotSharedSessionsBatch: vi.fn(),
  },
}));

function workspaceWithSnapshot() {
  return {
    import_run_id: 77,
    selected_academic_year: "2022/2023",
    programmes: [],
    programme_paths: [],
    curriculum_modules: [],
    attendance_groups: [],
    lecturers: [],
    rooms: [],
    shared_sessions: [],
  };
}

describe("SetupStudio minimal setup UI", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
    timetableStudioService.listImportTemplates.mockResolvedValue({
      templates: [],
    });
    timetableStudioService.listImportFixtures.mockResolvedValue({
      packs: [],
    });
    timetableStudioService.listImportRuns.mockResolvedValue({
      runs: [],
    });
    timetableStudioService.getImportWorkspace.mockResolvedValue(workspaceWithSnapshot());
  });

  it("shows the import-first landing state when no snapshot is active", async () => {
    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByText("Import Files")).toBeInTheDocument();
    expect(screen.getAllByText("Student Enrolments").length).toBeGreaterThan(0);
    expect(screen.getByText("What The System Understood")).toBeInTheDocument();
    expect(screen.getByText("Missing For Generation")).toBeInTheDocument();
    expect(screen.getByText("Continue")).toBeInTheDocument();
    expect(screen.getAllByText("Waiting for student enrolments").length).toBeGreaterThan(0);
    expect(screen.queryByText("Use Sample CSV")).not.toBeInTheDocument();
    expect(screen.queryByText("Edit Manually")).not.toBeInTheDocument();
    expect(screen.queryByText("CSV Uploads")).not.toBeInTheDocument();
  });

  it("shows utilities instead of auto-restoring a snapshot on load", async () => {
    timetableStudioService.listImportRuns.mockResolvedValue({
      runs: [
        {
          import_run_id: 77,
          source_file: "students_processed_TT_J.csv",
          status: "materialized",
          selected_academic_year: "2022/2023",
        },
      ],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByRole("button", { name: "Utilities" })).toBeInTheDocument();
    expect(screen.queryByText(/Restored snapshot/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download Fixture Pack" })).not.toBeInTheDocument();
    expect(screen.queryByText("Repair Missing Data")).not.toBeInTheDocument();
  });
});
