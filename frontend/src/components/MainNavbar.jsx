import React from "react";
import { NavLink } from "react-router-dom";
import "../styles/App.css";
import { useTheme } from "../hooks/useTheme";

const MainNavbar = ({ onHelp }) => {
  const { theme, toggle } = useTheme();
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
        <button
          className="help-btn"
          onClick={onHelp}
          title="Open tutorial"
          aria-label="Open tutorial"
          data-tour="nav-help"
        >
          ?
        </button>
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
