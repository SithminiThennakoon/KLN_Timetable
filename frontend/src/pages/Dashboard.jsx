import React from 'react';
import { useNavigate } from 'react-router-dom';
import { logout } from '../services/authService';
import '../styles/Dashboard.css';

function Dashboard({ userRole, onLogout }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    onLogout();
    navigate('/login');
  };

  return (
    <div className="dashboard-container">
      <nav className="dashboard-navbar">
        <div className="navbar-brand">
          <h2>KLN Timetable System</h2>
        </div>
        <div className="navbar-user">
          <span className="user-role">{userRole}</span>
          <button onClick={handleLogout} className="logout-button">
            Logout
          </button>
        </div>
      </nav>

      <div className="dashboard-content">
        <div className="welcome-section">
          <h1>Welcome to KLN Timetable System</h1>
          <p>Role: <strong>{userRole.toUpperCase()}</strong></p>
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-card">
            <h3>My Timetable</h3>
            <p>View your personal timetable</p>
            <button className="card-button">View</button>
          </div>

          <div className="dashboard-card">
            <h3>Faculty Timetable</h3>
            <p>View the complete faculty timetable</p>
            <button className="card-button">View</button>
          </div>

          {(userRole === 'admin' || userRole === 'department_head') && (
            <div className="dashboard-card">
              <h3>Manage Timetable</h3>
              <p>Generate and manage timetables</p>
              <button className="card-button">Manage</button>
            </div>
          )}

          {userRole === 'lecturer' && (
            <div className="dashboard-card">
              <h3>Availability</h3>
              <p>Update your availability</p>
              <button className="card-button">Update</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
