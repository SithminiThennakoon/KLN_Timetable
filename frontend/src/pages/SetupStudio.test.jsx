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
    updateSnapshotSharedSession: vi.fn(),
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
    timetableStudioService.listImportTemplates.mockResolvedValue({
      templates: [],
    });
    timetableStudioService.listImportFixtures.mockResolvedValue({
      packs: [],
    });
    timetableStudioService.listImportRuns.mockResolvedValue({
      runs: [],
    });
  });

  it("shows the minimal import-first setup flow before a CSV is chosen", async () => {
    renderSetupStudio();

    expect(await screen.findByText("Setup Studio")).toBeInTheDocument();
    expect(screen.getByText("Import Files")).toBeInTheDocument();
    expect(screen.getByText("What The System Understood")).toBeInTheDocument();
    expect(screen.getByText("Missing For Generation")).toBeInTheDocument();
    expect(screen.getByText("No CSV selected yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze Import" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Continue to Generate" })).toBeDisabled();
  });

  it("opens a previous snapshot explicitly from utilities and allows generation when setup is ready", async () => {
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
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      ...emptyWorkspace(),
      programmes: [{ id: 1, code: "PS", name: "Physical Science", duration_years: 3 }],
      lecturers: [{ id: 10, name: "Dr Silva", email: "silva@example.com", notes: null }],
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

    fireEvent.click(await screen.findByRole("button", { name: "Utilities" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open" }));

    expect(await screen.findByText(/Opened snapshot #77\./i)).toBeInTheDocument();
    expect(screen.getByText("This snapshot is currently generation-ready.")).toBeInTheDocument();
    const openGenerateButtons = screen.getAllByRole("button", { name: /generate/i });
    expect(openGenerateButtons.length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Open Generate" }));

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

    const fileInput = screen.getAllByLabelText("Import CSV")[0];
    const file = new File(["CoursePathNo,CourseCode\n1,CHEM 11612\n"], "student_enrollments.csv", {
      type: "text/csv",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze Import" }));

    expect(await screen.findByText(/CSV Year 2 does not match nominal module year 1\./i)).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "accept_exception" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Review Import" }));

    expect(await screen.findByText(/Review result:/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Use This Import" }));

      await waitFor(() => {
        expect(timetableStudioService.previewEnrollmentImport).toHaveBeenCalledWith(
          {
            rules: [
              expect.objectContaining({
                bucket_type: "year_code_mismatch",
                bucket_key: "year=2|nominal_year=1",
                action: "accept_exception",
              }),
            ],
          },
          file
        );
      expect(timetableStudioService.materializeEnrollmentImport).toHaveBeenCalledTimes(1);
      expect(timetableStudioService.materializeEnrollmentImport).toHaveBeenCalledWith(
        {
          rules: [
            expect.objectContaining({
              bucket_type: "year_code_mismatch",
              bucket_key: "year=2|nominal_year=1",
              action: "accept_exception",
            }),
          ],
        },
        file
      );
      expect(timetableStudioService.analyzeEnrollmentImport).toHaveBeenCalledWith(file);
      expect(timetableStudioService.getImportWorkspace).toHaveBeenCalledWith(88);
    });
    expect(
      await screen.findByText(/The CSV import has been materialized into snapshot #88\./i)
    ).toBeInTheDocument();
  });

  it("opens a targeted repair flow for sessions missing lecturer links", async () => {
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
    timetableStudioService.getImportWorkspace.mockResolvedValueOnce({
      ...emptyWorkspace(),
      import_run_id: 77,
      lecturers: [{ id: 10, name: "Dr Silva", email: "silva@example.com", notes: null }],
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
          lecturer_ids: [],
          curriculum_module_ids: [40],
          attendance_group_ids: [30],
        },
      ],
      readiness: {
        ready: false,
        import_needed: [],
        repair_needed: [
          {
            key: "sessions-missing-lecturers",
            title: "Sessions missing lecturers",
            detail: "1 session still need lecturers.",
            action: "Repair lecturers",
            form: "lecturer",
          },
        ],
        warnings: [],
      },
    });
    timetableStudioService.getImportWorkspace.mockResolvedValueOnce({
      ...emptyWorkspace(),
      import_run_id: 77,
      lecturers: [{ id: 10, name: "Dr Silva", email: "silva@example.com", notes: null }],
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
      readiness: { ready: true, import_needed: [], repair_needed: [], warnings: [] },
    });

    renderSetupStudio();

    fireEvent.click(await screen.findByRole("button", { name: "Utilities" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open" }));
    fireEvent.click(await screen.findByRole("button", { name: "Repair Session" }));

    expect(await screen.findByText(/Repairing shared session: Chemistry Lecture\./i)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Dr Silva"));
    fireEvent.click(screen.getByRole("button", { name: "Save Shared Session Repair" }));

    await waitFor(() => {
      expect(timetableStudioService.updateSnapshotSharedSession).toHaveBeenCalledWith(
        77,
        50,
        expect.objectContaining({
          name: "Chemistry Lecture",
          lecturer_ids: [10],
          curriculum_module_ids: [40],
          attendance_group_ids: [30],
        })
      );
    });
    expect(await screen.findByText(/Shared session repaired in the current snapshot\./i)).toBeInTheDocument();
  });

  it("lists room-related session blockers in the targeted repair queue", async () => {
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
    timetableStudioService.getImportWorkspace.mockResolvedValue({
      ...emptyWorkspace(),
      import_run_id: 77,
      lecturers: [{ id: 10, name: "Dr Silva", email: "silva@example.com", notes: null }],
      rooms: [
        {
          id: 20,
          name: "Tiny Lab",
          capacity: 20,
          room_type: "lab",
          lab_type: "chemistry",
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
          name: "Chemistry Practical",
          session_type: "lab",
          duration_minutes: 180,
          occurrences_per_week: 1,
          required_room_type: "lab",
          required_lab_type: "chemistry",
          specific_room_id: 20,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_ids: [10],
          curriculum_module_ids: [40],
          attendance_group_ids: [30],
        },
      ],
      readiness: {
        ready: false,
        import_needed: [],
        repair_needed: [
          {
            key: "room-capacity-50",
            title: "Specific room capacity is too small",
            detail: "Chemistry Practical has no room that can host it in required room Tiny Lab.",
            action: "Repair sessions",
            form: "session",
          },
        ],
        warnings: [],
      },
    });

    renderSetupStudio();

    fireEvent.click(await screen.findByRole("button", { name: "Utilities" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open" }));

    expect(await screen.findByText("Chemistry Practical")).toBeInTheDocument();
    expect(screen.getByText(/Missing room assignment\./i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Repair Session" })).toBeInTheDocument();
  });
});
