import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import MainNavbar from "./MainNavbar";

describe("MainNavbar", () => {
  it("opens the help menu and starts either walkthrough explicitly", () => {
    const onStartBasicTour = vi.fn();
    const onStartTechnicalTour = vi.fn();

    render(
      <MemoryRouter>
        <MainNavbar
          onStartBasicTour={onStartBasicTour}
          onStartTechnicalTour={onStartTechnicalTour}
        />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: /open walkthrough menu/i }));

    fireEvent.click(screen.getByRole("menuitem", { name: /start basic tour/i }));
    expect(onStartBasicTour).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /open walkthrough menu/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: /start technical tour/i }));
    expect(onStartTechnicalTour).toHaveBeenCalledTimes(1);
  });
});
