import React from 'react';
import './ViewTimetables.css';

export default function ViewTimetables() {
  return (
    <div className="view-timetables-page">
      <div className="view-timetables-header">
        <span className="view-timetables-icon"> <span style={{fontSize:'1.6rem'}}>👁️</span> </span>
        <div>
          <h2>View Timetables</h2>
          <p>View timetables by batch, student, lecturer, or department</p>
        </div>
      </div>
      <div className="view-timetables-empty">
        <span className="view-timetables-eye">👁️</span>
        <div className="view-timetables-empty-title">No Timetables Generated</div>
        <div className="view-timetables-empty-desc">Please go to the Generate page to create timetables for your batches.</div>
      </div>
    </div>
  );
}
