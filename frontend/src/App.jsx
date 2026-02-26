import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DatabaseManagement from './pages/DatabaseManagement_simple';
import Constraints from './pages/Constraints.jsx';
import './styles/App.css';

import MainNavbar from './components/MainNavbar.jsx';

function App() {
  return (
    <Router>
      <MainNavbar />
      <Routes>
         <Route path="/database" element={<DatabaseManagement />} />
         <Route path="/constraints" element={<Constraints />} />
         <Route path="/" element={<Navigate to="/database" />} />
      </Routes>
    </Router>
  );
}

export default App;
