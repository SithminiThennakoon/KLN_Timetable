import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DatabaseManagement from './pages/DatabaseManagement_simple';
import './styles/App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/database" element={<DatabaseManagement />} />
        <Route path="/" element={<Navigate to="/database" />} />
      </Routes>
    </Router>
  );
}

export default App;
