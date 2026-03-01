import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DatabaseDashboard from './pages/DatabaseDashboard.jsx';
import Constraints from './pages/Constraints.jsx';
import GeneratePage from './pages/GeneratePage.jsx';
import ViewTimetable from './pages/ViewTimetable.jsx';
import './styles/App.css';

import MainNavbar from './components/MainNavbar.jsx';

function App() {
  return (
    <Router>
      <MainNavbar />
      <Routes>
         <Route path="/database" element={<DatabaseDashboard />} />
         <Route path="/constraints" element={<Constraints />} />
         <Route path="/generate" element={<GeneratePage />} />
         <Route path="/view" element={<ViewTimetable />} />
         <Route path="/" element={<Navigate to="/database" />} />
      </Routes>
    </Router>
  );
}

export default App;
