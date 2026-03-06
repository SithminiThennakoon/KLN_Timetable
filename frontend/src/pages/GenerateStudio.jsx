import React, { useEffect, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";

function GenerateStudio() {
  const [generation, setGeneration] = useState(null);
  const [softConstraints, setSoftConstraints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadLatest = async () => {
    try {
      const response = await timetableStudioService.latestGeneration();
      setGeneration(response);
      setSoftConstraints(response.selected_soft_constraints || []);
    } catch {
      // ignore empty state
    }
  };

  useEffect(() => {
    loadLatest();
  }, []);

  const handleToggle = (key) => {
    setSoftConstraints((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
    );
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await timetableStudioService.generate({
        soft_constraints: softConstraints,
        max_solutions: 1000,
        preview_limit: 5,
        time_limit_seconds: 60,
      });
      setGeneration(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDefault = async (solutionId) => {
    setLoading(true);
    setError("");
    try {
      const response = await timetableStudioService.setDefault(solutionId);
      setGeneration(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <div className="panel studio-panel">
        <div className="studio-header">
          <div>
            <h1 className="section-title">Generate Solutions</h1>
            <p className="section-subtitle">
              Hard constraints are always enforced. Nice-to-have constraints only help reduce solution counts.
            </p>
          </div>
          <button className="primary-btn" onClick={handleGenerate} disabled={loading}>
            {loading ? "Generating..." : "Generate Timetables"}
          </button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <section className="studio-card">
          <h2>Nice-to-Have Constraints</h2>
          <div className="constraint-list">
            {(generation?.available_soft_constraints || [
              {
                key: "spread_sessions_across_days",
                label: "Spread repeated sessions across different days",
                description: "Keep repeated weekly sessions on separate days when possible.",
              },
            ]).map((option) => (
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

        {generation && (
          <>
            <section className={`studio-card result-card ${generation.status}`}>
              <h2>{generation.message}</h2>
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
              {generation.counts.total_solutions_found > 100 && (
                <div className="info-banner invalid">
                  More than 100 valid timetables exist. Select nice-to-have constraints or choose a representative preview.
                </div>
              )}
              {generation.counts.truncated && (
                <div className="info-banner invalid">
                  Enumeration stopped early because the configured threshold or time limit was reached.
                </div>
              )}
              {generation.possible_soft_constraint_combinations?.length > 0 && (
                <div className="schema-notes">
                  <h3>Possible nice-to-have combinations</h3>
                  <ul>
                    {generation.possible_soft_constraint_combinations.map((combo, index) => (
                      <li key={`${combo.join("-")}-${index}`}>{combo.join(", ")}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <section className="studio-card">
              <h2>Preview Solutions</h2>
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
                          disabled={loading || solution.is_default}
                        >
                          {solution.is_default ? "Selected" : "Set as Default"}
                        </button>
                      </div>
                      <div className="mini-entry-list">
                        {solution.entries.slice(0, 6).map((entry, index) => (
                          <div key={`${solution.solution_id}-${index}`} className="mini-entry">
                            <span>{entry.day}</span>
                            <strong>{entry.module_code}</strong>
                            <span>{entry.room_name}</span>
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
