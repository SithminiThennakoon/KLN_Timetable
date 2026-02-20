import React, { useState } from 'react';
import Modal from './Modal';
import './DatabaseManagement.css';

const TABS = [
  { label: 'Batches', key: 'batches' },
  { label: 'Courses', key: 'courses' },
  { label: 'Departments', key: 'departments' },
  { label: 'Rooms', key: 'rooms' },
];

function AddCourseModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Add Course">
      <form className="modal-form">
        <div className="modal-form-row">
          <label>Course Code</label>
          <input placeholder="e.g., PHY101" />
        </div>
        <div className="modal-form-row">
          <label>Type</label>
          <select defaultValue="Theory">
            <option>Theory</option>
            <option>Practical</option>
            <option>Seminar</option>
          </select>
        </div>
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Course Name</label>
          <input placeholder="e.g., Classical Mechanics" />
        </div>
        <div className="modal-form-row">
          <label>Credits</label>
          <input placeholder="3" defaultValue="3" />
        </div>
        <div className="modal-form-row">
          <label>Hours/Week</label>
          <input placeholder="3" defaultValue="3" />
        </div>
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Lecturer</label>
          <select defaultValue="">
            <option value="">Select Lecturer</option>
          </select>
        </div>
        <div className="modal-actions" style={{ flexBasis: '100%' }}>
          <button type="submit" className="save-btn">Save</button>
          <button type="button" className="cancel-btn" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}

function AddFacultyModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Add Faculty">
      <form className="modal-form">
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Name</label>
          <input placeholder="e.g., Dr. John Doe" />
        </div>
        <div className="modal-form-row">
          <label>Department</label>
          <input placeholder="e.g., Physics" />
        </div>
        <div className="modal-form-row">
          <label>Max Hours/Week</label>
          <input placeholder="20" defaultValue="20" />
        </div>
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Email</label>
          <input placeholder="e.g., john.doe@kln.ac.lk" />
        </div>
        <div className="modal-actions" style={{ flexBasis: '100%' }}>
          <button type="submit" className="save-btn">Save</button>
          <button type="button" className="cancel-btn" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}

function AddRoomModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Add Room">
      <form className="modal-form">
        <div className="modal-form-row">
          <label>Room Number</label>
          <input placeholder="e.g., 301" />
        </div>
        <div className="modal-form-row">
          <label>Type</label>
          <select defaultValue="Classroom">
            <option>Classroom</option>
            <option>Lab</option>
            <option>Auditorium</option>
          </select>
        </div>
        <div className="modal-form-row">
          <label>Capacity</label>
          <input placeholder="60" defaultValue="60" />
        </div>
        <div className="modal-form-row">
          <label>Building</label>
          <input placeholder="e.g., Science Block A" />
        </div>
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Available Time</label>
          <input placeholder="9:00 AM - 5:00 PM" defaultValue="9:00 AM - 5:00 PM" />
        </div>
        <div className="modal-actions" style={{ flexBasis: '100%' }}>
          <button type="submit" className="save-btn">Save</button>
          <button type="button" className="cancel-btn" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}

function AddBatchModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Add Batche">
      <form className="modal-form">
        <div className="modal-form-row">
          <label>Batch Name</label>
          <input placeholder="e.g., 2022/2023" />
        </div>
        <div className="modal-form-row">
          <label>Year</label>
          <input placeholder="2022" />
        </div>
        <div className="modal-form-row">
          <label>Semester</label>
          <input placeholder="1" />
        </div>
        <div className="modal-form-row">
          <label>Strength</label>
          <input placeholder="120" />
        </div>
        <div className="modal-form-row" style={{ flexBasis: '100%' }}>
          <label>Courses</label>
          <input placeholder="e.g., PHY101, MAT102" />
        </div>
        <div className="modal-actions" style={{ flexBasis: '100%' }}>
          <button type="submit" className="save-btn">Save</button>
          <button type="button" className="cancel-btn" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}

export default function DatabaseManagement() {
  const [activeTab, setActiveTab] = useState('batches');
  const [showBatch, setShowBatch] = useState(false);
  const [showCourse, setShowCourse] = useState(false);
  const [showFaculty, setShowFaculty] = useState(false);
  const [showRoom, setShowRoom] = useState(false);

  return (
    <div className="db-management">
      <h2>Database Management</h2>
      <p>Manage batches, courses, faculty, and rooms</p>
      <div className="db-tabs">
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={`db-tab${activeTab === tab.key ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="db-tab-content">
        {activeTab === 'batches' && (
          <div>
            <div className="db-table-header">
              <span>Batches</span>
              <button className="add-btn" onClick={() => setShowBatch(true)}>+ Add Batche</button>
            </div>
            <table className="db-table">
              <thead>
                <tr>
                  <th>Batch Name</th>
                  <th>Year</th>
                  <th>Semester</th>
                  <th>Strength</th>
                  <th>Courses</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', color: '#888' }}>
                    No data available. Click "Add" to create.
                  </td>
                </tr>
              </tbody>
            </table>
            <AddBatchModal open={showBatch} onClose={() => setShowBatch(false)} />
          </div>
        )}
        {activeTab === 'courses' && (
          <div>
            <div className="db-table-header">
              <span>Courses</span>
              <button className="add-btn" onClick={() => setShowCourse(true)}>+ Add Course</button>
            </div>
            <table className="db-table">
              <thead>
                <tr>
                  <th>Course Code</th>
                  <th>Course Name</th>
                  <th>Type</th>
                  <th>Credits</th>
                  <th>Lecturer</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', color: '#888' }}>
                    No data available. Click "Add" to create.
                  </td>
                </tr>
              </tbody>
            </table>
            <AddCourseModal open={showCourse} onClose={() => setShowCourse(false)} />
          </div>
        )}
        {activeTab === 'departments' && (
          <div>
            <div className="db-table-header">
              <span>Faculty</span>
              <button className="add-btn" onClick={() => setShowFaculty(true)}>+ Add Faculty</button>
            </div>
            <table className="db-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Department</th>
                  <th>Max Hours/Week</th>
                  <th>Email</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: '#888' }}>
                    No data available. Click "Add" to create.
                  </td>
                </tr>
              </tbody>
            </table>
            <AddFacultyModal open={showFaculty} onClose={() => setShowFaculty(false)} />
          </div>
        )}
        {activeTab === 'rooms' && (
          <div>
            <div className="db-table-header">
              <span>Rooms</span>
              <button className="add-btn" onClick={() => setShowRoom(true)}>+ Add Room</button>
            </div>
            <table className="db-table">
              <thead>
                <tr>
                  <th>Room Number</th>
                  <th>Type</th>
                  <th>Capacity</th>
                  <th>Building</th>
                  <th>Available Time</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', color: '#888' }}>
                    No data available. Click "Add" to create.
                  </td>
                </tr>
              </tbody>
            </table>
            <AddRoomModal open={showRoom} onClose={() => setShowRoom(false)} />
          </div>
        )}
      </div>
    </div>
  );
}
