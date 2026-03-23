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

function renderSetupStudio() {
  return render(
    <MemoryRouter>
      <SetupStudio />
    </MemoryRouter>
  );
}

function emptyWorkspace() {
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

describe("SetupStudio", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    navigateMock.mockReset();
    window.localStorage.clear();
  });

  it("shows snapshot-first import guidance before a CSV is chosen", async () => {
    renderSetupStudio();

    expect(await screen.findByText("Setup Studio")).toBeInTheDocument();
    expect(screen.getByText("Start with the easiest path")).toBeInTheDocument();
    expect(screen.getByText("Import Student Enrolments")).toBeInTheDocument();
    expect(screen.getByText("Review The CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start Demo with Sample Data" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze Enrollment CSV" })).toBeDisabled();
  });

  it("shows restored snapshot guidance and opens generation when setup is ready", async () => {
    window.localStorage.setItem("kln_active_import_run_id", "77");
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      ...emptyWorkspace(),
      programmes: [
        {
          id: 1,
          code: "PS",
          name: "Physical Science",
          duration_years: 3,
          intake_label: "PS Intake",
        },
      ],
      lecturers: [
        { id: 10, name: "Dr Silva", email: "silva@example.com", notes: null },
      ],
      rooms: [
        {
          id: 20,
          name: "A7 301",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "A7",
          year_restriction: null,
          notes: null,
        },
      ],
      attendance_groups: [
        {
          id: 30,
          programme_id: 1,
          programme_path_id: null,
          academic_year: "2022/2023",
          study_year: 1,
          label: "PS Y1 General",
          student_count: 80,
        },
      ],
      curriculum_modules: [
        {
          id: 40,
          code: "CHEM 11612",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          nominal_year: 1,
          semester_bucket: 1,
          is_full_year: false,
          attendance_group_ids: [30],
        },
      ],
      shared_sessions: [
        {
          id: 50,
          name: "Chemistry Lecture",
          session_type: "lecture",
          duration_minutes: 120,
          occurrences_per_week: 1,
          required_room_type: "lecture",
          required_lab_type: null,
          specific_room_id: 20,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_ids: [10],
          curriculum_module_ids: [40],
          attendance_group_ids: [30],
        },
      ],
    });

    renderSetupStudio();

    expect(
      await screen.findByText(/Restored snapshot #77\. Continue completing the missing teaching details\./i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Student enrolments are loaded\. Now complete the missing teaching details\./i)).toBeInTheDocument();
    const openGenerateButtons = screen.getAllByRole("button", { name: "Open Generate" });
    expect(openGenerateButtons.length).toBeGreaterThan(0);

    fireEvent.click(openGenerateButtons[0]);

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/generate");
    });
  });

  it("analyzes, reviews, and materializes an enrollment CSV into the active snapshot flow", async () => {
    timetableStudioService.analyzeEnrollmentImport.mockResolvedValue({
      source_file: "students_processed_TT_J.csv",
      summary: {
        total_rows: 10,
        unique_students: 3,
      },
      buckets: [
        {
          bucket_type: "year_code_mismatch",
          bucket_key: "year=2|nominal_year=1",
          description: "CSV Year 2 does not match nominal module year 1.",
          row_count: 6,
        },
      ],
    });
    timetableStudioService.previewEnrollmentImport.mockResolvedValue({
      projection_summary: {
        projected_rows: 6,
      },
    });
    timetableStudioService.materializeEnrollmentImport.mockResolvedValue({
      import_run_id: 88,
      counts: {
        programmes: 1,
        attendance_groups: 2,
      },
    });
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      ...emptyWorkspace(),
      import_run_id: 88,
    });

    renderSetupStudio();

    fireEvent.click(screen.getByRole("button", { name: "Use Sample CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "Analyze Enrollment CSV" }));

    expect(await screen.findByText(/CSV Year 2 does not match nominal module year 1\./i)).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "accept_exception" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Review Import" }));

    expect(await screen.findByText("Review result")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Use This Import" }));

    await waitFor(() => {
      expect(timetableStudioService.materializeEnrollmentImport).toHaveBeenCalledTimes(1);
      expect(timetableStudioService.getImportWorkspace).toHaveBeenCalledWith(88);
    });
    expect(
      await screen.findByText(/The CSV import has been materialized into snapshot #88\./i)
    ).toBeInTheDocument();
  });
});
