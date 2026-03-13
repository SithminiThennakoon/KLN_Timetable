import React, { useEffect, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";
import {
  combinationCatalogKey,
  softConstraintCombinationCatalog,
} from "../data/softConstraintCombinationCatalog";

const defaultSoftConstraints = [
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
    key: "prefer_afternoon_practicals",
    label: "Keep practicals in the afternoon",
    description: "Prefer practical and lab sessions to start after lunch so morning halls stay free for theory.",
  },
  {
    key: "avoid_late_afternoon_starts",
    label: "Avoid late-afternoon starts",
    description: "Prefer sessions to start by 3:00 PM so the timetable does not bunch up near the end of the day.",
  },
  {
    key: "avoid_friday_sessions",
    label: "Avoid Friday sessions",
    description: "Prefer teaching to stay within Monday to Thursday when possible so Friday remains lighter.",
  },
  {
    key: "prefer_standard_block_starts",
    label: "Use standard block starts",
    description: "Prefer sessions to begin on the faculty's common block boundaries instead of arbitrary half-hour placements.",
  },
  {
    key: "balance_teaching_load_across_week",
    label: "Balance teaching load across the week",
    description: "Prefer the weekly teaching load to stay spread across weekdays instead of bunching heavily at the start.",
  },
  {
    key: "avoid_monday_overload",
    label: "Avoid Monday overload",
    description: "Prefer Monday to carry no more scheduled teaching events than the other weekdays.",
  },
];

const softConstraintLabelByKey = new Map(
  defaultSoftConstraints.map((option) => [option.key, option.label])
);

