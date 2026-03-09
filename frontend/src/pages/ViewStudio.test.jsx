import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ViewStudio from "./ViewStudio";
import { timetableStudioService } from "../services/timetableStudioService";

const writeFileMock = vi.fn();
const saveMock = vi.fn();
const bookNewMock = vi.fn(() => ({}));
const jsonToSheetMock = vi.fn(() => ({}));
const appendSheetMock = vi.fn();
const pdfInstances = [];
const autoTableMock = vi.fn(function autoTable() {
  this.lastAutoTable = { finalY: 140 };
});

vi.mock("xlsx", () => ({
  utils: {
    book_new: bookNewMock,
    json_to_sheet: jsonToSheetMock,
    book_append_sheet: appendSheetMock,
  },
  writeFile: writeFileMock,
}));

function MockJsPDF() {
  this.setFontSize = vi.fn();
  this.text = vi.fn();
  this.autoTable = autoTableMock;
  this.save = saveMock;
  this.lastAutoTable = { finalY: 140 };
  pdfInstances.push(this);
}

vi.mock("jspdf", () => ({
  default: MockJsPDF,
}));

vi.mock("jspdf-autotable", () => ({}));

vi.mock("../services/timetableStudioService", () => ({
  timetableStudioService: {
    getLookups: vi.fn(),
    view: vi.fn(),
    exportView: vi.fn(),
  },
}));

function buildViewResponse(overrides = {}) {
  return {
    mode: "admin",
    title: "Faculty Timetable",
    subtitle: "Default faculty timetable with all session details.",
    solution: {
      entries: [
        {
          session_id: 1,
          module_code: "CHEM101",
          module_name: "Foundations of Chemistry",
          session_name: "Chemistry Lab",
          room_name: "Lab 1",
          room_location: "Science Block",
          lecturer_names: ["Lecturer 1"],
          student_group_names: ["PS Y1 Main"],
          degree_path_labels: ["PS Year 1 - PHY-MATH-STAT"],
          total_students: 50,
          day: "Monday",
          start_minute: 480,
          duration_minutes: 60,
        },
      ],
    },
    ...overrides,
  };
}

