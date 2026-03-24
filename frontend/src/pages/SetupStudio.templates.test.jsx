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
    listImportTemplates: vi.fn(),
    downloadImportTemplate: vi.fn(),
    analyzeEnrollmentImport: vi.fn(),
    previewEnrollmentImport: vi.fn(),
    materializeEnrollmentImport: vi.fn(),
    uploadModulesCsv: vi.fn(),
    uploadRoomsCsv: vi.fn(),
    uploadLecturersCsv: vi.fn(),
    uploadSessionsCsv: vi.fn(),
    uploadSessionLecturersCsv: vi.fn(),
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
    expect(screen.getAllByText("Needs snapshot").length).toBeGreaterThan(0);
    expect(screen.queryByText("Edit Manually")).not.toBeInTheDocument();
    expect(screen.queryByText("CSV Uploads")).not.toBeInTheDocument();
  });

  it("shows the snapshot gap-fill forms when an active import exists", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(
      await screen.findByText(/Restored snapshot #77\. Continue completing the missing teaching details\./i)
    ).toBeInTheDocument();
    expect(screen.getByText("Gap Fill Forms")).toBeInTheDocument();
    expect(screen.getAllByText("Ready to import").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Add Lecturer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Room" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Shared Session" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fill Demo Teaching Data" })).toBeInTheDocument();
  });
});
