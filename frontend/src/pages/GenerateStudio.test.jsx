import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GenerateStudio from "./GenerateStudio";
import { timetableStudioService } from "../services/timetableStudioService";

vi.mock("../services/timetableStudioService", () => ({
  timetableStudioService: {
    latestGeneration: vi.fn(),
    generate: vi.fn(),
    setDefault: vi.fn(),
  },
}));

describe("GenerateStudio", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows first-run guidance when no generation run exists yet", async () => {
    timetableStudioService.latestGeneration.mockRejectedValue(new Error("empty"));

    render(<GenerateStudio />);

    expect(await screen.findByText("No generation run yet")).toBeInTheDocument();
    expect(screen.getByLabelText(/Keep theory sessions in the morning/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Keep practicals in the afternoon/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Avoid late-afternoon starts/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Avoid Friday sessions/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Use standard block starts/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Balance teaching load across the week/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Avoid Monday overload/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Finish the setup first, then generate the timetable here/i)
    ).toBeInTheDocument();
  });

  it("selects all available nice-to-have constraints with one action", async () => {
    timetableStudioService.latestGeneration.mockRejectedValue(new Error("empty"));

    render(<GenerateStudio />);

    fireEvent.click(await screen.findByRole("button", { name: /Select All Constraints/i }));

    expect(screen.getByLabelText(/Spread repeated sessions across different days/i)).toBeChecked();
    expect(screen.getByLabelText(/Keep theory sessions in the morning/i)).toBeChecked();
    expect(screen.getByLabelText(/Keep practicals in the afternoon/i)).toBeChecked();
    expect(screen.getByLabelText(/Avoid late-afternoon starts/i)).toBeChecked();
    expect(screen.getByLabelText(/Avoid Friday sessions/i)).toBeChecked();
    expect(screen.getByLabelText(/Use standard block starts/i)).toBeChecked();
    expect(screen.getByLabelText(/Balance teaching load across the week/i)).toBeChecked();
    expect(screen.getByLabelText(/Avoid Monday overload/i)).toBeChecked();
    expect(screen.getByRole("button", { name: /All Constraints Selected/i })).toBeDisabled();
  });

  it("shows threshold and truncation messaging from generation results", async () => {
    timetableStudioService.latestGeneration.mockResolvedValue({
      generation_run_id: 8,
      status: "feasible",
      message: "Generated timetable solutions.",
      performance_preset: "balanced",
      timing: { precheck_ms: 10, model_build_ms: 20, solve_ms: 30, fallback_search_ms: 0, total_ms: 60 },
      stats: {
        task_count: 1,
        assignment_variable_count: 5,
        candidate_option_count: 5,
        feasible_combo_count: 1,
        fallback_combo_evaluated_count: 0,
        fallback_combo_truncated: false,
        exact_enumeration_single_worker: true,
        machine_cpu_count: 8,
      },
      counts: {
        total_solutions_found: 150,
        preview_solution_count: 1,
        truncated: true,
      },
      selected_soft_constraints: [],
      available_soft_constraints: [],
      possible_soft_constraint_combinations: [
        {
          constraints: ["spread_sessions_across_days"],
          solution_count: 12,
          solution_count_capped: false,
        },
      ],
      solutions: [
        {
          solution_id: 1,
          ordinal: 1,
          is_default: false,
          is_representative: true,
          entries: [],
        },
      ],
    });

    render(<GenerateStudio />);

    expect(await screen.findByText("Generated timetable solutions.")).toBeInTheDocument();
    expect(
      screen.getByText(/More than 100 valid timetables exist/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Enumeration stopped early because the configured solution threshold or the 60-second time limit was reached/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Spread repeated sessions across different days")).toBeInTheDocument();
  });

  it("lets the user select a suggested soft-constraint combination", async () => {
    timetableStudioService.latestGeneration.mockResolvedValue({
      generation_run_id: 12,
      status: "infeasible",
      message: "Selected nice-to-have constraints cannot be satisfied together.",
      performance_preset: "balanced",
      timing: { precheck_ms: 0, model_build_ms: 0, solve_ms: 0, fallback_search_ms: 0, total_ms: 0 },
      stats: {
        task_count: 0,
        assignment_variable_count: 0,
        candidate_option_count: 0,
        feasible_combo_count: 1,
        fallback_combo_evaluated_count: 1,
        fallback_combo_truncated: false,
        exact_enumeration_single_worker: true,
        machine_cpu_count: 8,
      },
      counts: {
        total_solutions_found: 0,
        preview_solution_count: 0,
        truncated: false,
      },
      selected_soft_constraints: ["avoid_friday_sessions", "prefer_morning_theory"],
      available_soft_constraints: defaultOptions(),
      possible_soft_constraint_combinations: [
        {
          constraints: ["spread_sessions_across_days", "prefer_morning_theory"],
          solution_count: 7,
          solution_count_capped: false,
        },
      ],
      solutions: [],
    });

    render(<GenerateStudio />);

    expect(await screen.findByText("Use This Combination")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A timetable that keeps theory in the morning and spreads repeated sessions across different days"
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/2 selected preferences \| 7 possible timetables/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Use This Combination/i }));

    expect(screen.getByLabelText(/Spread repeated sessions across different days/i)).toBeChecked();
    expect(screen.getByLabelText(/Keep theory sessions in the morning/i)).toBeChecked();
    expect(screen.getByLabelText(/Avoid Friday sessions/i)).not.toBeChecked();
  });

  it("shows larger possible combinations before smaller ones", async () => {
    timetableStudioService.latestGeneration.mockResolvedValue({
      generation_run_id: 13,
      status: "infeasible",
      message: "Selected nice-to-have constraints cannot be satisfied together.",
      performance_preset: "balanced",
      timing: { precheck_ms: 0, model_build_ms: 0, solve_ms: 0, fallback_search_ms: 0, total_ms: 0 },
      stats: {
        task_count: 0,
        assignment_variable_count: 0,
        candidate_option_count: 0,
        feasible_combo_count: 2,
        fallback_combo_evaluated_count: 2,
        fallback_combo_truncated: false,
        exact_enumeration_single_worker: true,
        machine_cpu_count: 8,
      },
      counts: {
        total_solutions_found: 0,
        preview_solution_count: 0,
        truncated: false,
      },
      selected_soft_constraints: [],
      available_soft_constraints: defaultOptions(),
      possible_soft_constraint_combinations: [
        {
          constraints: ["spread_sessions_across_days"],
          solution_count: 4,
          solution_count_capped: false,
        },
        {
          constraints: ["spread_sessions_across_days", "prefer_morning_theory"],
          solution_count: 101,
          solution_count_capped: true,
        },
      ],
      solutions: [],
    });

    render(<GenerateStudio />);

    await screen.findAllByText("Use This Combination");
    const comboTitles = [
      screen.getByText(
        "A timetable that keeps theory in the morning and spreads repeated sessions across different days"
      ),
      screen.getByText("A timetable that spreads repeated weekly sessions across different days"),
    ];
    expect(comboTitles[0].compareDocumentPosition(comboTitles[1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(/2 selected preferences \| 100\+ possible timetables/i)).toBeInTheDocument();
    expect(screen.getByText(/1 selected preference \| 4 possible timetables/i)).toBeInTheDocument();
  });

  function defaultOptions() {
    return [
      {
        key: "spread_sessions_across_days",
        label: "Spread repeated sessions across different days",
        description: "Keep repeated weekly sessions on separate days when possible.",
      },
      {
        key: "prefer_morning_theory",
        label: "Keep theory sessions in the morning",
        description: "Prefer lectures and tutorials to finish before lunch when possible.",
      },
      {
        key: "avoid_friday_sessions",
        label: "Avoid Friday sessions",
        description: "Prefer teaching to stay within Monday to Thursday when possible so Friday remains lighter.",
      },
    ];
  }

  it("submits soft constraints when generate is clicked", async () => {
    timetableStudioService.latestGeneration.mockRejectedValue(new Error("empty"));
    timetableStudioService.generate.mockResolvedValue({
      generation_run_id: 9,
      status: "optimal",
      message: "Generated timetable solutions.",
      performance_preset: "balanced",
      timing: { precheck_ms: 10, model_build_ms: 20, solve_ms: 30, fallback_search_ms: 0, total_ms: 60 },
      stats: {
        task_count: 1,
        assignment_variable_count: 4,
        candidate_option_count: 4,
        feasible_combo_count: 0,
        fallback_combo_evaluated_count: 0,
        fallback_combo_truncated: false,
        exact_enumeration_single_worker: true,
        machine_cpu_count: 8,
      },
      counts: {
        total_solutions_found: 1,
        preview_solution_count: 1,
        truncated: false,
      },
      selected_soft_constraints: ["spread_sessions_across_days"],
      available_soft_constraints: [
        {
          key: "spread_sessions_across_days",
          label: "Spread repeated sessions across different days",
          description: "Keep repeated weekly sessions on separate days when possible.",
        },
      ],
      possible_soft_constraint_combinations: [],
      solutions: [],
    });

    render(<GenerateStudio />);

    fireEvent.click(screen.getByLabelText(/Spread repeated sessions across different days/i));
    fireEvent.click(screen.getByRole("button", { name: /Show Advanced Performance/i }));
    fireEvent.change(screen.getByLabelText(/Performance preset/i), {
      target: { value: "thorough" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Generate Timetable/i }));

    await waitFor(() =>
      expect(timetableStudioService.generate).toHaveBeenCalledWith({
        import_run_id: undefined,
        soft_constraints: ["spread_sessions_across_days"],
        performance_preset: "thorough",
        max_solutions: 1000,
        preview_limit: 5,
        time_limit_seconds: 180,
      })
    );
  });

  it("shows a blocking overlay while generation is running", async () => {
    timetableStudioService.latestGeneration.mockRejectedValue(new Error("empty"));

    let resolveGenerate;
    timetableStudioService.generate.mockReturnValue(
      new Promise((resolve) => {
        resolveGenerate = resolve;
      })
    );

    render(<GenerateStudio />);

    fireEvent.click(await screen.findByRole("button", { name: /Generate Timetable/i }));

    expect(await screen.findByText("Generating timetable")).toBeInTheDocument();
    expect(
      screen.getByText(/Generating timetable solutions from the current snapshot/i)
    ).toBeInTheDocument();

    resolveGenerate({
      generation_run_id: 15,
      status: "optimal",
      message: "Generated timetable solutions.",
      performance_preset: "balanced",
      timing: { precheck_ms: 10, model_build_ms: 20, solve_ms: 30, fallback_search_ms: 0, total_ms: 60 },
      stats: {
        task_count: 1,
        assignment_variable_count: 4,
        candidate_option_count: 4,
        feasible_combo_count: 0,
        fallback_combo_evaluated_count: 0,
        fallback_combo_truncated: false,
        exact_enumeration_single_worker: true,
        machine_cpu_count: 8,
      },
      counts: {
        total_solutions_found: 1,
        preview_solution_count: 1,
        truncated: false,
      },
      selected_soft_constraints: [],
      available_soft_constraints: [],
      possible_soft_constraint_combinations: [],
      solutions: [],
    });

    await waitFor(() => {
      expect(screen.queryByText("Generating timetable")).not.toBeInTheDocument();
    });
  });

  it("clamps advanced performance values to backend limits before submit", async () => {
    timetableStudioService.latestGeneration.mockRejectedValue(new Error("empty"));
    timetableStudioService.generate.mockResolvedValue({
      generation_run_id: 10,
      status: "optimal",
      message: "Generated timetable solutions.",
      performance_preset: "thorough",
      timing: { precheck_ms: 1, model_build_ms: 2, solve_ms: 3, fallback_search_ms: 0, total_ms: 6 },
      stats: {
        task_count: 1,
        assignment_variable_count: 1,
        candidate_option_count: 1,
        feasible_combo_count: 0,
        fallback_combo_evaluated_count: 0,
        fallback_combo_truncated: false,
        exact_enumeration_single_worker: true,
        machine_cpu_count: 8,
      },
      counts: {
        total_solutions_found: 1,
        preview_solution_count: 1,
        truncated: false,
      },
      selected_soft_constraints: [],
      available_soft_constraints: [],
      possible_soft_constraint_combinations: [],
      solutions: [],
    });

    render(<GenerateStudio />);

    fireEvent.click(screen.getByRole("button", { name: /Show Advanced Performance/i }));
    fireEvent.change(screen.getByLabelText(/Max solutions/i), { target: { value: "100000" } });
    fireEvent.change(screen.getByLabelText(/Preview limit/i), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText(/Time limit \(seconds\)/i), { target: { value: "600" } });
    fireEvent.click(screen.getByRole("button", { name: /Generate Timetable/i }));

    await waitFor(() =>
      expect(timetableStudioService.generate).toHaveBeenCalledWith({
        import_run_id: undefined,
        soft_constraints: [],
        performance_preset: "balanced",
        max_solutions: 5000,
        preview_limit: 1,
        time_limit_seconds: 600,
      })
    );
  });

  it("shows performance summary for the latest run", async () => {
    timetableStudioService.latestGeneration.mockResolvedValue({
      generation_run_id: 14,
      status: "feasible",
      message: "Generated timetable solutions.",
      performance_preset: "thorough",
      timing: { precheck_ms: 11, model_build_ms: 22, solve_ms: 3333, fallback_search_ms: 44, total_ms: 3410 },
      stats: {
        task_count: 7,
        assignment_variable_count: 91,
        candidate_option_count: 91,
        feasible_combo_count: 2,
        fallback_combo_evaluated_count: 5,
        fallback_combo_truncated: true,
        exact_enumeration_single_worker: true,
        machine_cpu_count: 16,
      },
      counts: {
        total_solutions_found: 3,
        preview_solution_count: 2,
        truncated: false,
      },
      selected_soft_constraints: [],
      available_soft_constraints: [],
      possible_soft_constraint_combinations: [],
      solutions: [],
    });

    render(<GenerateStudio />);

    expect(await screen.findByText("thorough")).toBeInTheDocument();
    expect(screen.getAllByText("91")).toHaveLength(2);
    expect(screen.getByText(/Fallback combination search was capped early/i)).toBeInTheDocument();
  });
});
