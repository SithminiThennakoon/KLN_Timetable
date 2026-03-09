# Local AGENTS Instructions

**IMPORTANT: For this project, ignore the global AGENTS.md file located at `~/.config/opencode/AGENTS.md`**

This repository uses local agent instructions that are specific to the KLN Timetable System project structure and workflow.

---

## Project-Specific Notes

- This is a timetable management system for University of Kelaniya
- Uses React 19 + Vite frontend, FastAPI backend, MySQL database
- Authentication system has legacy tables (admin_login, student_login) with plain text passwords
- New users table uses bcrypt hashed passwords
- Main branch: dev (not main)
