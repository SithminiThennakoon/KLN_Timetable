import React from 'react';
import './Generate.css';

export default function Generate() {
  return (
    <div className="generate-page">
      <div className="generate-header">
        <span className="generate-icon"> <span style={{fontSize:'1.6rem'}}>⚡</span> </span>
        <div>
          <h2>Generate Timetables</h2>
          <p>Automatically generate timetables for all batches based on your data and constraints</p>
        </div>
      </div>
      <div className="generate-warning">
        <strong>Setup Required</strong>
        <p>Please complete the database setup before generating timetables. You need to add:</p>
        <ul>
          <li>At least one batch</li>
          <li>At least one course</li>
          <li>At least one faculty member</li>
          <li>At least one room</li>
          <li>Assign courses to at least one batch</li>
        </ul>
      </div>
      <div className="generate-stats">
        <h4>Current Setup Statistics</h4>
        <div className="generate-stats-grid">
          <div className="stat-box stat-blue"><span>0</span>Batches</div>
          <div className="stat-box stat-purple"><span>0</span>Courses</div>
          <div className="stat-box stat-green"><span>0</span>Faculty Members</div>
          <div className="stat-box stat-orange"><span>0</span>Rooms</div>
          <div className="stat-box stat-indigo"><span>0</span>Course Assignments</div>
          <div className="stat-box stat-pink"><span>0</span>Total Hours/Week</div>
          <div className="stat-box stat-cyan"><span>5</span>Active Constraints</div>
          <div className="stat-box stat-light"><span>5</span>Working Days</div>
        </div>
      </div>
    </div>
  );
}
