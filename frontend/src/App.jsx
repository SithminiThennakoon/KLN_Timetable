import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import SetupStudio from './pages/SetupStudio.jsx';
import GenerateStudio from './pages/GenerateStudio.jsx';
import ViewStudio from './pages/ViewStudio.jsx';
import './styles/App.css';

import MainNavbar from './components/MainNavbar.jsx';
import OnboardingTutorial from './components/OnboardingTutorial.jsx';
import { onboardingTourSteps } from './components/onboardingTourSteps.js';
import { useOnboarding } from './hooks/useOnboarding.js';

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { open, close, complete, reopen, currentStep, updateStep } = useOnboarding();
  const safeCurrentStep = Math.max(0, Math.min(currentStep, onboardingTourSteps.length - 1));
  const currentTourStep = onboardingTourSteps[safeCurrentStep] || onboardingTourSteps[0];

  useEffect(() => {
    if (!open) {
      return;
    }
    if (!currentTourStep?.route || currentTourStep.route === location.pathname) {
      return;
    }
    navigate(currentTourStep.route);
  }, [currentTourStep, location.pathname, navigate, open]);

  const handleComplete = () => {
    complete();
    navigate('/setup');
  };

  return (
    <>
      <MainNavbar onHelp={reopen} />
      <Routes>
         <Route path="/setup" element={<SetupStudio />} />
         <Route path="/generate" element={<GenerateStudio />} />
         <Route path="/views" element={<ViewStudio />} />
         <Route path="/" element={<Navigate to="/setup" />} />
      </Routes>
      {open && (
        <OnboardingTutorial
          steps={onboardingTourSteps}
          currentStep={safeCurrentStep}
          onClose={close}
          onComplete={handleComplete}
          onStepChange={updateStep}
        />
      )}
    </>
  );
}

function App() {
  return (
    <Router>
      <AppShell />
    </Router>
  );
}

export default App;
