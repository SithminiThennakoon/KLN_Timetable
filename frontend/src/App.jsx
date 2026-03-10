import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import SetupStudio from './pages/SetupStudio.jsx';
import GenerateStudio from './pages/GenerateStudio.jsx';
import ViewStudio from './pages/ViewStudio.jsx';
import './styles/App.css';

import MainNavbar from './components/MainNavbar.jsx';
import OnboardingTutorial from './components/OnboardingTutorial.jsx';
import { useOnboarding } from './hooks/useOnboarding.js';

function App() {
  const { open, dismiss, reopen } = useOnboarding();

  return (
    <Router>
      <MainNavbar onHelp={reopen} />
      <Routes>
         <Route path="/setup" element={<SetupStudio />} />
         <Route path="/generate" element={<GenerateStudio />} />
         <Route path="/views" element={<ViewStudio />} />
         <Route path="/" element={<Navigate to="/setup" />} />
      </Routes>
      {open && <OnboardingTutorial onClose={dismiss} />}
    </Router>
  );
}

export default App;
