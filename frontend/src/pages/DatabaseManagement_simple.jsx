import React, { useState } from 'react';
import '../styles/DatabaseManagement.css';

const DatabaseManagement = () => {
  const [activeTab, setActiveTab] = useState('batch');

  const tabs = [
    { id: 'batch', label: 'Batch' },
    { id: 'courses', label: 'Courses' },
    { id: 'departments', label: 'Departments' },
    { id: 'rooms', label: 'Rooms' }
  ];

  return (
    <div className="database-management">
      <div className="header">
        <div className="logo">
          <img src="https://placehold.co/40x40/4a5568/ffffff?text=FS" alt="Faculty of Science logo" />
          <div className="title">
            <h1>Faculty of Science</h1>
            <p>University of Kelaniya - Timetable Generator</p>
          </div>
        </div>
        <nav className="main-nav">
          <ul>
            <li className="active">Database</li>
            <li>Constraints</li>
            <li>Generate</li>
            <li>View</li>
          </ul>
        </nav>
      </div>

      <div className="content">
        <div className="section-header">
          <h2>Database Management</h2>
          <p>Manage batches, courses, faculty, and rooms</p>
        </div>

        <div className="tabs">
          <div className="tab-container">
            {tabs.map(tab => (
              <button
                key={tab.id}
                className={`tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="tab-content">
            {activeTab === 'batch' && (
              <div className="batches-section">
                <div className="section-header">
                  <h3>Batches</h3>
                  <button className="add-button">+ Add Batch</button>
                </div>
                <div className="table-container">
                  <table className="batches-table">
                    <thead>
                      <tr>
                        <th>Batch Name</th>
                        <th>Year</th>
                        <th>Semester</th>
                        <th>Strength</th>
                        <th>Courses</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colSpan="5" className="no-data">
                          No data available. Click "Add" to create.
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'courses' && (
              <div className="courses-section">
                <div className="section-header">
                  <h3>Courses</h3>
                  <button className="add-button">+ Add Course</button>
                </div>
                <div className="table-container">
                  <table className="courses-table">
                    <thead>
                      <tr>
                        <th>Courses</th>
                        <th>Courses</th>
                        <th>Courses</th>
                        <th>Courses</th>
                        <th>Courses</th>
                        <th>Courses</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colSpan="6" className="no-data">
                          No data available. Click "Add" to create.
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'departments' && (
              <div className="departments-section">
                <div className="section-header">
                  <h3>Departments</h3>
                  <button className="add-button">+ Add Department</button>
                </div>
                <div className="table-container">
                  <table className="departments-table">
                    <thead>
                      <tr>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                        <th>Departments</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colSpan="6" className="no-data">
                          No data available. Click "Add" to create.
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'rooms' && (
              <div className="rooms-section">
                <div className="section-header">
                  <h3>Rooms</h3>
                  <button className="add-button">+ Add Room</button>
                </div>
                <div className="table-container">
                  <table className="rooms-table">
                    <thead>
                      <tr>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                        <th>Rooms</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td colSpan="6" className="no-data">
                          No data available. Click "Add" to create.
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DatabaseManagement;