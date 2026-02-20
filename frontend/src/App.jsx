import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AdminDashboard from './pages/AdminDashboard.jsx';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [userRole, setUserRole] = useState('admin');

  const handleLogout = () => {
    setIsAuthenticated(false);
    setUserRole('');
  };

  return (
    <Routes>
      <Route 
        path="/" 
        element={<Navigate to="/dashboard" />} 
      />
      <Route 
        path="/dashboard" 
        element={<AdminDashboard onLogout={handleLogout} userRole={userRole} />} 
      />
    </Routes>
  );
}

function AppWrapper() {
  return (
    <Router>
      <App />
    </Router>
  );
}

export default AppWrapper;
