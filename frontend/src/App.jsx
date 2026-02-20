import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import AppBar from './components/AppBar';
import DatabaseManagement from './components/DatabaseManagement';
import Constraints from './pages/Constraints';
import Generate from './pages/Generate';
import ViewTimetables from './pages/ViewTimetables';
import './App.css';

export default function App() {
  return (
    <Router>
      <AppBar />
      <Routes>
        <Route path="/" element={<DatabaseManagement />} />
        <Route path="/dashboard" element={<DatabaseManagement />} />
        <Route path="/constraints" element={<Constraints />} />
        <Route path="/generate" element={<Generate />} />
        <Route path="/view" element={<ViewTimetables />} />
      </Routes>
    </Router>
  );
}
