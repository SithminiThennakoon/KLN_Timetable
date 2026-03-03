import React, { useState } from "react";
import "../styles/GeneratePage.css";
import { timetableService } from "../services/timetableService";

function GeneratePage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await timetableService.generate();
      setStatus(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <div className="panel generate-panel">
        <div className="generate-header">
          <div>
            <h1 className="section-title">Generate Timetable</h1>
            <p className="section-subtitle">
              Run the solver to produce the full faculty timetable.
            </p>
          </div>
          <button className="primary-btn" onClick={handleGenerate} disabled={loading}>
            {loading ? "Generating..." : "Generate"}
          </button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        {status && (
          <div className={`result-card ${status.status}`}>
            <h2>Status: {status.status}</h2>
            <div className="result-grid">
              <div>
                <span>Total Scheduled</span>
                <strong>{status.total_scheduled_sessions}</strong>
              </div>
              <div>
                <span>Unscheduled</span>
                <strong>{status.unscheduled_sessions}</strong>
              </div>
              <div>
                <span>Version</span>
                <strong>{status.version || "-"}</strong>
              </div>
            </div>
            {status.diagnostics && status.diagnostics.length > 0 && (
              <div className="diagnostics">
                <h3>Diagnostics</h3>
                <ul>
                  {status.diagnostics.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default GeneratePage;