function formatClock(minuteOfDay) {
  const hours = Math.floor(minuteOfDay / 60);
  const minutes = minuteOfDay % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function formatEntryWindow(entry) {
  const start = formatClock(entry.start_minute);
  const end = formatClock(entry.start_minute + entry.duration_minutes);
  return `${entry.day} ${start}-${end}`;
}

function formatConstraintLabel(key) {
  return softConstraintLabelByKey.get(key) || key;
}

const defaultPerformanceSettings = {
  performance_preset: "balanced",
  max_solutions: 1000,
  preview_limit: 5,
  time_limit_seconds: 180,
};

const generationLimits = {
  max_solutions: { min: 1, max: 5000 },
  preview_limit: { min: 1, max: 100 },
  time_limit_seconds: { min: 1, max: 600 },
};
const activeImportRunStorageKey = "kln_active_import_run_id";

function formatMilliseconds(value) {
  if (!value) {
    return "0 ms";
  }
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${value} ms`;
}

function clampNumber(value, { min, max }, fallback) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.trunc(numeric)));
}

function lookupCombinationName(combo) {
  return (
    softConstraintCombinationCatalog[combinationCatalogKey(combo)] ||
    combo.map((key) => formatConstraintLabel(key)).join(" + ")
  );
}

function sortConstraintCombinations(combos) {
  return [...combos].sort((left, right) => {
    if (right.constraints.length !== left.constraints.length) {
      return right.constraints.length - left.constraints.length;
    }
    return left.constraints.join(",").localeCompare(right.constraints.join(","));
  });
}

function formatCombinationCount(suggestion) {
  if (suggestion.solution_count_capped || suggestion.solution_count > 100) {
    return "100+";
  }
  return String(suggestion.solution_count);
}

function GenerateStudio() {
  const [generation, setGeneration] = useState(null);
  const [verification, setVerification] = useState(null);
  const [verificationLoading, setVerificationLoading] = useState(false);
  const [verificationError, setVerificationError] = useState("");
  const [activeImportRunId, setActiveImportRunId] = useState(() => {
    if (typeof window === "undefined") {
      return null;
    }
    const raw = window.localStorage.getItem(activeImportRunStorageKey);
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  });
  const [softConstraints, setSoftConstraints] = useState([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [settings, setSettings] = useState(defaultPerformanceSettings);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadVerification = async (importRunId, nextGeneration = null) => {
    if (!importRunId || !nextGeneration || (nextGeneration.solutions || []).length === 0) {
      setVerification(null);
      setVerificationError("");
      return;
    }
    setVerificationLoading(true);
    setVerificationError("");
    try {
      const response = await timetableStudioService.verifySnapshotGeneration(importRunId);
      setVerification(response);
    } catch (err) {
      setVerification(null);
      setVerificationError(err.message);
    } finally {
      setVerificationLoading(false);
    }
  };

  const loadLatest = async () => {
    try {
      const response = await timetableStudioService.latestGeneration(activeImportRunId);
      setGeneration(response);
      setSoftConstraints(response.selected_soft_constraints || []);
      setSettings((prev) => ({
        ...prev,
        performance_preset: response.performance_preset || prev.performance_preset,
      }));
      await loadVerification(activeImportRunId, response);
    } catch {
      setGeneration(null);
      setVerification(null);
      setVerificationError("");
    }
  };

  useEffect(() => {
    loadLatest();
  }, [activeImportRunId]);

  const handleToggle = (key) => {
    setSoftConstraints((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
    );
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    const requestSettings = {
      performance_preset: settings.performance_preset,
      max_solutions: clampNumber(
        settings.max_solutions,
        generationLimits.max_solutions,
        defaultPerformanceSettings.max_solutions
      ),
      preview_limit: clampNumber(
        settings.preview_limit,
        generationLimits.preview_limit,
        defaultPerformanceSettings.preview_limit
      ),
      time_limit_seconds: clampNumber(
        settings.time_limit_seconds,
        generationLimits.time_limit_seconds,
        defaultPerformanceSettings.time_limit_seconds
      ),
    };
    setSettings((prev) => ({ ...prev, ...requestSettings }));
    try {
      const response = await timetableStudioService.generate({
        import_run_id: activeImportRunId || undefined,
        soft_constraints: softConstraints,
        ...requestSettings,
      });
      setGeneration(response);
      await loadVerification(activeImportRunId, response);
    } catch (err) {
      setError(err.message);
      setVerification(null);
      setVerificationError("");
    } finally {
      setLoading(false);
    }
  };

  const handleDefault = async (solutionId) => {
    setLoading(true);
    setError("");
    try {
      const response = await timetableStudioService.setDefault(
        solutionId,
        activeImportRunId
      );
      setGeneration(response);
      await loadVerification(activeImportRunId, response);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUseCombination = (combo) => {
    setSoftConstraints(combo);
    setError("");
  };

  const availableSoftConstraints =
    generation?.available_soft_constraints || defaultSoftConstraints;

  const handleSelectAllConstraints = () => {
    setSoftConstraints(availableSoftConstraints.map((option) => option.key));
    setError("");
  };

  const updateSetting = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const sortedPossibleCombinations = sortConstraintCombinations(
    generation?.possible_soft_constraint_combinations || []
  );
  const allConstraintsSelected =
    availableSoftConstraints.length > 0 &&
    availableSoftConstraints.every((option) => softConstraints.includes(option.key));
  const requiresConstraintNarrowing =
    Boolean(generation) &&
    generation.counts.total_solutions_found > 100 &&
    !allConstraintsSelected;
  const representativePreviewMode =
    Boolean(generation) && generation.counts.total_solutions_found > 100;

  return (
    <div className="page-shell">
      <div className="panel studio-panel">
        <div className="studio-header">
          <div>
            <h1 className="section-title">Generate Timetable</h1>
            <p className="section-subtitle">
              Generate timetable options from the current setup. The system checks the result automatically before you use it.
            </p>
            {activeImportRunId && (
              <>
                <p className="helper-copy">Using import snapshot #{activeImportRunId} directly.</p>
                <p className="helper-copy">
                  This run uses the current snapshot directly, and the selected timetable is verified against the same snapshot before it is considered trusted.
                </p>
              </>
            )}
          </div>
          <button className="primary-btn" onClick={handleGenerate} disabled={loading}>
            {loading ? "Generating..." : "Generate Timetable"}
          </button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <section className="studio-card">
          <h2>Optional Preferences</h2>
          <p className="helper-copy">
            Start without extra preferences if you want the broadest result. Add them only when you need the system to narrow a large solution set.
          </p>
          <div className="studio-actions">
            <button
              type="button"
              className="ghost-btn"
              onClick={handleSelectAllConstraints}
              disabled={allConstraintsSelected}
            >
              {allConstraintsSelected ? "All Constraints Selected" : "Select All Constraints"}
            </button>
            <button
              type="button"
              className="ghost-btn"
              onClick={() => setShowAdvanced((prev) => !prev)}
            >
              {showAdvanced ? "Hide Advanced Performance" : "Show Advanced Performance"}
            </button>
          </div>
          {showAdvanced && (
            <div className="advanced-panel">
              <div className="form-grid four-column">
                <label>
                  <span>Performance preset</span>
                  <select
                    value={settings.performance_preset}
                    onChange={(event) => updateSetting("performance_preset", event.target.value)}
                  >
                    <option value="balanced">Balanced</option>
                    <option value="thorough">Thorough</option>
                    <option value="fast_diagnostics">Fast diagnostics</option>
                  </select>
                </label>
                <label>
                  <span>Max solutions</span>
                  <input
                    type="number"
                    min={generationLimits.max_solutions.min}
                    max={generationLimits.max_solutions.max}
                    value={settings.max_solutions}
                    onChange={(event) => updateSetting("max_solutions", event.target.value)}
                  />
                </label>
                <label>
                  <span>Preview limit</span>
                  <input
                    type="number"
                    min={generationLimits.preview_limit.min}
                    max={generationLimits.preview_limit.max}
                    value={settings.preview_limit}
                    onChange={(event) => updateSetting("preview_limit", event.target.value)}
                  />
                </label>
                <label>
                  <span>Time limit (seconds)</span>
                  <input
                    type="number"
                    min={generationLimits.time_limit_seconds.min}
                    max={generationLimits.time_limit_seconds.max}
                    value={settings.time_limit_seconds}
                    onChange={(event) => updateSetting("time_limit_seconds", event.target.value)}
                  />
                </label>
              </div>
              <p className="helper-copy">
                More CPU helps mainly for diagnostics and fallback probing. Exact all-solution enumeration still runs as a single-worker search to preserve the true count.
              </p>
            </div>
          )}
          <div className="constraint-list">
            {availableSoftConstraints.map((option) => (
              <label key={option.key} className="constraint-row">
                <input
                  type="checkbox"
                  checked={softConstraints.includes(option.key)}
                  onChange={() => handleToggle(option.key)}
                />
                <div>
                  <strong>{option.label}</strong>
                  <span>{option.description}</span>
                </div>
              </label>
            ))}
          </div>
        </section>

        {!generation && !error && (
          <section className="studio-card">
              <h2>No generation run yet</h2>
              <p className="empty-state">
                {activeImportRunId
                ? "Complete the setup in Setup, then generate the timetable here."
                : "Finish the setup first, then generate the timetable here."}
              </p>
            </section>
          )}

        {generation && (
          <>
            <section className={`studio-card result-card ${generation.status}`}>
              <h2>{generation.message}</h2>
              <p className="helper-copy">
                Use the stored preview solutions below to inspect alternatives. One solution can be marked as the default timetable used by the Views page.
              </p>
              <div className="summary-grid">
                <div className="summary-item">
                  <span>Total solutions found</span>
                  <strong>{generation.counts.total_solutions_found}</strong>
                </div>
                <div className="summary-item">
                  <span>Preview solutions stored</span>
                  <strong>{generation.counts.preview_solution_count}</strong>
                </div>
                <div className="summary-item">
                  <span>Generation run</span>
                  <strong>{generation.generation_run_id}</strong>
                </div>
              </div>
              <div className="performance-grid">
                <div className="summary-item">
                  <span>Solver engine</span>
                  <strong>{generation.stats?.solver_engine || "legacy_guarded"}</strong>
                </div>
                <div className="summary-item">
                  <span>Performance preset</span>
                  <strong>{generation.performance_preset || "balanced"}</strong>
                </div>
                <div className="summary-item">
                  <span>Total time</span>
                  <strong>{formatMilliseconds(generation.timing?.total_ms)}</strong>
                </div>
                <div className="summary-item">
                  <span>Solve time</span>
                  <strong>{formatMilliseconds(generation.timing?.solve_ms)}</strong>
                </div>
                <div className="summary-item">
                  <span>Assignment variables</span>
                  <strong>{generation.stats?.assignment_variable_count || 0}</strong>
                </div>
                <div className="summary-item">
                  <span>Slot variables</span>
                  <strong>{generation.stats?.slot_variable_count || 0}</strong>
                </div>
                <div className="summary-item">
                  <span>Candidate options</span>
                  <strong>{generation.stats?.candidate_option_count || 0}</strong>
                </div>
                <div className="summary-item">
                  <span>Room retries</span>
                  <strong>{generation.stats?.room_assignment_retry_count || 0}</strong>
                </div>
                <div className="summary-item">
                  <span>Machine CPU count</span>
                  <strong>{generation.stats?.machine_cpu_count || 1}</strong>
                </div>
              </div>
              <p className="helper-copy">
                Precheck {formatMilliseconds(generation.timing?.precheck_ms)} | Model build{" "}
                {formatMilliseconds(generation.timing?.model_build_ms)} | Room assignment{" "}
                {formatMilliseconds(generation.timing?.room_assignment_ms)} | Fallback search{" "}
                {formatMilliseconds(generation.timing?.fallback_search_ms)}
                {generation.stats?.fallback_combo_truncated
                  ? " | Fallback combination search was capped early."
                  : ""}
              </p>
              {generation.stats?.domain_reduction_ratio > 0 && (
                <p className="helper-copy">
                  Domain reduction {(generation.stats.domain_reduction_ratio * 100).toFixed(1)}% | Memory
                  limit {generation.stats?.memory_limit_mb || 0} MB
                </p>
              )}
              {requiresConstraintNarrowing && (
                <div className="info-banner invalid">
                  More than 100 valid timetables exist. Select more nice-to-have constraints and generate again before choosing a default timetable.
                </div>
              )}
              {!requiresConstraintNarrowing && representativePreviewMode && (
                <div className="info-banner invalid">
                  More than 100 valid timetables still exist even with the current nice-to-have set. The stored previews are representative options rather than the full list, so pick one only if you are satisfied with that reduced guidance.
                </div>
              )}
              {generation.counts.truncated && (
                <div className="info-banner invalid">
                  Enumeration stopped early because the configured solution threshold or the 60-second time limit was reached.
                </div>
              )}
              {sortedPossibleCombinations.length > 0 && (
                <div className="schema-notes">
                  <h3>Possible nice-to-have combinations</h3>
                  <p>
                    The selected nice-to-have set could not be satisfied together. Try one of the combinations below instead.
                  </p>
                  <div className="combo-list">
                    {sortedPossibleCombinations.map((suggestion, index) => {
                      const combo = suggestion.constraints;
                      const isSelected =
                        combo.length === softConstraints.length &&
                        combo.every((item) => softConstraints.includes(item));
                      return (
                        <article key={`${combo.join("-")}-${index}`} className="combo-card">
                          <div className="combo-card-head">
                            <div>
                              <strong>{lookupCombinationName(combo)}</strong>
                              <p>
                                {combo.length} selected preference{combo.length === 1 ? "" : "s"} |{" "}
                                {formatCombinationCount(suggestion)} possible timetable
                                {formatCombinationCount(suggestion) === "1" ? "" : "s"}
                              </p>
                            </div>
                            <button
                              className="ghost-btn"
                              type="button"
                              onClick={() => handleUseCombination(combo)}
                              disabled={loading || isSelected}
                            >
                              {isSelected ? "Selected" : "Use This Combination"}
                            </button>
                          </div>
                          <div className="chip-row">
                            {combo.map((item) => (
                              <span key={item} className="tag-chip">
                                {formatConstraintLabel(item)}
                              </span>
                            ))}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>

            {activeImportRunId && (
              <section className="studio-card">
                <div className="studio-header compact">
                  <div>
                    <h2>Verification</h2>
                    <p className="helper-copy">
                      The selected timetable is checked against the normalized snapshot using three independent verifiers: Python, Rust, and Elixir.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => loadVerification(activeImportRunId, generation)}
                    disabled={verificationLoading || loading}
                  >
                    {verificationLoading ? "Verifying..." : "Run Verification"}
                  </button>
                </div>
                {verificationError && <div className="error-banner">{verificationError}</div>}
                {!verification && !verificationError && (
                  <p className="empty-state">
                    Verification will appear here after a snapshot-backed generation run finishes.
                  </p>
                )}
                {verification && (
                  <>
                    <div className="summary-grid">
                      <div className="summary-item">
                        <span>Completed verifiers</span>
                        <strong>{(verification.completed_verifiers || []).join(", ") || "None"}</strong>
                      </div>
                      <div className="summary-item">
                        <span>Hard constraints</span>
                        <strong>{verification.hard_valid_all ? "Pass" : "Not fully trusted yet"}</strong>
                      </div>
                      <div className="summary-item">
                        <span>Missing verifiers</span>
                        <strong>{(verification.missing_verifiers || []).join(", ") || "None"}</strong>
                      </div>
                      <div className="summary-item">
                        <span>Verified solution</span>
                        <strong>{verification.solution_id || "-"}</strong>
                      </div>
                    </div>
                    {(verification.missing_verifiers || []).length > 0 && (
                      <div className="info-banner invalid">
                        The timetable is not fully trusted yet because these required verifiers have not completed:{" "}
                        {(verification.missing_verifiers || []).join(", ")}.
                      </div>
                    )}
                    {Object.entries(verification.errors || {}).length > 0 && (
                      <div className="constraint-list">
                        {Object.entries(verification.errors).map(([key, value]) => (
                          <div key={key} className="constraint-row static">
                            <div>
                              <strong>{key}</strong>
                              <span>{value}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {Object.entries(verification.results || {}).map(([key, result]) => (
                      <div key={key} className="schema-notes">
                        <h3>{key} verifier</h3>
                        <p>
                          Hard constraints: {result.hard_valid ? "Pass" : "Fail"} | Violations:{" "}
                          {result.hard_violations?.length || 0} | Checked entries:{" "}
                          {result.stats?.entry_count || 0}
                        </p>
                        {(result.hard_violations || []).length > 0 && (
                          <div className="info-banner invalid">
                            {(result.hard_violations || [])
                              .slice(0, 5)
                              .map((item) => item.message)
                              .join(" ")}
                          </div>
                        )}
                        {(result.soft_summary || []).length > 0 && (
                          <div className="constraint-list">
                            {result.soft_summary.map((item) => (
                              <div key={`${key}-${item.key}`} className="constraint-row static">
                                <div>
                                  <strong>
                                    {item.label}: {item.satisfied ? "Satisfied" : "Not satisfied"}
                                  </strong>
                                  <span>{item.details}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </>
                )}
              </section>
            )}

            <section className="studio-card">
              <h2>Preview Solutions</h2>
              {requiresConstraintNarrowing && (
                <p className="helper-copy">
                  Default selection is locked until you narrow the solution count below 100 or exhaust all nice-to-have constraints.
                </p>
              )}
              <div className="solution-list">
                {generation.solutions.length === 0 ? (
                  <p className="empty-state">No preview solutions available.</p>
                ) : (
                  generation.solutions.map((solution) => (
                    <article key={solution.solution_id} className="solution-card">
                      <div className="solution-card-head">
                        <div>
                          <strong>Solution {solution.ordinal}</strong>
                          <p>
                            {solution.is_default ? "Default timetable" : "Available for selection"}
                            {solution.is_representative ? " - representative preview" : ""}
                          </p>
                        </div>
                        <button
                          className="ghost-btn"
                          onClick={() => handleDefault(solution.solution_id)}
                          disabled={loading || solution.is_default || requiresConstraintNarrowing}
                        >
                          {solution.is_default
                            ? "Selected"
                            : requiresConstraintNarrowing
                              ? "Select More Constraints First"
                              : "Set as Default"}
                        </button>
                      </div>
                      <div className="mini-entry-list">
                        {solution.entries.slice(0, 6).map((entry, index) => (
                          <div key={`${solution.solution_id}-${index}`} className="mini-entry">
                            <div className="mini-entry-head">
                              <strong>{entry.module_code}</strong>
                              <span>{formatEntryWindow(entry)}</span>
                            </div>
                            <p>{entry.module_name}</p>
                            <p>
                              {entry.room_name}
                              {entry.room_location ? `, ${entry.room_location}` : ""}
                            </p>
                            <p>
                              {(entry.degree_path_labels || []).join(", ")}
                              {entry.lecturer_names?.length ? ` | ${entry.lecturer_names.join(", ")}` : ""}
                            </p>
                          </div>
                        ))}
                      </div>
                    </article>
                  ))
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default GenerateStudio;
