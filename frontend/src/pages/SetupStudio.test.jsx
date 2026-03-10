import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SetupStudio from "./SetupStudio";
import { timetableStudioService } from "../services/timetableStudioService";

vi.mock("../services/timetableStudioService", () => ({
  timetableStudioService: {
    getFullDataset: vi.fn(),
    saveDataset: vi.fn(),
    loadDemoDataset: vi.fn(),
  },
}));

function emptyDataset() {
  return {
    degrees: [],
    paths: [],
    lecturers: [],
    rooms: [],
    student_groups: [],
    modules: [],
    sessions: [],
  };
}

describe("SetupStudio", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows operator guidance for the active setup step", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue(emptyDataset());

    render(<SetupStudio />);

    expect(
      await screen.findByText(/Start by defining each degree and any allowed year-specific paths/i)
    ).toBeInTheDocument();
  });

  it("shows current step checks before the review step", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue(emptyDataset());

    render(<SetupStudio />);

    expect(await screen.findByText("Current Step Checks")).toBeInTheDocument();
    expect(screen.getByText(/Add at least one degree before continuing/i)).toBeInTheDocument();
  });

  it("adds lecturer templates without duplicating existing names", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      lecturers: [
        {
          client_key: "lect_existing",
          name: "Dr. Perera",
          email: "existing@science.kln.ac.lk",
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "2. Lecturers" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Lecturer Templates" }));

    expect(screen.getAllByDisplayValue("Dr. Perera")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Dr. Silva")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Prof. Fernando")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Ms. Jayasinghe")).toHaveLength(1);
  });

  it("shows inline validation for invalid room capacity on the rooms step", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "3. Rooms" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Room" }));

    const roomEditor = screen.getByText("Capacity").closest("label");
    const capacityInput = within(roomEditor).getByRole("spinbutton");
    fireEvent.change(capacityInput, { target: { value: "0" } });
    fireEvent.blur(capacityInput);

    expect(await screen.findAllByText(/Room 1 needs a positive capacity/i)).not.toHaveLength(0);
    expect(capacityInput.className).toContain("field-invalid");
  });

  it("adds room template batches without duplicating existing template rooms", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_existing",
          name: "A7 Hall 1",
          capacity: 180,
          room_type: "lecture",
          lab_type: null,
          location: "A7 Building",
          year_restriction: null,
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "3. Rooms" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Lecture Hall Templates" }));
    fireEvent.click(screen.getByRole("button", { name: "Add Lab Templates" }));

    expect(screen.getAllByDisplayValue("A7 Hall 1")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("A7 Hall 2")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Physics Lab 1")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Chemistry Lab 1")).toHaveLength(1);
  });

  it("shows inline validation for incomplete degree details on the structure step", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "",
        },
      ],
    });

    render(<SetupStudio />);

    const codeLabel = (await screen.findByText("Code")).closest("label");
    const codeInput = within(codeLabel).getByRole("textbox");
    fireEvent.blur(codeInput);

    expect(await screen.findAllByText(/Degree 1 is missing code, name, or intake label/i)).not.toHaveLength(0);
    expect(codeInput.className).toContain("field-invalid");
  });

  it("loads science structure templates without duplicating existing degree codes", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 3,
          intake_label: "Existing PS Intake",
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "Load Science Structure Templates" }));

    const degreesSection = screen.getByText("Degrees").closest("section");
    const pathsSection = screen.getByText("Paths").closest("section");

    expect(within(degreesSection).getAllByDisplayValue("PS")).toHaveLength(1);
    expect(within(degreesSection).getAllByDisplayValue("BS")).toHaveLength(1);
    expect(within(degreesSection).getAllByDisplayValue("ENCM")).toHaveLength(1);
    expect(within(degreesSection).getAllByDisplayValue("AC")).toHaveLength(1);
    expect(within(degreesSection).getAllByDisplayValue("ECS")).toHaveLength(1);
    expect(within(degreesSection).getAllByDisplayValue("PE")).toHaveLength(1);
    expect(within(pathsSection).getAllByDisplayValue("PHY-CHEM-MATH")).toHaveLength(1);
  });

  it("shows inline validation for incomplete session identity on the sessions step", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "CHEM101",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "",
          session_type: "",
          duration_minutes: 60,
          occurrences_per_week: 1,
          required_room_type: "lecture",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: [],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));

    expect(await screen.findAllByText(/Session 1 is missing module, name, or type/i)).not.toHaveLength(0);
    const sessionNameLabel = screen.getByText("Name").closest("label");
    const sessionNameInput = within(sessionNameLabel).getByRole("textbox");
    fireEvent.blur(sessionNameInput);
    expect(sessionNameInput.className).toContain("field-invalid");
  });

  it("shows inline validation for invalid override groups on the cohorts step", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      student_groups: [
        {
          client_key: "group_base",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
        {
          client_key: "group_override",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "",
          size: 0,
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "4. Student Cohorts" }));

    expect(await screen.findAllByText(/Override group 1 is missing degree or name/i)).not.toHaveLength(0);
    expect(await screen.findAllByText(/Override group 1 needs a positive student count/i)).not.toHaveLength(0);

    const overrideNameLabel = screen.getByText("Override group name").closest("label");
    const overrideNameInput = within(overrideNameLabel).getByRole("textbox");
    fireEvent.blur(overrideNameInput);
    expect(overrideNameInput.className).toContain("field-invalid");
  });

  it("shows lab duration validation that matches the solver", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_lab_1",
          name: "Physics Lab 1",
          capacity: 40,
          room_type: "lab",
          lab_type: "physics",
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 30,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "PHYS101",
          name: "Physics Laboratory",
          subject_name: "Physics",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Physics Lab",
          session_type: "lab",
          duration_minutes: 120,
          occurrences_per_week: 1,
          required_room_type: "lab",
          required_lab_type: "physics",
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: ["group_main"],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));

    expect(await screen.findAllByText(/Session 1 is treated as a lab and must be 180 minutes/i)).not.toHaveLength(0);
  });

  it("matches the backend occurrence cap on the sessions step", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "CHEM101",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Chemistry Lecture",
          session_type: "lecture",
          duration_minutes: 60,
          occurrences_per_week: 11,
          required_room_type: "lecture",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: ["group_main"],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));

    expect(await screen.findAllByText(/Session 1 weekly occurrence count must be between 1 and 10/i)).not.toHaveLength(0);
  });

  it("makes it explicit that room year restriction is not enforced by the solver", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: 1,
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "3. Rooms" }));

    expect(
      await screen.findAllByText(/stored with the dataset, but not currently enforced during timetable generation/i)
    ).not.toHaveLength(0);
  });

  it("warns when a lab session has no lab type", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_lab_1",
          name: "Physics Lab 1",
          capacity: 40,
          room_type: "lab",
          lab_type: "physics",
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 30,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "PHYS101",
          name: "Physics Laboratory",
          subject_name: "Physics",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Physics Lab",
          session_type: "lab",
          duration_minutes: 180,
          occurrences_per_week: 1,
          required_room_type: "lab",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: ["group_main"],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));

    expect(
      await screen.findAllByText(/uses room type lab but has no lab type, so it may match the wrong lab pool/i)
    ).not.toHaveLength(0);
  });

  it("blocks sessions that pin a room with mismatched room type", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "CHEM101",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Chemistry Lab",
          session_type: "lab",
          duration_minutes: 180,
          occurrences_per_week: 1,
          required_room_type: "lab",
          required_lab_type: "chemistry",
          specific_room_client_key: "room_1",
          max_students_per_group: 40,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: ["group_main"],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));

    expect(
      await screen.findAllByText(/pins room "Room 1" but its room type does not match the selected requirement/i)
    ).not.toHaveLength(0);
  });

  it("blocks sessions that exceed every matching room capacity without a split limit", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_lab_1",
          name: "Physics Lab 1",
          capacity: 25,
          room_type: "lab",
          lab_type: "physics",
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 30,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "PHYS101",
          name: "Physics Laboratory",
          subject_name: "Physics",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Physics Lab",
          session_type: "lab",
          duration_minutes: 180,
          occurrences_per_week: 1,
          required_room_type: "lab",
          required_lab_type: "physics",
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: ["group_main"],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));

    expect(
      await screen.findAllByText(/exceeds every matching room capacity for 30 students, so add a split limit or expand the room pool/i)
    ).not.toHaveLength(0);
  });

  it("duplicates a session with its key settings and links", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
      lecturers: [
        {
          client_key: "lect_1",
          name: "Lecturer 1",
          email: "lect1@example.com",
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "CHEM101",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Chemistry Lecture",
          session_type: "lecture",
          duration_minutes: 60,
          occurrences_per_week: 1,
          required_room_type: "lecture",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: ["lect_1"],
          student_group_client_keys: ["group_main"],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));
    fireEvent.click(screen.getByRole("button", { name: "Duplicate Session" }));

    expect(screen.getAllByDisplayValue("Chemistry Lecture")).toHaveLength(2);
    expect(screen.getAllByDisplayValue("60")).toHaveLength(2);
    expect(screen.getAllByLabelText("Type").map((element) => element.value)).toEqual(["lecture", "lecture"]);
    expect(screen.getAllByText("Lecturer 1")).not.toHaveLength(0);
    expect(screen.getAllByText("PS Y1 General")).not.toHaveLength(0);
  });

  it("creates override templates from existing base cohorts", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      student_groups: [
        {
          client_key: "group_base",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "4. Student Cohorts" }));
    fireEvent.click(screen.getByRole("button", { name: "Create Override Templates" }));

    expect(screen.getAllByDisplayValue("PS Y1 General Override")).toHaveLength(1);
    expect(screen.getAllByText("PS").length).toBeGreaterThan(0);
  });

  it("creates starter sessions only for modules that do not already have one", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "CHEM101",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
        {
          client_key: "mod_2",
          code: "PHYS101",
          name: "Mechanics",
          subject_name: "Physics",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Chemistry Lecture",
          session_type: "lecture",
          duration_minutes: 60,
          occurrences_per_week: 1,
          required_room_type: "lecture",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: [],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));
    fireEvent.click(screen.getByRole("button", { name: "Create Starter Sessions" }));

    expect(screen.getAllByDisplayValue("Chemistry Lecture")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Mechanics Session")).toHaveLength(1);
  });

  it("creates a lecture and tutorial set only for modules without existing sessions", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "CHEM101",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
        {
          client_key: "mod_2",
          code: "PHYS101",
          name: "Mechanics",
          subject_name: "Physics",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Foundations of Chemistry Lecture",
          session_type: "lecture",
          duration_minutes: 120,
          occurrences_per_week: 1,
          required_room_type: "lecture",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: [],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));
    fireEvent.click(screen.getByRole("button", { name: "Create Lecture + Tutorial Set" }));

    expect(screen.getAllByDisplayValue("Foundations of Chemistry Lecture")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Mechanics Lecture")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("Mechanics Tutorial")).toHaveLength(1);
    expect(screen.getAllByLabelText("Type").map((element) => element.value)).toEqual([
      "lecture",
      "lecture",
      "tutorial",
    ]);
  });

  it("creates semester module shells only for uncovered year-semester combinations", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 2,
          intake_label: "PS Intake",
        },
      ],
      student_groups: [
        {
          client_key: "group_y1",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
        {
          client_key: "group_y2",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 2,
          name: "PS Y2 General",
          size: 75,
        },
      ],
      modules: [
        {
          client_key: "mod_existing",
          code: "PS1101",
          name: "Existing Year 1 Sem 1",
          subject_name: "Physical Science Year 1",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "5. Modules" }));
    fireEvent.click(screen.getByRole("button", { name: "Create Semester 1 Module Shells" }));

    expect(screen.getAllByDisplayValue("Existing Year 1 Sem 1")).toHaveLength(1);
    expect(screen.getAllByDisplayValue("PS Year 2 Semester 1 Module")).toHaveLength(1);
    expect(screen.queryByDisplayValue("PS Year 1 Semester 1 Module")).not.toBeInTheDocument();
  });

  it("copies lecturers and cohorts across a module's session set", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 1,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "Room 1",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "Science Block",
          year_restriction: null,
        },
      ],
      student_groups: [
        {
          client_key: "group_main",
          degree_client_key: "degree_ps",
          path_client_key: null,
          year: 1,
          name: "PS Y1 General",
          size: 80,
        },
      ],
      lecturers: [
        {
          client_key: "lect_1",
          name: "Lecturer 1",
          email: "lect1@example.com",
        },
      ],
      modules: [
        {
          client_key: "mod_1",
          code: "CHEM101",
          name: "Foundations of Chemistry",
          subject_name: "Chemistry",
          year: 1,
          semester: 1,
          is_full_year: false,
        },
      ],
      sessions: [
        {
          client_key: "sess_1",
          module_client_key: "mod_1",
          name: "Foundations of Chemistry Lecture",
          session_type: "lecture",
          duration_minutes: 120,
          occurrences_per_week: 1,
          required_room_type: "lecture",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: ["lect_1"],
          student_group_client_keys: ["group_main"],
        },
        {
          client_key: "sess_2",
          module_client_key: "mod_1",
          name: "Foundations of Chemistry Tutorial",
          session_type: "tutorial",
          duration_minutes: 60,
          occurrences_per_week: 1,
          required_room_type: "seminar",
          required_lab_type: null,
          specific_room_client_key: null,
          max_students_per_group: null,
          allow_parallel_rooms: false,
          notes: null,
          lecturer_client_keys: [],
          student_group_client_keys: [],
        },
      ],
    });

    render(<SetupStudio />);

    await screen.findByDisplayValue("PS");
    fireEvent.click(screen.getByRole("button", { name: "6. Sessions" }));

    const lectureCard = screen
      .getByDisplayValue("Foundations of Chemistry Lecture")
      .closest(".editor-card");
    const tutorialCard = screen
      .getByDisplayValue("Foundations of Chemistry Tutorial")
      .closest(".editor-card");

    fireEvent.click(
      within(lectureCard).getByRole("button", { name: "Copy Lecturers + Cohorts To Module Set" })
    );
    // Two-step confirm: click the "Overwrite" button that appears in the confirm strip
    fireEvent.click(
      within(lectureCard).getByRole("button", { name: "Overwrite" })
    );

    expect(within(tutorialCard).getByRole("checkbox", { name: "Lecturer 1" })).toBeChecked();
    expect(within(tutorialCard).getByRole("checkbox", { name: "PS Y1 General" })).toBeChecked();
  });

  it("hydrates the wizard from the saved full dataset summary", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue({
      ...emptyDataset(),
      degrees: [
        {
          client_key: "degree_ps",
          code: "PS",
          name: "Physical Science",
          duration_years: 3,
          intake_label: "PS Intake",
        },
      ],
      rooms: [
        {
          client_key: "room_1",
          name: "A7 301",
          capacity: 120,
          room_type: "lecture",
          lab_type: null,
          location: "A7 Building",
          year_restriction: null,
        },
      ],
    });

    render(<SetupStudio />);

    expect(await screen.findByDisplayValue("PS")).toBeInTheDocument();
    const summaryCards = screen.getAllByText("1");
    expect(summaryCards.length).toBeGreaterThan(0);
    expect(screen.getByText("degrees")).toBeInTheDocument();
    expect(screen.getByText("rooms")).toBeInTheDocument();
  });

  it("derives base cohorts from degree and path structure", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue(emptyDataset());

    render(<SetupStudio />);
    await screen.findByText("No degrees added yet.");

    fireEvent.click(screen.getByRole("button", { name: "Add Degree" }));
    const degreeCodeInput = within(screen.getByText("Code").closest("label")).getByRole("textbox");
    const degreeNameInput = within(screen.getByText("Name").closest("label")).getByRole("textbox");
    const degreeDurationInput = within(screen.getByText("Duration").closest("label")).getByRole("spinbutton");
    const intakeLabelInput = within(screen.getByText("Intake label").closest("label")).getByRole("textbox");
    fireEvent.change(degreeCodeInput, { target: { value: "PS" } });
    fireEvent.change(degreeNameInput, { target: { value: "Physical Science" } });
    fireEvent.change(degreeDurationInput, { target: { value: "1" } });
    fireEvent.change(intakeLabelInput, { target: { value: "PS Intake" } });

    fireEvent.click(screen.getByRole("button", { name: "Add Path" }));
    const pathSection = screen.getByText("Paths").closest("section");
    const pathDegreeLabel = within(pathSection).getByText("Degree").closest("label");
    const degreeSelect = within(pathDegreeLabel).getByRole("combobox");
    const degreeOption = within(pathSection).getAllByRole("option").find((option) => option.textContent === "PS");
    fireEvent.change(degreeSelect, {
      target: { value: degreeOption.value },
    });
    fireEvent.change(within(within(pathSection).getByText("Code").closest("label")).getByRole("textbox"), {
      target: { value: "PHY-MATH-STAT" },
    });
    fireEvent.change(within(within(pathSection).getByText("Name").closest("label")).getByRole("textbox"), {
      target: { value: "Physics Mathematics Statistics" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    const baseCohortsSection = (await screen.findByText("Base Cohorts")).closest("section");
    expect(within(baseCohortsSection).getAllByText("PS").length).toBeGreaterThan(0);
    expect(within(baseCohortsSection).getAllByText(/Year 1/).length).toBeGreaterThan(0);
    expect(within(baseCohortsSection).getByText("PHY-MATH-STAT")).toBeInTheDocument();
  });

  it("shows blocking review validation when required setup data is missing", async () => {
    timetableStudioService.getFullDataset.mockResolvedValue(emptyDataset());

    render(<SetupStudio />);
    await screen.findByText("No degrees added yet.");

    fireEvent.click(screen.getByRole("button", { name: "7. Review & Save" }));

    expect(await screen.findByText("Readiness Review")).toBeInTheDocument();
    expect(screen.getByText(/Add at least one degree before continuing/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Dataset" })).toBeDisabled();
  });

  it("saves a transformed v2 dataset payload from the wizard draft", async () => {
    timetableStudioService.getFullDataset
      .mockResolvedValueOnce({
        ...emptyDataset(),
        degrees: [
          {
            client_key: "degree_ps",
            code: "PS",
            name: "Physical Science",
            duration_years: 1,
            intake_label: "PS Intake",
          },
        ],
        rooms: [
          {
            client_key: "room_1",
            name: "Room 1",
            capacity: 120,
            room_type: "lecture",
            lab_type: null,
            location: "Science Block",
            year_restriction: null,
          },
        ],
        student_groups: [
          {
            client_key: "group_main",
            degree_client_key: "degree_ps",
            path_client_key: null,
            year: 1,
            name: "PS Y1 General",
            size: 80,
          },
        ],
        lecturers: [
          {
            client_key: "lect_1",
            name: "Lecturer 1",
            email: "lect1@example.com",
          },
        ],
        modules: [
          {
            client_key: "mod_1",
            code: "CHEM101",
            name: "Foundations of Chemistry",
            subject_name: "Chemistry",
            year: 1,
            semester: 1,
            is_full_year: false,
          },
        ],
        sessions: [
          {
            client_key: "sess_1",
            module_client_key: "mod_1",
            name: "Chemistry Lecture",
            session_type: "lecture",
            duration_minutes: 60,
            occurrences_per_week: 1,
            required_room_type: "lecture",
            required_lab_type: null,
            specific_room_client_key: null,
            max_students_per_group: null,
            allow_parallel_rooms: false,
            notes: null,
            lecturer_client_keys: ["lect_1"],
            student_group_client_keys: ["group_main"],
          },
        ],
        paths: [],
      })
      .mockResolvedValueOnce({
        ...emptyDataset(),
        degrees: [
          {
            client_key: "degree_saved",
            code: "PS",
            name: "Physical Science",
            duration_years: 1,
            intake_label: "PS Intake",
          },
        ],
        rooms: [
          {
            client_key: "room_saved",
            name: "Room 1",
            capacity: 120,
            room_type: "lecture",
            lab_type: null,
            location: "Science Block",
            year_restriction: null,
          },
        ],
        student_groups: [
          {
            client_key: "group_saved",
            degree_client_key: "degree_saved",
            path_client_key: null,
            year: 1,
            name: "PS Y1 General",
            size: 80,
          },
        ],
        lecturers: [
          {
            client_key: "lect_saved",
            name: "Lecturer 1",
            email: "lect1@example.com",
          },
        ],
        modules: [
          {
            client_key: "mod_saved",
            code: "CHEM101",
            name: "Foundations of Chemistry",
            subject_name: "Chemistry",
            year: 1,
            semester: 1,
            is_full_year: false,
          },
        ],
        sessions: [
          {
            client_key: "sess_saved",
            module_client_key: "mod_saved",
            name: "Chemistry Lecture",
            session_type: "lecture",
            duration_minutes: 60,
            occurrences_per_week: 1,
            required_room_type: "lecture",
            required_lab_type: null,
            specific_room_client_key: null,
            max_students_per_group: null,
            allow_parallel_rooms: false,
            notes: null,
            lecturer_client_keys: ["lect_saved"],
            student_group_client_keys: ["group_saved"],
          },
        ],
        paths: [],
      });
    timetableStudioService.saveDataset.mockResolvedValue({
      summary: {
        degrees: 1,
        paths: 0,
        lecturers: 1,
        rooms: 1,
        student_groups: 1,
        modules: 1,
        sessions: 1,
      },
    });

    render(<SetupStudio />);

    expect(await screen.findByDisplayValue("PS")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save Dataset" }));

    await waitFor(() => expect(timetableStudioService.saveDataset).toHaveBeenCalledTimes(1));

    const savedPayload = timetableStudioService.saveDataset.mock.calls[0][0];
    expect(savedPayload.degrees).toHaveLength(1);
    expect(savedPayload.student_groups).toHaveLength(1);
    expect(savedPayload.modules).toHaveLength(1);
    expect(savedPayload.sessions).toHaveLength(1);
    expect(savedPayload.sessions[0]).toMatchObject({
      name: "Chemistry Lecture",
      duration_minutes: 60,
      occurrences_per_week: 1,
      required_room_type: "lecture",
    });
    expect(savedPayload.sessions[0].lecturer_client_keys).toHaveLength(1);
    expect(savedPayload.sessions[0].student_group_client_keys).toHaveLength(1);
    expect(await screen.findByText(/Dataset saved\. The new setup flow is now ready for generation/i)).toBeInTheDocument();
  });
});