describe("ViewStudio", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
    writeFileMock.mockReset();
    saveMock.mockReset();
    bookNewMock.mockClear();
    jsonToSheetMock.mockClear();
    appendSheetMock.mockClear();
    autoTableMock.mockClear();
    pdfInstances.length = 0;
    global.URL.createObjectURL = vi.fn(() => "blob:mock");
    global.URL.revokeObjectURL = vi.fn();
    global.Blob = class MockBlob {
      constructor(parts, options = {}) {
        this.parts = parts;
        this.type = options.type;
      }
    };
    global.atob = vi.fn(() => "csv");

    const realCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName) => {
      if (tagName === "a") {
        return { click: vi.fn(), href: "", download: "" };
      }
      if (tagName === "canvas") {
        return {
          width: 0,
          height: 0,
          getContext: vi.fn(() => ({
            fillStyle: "",
            strokeStyle: "",
            font: "",
            fillRect: vi.fn(),
            strokeRect: vi.fn(),
            fillText: vi.fn(),
          })),
          toBlob: (callback) => callback(new Blob(["png"], { type: "image/png" })),
        };
      }
      return realCreateElement(tagName);
    });
  });

  it("requires degree and path selection before applying student view filters", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [{ id: 1, label: "Lecturer 1" }],
      degrees: [{ id: 10, label: "PS - Physical Science" }],
      student_paths: [{ id: 100, degree_id: 10, year: 1, label: "Year 1 - PHY-MATH-STAT" }],
    });
    timetableStudioService.view.mockResolvedValue(buildViewResponse());

    render(<ViewStudio />);

    expect(await screen.findByText("Faculty Timetable")).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("Admin View"), {
      target: { value: "student" },
    });

    expect(await screen.findByText("Select a degree and path")).toBeInTheDocument();

    const applyButton = screen.getByRole("button", { name: "Apply" });
    expect(applyButton).toBeDisabled();

    fireEvent.change(screen.getByDisplayValue("Select Degree"), {
      target: { value: "10" },
    });
    expect(applyButton).toBeDisabled();

    fireEvent.change(screen.getByDisplayValue("Select Path"), {
      target: { value: "100" },
    });
    expect(applyButton).not.toBeDisabled();
  });

  it("sends degree and path ids when applying student view filters", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [],
      degrees: [{ id: 10, label: "PS - Physical Science" }],
      student_paths: [{ id: 100, degree_id: 10, year: 1, label: "Year 1 - PHY-MATH-STAT" }],
    });
    timetableStudioService.view
      .mockResolvedValueOnce(buildViewResponse())
      .mockResolvedValueOnce(
        buildViewResponse({
          mode: "student",
          title: "Student Timetable - PS - PHY-MATH-STAT",
          subtitle: "Sessions attended by the selected degree and path.",
        })
      );

    render(<ViewStudio />);

    await screen.findByText("Faculty Timetable");

    fireEvent.change(screen.getByDisplayValue("Admin View"), {
      target: { value: "student" },
    });
    fireEvent.change(screen.getByDisplayValue("Select Degree"), {
      target: { value: "10" },
    });
    fireEvent.change(screen.getByDisplayValue("Select Path"), {
      target: { value: "100" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(timetableStudioService.view).toHaveBeenLastCalledWith({
        mode: "student",
        lecturerId: undefined,
        degreeId: "10",
        pathId: "100",
      })
    );
  });

  it("shows admin empty state when no default timetable exists yet", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [],
      degrees: [],
      student_paths: [],
    });
    timetableStudioService.view.mockRejectedValue(new Error("No default solution selected"));

    render(<ViewStudio />);

    expect(await screen.findByText("No default timetable available")).toBeInTheDocument();
    expect(
      screen.getByText(/Generate timetable solutions in the Generate page and mark one as the default timetable/i)
    ).toBeInTheDocument();
  });

  it("uses backend export only for csv", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [],
      degrees: [],
      student_paths: [],
    });
    timetableStudioService.view.mockResolvedValue(buildViewResponse());
    timetableStudioService.exportView.mockResolvedValue({
      filename: "admin-timetable.csv",
      content_type: "text/csv",
      content: "Y3N2",
    });

    render(<ViewStudio />);

    await screen.findByText("Faculty Timetable");
    fireEvent.click(screen.getByRole("button", { name: "CSV" }));

    await waitFor(() =>
      expect(timetableStudioService.exportView).toHaveBeenCalledWith({
        mode: "admin",
        format: "csv",
        lecturerId: undefined,
        degreeId: undefined,
        pathId: undefined,
      })
    );
    expect(writeFileMock).not.toHaveBeenCalled();
    expect(saveMock).not.toHaveBeenCalled();
  });

  it("exports xlsx locally without calling backend export", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [],
      degrees: [],
      student_paths: [],
    });
    timetableStudioService.view.mockResolvedValue(buildViewResponse());

    render(<ViewStudio />);

    await screen.findByText("Faculty Timetable");
    fireEvent.click(screen.getByRole("button", { name: "XLSX" }));

    await waitFor(() => expect(writeFileMock).toHaveBeenCalled());
    expect(writeFileMock).toHaveBeenCalledWith(expect.any(Object), "admin-timetable.xlsx");
    expect(bookNewMock).toHaveBeenCalledTimes(1);
    expect(jsonToSheetMock).toHaveBeenCalledTimes(3);
    expect(appendSheetMock).toHaveBeenNthCalledWith(1, expect.any(Object), expect.any(Object), "Summary");
    expect(appendSheetMock).toHaveBeenNthCalledWith(2, expect.any(Object), expect.any(Object), "Timetable");
    expect(appendSheetMock).toHaveBeenNthCalledWith(3, expect.any(Object), expect.any(Object), "Session Details");

    const detailRows = jsonToSheetMock.mock.calls[1][0];
    expect(detailRows[0]).toMatchObject({
      Day: "Monday",
      Start: "08:00",
      ModuleCode: "CHEM101",
      Session: "Chemistry Lab",
      Students: 50,
    });
    expect(timetableStudioService.exportView).not.toHaveBeenCalled();
  });

  it("exports pdf locally without calling backend export", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [],
      degrees: [],
      student_paths: [],
    });
    timetableStudioService.view.mockResolvedValue(buildViewResponse());

    render(<ViewStudio />);

    await screen.findByText("Faculty Timetable");
    fireEvent.click(screen.getByRole("button", { name: "PDF" }));

    await waitFor(() => expect(saveMock).toHaveBeenCalledWith("admin-timetable.pdf"));
    expect(pdfInstances).toHaveLength(1);
    expect(pdfInstances[0].text).toHaveBeenCalledWith("Faculty Timetable", 40, 36);
    expect(pdfInstances[0].text).toHaveBeenCalledWith(
      "Default faculty timetable with all session details.",
      40,
      54
    );
    expect(autoTableMock).toHaveBeenCalledTimes(2);
    expect(timetableStudioService.exportView).not.toHaveBeenCalled();
  });

  it("exports png locally without calling backend export", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [],
      degrees: [],
      student_paths: [],
    });
    timetableStudioService.view.mockResolvedValue(buildViewResponse());

    render(<ViewStudio />);

    await screen.findByText("Faculty Timetable");
    fireEvent.click(screen.getByRole("button", { name: "PNG" }));

    await waitFor(() => expect(global.URL.createObjectURL).toHaveBeenCalled());
    expect(timetableStudioService.exportView).not.toHaveBeenCalled();
  });

  it("defaults to agenda and supports focused calendar mode", async () => {
    timetableStudioService.getLookups.mockResolvedValue({
      lecturers: [],
      degrees: [],
      student_paths: [],
    });
    timetableStudioService.view.mockResolvedValue(
      buildViewResponse({
        solution: {
          entries: [
            {
              session_id: 1,
              module_code: "CHEM101",
              module_name: "Foundations of Chemistry",
              session_name: "Chemistry Lecture",
              room_name: "A11 201",
              room_location: "Science Block",
              lecturer_names: ["Lecturer 1"],
              student_group_names: ["PS Y1 Main"],
              degree_path_labels: ["PS Year 1 - PHY-MATH-STAT"],
              total_students: 50,
              day: "Monday",
              start_minute: 480,
              duration_minutes: 180,
            },
          ],
        },
      })
    );

    render(<ViewStudio />);

    expect(await screen.findByRole("button", { name: "Agenda" })).toBeInTheDocument();
    expect(screen.getByText("Session Details")).toBeInTheDocument();
    expect(screen.queryByText("Session Detail List")).not.toBeInTheDocument();
    expect(screen.getByText("Monday")).toBeInTheDocument();
    expect(screen.getByText("A11 201 | Lecturer 1")).toBeInTheDocument();
    expect(document.querySelector(".agenda-entry.selected-entry")).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Calendar" }));

    const card = await screen.findByTitle(/CHEM101 Chemistry Lecture/i);
    expect(card.className).toContain("selected-entry");
    expect(card).toHaveStyle({ height: "179px" });
    fireEvent.click(card);
    expect(card.className).toContain("selected-entry");
    expect(screen.getByText("Monday 08:00 for 180 minutes")).toBeInTheDocument();
  });
});
