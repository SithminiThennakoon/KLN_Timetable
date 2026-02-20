import React from 'react';
import AppBar from '../components/AppBar';
import DatabaseManagement from '../components/DatabaseManagement';
import '../styles/Dashboard.css';

function Dashboard({ userRole, onLogout }) {
  return (
    <div style={{ background: '#f5f6fa', minHeight: '100vh' }}>
      <AppBar />
      <main>
        <DatabaseManagement />
      </main>
    </div>
  );
}

export default Dashboard;
