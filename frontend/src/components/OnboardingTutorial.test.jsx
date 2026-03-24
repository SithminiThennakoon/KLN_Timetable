import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import OnboardingTutorial from "./OnboardingTutorial";

const steps = [
  {
    id: "help",
    targetId: "nav-help",
    title: "Help button",
    body: "Use this to replay the tour.",
    placement: "bottom",
  },
  {
    id: "setup",
    targetId: "setup-header",
    title: "Setup header",
    body: "This is where setup starts.",
    placement: "bottom",
  },
];

function renderTour(currentStep = 0, extraTarget = null) {
  return render(
    <div>
      <button data-tour="nav-help">Help</button>
      {extraTarget}
      <OnboardingTutorial
        steps={steps}
        currentStep={currentStep}
        onStepChange={vi.fn()}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    </div>
  );
}

describe("OnboardingTutorial", () => {
  it("renders a coachmark against the current target", async () => {
    renderTour();

    expect(await screen.findByText("Help button")).toBeInTheDocument();
    expect(screen.getByText(/replay the tour/i)).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: /onboarding tour/i })).toBeInTheDocument();
  });

  it("shows a waiting message when the current target is not mounted yet", async () => {
    render(
      <OnboardingTutorial
        steps={steps}
        currentStep={1}
        onStepChange={vi.fn()}
        onClose={vi.fn()}
        onComplete={vi.fn()}
      />
    );

    expect(await screen.findByText(/Preparing the next area of the app/i)).toBeInTheDocument();
  });

  it("uses the supplied callbacks for next and close actions", async () => {
    const onStepChange = vi.fn();
    const onClose = vi.fn();

    render(
      <div>
        <button data-tour="nav-help">Help</button>
        <OnboardingTutorial
          steps={steps}
          currentStep={0}
          onStepChange={onStepChange}
          onClose={onClose}
          onComplete={vi.fn()}
        />
      </div>
    );

    fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));

    expect(onStepChange).toHaveBeenCalledWith(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
