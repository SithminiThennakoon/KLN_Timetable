import React, { useState } from "react";
import "../styles/ConstraintsPage.css";

const defaultConstraints = [
  { id: "no_lunch", label: "Block lunch hour (12:00-13:00)", enabled: true },
  { id: "weekday_only", label: "Weekdays only (Mon-Fri)", enabled: true },
  { id: "room_capacity", label: "Room capacity must fit group", enabled: true },
  { id: "lecturer_conflict", label: "No lecturer overlap", enabled: true },
  { id: "pathway_conflict", label: "No pathway overlap", enabled: true },
  { id: "lab_type", label: "Lab type must match practical", enabled: true },
  { id: "year_restriction", label: "Room year restrictions enforced", enabled: true },
  { id: "concurrent_split", label: "Concurrent split groups aligned", enabled: true },
];

function Constraints() {
  const [constraints, setConstraints] = useState(defaultConstraints);
  const [status, setStatus] = useState("");

  const toggleConstraint = (id) => {
    setConstraints((prev) =>
      prev.map((item) => (item.id === id ? { ...item, enabled: !item.enabled } : item))
    );
  };

  const handleSave = () => {
    setStatus("Constraints saved (local UI only). Backend toggle support coming next.");
  };

  return (
    <div className="page-shell">
      <div className="panel constraints-panel">
        <div className="constraints-header">
          <div>
            <h1 className="section-title">Constraints</h1>
            <p className="section-subtitle">
              Control which rules the solver enforces.
            </p>
          </div>
          <button className="primary-btn" onClick={handleSave}>Save</button>
        </div>

        {status && <div className="info-banner">{status}</div>}

        <div className="constraints-grid">
          {constraints.map((constraint) => (
            <label key={constraint.id} className={`constraint-card ${constraint.enabled ? "enabled" : ""}`}>
              <input
                type="checkbox"
                checked={constraint.enabled}
                onChange={() => toggleConstraint(constraint.id)}
              />
              <span>{constraint.label}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Constraints;
