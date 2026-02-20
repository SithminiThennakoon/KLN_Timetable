import React, { useState } from 'react';
import Modal from '../components/Modal';
import './Constraints.css';

const constraints = [
  {
    title: 'No Department Conflict',
    desc: 'Prevents multiple classes from the same department being scheduled at the same time',
    enabled: true,
  },
  {
    title: 'Room Availability',
    desc: 'Ensures that a room is not assigned to multiple classes simultaneously',
    enabled: true,
  },
  {
    title: 'Maximum Hours Per Day',
    desc: 'Limits the number of teaching hours per day for faculty members',
    enabled: true,
    config: (
      <div className="constraint-config-row">
        <label>Maximum Hours Per Day</label>
        <input type="number" min="1" max="12" defaultValue={6} />
      </div>
    ),
  },
  {
    title: 'Lunch Break',
    desc: 'Reserves a time slot for lunch break (no classes scheduled during this period)',
    enabled: true,
    config: (
      <div className="constraint-config-row">
        <label>Start Time</label>
        <input type="time" defaultValue="12:00" />
        <label style={{marginLeft:8}}>End Time</label>
        <input type="time" defaultValue="13:00" />
      </div>
    ),
  },
  {
    title: 'No Consecutive Labs',
    desc: 'Prevents scheduling lab sessions back-to-back for the same batch',
    enabled: true,
  },
];

function AddConstraintModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Add Custom Constraint">
      <form className="modal-form">
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Constraint Name</label>
          <input placeholder="e.g., No Friday Classes for First Years" />
        </div>
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Description</label>
          <textarea style={{ minHeight: 60, resize: 'vertical', fontSize: '1rem', padding: '10px 12px', borderRadius: '7px', border: '1.5px solid #e0e3e8', background: '#fafbfc' }} placeholder="Describe what this constraint does..." />
        </div>
        <div style={{ flexBasis: '100%', marginTop: 12, marginBottom: 8 }}>
          <div style={{ background: '#fffde7', border: '1.5px solid #ffe082', borderRadius: '8px', padding: '12px 18px', color: '#b28704', fontSize: '1.05rem' }}>
            <strong>Note:</strong> Custom constraints are informational only. You'll need to manually verify them when reviewing the generated timetable.
          </div>
        </div>
        <div className="modal-actions" style={{ flexBasis: '100%' }}>
          <button type="submit" className="save-btn">Add Constraint</button>
          <button type="button" className="cancel-btn" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Constraints() {
  const [showAdd, setShowAdd] = useState(false);
  return (
    <div className="constraints-page">
      <div className="constraints-header">
        <span className="constraints-icon"> <span style={{fontSize:'1.6rem'}}>🛠️</span> </span>
        <div>
          <h2>Constraints Configuration</h2>
          <p>Configure the rules and constraints that the auto-generation algorithm will follow</p>
        </div>
        <button className="add-constraint-btn" onClick={() => setShowAdd(true)}>+ Add Constraint</button>
      </div>
      <div className="constraints-list">
        {constraints.map((c, i) => (
          <div className="constraint-card" key={i}>
            <div className="constraint-card-row">
              <span className="constraint-check">✔️</span>
              <div className="constraint-info">
                <div className="constraint-title">{c.title}</div>
                <div className="constraint-desc">{c.desc}</div>
                {c.config}
              </div>
              <span className="constraint-enabled">Enabled</span>
            </div>
          </div>
        ))}
      </div>
      <div className="constraints-how">
        <h4>How It Works</h4>
        <ul>
          <li>Enable the constraints you want the system to follow during timetable generation</li>
          <li>The auto-generation algorithm will respect all enabled constraints</li>
          <li>If a valid timetable cannot be generated with the current constraints, try adjusting them</li>
          <li>Some constraints have additional configuration options when enabled</li>
        </ul>
      </div>
      <AddConstraintModal open={showAdd} onClose={() => setShowAdd(false)} />
    </div>
  );
}
