import React, { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import "../styles/App.css";
import { useTheme } from "../hooks/useTheme";

const MainNavbar = ({ onStartBasicTour, onStartTechnicalTour }) => {
  const { theme, toggle } = useTheme();
  const [helpMenuOpen, setHelpMenuOpen] = useState(false);
  const helpMenuRef = useRef(null);

  useEffect(() => {
    const handleClickAway = (event) => {
      if (!helpMenuRef.current?.contains(event.target)) {
        setHelpMenuOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setHelpMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickAway);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickAway);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const handleStartBasicTour = () => {
    setHelpMenuOpen(false);
    onStartBasicTour?.();
  };

  const handleStartTechnicalTour = () => {
    setHelpMenuOpen(false);
    onStartTechnicalTour?.();
  };

  return (
    <header className="main-header">
      <div className="main-logo">
        <span className="logo-circle">FS</span>
        <div className="main-title-block">
          <span className="main-title">Faculty of Science</span><br />
          <span className="main-subtitle">University of Kelaniya - Timetable Studio</span>
        </div>
      </div>
      <div className="header-right">
        <nav className="main-menu" data-tour="nav-pages">
          <NavLink to="/setup" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Setup</NavLink>
          <NavLink to="/generate" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Generate</NavLink>
          <NavLink to="/views" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Views</NavLink>
        </nav>
        <div className="help-menu-shell" ref={helpMenuRef} data-tour="nav-help">
          <button
            className="help-btn"
            onClick={() => setHelpMenuOpen((prev) => !prev)}
            title="Open walkthrough menu"
            aria-label="Open walkthrough menu"
            aria-expanded={helpMenuOpen}
            aria-haspopup="menu"
          >
            ?
          </button>
          {helpMenuOpen ? (
            <div className="help-menu-popover" role="menu" aria-label="Walkthrough menu">
              <button
                type="button"
                className="help-menu-item"
                onClick={handleStartBasicTour}
                role="menuitem"
              >
                <strong>Start basic tour</strong>
                <span>Beginner walkthrough across Setup, Generate, and Views.</span>
              </button>
              <button
                type="button"
                className="help-menu-item"
                onClick={handleStartTechnicalTour}
                role="menuitem"
              >
                <strong>Start technical tour</strong>
                <span>Advanced workflow and model concepts for technical users.</span>
              </button>
            </div>
          ) : null}
        </div>
        <button
          className="theme-toggle"
          onClick={toggle}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
};

export default MainNavbar;
