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
  },
}));

function workspaceWithSnapshot() {
  return {
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

describe("SetupStudio current UI", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();
    timetableStudioService.getImportWorkspace.mockResolvedValue(workspaceWithSnapshot());
  });

  it("shows compact enrollment controls", async () => {
    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByText("Import student enrollments")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Download enrollment template/i })).toBeInTheDocument();
    expect(screen.getByText("Choose CSV File")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use Sample CSV" })).toBeInTheDocument();
  });

  it("shows teaching data step after restoring a snapshot", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByText("Current Snapshot")).toBeInTheDocument();
    expect(screen.getByText("Step 2: Add Teaching Data")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Fill Demo Teaching Data" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Edit Manually" })).toBeInTheDocument();
  });
});
