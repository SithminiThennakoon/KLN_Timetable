import React from "react";
import { NavLink } from "react-router-dom";
import "../styles/App.css";

const MainNavbar = () => (
  <header className="main-header">
    <div className="main-logo">
      <span className="logo-circle">FS</span>
      <div className="main-title-block">
        <span className="main-title">Faculty of Science</span><br />
        <span className="main-subtitle">University of Kelaniya - Timetable Generator</span>
      </div>
    </div>
    <nav className="main-menu">
      <NavLink to="/database" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Database</NavLink>
      <NavLink to="/constraints" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Constraints</NavLink>
      <NavLink to="/generate" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>Generate</NavLink>
      <NavLink to="/view" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>View</NavLink>
    </nav>
  </header>
);

export default MainNavbar;
