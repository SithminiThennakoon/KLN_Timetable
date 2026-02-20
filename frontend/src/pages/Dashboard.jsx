import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { logout } from '../services/authService';
import '../styles/Dashboard.css';

function Dashboard({ userRole, onLogout }) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('dashboard');

  const handleLogout = () => {
    logout();
    onLogout();
    navigate('/login');
  };

  const stats = [
    { label: 'Total Courses', value: '45', icon: '📚' },
    { label: 'Total Lecturers', value: '32', icon: '👨‍🏫' },
    { label: 'Total Students', value: '1250', icon: '👨‍🎓' },
    { label: 'Total Classrooms', value: '28', icon: '🏫' },
    { label: 'Departments', value: '6', icon: '🏢' },
    { label: 'Generated Timetables', value: '12', icon: '📅' },
  ];

  const quickActions = [
    { title: 'Generate Timetable', desc: 'Create new timetable', icon: '⚡', action: () => navigate('/generate') },
    { title: 'Manage Courses', desc: 'Add/Edit courses', icon: '📖', action: () => navigate('/courses') },
    { title: 'Manage Lecturers', desc: 'Add/Edit lecturers', icon: '👨‍🏫', action: () => navigate('/lecturers') },
    { title: 'Manage Classrooms', desc: 'Add/Edit classrooms', icon: '🏫', action: () => navigate('/classrooms') },
  ];

  const recentActivity = [
    { id: 1, action: 'Generated timetable for Computer Science', time: '2 hours ago', type: 'success' },
    { id: 2, action: 'Added new lecturer Dr. John Smith', time: '5 hours ago', type: 'info' },
    { id: 3, action: 'Updated Mathematics department courses', time: '1 day ago', type: 'warning' },
    { id: 4, action: 'Deleted classroom LB-101', time: '2 days ago', type: 'error' },
  ];

  const renderAdminDashboard = () => (
    <>
      <div className="stats-grid">
        {stats.map((stat, index) => (
          <div key={index} className="stat-card">
            <div className="stat-icon">{stat.icon}</div>
            <div className="stat-content">
              <h3>{stat.value}</h3>
              <p>{stat.label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="quick-actions">
        <h2>Quick Actions</h2>
        <div className="actions-grid">
          {quickActions.map((action, index) => (
            <div key={index} className="action-card" onClick={action.action}>
              <div className="action-icon">{action.icon}</div>
              <h3>{action.title}</h3>
              <p>{action.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="recent-activity">
        <h2>Recent Activity</h2>
        <div className="activity-list">
          {recentActivity.map((activity) => (
            <div key={activity.id} className={`activity-item ${activity.type}`}>
              <div className="activity-dot"></div>
              <div className="activity-content">
                <p>{activity.action}</p>
                <span className="activity-time">{activity.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );

  const renderUserDashboard = () => (
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

      {userRole === 'lecturer' && (
        <div className="dashboard-card">
          <h3>Availability</h3>
          <p>Update your availability</p>
          <button className="card-button">Update</button>
        </div>
      )}
    </div>
  );

  return (
    <div className="dashboard-container">
      <nav className="dashboard-navbar">
        <div className="navbar-brand">
          <h2>⏰ KLN Timetable System</h2>
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
          <h1>
            {userRole === 'admin' ? 'Admin Dashboard' : 
             userRole === 'department_head' ? 'Department Head Dashboard' :
             userRole === 'lecturer' ? 'Lecturer Dashboard' : 'Student Dashboard'}
          </h1>
          <p>Role: <strong>{userRole.toUpperCase()}</strong></p>
        </div>

        {userRole === 'admin' || userRole === 'department_head' ? renderAdminDashboard() : renderUserDashboard()}
      </div>
    </div>
  );
}

export default Dashboard;
