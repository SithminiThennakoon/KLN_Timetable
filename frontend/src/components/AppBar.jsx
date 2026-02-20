import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import './AppBar.css';

export default function AppBar() {
  const location = useLocation();
  return (
    <header className="appbar">
      <div className="appbar-title">
        <span className="appbar-icon">🎓</span>
        <div>
          <div className="faculty-title">Faculty of Science</div>
          <div className="faculty-sub">University of Kelaniya - Timetable Generator</div>
        </div>
      </div>
      <nav className="appbar-nav">
        <NavLink to="/dashboard" className={({isActive}) => isActive ? 'active' : ''}>Database</NavLink>
        <NavLink to="/constraints" className={({isActive}) => isActive ? 'active' : ''}>Constraints</NavLink>
        <NavLink to="/generate" className={({isActive}) => isActive ? 'active' : ''}>Generate</NavLink>
        <NavLink to="/view-timetables" className={({isActive}) => isActive ? 'active' : ''}>View Timetables</NavLink>
      </nav>
    </header>
  );
}
