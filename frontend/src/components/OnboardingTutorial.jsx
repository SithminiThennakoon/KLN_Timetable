import React, { useEffect, useRef, useState } from "react";

const STEPS = [
  {
    id: "welcome",
    title: "Welcome to KLN Timetable Studio",
    subtitle: "A guided path from enrolments to timetable",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          This tool is meant to guide you through one clear flow: prepare the data, generate a
          timetable, then inspect the result.
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
            <span className="ob-flow-label">Views</span>
          </div>
        </div>
        <div className="ob-info-box">
          <strong>Fastest route for the demo:</strong> use the guided sample setup in Setup, then
          generate a timetable, then inspect it in Views.
        </div>
      </div>
    ),
  },
  {
    id: "setup",
    title: "Step 1 — Setup",
    subtitle: "Start with student enrolments, then fill the missing teaching details",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          Setup now starts with the student-enrolment CSV. After that, you only add the teaching
          details the CSV cannot provide.
        </p>
        <div className="ob-step-list">
          {[
            "Start Demo with Sample Data for the fastest path",
            "Or choose your own CSV and continue with the import",
            "Add lecturers, rooms, and teaching sessions",
            "Use the final review to catch anything required before generation",
          ].map((item, index) => (
            <div key={item} className="ob-step-item">
              <span className="ob-step-badge">{index + 1}</span>
              <div>
                <strong>{item}</strong>
              </div>
            </div>
          ))}
        </div>
        <div className="ob-tip-box">
          You do not need to build the full faculty structure manually during the demo flow. The
          import supplies the student-side data first.
        </div>
      </div>
    ),
  },
  {
    id: "generate",
    title: "Step 2 — Generate",
    subtitle: "Create timetable options and let the system verify them",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          Once Setup is ready, Generate creates timetable options from the current snapshot and
          checks the result automatically.
        </p>
        <div className="ob-info-box">
          <strong>Keep it simple first:</strong> click <em>Generate Timetable</em>. Only use the
          advanced preferences if you need to narrow a very large result set.
        </div>
      </div>
    ),
  },
  {
    id: "views",
    title: "Step 3 — Views",
    subtitle: "Open the result and switch to lecturer or student mode only when needed",
    content: (
      <div className="ob-step-body">
        <p className="ob-lead">
          Views opens with the default timetable first. You can then switch to lecturer or student
          mode for filtered views and exports.
        </p>
        <div className="ob-tip-box">
          The normal path is: open the timetable, confirm it looks right, then export what you
          need.
        </div>
      </div>
    ),
  },
];

function getFocusableElements(root) {
  if (!root) return [];
  return [...root.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )].filter((el) => !el.hasAttribute("disabled"));
}

function ProgressDots({ total, current, onGoTo }) {
  return (
    <div className="ob-progress-dots" role="tablist" aria-label="Tutorial steps">
      {Array.from({ length: total }).map((_, index) => (
        <button
          key={index}
          type="button"
          className={index === current ? "ob-dot active" : "ob-dot"}
          onClick={() => onGoTo(index)}
          aria-label={`Go to step ${index + 1}`}
        />
      ))}
    </div>
  );
}

function OnboardingTutorial({ onClose, onComplete, initialStep = 0, onStepChange }) {
  const [current, setCurrent] = useState(() =>
    Math.max(0, Math.min(initialStep, STEPS.length - 1))
  );
  const modalRef = useRef(null);
  const contentRef = useRef(null);

  const step = STEPS[current];
  const isFirst = current === 0;
  const isLast = current === STEPS.length - 1;

  useEffect(() => {
    const previous = document.activeElement;
    const focusable = getFocusableElements(modalRef.current);
    if (focusable.length > 0) {
      focusable[0].focus();
    } else {
      modalRef.current?.focus();
    }
    return () => previous?.focus();
  }, []);

  useEffect(() => {
    const handle = (event) => {
      if (event.key === "Tab") {
        const focusable = getFocusableElements(modalRef.current);
        if (focusable.length === 0) {
          event.preventDefault();
          modalRef.current?.focus();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement;
        if (event.shiftKey) {
          if (active === first || !modalRef.current?.contains(active)) {
            event.preventDefault();
            last.focus();
          }
          return;
        }
        if (active === last || !modalRef.current?.contains(active)) {
          event.preventDefault();
          first.focus();
        }
        return;
      }
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key === "ArrowRight" && !isLast) {
        setCurrent((value) => Math.min(value + 1, STEPS.length - 1));
        return;
      }
      if (event.key === "ArrowLeft" && !isFirst) {
        setCurrent((value) => Math.max(value - 1, 0));
      }
    };
    document.addEventListener("keydown", handle);
    return () => document.removeEventListener("keydown", handle);
  }, [isFirst, isLast, onClose]);

  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = 0;
    }
  }, [current]);

  useEffect(() => {
    onStepChange?.(current);
  }, [current, onStepChange]);

  const handleOverlayClick = (event) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="ob-overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Onboarding tutorial"
    >
      <div className="ob-modal" ref={modalRef} tabIndex={-1} role="document">
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

        <div className="ob-content" ref={contentRef}>
          {step.content}
        </div>

        <div className="ob-footer">
          <ProgressDots total={STEPS.length} current={current} onGoTo={setCurrent} />
          <div className="ob-nav-btns">
            <button
              type="button"
              className="ghost-btn ob-nav-btn"
              onClick={() => setCurrent((value) => Math.max(value - 1, 0))}
              disabled={isFirst}
            >
              Back
            </button>
            {isLast ? (
              <button
                type="button"
                className="primary-btn ob-nav-btn"
                onClick={onComplete || onClose}
              >
                Get started
              </button>
            ) : (
              <button
                type="button"
                className="primary-btn ob-nav-btn"
                onClick={() => setCurrent((value) => Math.min(value + 1, STEPS.length - 1))}
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
