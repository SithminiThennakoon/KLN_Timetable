import React, { useMemo, useState } from "react";
import { timetableStudioService } from "../services/timetableStudioService";

const emptyDataset = {
  degrees: [],
  paths: [],
  lecturers: [],
  rooms: [],
  student_groups: [],
  modules: [],
  sessions: [],
};

function SetupStudio() {
  const [datasetText, setDatasetText] = useState(JSON.stringify(emptyDataset, null, 2));
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const parsedPreview = useMemo(() => {
    try {
      return JSON.parse(datasetText);
    } catch {
      return null;
    }
  }, [datasetText]);

  const handleLoadDemo = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await timetableStudioService.loadDemoDataset();
      setSummary(response.summary);
      setDatasetText(JSON.stringify(emptyDataset, null, 2));
      setStatus("Demo dataset loaded into the v2 timetable model.");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setError("");
    setStatus("");
    try {
      const payload = JSON.parse(datasetText);
      const response = await timetableStudioService.saveDataset(payload);
      setSummary(response.summary);
      setStatus("Dataset saved. You can now generate timetable solutions.");
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
            <h1 className="section-title">Setup Studio</h1>
            <p className="section-subtitle">
              Load a demo dataset or paste structured setup data for degrees, paths, rooms, modules, sessions, and student groups.
            </p>
          </div>
          <div className="studio-actions">
            <button className="ghost-btn" onClick={handleLoadDemo} disabled={loading}>
              Load Demo
            </button>
            <button className="primary-btn" onClick={handleSave} disabled={loading || !parsedPreview}>
              Save Dataset
            </button>
          </div>
        </div>

        {status && <div className="info-banner valid">{status}</div>}
        {error && <div className="error-banner">{error}</div>}

        <div className="studio-grid two-column">
          <section className="studio-card">
            <h2>Dataset JSON</h2>
            <p>Use the v2 schema structure. Durations are in minutes and must be multiples of 30.</p>
            <textarea
              className="studio-textarea"
              value={datasetText}
              onChange={(event) => setDatasetText(event.target.value)}
            />
          </section>

          <section className="studio-card">
            <h2>Quick Readiness</h2>
            <div className="summary-grid">
              {summary ? (
                Object.entries(summary).map(([key, value]) => (
                  <div key={key} className="summary-item">
                    <span>{key.replace(/_/g, " ")}</span>
                    <strong>{value}</strong>
                  </div>
                ))
              ) : (
                <p className="empty-state">No dataset saved yet.</p>
              )}
            </div>
            <div className="schema-notes">
              <h3>Expected collections</h3>
              <ul>
                <li>`degrees`, `paths`, `lecturers`, `rooms`</li>
                <li>`student_groups`, `modules`, `sessions`</li>
                <li>Session records reference lecturers and student groups by `client_key`</li>
              </ul>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default SetupStudio;
