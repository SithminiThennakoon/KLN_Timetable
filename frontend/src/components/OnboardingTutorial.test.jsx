import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import OnboardingTutorial from "./OnboardingTutorial";

describe("OnboardingTutorial", () => {
  it("states that setup changes are saved only when Save Dataset is clicked", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    expect(
      screen.getByText(/your setup changes are only persisted when you click/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Save Dataset")).toBeInTheDocument();
    expect(screen.getByText(/\?/)).toBeInTheDocument();
    expect(screen.getByText(/help icon in the top navigation bar/i)).toBeInTheDocument();
    expect(
      screen.getByText(/filter by lecturer or by degree plus path\/cohort for students/i)
    ).toBeInTheDocument();
  });

  it("describes demo loading as replacing the current wizard state", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Step 2" }));

    const shortcutBox = screen.getByText(/fastest way to see a working timetable/i).closest("div");
    expect(shortcutBox).toHaveTextContent(/load a ready-made demo dataset into the wizard/i);
    expect(shortcutBox).toHaveTextContent(/this replaces the current setup state shown on the page/i);
  });

  it("documents that year restriction is stored but not enforced", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Step 5" }));

    expect(
      screen.getByText(/the current solver does not enforce it during timetable generation/i)
    ).toBeInTheDocument();
  });

  it("documents solver-aligned session rules", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Step 8" }));

    expect(
      screen.getByText(/setup page no longer accepts arbitrary free-text values/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/lab-style sessions must be entered as one/i)
    ).toBeInTheDocument();
    expect(screen.getByText("180")).toBeInTheDocument();
  });

  it("describes bounded generation and preview solutions", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Step 10" }));

    expect(
      screen.getByText(/large runs are bounded by time and resource limits/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the result shows total solutions found and a stored preview subset/i)
    ).toBeInTheDocument();
  });

  it("describes student view as degree plus saved path option rather than year-only selection", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("tab", { name: "Step 11" }));

    expect(
      screen.getByText(/select the degree, then choose the matching path option shown by the dataset/i)
    ).toBeInTheDocument();
  });

  it("keeps keyboard focus inside the modal when tabbing", () => {
    render(<OnboardingTutorial onClose={vi.fn()} />);

    const closeButton = screen.getByRole("button", { name: "Close tutorial" });
    const backButton = screen.getByRole("button", { name: "Back" });
    const nextButton = screen.getByRole("button", { name: "Next" });

    expect(closeButton).toHaveFocus();

    nextButton.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(closeButton).toHaveFocus();

    closeButton.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(nextButton).toHaveFocus();

    expect(backButton).toBeDisabled();
  });

  it("resumes from the provided step and reports step changes", () => {
    const onStepChange = vi.fn();
    render(<OnboardingTutorial onClose={vi.fn()} initialStep={3} onStepChange={onStepChange} />);

    expect(screen.getByText("Step 4 of 12")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByText("Step 5 of 12")).toBeInTheDocument();
    expect(onStepChange).toHaveBeenCalledWith(3);
    expect(onStepChange).toHaveBeenLastCalledWith(4);
  });

  it("uses the completion handler on the final get started action", () => {
    const onClose = vi.fn();
    const onComplete = vi.fn();
    render(<OnboardingTutorial onClose={onClose} onComplete={onComplete} initialStep={11} />);

    fireEvent.click(screen.getByRole("button", { name: "Get started" }));

    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });
});
