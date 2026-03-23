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
    analyzeEnrollmentImport: vi.fn(),
    previewEnrollmentImport: vi.fn(),
    materializeEnrollmentImport: vi.fn(),
    seedRealisticSnapshotMissingData: vi.fn(),
    createSnapshotLecturersBatch: vi.fn(),
    createSnapshotRoomsBatch: vi.fn(),
    createSnapshotSharedSessionsBatch: vi.fn(),
    updateSnapshotLecturer: vi.fn(),
    updateSnapshotRoom: vi.fn(),
    updateSnapshotSharedSession: vi.fn(),
    deleteSnapshotLecturer: vi.fn(),
    deleteSnapshotRoom: vi.fn(),
    deleteSnapshotSharedSession: vi.fn(),
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

describe("SetupStudio snapshot-first UI", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
    timetableStudioService.getImportWorkspace.mockResolvedValue(workspaceWithSnapshot());
  });

  it("shows the import-first landing state when no snapshot is active", async () => {
    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByText("Import Student Enrolments")).toBeInTheDocument();
    expect(screen.getByText("Start with the easiest path")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start Demo with Sample Data" })
    ).toBeInTheDocument();
    expect(screen.getByText("Review The CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze Enrollment CSV" })).toBeDisabled();
    expect(screen.getByText("No CSV selected yet")).toBeInTheDocument();
  });

  it("restores the snapshot completion flow when an active import exists", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(
      await screen.findByText(/Restored snapshot #77\. Continue completing the missing teaching details\./i)
    ).toBeInTheDocument();
    expect(screen.getByText("Complete Missing Details")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Fill Demo Teaching Data" }).length
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Review Before Generate" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit Manually" })).not.toBeInTheDocument();
    expect(screen.queryByText("CSV Uploads")).not.toBeInTheDocument();
  });
});
