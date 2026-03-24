import React, { useEffect, useMemo, useState } from "react";

const COACHMARK_WIDTH = 320;
const VIEWPORT_PADDING = 16;
const SPOTLIGHT_PADDING = 12;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function findTarget(step) {
  if (!step?.targetId || typeof document === "undefined") {
    return null;
  }
  return document.querySelector(`[data-tour="${step.targetId}"]`);
}

function resolvePlacement(rect, placement, viewportWidth, viewportHeight) {
  const panelWidth = Math.min(COACHMARK_WIDTH, viewportWidth - VIEWPORT_PADDING * 2);
  const panelHeight = 210;
  const spacing = 18;
  const mobile = viewportWidth < 720;

  if (!rect || mobile) {
    return {
      left: VIEWPORT_PADDING,
      top: Math.max(VIEWPORT_PADDING, viewportHeight - panelHeight - VIEWPORT_PADDING),
      width: panelWidth,
      mobile: true,
    };
  }

  const centeredLeft = rect.left + rect.width / 2 - panelWidth / 2;
  const centeredTop = rect.top + rect.height / 2 - panelHeight / 2;

  const placements = {
    right: {
      left: rect.right + spacing,
      top: centeredTop,
    },
    left: {
      left: rect.left - panelWidth - spacing,
      top: centeredTop,
    },
    top: {
      left: centeredLeft,
      top: rect.top - panelHeight - spacing,
    },
    bottom: {
      left: centeredLeft,
      top: rect.bottom + spacing,
    },
  };

  const preferred = placements[placement] || placements.bottom;
  const fitsPreferred =
    preferred.left >= VIEWPORT_PADDING &&
    preferred.left + panelWidth <= viewportWidth - VIEWPORT_PADDING &&
    preferred.top >= VIEWPORT_PADDING &&
    preferred.top + panelHeight <= viewportHeight - VIEWPORT_PADDING;

  const fallbackOrder = ["bottom", "right", "left", "top"];
  const chosen = fitsPreferred
    ? preferred
    : fallbackOrder
        .map((key) => placements[key])
        .find(
          (candidate) =>
            candidate.left >= VIEWPORT_PADDING &&
            candidate.left + panelWidth <= viewportWidth - VIEWPORT_PADDING &&
            candidate.top >= VIEWPORT_PADDING &&
            candidate.top + panelHeight <= viewportHeight - VIEWPORT_PADDING
        ) || preferred;

  return {
    left: clamp(chosen.left, VIEWPORT_PADDING, viewportWidth - panelWidth - VIEWPORT_PADDING),
    top: clamp(chosen.top, VIEWPORT_PADDING, viewportHeight - panelHeight - VIEWPORT_PADDING),
    width: panelWidth,
    mobile: false,
  };
}

function buildSpotlightRect(rect) {
  if (!rect) {
    return null;
  }
  return {
    top: Math.max(rect.top - SPOTLIGHT_PADDING, VIEWPORT_PADDING),
    left: Math.max(rect.left - SPOTLIGHT_PADDING, VIEWPORT_PADDING),
    width: rect.width + SPOTLIGHT_PADDING * 2,
    height: rect.height + SPOTLIGHT_PADDING * 2,
  };
}

function OnboardingTutorial({
  steps,
  currentStep,
  onStepChange,
  onClose,
  onComplete,
}) {
  const [targetRect, setTargetRect] = useState(null);
  const step = steps[currentStep] || steps[0];
  const isFirst = currentStep === 0;
  const isLast = currentStep === steps.length - 1;

  useEffect(() => {
    let frame = null;
    let cancelled = false;
    let didScrollToTarget = false;
    let attempts = 0;

    const measure = () => {
      if (cancelled) {
        return;
      }
      const target = findTarget(step);
      if (target) {
        const nextRect = target.getBoundingClientRect();
        setTargetRect(nextRect);
        if (!didScrollToTarget) {
          target.scrollIntoView?.({ block: "center", inline: "center", behavior: "smooth" });
          didScrollToTarget = true;
        }
        return;
      }
      setTargetRect(null);
      attempts += 1;
      if (attempts < 120) {
        frame = window.requestAnimationFrame(measure);
      }
    };

    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      cancelled = true;
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, [step]);

  useEffect(() => {
    const handle = (event) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key === "ArrowRight") {
        if (isLast) {
          onComplete();
        } else {
          onStepChange(currentStep + 1);
        }
        return;
      }
      if (event.key === "ArrowLeft" && !isFirst) {
        onStepChange(currentStep - 1);
      }
    };

    document.addEventListener("keydown", handle);
    return () => document.removeEventListener("keydown", handle);
  }, [currentStep, isFirst, isLast, onClose, onComplete, onStepChange]);

  const coachmarkBox = useMemo(() => {
    if (typeof window === "undefined") {
      return { left: VIEWPORT_PADDING, top: VIEWPORT_PADDING, width: COACHMARK_WIDTH, mobile: true };
    }
    return resolvePlacement(
      targetRect,
      step?.placement || "bottom",
      window.innerWidth,
      window.innerHeight
    );
  }, [step, targetRect]);

  const spotlightRect = useMemo(() => buildSpotlightRect(targetRect), [targetRect]);

  return (
    <div className="ob-tour-layer" aria-live="polite">
      <div className="ob-tour-dim" />
      {spotlightRect ? (
        <div
          className="ob-tour-spotlight"
          style={{
            top: spotlightRect.top,
            left: spotlightRect.left,
            width: spotlightRect.width,
            height: spotlightRect.height,
          }}
        />
      ) : null}

      <section
        className={`ob-coachmark${coachmarkBox.mobile ? " is-mobile" : ""}`}
        style={{
          top: coachmarkBox.top,
          left: coachmarkBox.left,
          width: coachmarkBox.width,
        }}
        role="dialog"
        aria-label="Onboarding tour"
      >
        <div className="ob-coachmark-header">
          <span className="ob-step-counter">Step {currentStep + 1} of {steps.length}</span>
          <button
            type="button"
            className="ob-close-btn"
            onClick={onClose}
            aria-label="Close tutorial"
          >
            ×
          </button>
        </div>
        <div className="ob-coachmark-body">
          <h2 className="ob-title">{step.title}</h2>
          <p className="ob-subtitle">{step.body}</p>
          {!targetRect ? (
            <p className="ob-target-wait">Preparing the next area of the app…</p>
          ) : null}
        </div>
        <div className="ob-footer">
          <div className="ob-progress-dots" role="tablist" aria-label="Tutorial steps">
            {steps.map((tourStep, index) => (
              <button
                key={tourStep.id}
                type="button"
                className={index === currentStep ? "ob-dot active" : "ob-dot"}
                aria-label={`Go to step ${index + 1}`}
                onClick={() => onStepChange(index)}
              />
            ))}
          </div>
          <div className="ob-nav-btns">
            <button
              type="button"
              className="ghost-btn ob-nav-btn"
              onClick={onClose}
            >
              Skip
            </button>
            <button
              type="button"
              className="ghost-btn ob-nav-btn"
              onClick={() => onStepChange(Math.max(currentStep - 1, 0))}
              disabled={isFirst}
            >
              Back
            </button>
            {isLast ? (
              <button type="button" className="primary-btn ob-nav-btn" onClick={onComplete}>
                Done
              </button>
            ) : (
              <button
                type="button"
                className="primary-btn ob-nav-btn"
                onClick={() => onStepChange(currentStep + 1)}
              >
                Next
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export default OnboardingTutorial;
