import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import SetupStudio from "./SetupStudio";
import { timetableStudioService } from "../services/timetableStudioService";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
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

function emptyWorkspace() {
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

describe("SetupStudio", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    navigateMock.mockReset();
    window.localStorage.clear();
    timetableStudioService.getImportWorkspace.mockResolvedValue(emptyWorkspace());
  });

  it("shows a compact start flow", async () => {
    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByText("Start")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start Demo with Sample Data" })).toBeInTheDocument();
    expect(screen.getAllByText(/Import student enrollments/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("Review The CSV")).not.toBeInTheDocument();
  });

  it("lets the user replace enrollments from a collapsed section after snapshot restore", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      ...emptyWorkspace(),
      lecturers: [{ id: 1, name: "Dr. Silva", email: "silva@example.edu", notes: "Imported from lecturers.csv" }],
      rooms: [{ id: 1, name: "A7 Hall 1", capacity: 180, room_type: "lecture" }],
      shared_sessions: [{ id: 1, name: "Chemistry Lecture", session_type: "lecture", lecturer_ids: [1], attendance_group_ids: [] }],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Restored snapshot #77/i)).toBeInTheDocument();
    expect(screen.getByText("Current Snapshot")).toBeInTheDocument();
    expect(screen.getByText("Replace enrollments")).toBeInTheDocument();
  });

  it("blocks opening generate when review has blockers", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      ...emptyWorkspace(),
      lecturers: [{ id: 1, name: "Dr. Silva" }],
      rooms: [{ id: 1, name: "A7 Hall 1", capacity: 180, room_type: "lecture" }],
      shared_sessions: [{ id: 1, name: "Chemistry Lecture", session_type: "lecture", lecturer_ids: [1], attendance_group_ids: [] }],
    });

    render(
      <MemoryRouter>
        <SetupStudio />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "Review blockers" }));

    await waitFor(() => {
      expect(screen.getByText("Ready to Generate")).toBeInTheDocument();
    });
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
