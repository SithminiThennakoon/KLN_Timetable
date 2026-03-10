import React, { useEffect, useRef, useState } from "react";

// ─── Tutorial step definitions ─────────────────────────────────────────────────

const STEPS = [
  {
    id: "welcome",
    title: "Welcome to KLN Timetable Studio",
    subtitle: "University of Kelaniya — Faculty of Science",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          This tool generates valid, conflict-free weekly timetables for the entire Faculty of
          Science. It handles room assignments, lecturer scheduling, and student cohort splits
          automatically — but it needs you to describe the faculty first.
        </p>
        <div className="ob-flow-diagram">
          <div className="ob-flow-node ob-flow-active">
            <span className="ob-flow-num">1</span>
            <span className="ob-flow-label">Setup</span>
          </div>
          <div className="ob-flow-arrow">→</div>
          <div className="ob-flow-node">
            <span className="ob-flow-num">2</span>
            <span className="ob-flow-label">Generate</span>
          </div>
          <div className="ob-flow-arrow">→</div>
          <div className="ob-flow-node">
            <span className="ob-flow-num">3</span>
            <span className="ob-flow-label">View</span>
          </div>
        </div>
        <div className="ob-info-box">
          <strong>Three pages, in order.</strong> Start with Setup to enter all faculty data.
          Then Generate to run the solver and find valid timetables. Then View to inspect,
          filter by lecturer or degree, and export the final schedule.
        </div>
        <p className="ob-note">
          Everything is saved to the backend as you go. You can close this tutorial at any time
          and reopen it using the <strong>Help</strong> button in the top navigation bar.
        </p>
      </div>
    ),
  },
  {
    id: "setup-overview",
    title: "Step 1 — Setup Studio",
    subtitle: "7 wizard steps, one validated dataset",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          The Setup page is a guided 7-step wizard. Each step unlocks the next. You must complete
          them roughly in order because later steps depend on earlier ones.
        </p>
        <div className="ob-step-list">
          {[
            { num: 1, name: "Structure", desc: "Degrees and year-specific subject paths" },
            { num: 2, name: "Lecturers", desc: "Teaching staff who can be assigned to sessions" },
            { num: 3, name: "Rooms", desc: "All teaching spaces the solver may use" },
            { num: 4, name: "Student Cohorts", desc: "Group sizes derived from degree/year/path structure" },
            { num: 5, name: "Modules", desc: "The semester subjects that sessions belong to" },
            { num: 6, name: "Sessions", desc: "The actual weekly classes the solver must schedule" },
            { num: 7, name: "Review & Save", desc: "Validate everything, then save for generation" },
          ].map((s) => (
            <div key={s.num} className="ob-step-item">
              <span className="ob-step-badge">{s.num}</span>
              <div>
                <strong>{s.name}</strong>
                <span className="ob-step-desc">{s.desc}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="ob-tip-box">
          <strong>Shortcut:</strong> Use <em>Load Realistic Demo</em> or <em>Load Tuned Demo</em> at
          the top of the Setup page to pre-fill everything with real Faculty of Science data. This is
          the fastest way to see a working timetable.
        </div>
      </div>
    ),
  },
  {
    id: "structure",
    title: "Step 1a — Structure: Degrees and Paths",
    subtitle: "The academic skeleton everything else is built on",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          A <strong>Degree</strong> is a programme (e.g. Physical Science). A <strong>Path</strong>
          is a year-specific subject combination within that degree (e.g. Physics-Chemistry-Maths
          in Year 1).
        </p>

        <div className="ob-field-group">
          <h4>Degree fields</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Code</span>
              <span className="ob-field-desc">
                Short abbreviation used throughout the app. Example: <code>PS</code>, <code>ECS</code>,{" "}
                <code>ENCM</code>. Keep it brief — it appears on timetable cards.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Name</span>
              <span className="ob-field-desc">
                Full programme name. Example: <em>Physical Science</em>,{" "}
                <em>Electronics and Computer Science</em>.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Duration</span>
              <span className="ob-field-desc">
                Number of years in the programme (1–6). This controls how many year-cohorts are
                created automatically. PS and BS are 3 years; ECS, AC, ENCM, PE are 4 years.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Intake label</span>
              <span className="ob-field-desc">
                A human-readable label for the intake group. Example: <em>PS Intake</em>. Used in
                timetable view headers and exports.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-field-group">
          <h4>Path fields</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Degree</span>
              <span className="ob-field-desc">
                Which degree this path belongs to.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Year</span>
              <span className="ob-field-desc">
                Which year of study this path applies to. Year 1 students of PS may take
                PHY-CHEM-MATH; Year 2 may split into PHY-MATH-STAT.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Code</span>
              <span className="ob-field-desc">
                Short path code. Example: <code>PHY-CHEM-MATH</code>. Appears on cohort chips and
                timetable labels.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Name</span>
              <span className="ob-field-desc">
                Full path name. Example: <em>Physics Chemistry Mathematics</em>.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-info-box">
          <strong>No paths needed for direct-entry degrees.</strong> If a degree has no subject
          choice (e.g. ECS Year 1 is always the same), leave paths empty for that year. One{" "}
          <em>General</em> cohort is created automatically.
        </div>
      </div>
    ),
  },
  {
    id: "lecturers",
    title: "Step 1b — Lecturers",
    subtitle: "Teaching staff who can be assigned to weekly sessions",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          Lecturers are the people you assign to sessions. The solver enforces that no lecturer
          is scheduled in two places at the same time. Their names also appear in the{" "}
          <em>Lecturer</em> view on the Views page.
        </p>

        <div className="ob-field-group">
          <h4>Lecturer fields</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Name</span>
              <span className="ob-field-desc">
                Full name as it should appear on timetable cards and exports. Example:{" "}
                <em>Dr. Perera</em>, <em>Prof. Fernando</em>.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Email</span>
              <span className="ob-field-desc">
                Optional. Not used by the solver — stored for reference and future features.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-warn-box">
          <strong>Lecturers are optional at save time</strong> — the dataset can be saved without
          them. However, any session with no lecturer assigned will show a warning in the Review
          step, and the timetable cards in Views will display "Unassigned".
        </div>

        <div className="ob-tip-box">
          You can assign multiple lecturers to a single session (e.g. a joint lecture). When
          parallel room splitting is used, you should assign at least two lecturers — one per room
          group.
        </div>
      </div>
    ),
  },
  {
    id: "rooms",
    title: "Step 1c — Rooms",
    subtitle: "Every teaching space the solver is allowed to use",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          The solver assigns sessions to rooms automatically. It matches sessions to rooms based
          on type, capacity, and optional restrictions. You must enter every room the faculty
          uses — the solver cannot invent rooms.
        </p>

        <div className="ob-field-group">
          <h4>Room fields</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Name</span>
              <span className="ob-field-desc">
                The room identifier shown on timetable cards. Example: <em>A7 Hall 1</em>,{" "}
                <em>Physics Lab 1</em>. Make it recognisable at a glance.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Capacity</span>
              <span className="ob-field-desc">
                Maximum number of students the room can hold. The solver will not assign a session
                to a room smaller than the attending cohort — unless a split limit is set on the
                session.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Room type</span>
              <span className="ob-field-desc">
                <strong>lecture</strong> — large hall for lectures and tutorials.{" "}
                <strong>lab</strong> — specialist lab space.{" "}
                <strong>seminar</strong> — smaller discussion room. Sessions can request a specific
                type; only matching rooms are considered.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Lab type</span>
              <span className="ob-field-desc">
                Only for lab rooms. A free-text label that must match the session's{" "}
                <em>Required lab type</em> field exactly. Example: <code>physics</code>,{" "}
                <code>chemistry</code>, <code>computing</code>. Leave blank for non-specialist labs.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Location</span>
              <span className="ob-field-desc">
                Building or block name shown on timetable cards. Example:{" "}
                <em>A7 Building</em>, <em>Science Labs Block</em>. Required.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Year restriction</span>
              <span className="ob-field-desc">
                Optional. If set to <code>1</code>, only Year 1 sessions are placed here. Use
                this for rooms physically allocated to a specific year group. Leave blank for
                unrestricted rooms.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-info-box">
          Use <em>Duplicate Room</em> to quickly create similar rooms (e.g. Physics Lab 1 and
          Physics Lab 2 share the same type and location).
        </div>
      </div>
    ),
  },
  {
    id: "cohorts",
    title: "Step 1d — Student Cohorts",
    subtitle: "Who attends what, and in what numbers",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          Cohorts are the student groups the solver tracks for capacity and clash detection.
          There are two kinds: <strong>base cohorts</strong> (auto-created from your
          degree/year/path structure) and <strong>override groups</strong> (created manually for
          electives or special attendance patterns).
        </p>

        <div className="ob-field-group">
          <h4>Base cohorts — what to enter</h4>
          <p className="ob-sub">
            These are generated automatically from your degrees, years, and paths. You only need
            to fill in two things:
          </p>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Cohort name</span>
              <span className="ob-field-desc">
                Auto-filled based on degree code, year, and path. Example: <em>PS Y1 PHY-CHEM-MATH</em>.
                You can rename it for clarity — the name appears on session cards and exports.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Student count</span>
              <span className="ob-field-desc">
                How many students are in this cohort. This is the number the solver checks
                against room capacity. Use the actual enrollment figure from the registry.
                Example: <code>87</code> for PS Year 1 PHY-CHEM-MATH.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-field-group">
          <h4>Override groups — when to add them</h4>
          <p className="ob-sub">
            Only add an override group when a subset of a cohort has a <em>different attendance
            pattern</em> — not just when the room is too small (use split limits for that instead).
          </p>
          <div className="ob-example-box">
            <strong>Good use of an override group:</strong> 40 out of 87 PS Y2 students take
            an optional Statistics elective. Create a 40-student override group and assign only
            them to the Statistics session.
          </div>
          <div className="ob-example-box ob-example-bad">
            <strong>Not needed:</strong> Your lecture hall holds 60 but 87 students need to
            attend. Use <em>Split limit per room</em> on the session instead — the solver
            auto-creates the split groups internally.
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "modules",
    title: "Step 1e — Modules",
    subtitle: "The academic subjects that sessions are grouped under",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          A <strong>module</strong> is a course unit — e.g. <em>Mechanics</em> or{" "}
          <em>Organic Chemistry</em>. Sessions are children of modules. The module provides
          the subject identity; the session provides the scheduling details.
        </p>

        <div className="ob-field-group">
          <h4>Module fields</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Code</span>
              <span className="ob-field-desc">
                The module code used in timetable views and exports. Example: <code>PS1101</code>,{" "}
                <code>ECS2203</code>. Shown prominently on session cards.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Name</span>
              <span className="ob-field-desc">
                Full module name. Example: <em>Mechanics and Properties of Matter</em>.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Subject</span>
              <span className="ob-field-desc">
                The subject area this module belongs to. Example: <em>Physics</em>,{" "}
                <em>Mathematics</em>. Used for grouping in views.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Year</span>
              <span className="ob-field-desc">
                Which year of study this module is taught in (1–4). Modules are filtered by year
                when building student views.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Semester</span>
              <span className="ob-field-desc">
                Semester 1 or Semester 2. The solver generates a timetable per semester — make
                sure every session's module is in the correct semester.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Full-year module</span>
              <span className="ob-field-desc">
                Check this if the module runs across both semesters. Sessions under a full-year
                module are included in both semester timetables.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-tip-box">
          Use <em>Create Semester 1 Module Shells</em> to instantly generate one placeholder
          module per degree/year combination for that semester. Fill in the real codes and names
          afterwards.
        </div>
      </div>
    ),
  },
  {
    id: "sessions",
    title: "Step 1f — Sessions",
    subtitle: "The actual weekly classes the solver must schedule",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          A <strong>session</strong> is one recurring weekly class — a lecture, tutorial, or lab.
          This is what the solver places into time slots. Every session must be linked to a module,
          given a room type requirement, assigned at least one cohort, and (recommended) a lecturer.
        </p>

        <div className="ob-field-group">
          <h4>Core session fields</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Module</span>
              <span className="ob-field-desc">
                Which module this session belongs to. The module code appears on timetable cards.
                One module can have multiple sessions (e.g. a lecture and a tutorial).
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Name</span>
              <span className="ob-field-desc">
                Descriptive label shown on timetable cards. Keep it short. Example:{" "}
                <em>Mechanics Lecture</em>, <em>Organic Chemistry Lab</em>.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Type</span>
              <span className="ob-field-desc">
                Free-text session type. Conventional values: <code>lecture</code>,{" "}
                <code>tutorial</code>, <code>lab</code>. The timetable card colour (blue vs teal)
                is driven by whether the session name or type contains "lab".
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Duration</span>
              <span className="ob-field-desc">
                Length in minutes. Must be a positive multiple of 30. The solver works in 30-minute
                slots. Common values: <code>60</code> (1 h), <code>90</code> (1.5 h),{" "}
                <code>120</code> (2 h). Labs are typically 120 minutes.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Occurrences / week</span>
              <span className="ob-field-desc">
                How many times per week this session runs. Almost always <code>1</code>. Set to{" "}
                <code>2</code> only if the same session genuinely occurs twice a week (e.g. a
                second separate lab rotation).
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Required room type</span>
              <span className="ob-field-desc">
                Which type of room this session needs. <strong>lecture</strong> — any lecture hall.{" "}
                <strong>lab</strong> — a lab room (further filtered by lab type if set).{" "}
                <strong>seminar</strong> — small group room. Leave blank for no restriction.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Also counts as modules</span>
              <span className="ob-field-desc">
                Advanced. If this session simultaneously satisfies attendance for multiple modules
                (e.g. a combined lecture), select those modules here. Leave empty in almost all
                cases.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-field-group">
          <h4>Advanced options</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Specific room</span>
              <span className="ob-field-desc">
                Pin this session to one particular room (overrides room type matching). Use only
                when a session must always happen in a specific space — e.g. a dedicated computing
                lab.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Required lab type</span>
              <span className="ob-field-desc">
                Only for lab sessions. Must match a room's Lab type field exactly. Example:{" "}
                <code>chemistry</code> will only match rooms labelled <code>chemistry</code>.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Split limit per room</span>
              <span className="ob-field-desc">
                Maximum students per room for this session. If the attending cohort exceeds this,
                the solver automatically divides them into internal groups and schedules each group
                separately. You do not need to create override groups for this — it is handled
                internally.
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Same-time parallel rooms</span>
              <span className="ob-field-desc">
                When a split occurs, run all room groups at the same time (parallel delivery).
                Requires at least two lecturers assigned. If unchecked, split groups are placed
                at different times (sequential delivery).
              </span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Notes</span>
              <span className="ob-field-desc">
                Free text for anything the solver does not use — internal comments, scheduling
                requests to share with colleagues.
              </span>
            </div>
          </div>
        </div>

        <div className="ob-field-group">
          <h4>Lecturers and Attending cohorts</h4>
          <p className="ob-sub">
            These are checkboxes at the bottom of each session card. Tick every lecturer who
            delivers this session and every cohort whose students attend it.
          </p>
          <div className="ob-warn-box">
            <strong>At least one cohort is required.</strong> Sessions with no cohort are a
            blocking error and cannot be saved. A session with no lecturer is allowed but will
            show a warning.
          </div>
          <div className="ob-tip-box">
            Use <em>Copy Lecturers + Cohorts To Module Set</em> to broadcast the same
            lecturer/cohort selection from one session to all other sessions under the same
            module. Useful when a module has a lecture, tutorial, and lab that all go to the
            same students.
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "review-save",
    title: "Step 1g — Review & Save",
    subtitle: "Fix blocking issues, then save the validated dataset",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          The Review step shows a full readiness check before you save. There are two levels of
          issue:
        </p>

        <div className="ob-two-col">
          <div className="ob-check-card ob-check-block">
            <strong>Blocking issues</strong>
            <p>
              Must be fixed before the Save button is enabled. Examples: missing degree code,
              room with zero capacity, session with no cohort. Go back to the relevant step and
              correct them.
            </p>
          </div>
          <div className="ob-check-card ob-check-warn">
            <strong>Warnings</strong>
            <p>
              Allowed — the dataset can still be saved. Examples: sessions with no lecturer
              assigned, parallel rooms with fewer than two lecturers. These hint at incomplete
              data but not invalid data.
            </p>
          </div>
        </div>

        <div className="ob-field-group">
          <h4>What the Save action writes to the backend</h4>
          <ul className="ob-checklist">
            <li>All degrees, paths, and duration information</li>
            <li>All lecturers and their email addresses</li>
            <li>All rooms with types, capacities, and restrictions</li>
            <li>All base cohorts (auto-derived) and override groups (manual)</li>
            <li>All modules with semester and year assignments</li>
            <li>All sessions with their advanced delivery options and split limits</li>
          </ul>
        </div>

        <div className="ob-info-box">
          <strong>Saving replaces the entire dataset.</strong> Each save is a full overwrite of
          the stored faculty data. You can save and re-save as many times as needed — generation
          always uses the most recently saved dataset.
        </div>
      </div>
    ),
  },
  {
    id: "generate",
    title: "Step 2 — Generate Timetable Solutions",
    subtitle: "Run the solver and find all valid timetables",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          Once the dataset is saved, go to the <strong>Generate</strong> page. The solver will
          enumerate every valid weekly timetable that satisfies all hard constraints — no room
          clashes, no lecturer double-bookings, no cohort conflicts, all room capacities respected.
        </p>

        <div className="ob-field-group">
          <h4>Nice-to-have (soft) constraints</h4>
          <p className="ob-sub">
            These are optional preferences that filter or rank solutions. They do not invalidate
            timetables on their own — they reduce a large solution set to a more manageable one.
          </p>
          <div className="ob-constraint-list">
            {[
              { key: "Spread sessions across days", desc: "Keeps repeated weekly sessions on different days." },
              { key: "Morning theory", desc: "Lectures and tutorials finish before lunch." },
              { key: "Afternoon practicals", desc: "Labs start after lunch, leaving morning halls free." },
              { key: "Avoid late-afternoon starts", desc: "Sessions begin by 3:00 PM." },
              { key: "Avoid Fridays", desc: "Teaching stays within Monday–Thursday." },
              { key: "Standard block starts", desc: "Sessions begin on faculty block boundaries, not arbitrary half-hours." },
              { key: "Balanced load", desc: "Teaching load spread across the week, not bunched at the start." },
              { key: "Avoid Monday overload", desc: "Monday carries no more sessions than other days." },
            ].map((c) => (
              <div key={c.key} className="ob-constraint-row">
                <strong>{c.key}</strong>
                <span>{c.desc}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="ob-tip-box">
          <strong>Start without constraints</strong> to see how many valid timetables exist.
          If the count is very high (100+), add constraints to narrow it down. If no solutions
          are found with your constraints, the solver suggests which subset of them can be
          satisfied together.
        </div>

        <div className="ob-field-group">
          <h4>After generation</h4>
          <ul className="ob-checklist">
            <li>The result shows total solutions found and up to 5 preview solutions.</li>
            <li>Click <em>Set as Default</em> on the solution you want to use in Views.</li>
            <li>You can re-run generation as many times as you like — old preview solutions are replaced.</li>
          </ul>
        </div>
      </div>
    ),
  },
  {
    id: "views",
    title: "Step 3 — Timetable Views",
    subtitle: "Inspect, filter, and export the generated timetable",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          The Views page shows the default timetable in a day-by-day calendar or agenda layout.
          There are three view modes, toggled at the top of the page.
        </p>

        <div className="ob-two-col">
          <div className="ob-mode-card">
            <strong>Admin</strong>
            <p>Full faculty view — all sessions for all degrees on the selected day, laid out in
            parallel lanes. Use this to spot room and time conflicts and review the full schedule
            at once.</p>
          </div>
          <div className="ob-mode-card">
            <strong>Lecturer</strong>
            <p>Personal timetable for one staff member. Select a lecturer from the dropdown, then
            click Apply. Shows only their sessions. This is the view to share with staff.</p>
          </div>
        </div>
        <div className="ob-mode-card ob-mode-card-wide">
          <strong>Student</strong>
          <p>Timetable for a specific degree and path. Select the degree, then the path (Year 1,
          Year 2, etc.), then click Apply. This is the view to share with students.</p>
        </div>

        <div className="ob-field-group">
          <h4>Layout and density</h4>
          <div className="ob-field-table">
            <div className="ob-field-row">
              <span className="ob-field-name">Calendar</span>
              <span className="ob-field-desc">Visual time-block grid, 08:00–18:00. Click any block to see full session details.</span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Agenda</span>
              <span className="ob-field-desc">Tabular list sorted by time. Easier to scan or print.</span>
            </div>
            <div className="ob-field-row">
              <span className="ob-field-name">Density</span>
              <span className="ob-field-desc">Compact / Comfortable / Expanded — controls how tall session cards are on the calendar.</span>
            </div>
          </div>
        </div>

        <div className="ob-field-group">
          <h4>Export formats</h4>
          <div className="ob-field-table">
            <div className="ob-field-row"><span className="ob-field-name">PDF</span><span className="ob-field-desc">One-page timetable for the selected day — ready to print or share.</span></div>
            <div className="ob-field-row"><span className="ob-field-name">XLSX</span><span className="ob-field-desc">Full workbook: summary, grid view, and detailed session list.</span></div>
            <div className="ob-field-row"><span className="ob-field-name">CSV</span><span className="ob-field-desc">Raw session data for import into other tools.</span></div>
            <div className="ob-field-row"><span className="ob-field-name">PNG</span><span className="ob-field-desc">Image snapshot of the calendar for the selected day.</span></div>
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "tips",
    title: "Common gotchas and tips",
    subtitle: "Things that often trip up first-time users",
    content: (
      <div className="ob-step-body">
        <div className="ob-gotcha-list">
          <div className="ob-gotcha">
            <span className="ob-gotcha-icon">!</span>
            <div>
              <strong>Duration must be a multiple of 30</strong>
              <p>The solver uses 30-minute time slots. 45-minute sessions are not supported.
              Use 60 or 90 minutes.</p>
            </div>
          </div>
          <div className="ob-gotcha">
            <span className="ob-gotcha-icon">!</span>
            <div>
              <strong>Lab type must match exactly</strong>
              <p>If a session says <code>chemistry</code> and the room says <code>Chemistry</code>
              (capital C), the solver will not match them. Use consistent lowercase strings.</p>
            </div>
          </div>
          <div className="ob-gotcha">
            <span className="ob-gotcha-icon">!</span>
            <div>
              <strong>Sessions with no cohort block saving</strong>
              <p>Every session must target at least one cohort. If you use "Create Starter
              Sessions", the cohort checkboxes start empty — you must tick them before saving.</p>
            </div>
          </div>
          <div className="ob-gotcha">
            <span className="ob-gotcha-icon">!</span>
            <div>
              <strong>No default timetable = Views page is empty</strong>
              <p>After generation, you must click <em>Set as Default</em> on one solution before
              the Views page will show anything.</p>
            </div>
          </div>
          <div className="ob-gotcha">
            <span className="ob-gotcha-icon">✓</span>
            <div>
              <strong>Use demo data to learn the structure</strong>
              <p>Load the Realistic Demo from the Setup page. Inspect how degrees, paths, cohorts,
              modules, and sessions are connected before entering real data.</p>
            </div>
          </div>
          <div className="ob-gotcha">
            <span className="ob-gotcha-icon">✓</span>
            <div>
              <strong>Use "Copy Lecturers + Cohorts To Module Set" freely</strong>
              <p>When a module has a lecture, tutorial, and lab all attended by the same students,
              set up one session fully, then use this button to copy the audience to the others.</p>
            </div>
          </div>
          <div className="ob-gotcha">
            <span className="ob-gotcha-icon">✓</span>
            <div>
              <strong>Saving is safe to do repeatedly</strong>
              <p>Save as often as you like. You can always re-run generation after a save. The
              previous generation results are replaced each run.</p>
            </div>
          </div>
        </div>
      </div>
    ),
  },
];

// ─── Progress dots ─────────────────────────────────────────────────────────────

function ProgressDots({ total, current, onGoTo }) {
  return (
    <div className="ob-progress" role="tablist" aria-label="Tutorial progress">
      {Array.from({ length: total }, (_, i) => (
        <button
          key={i}
          type="button"
          role="tab"
          aria-selected={i === current}
          aria-label={`Step ${i + 1}`}
          className={`ob-dot${i === current ? " ob-dot-active" : i < current ? " ob-dot-done" : ""}`}
          onClick={() => onGoTo(i)}
        />
      ))}
    </div>
  );
}

// ─── Main modal ────────────────────────────────────────────────────────────────

function OnboardingTutorial({ onClose }) {
  const [current, setCurrent] = useState(0);
  const modalRef = useRef(null);
  const contentRef = useRef(null);

  const step = STEPS[current];
  const isFirst = current === 0;
  const isLast = current === STEPS.length - 1;

  // Trap focus inside the modal
  useEffect(() => {
    const prev = document.activeElement;
    modalRef.current?.focus();
    return () => prev?.focus();
  }, []);

  // Keyboard navigation
  useEffect(() => {
    const handle = (e) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowRight" && !isLast) { next(); return; }
      if (e.key === "ArrowLeft" && !isFirst) { prev(); }
    };
    document.addEventListener("keydown", handle);
    return () => document.removeEventListener("keydown", handle);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, isFirst, isLast]);

  // Scroll content to top when step changes
  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = 0;
  }, [current]);

  const next = () => setCurrent((c) => Math.min(c + 1, STEPS.length - 1));
  const prev = () => setCurrent((c) => Math.max(c - 1, 0));
  const goTo = (i) => setCurrent(i);

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      className="ob-overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Onboarding tutorial"
    >
      <div
        className="ob-modal"
        ref={modalRef}
        tabIndex={-1}
        role="document"
      >
        {/* Header */}
        <div className="ob-header">
          <div className="ob-header-text">
            <span className="ob-step-counter">Step {current + 1} of {STEPS.length}</span>
            <h2 className="ob-title">{step.title}</h2>
            {step.subtitle && <p className="ob-subtitle">{step.subtitle}</p>}
          </div>
          <button
            type="button"
            className="ob-close-btn"
            onClick={onClose}
            aria-label="Close tutorial"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M4 4L14 14M14 4L4 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="ob-content" ref={contentRef}>
          {step.content}
        </div>

        {/* Footer */}
        <div className="ob-footer">
          <ProgressDots total={STEPS.length} current={current} onGoTo={goTo} />
          <div className="ob-nav-btns">
            <button
              type="button"
              className="ghost-btn ob-nav-btn"
              onClick={prev}
              disabled={isFirst}
            >
              Back
            </button>
            {isLast ? (
              <button
                type="button"
                className="primary-btn ob-nav-btn"
                onClick={onClose}
              >
                Get started
              </button>
            ) : (
              <button
                type="button"
                className="primary-btn ob-nav-btn"
                onClick={next}
              >
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default OnboardingTutorial;
