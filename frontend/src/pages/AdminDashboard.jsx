import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { logout } from '../services/authService';
import '../styles/AdminDashboard.css';

function AdminDashboard({ userRole, onLogout }) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('database');
  const [activeSubTab, setActiveSubTab] = useState('batches');

  const handleLogout = () => {
    logout();
    onLogout();
    navigate('/login');
  };

  const handleAddBatch = () => {
    navigate('/add-batch');
  };

  return (
    <div className="admin-dashboard">
      {/* Header */}
      <header className="admin-header">
        <div className="header-content">
          <div className="header-brand">
            <div className="logo">
              <div className="logo-icon">🏫</div>
              <div className="logo-text">
                <h1>Faculty of Science</h1>
                <p>University of Kelaniya - Timetable Generator</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="admin-nav">
        <div className="nav-container">
          <button 
            className={`nav-tab ${activeTab === 'database' ? 'active' : ''}`}
            onClick={() => setActiveTab('database')}
          >
            <span className="nav-icon">📋</span>
            Database
          </button>
          <button 
            className={`nav-tab ${activeTab === 'constraints' ? 'active' : ''}`}
            onClick={() => setActiveTab('constraints')}
          >
            <span className="nav-icon">⚙️</span>
            Constraints
          </button>
          <button 
            className={`nav-tab ${activeTab === 'generate' ? 'active' : ''}`}
            onClick={() => setActiveTab('generate')}
          >
            <span className="nav-icon">⚡</span>
            Generate
          </button>
          <button 
            className={`nav-tab ${activeTab === 'view' ? 'active' : ''}`}
            onClick={() => setActiveTab('view')}
          >
            <span className="nav-icon">👁️</span>
            View Timetables
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <main className="admin-content">
        {/* Database Management Section */}
        <section className="database-section">
          <div className="section-header">
            <h2>Database Management</h2>
            <p>Manage batches, courses, faculty, and rooms</p>
          </div>

          {/* Sub Navigation Tabs */}
          <div className="sub-nav">
            <button 
              className={`sub-tab ${activeSubTab === 'batches' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('batches')}
            >
              <span className="sub-icon">👥</span>
              Batches
            </button>
            <button 
              className={`sub-tab ${activeSubTab === 'courses' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('courses')}
            >
              <span className="sub-icon">📚</span>
              Courses
            </button>
            <button 
              className={`sub-tab ${activeSubTab === 'departments' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('departments')}
            >
              <span className="sub-icon">🏢</span>
              Departments
            </button>
            <button 
              className={`sub-tab ${activeSubTab === 'rooms' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('rooms')}
            >
              <span className="sub-icon">🏫</span>
              Rooms
            </button>
          </div>

          {/* Batches Table */}
          <div className="table-container">
            <div className="table-header">
              <h3>Batches</h3>
              <button 
                className="add-button"
                onClick={handleAddBatch}
              >
                + Add Batche
              </button>
            </div>

            <div className="table-wrapper">
              <table className="batches-table">
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
                    <td colSpan="6" className="no-data">
                      No data available. Click "Add" to create.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </main>

      {/* Help Button */}
      <div className="help-button">
        <button className="help-icon">❓</button>
      </div>
    </div>
  );
}

export default AdminDashboard;