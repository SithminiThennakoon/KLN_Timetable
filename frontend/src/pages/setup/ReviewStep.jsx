import React from "react";

export function ReviewStep({ validation, summary }) {
  return (
    <div className="studio-grid two-column">
      {/* ── Readiness ── */}
      <section className="studio-card">
        <h2>Readiness Review</h2>

        {validation.blocking.length === 0 ? (
          <div className="info-banner valid">
            The setup draft is complete enough to save and use for timetable generation.
          </div>
        ) : (
          <div className="error-banner">
            <strong>Fix these blocking issues before saving:</strong>
            <ul>
              {validation.blocking.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        )}

        {validation.warnings.length > 0 && (
          <div className="schema-notes" style={{ marginTop: 16 }}>
            <h3>Warnings you may still want to review</h3>
            <ul>
              {validation.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="schema-notes" style={{ marginTop: 16 }}>
          <h3>What this save action will write</h3>
          <ul>
            <li>Degrees and year-specific paths</li>
            <li>Rooms and lecturers used by the timetable views</li>
            <li>Derived base cohorts plus any override groups</li>
            <li>Modules and weekly sessions with advanced delivery options</li>
            <li>Split limits that can auto-create internal session parts during generation</li>
          </ul>
        </div>
      </section>

      {/* ── Manual entry note ── */}
      <section className="studio-card">
        <h2>Manual Entry First</h2>
        <p>CSV import will come later once the exact university source format is confirmed.</p>

        <div className="schema-notes" style={{ marginTop: 12 }}>
          <h3>Split behaviour</h3>
          <ul>
            <li>
              Use <strong>Split limit per room</strong> when one room cannot fit an entire cohort.
            </li>
            <li>
              The generator can divide a single cohort into internal parts automatically.
            </li>
            <li>
              Create override groups only when attendance itself is different, such as electives.
            </li>
          </ul>
        </div>

        <div className="future-card" style={{ marginTop: 16 }}>
          <strong>Future CSV import</strong>
          <span>Disabled for now. This wizard remains the supported path for setup data.</span>
        </div>
      </section>
    </div>
  );
}
