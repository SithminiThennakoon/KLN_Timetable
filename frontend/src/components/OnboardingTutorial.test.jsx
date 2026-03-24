import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import OnboardingTutorial from "./OnboardingTutorial";

describe("OnboardingTutorial", () => {
  it("describes the simplified three-page flow", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    expect(screen.getByText(/guided path from enrolments to timetable/i)).toBeInTheDocument();
    expect(screen.getByText(/start demo with sample data/i)).toBeInTheDocument();
    expect(screen.getByText(/generate timetable/i)).toBeInTheDocument();
    expect(screen.getByText(/views/i)).toBeInTheDocument();
  });

  it("explains that setup starts from the CSV-first flow", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Go to step 2" }));

    expect(
      screen.getByText(/setup now starts with the student-enrolment csv/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/you do not need to build the full faculty structure manually/i)
    ).toBeInTheDocument();
  });

  it("keeps keyboard focus inside the modal when tabbing", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    const closeButton = screen.getByRole("button", { name: /close tutorial/i });
    closeButton.focus();
    fireEvent.keyDown(document, { key: "Tab" });

    expect(document.activeElement).not.toBe(document.body);
  });
});
