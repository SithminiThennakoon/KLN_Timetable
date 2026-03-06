import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import SetupStudio from './pages/SetupStudio.jsx';
import GenerateStudio from './pages/GenerateStudio.jsx';
import ViewStudio from './pages/ViewStudio.jsx';
import './styles/App.css';

import MainNavbar from './components/MainNavbar.jsx';

function App() {
  return (
    <Router>
      <MainNavbar />
      <Routes>
         <Route path="/setup" element={<SetupStudio />} />
         <Route path="/generate" element={<GenerateStudio />} />
         <Route path="/views" element={<ViewStudio />} />
         <Route path="/" element={<Navigate to="/setup" />} />
      </Routes>
    </Router>
  );
}

export default App;
