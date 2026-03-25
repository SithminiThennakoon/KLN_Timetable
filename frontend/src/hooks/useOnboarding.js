import { useState } from 'react'
import { BASIC_TOUR, TECHNICAL_TOUR } from '../components/onboardingTourSteps.js'

const BASIC_SEEN_STORAGE_KEY = 'kln-onboarding-basic-seen'
const TECHNICAL_SEEN_STORAGE_KEY = 'kln-onboarding-technical-seen'
const BASIC_STEP_STORAGE_KEY = 'kln-onboarding-basic-step'
const TECHNICAL_STEP_STORAGE_KEY = 'kln-onboarding-technical-step'
const ACTIVE_TOUR_STORAGE_KEY = 'kln-onboarding-active-tour'
const ACTIVE_SESSION_OPEN_KEY = 'kln-onboarding-open-session'
const BASIC_SESSION_DISMISSED_KEY = 'kln-onboarding-basic-dismissed-session'
const TECHNICAL_SESSION_DISMISSED_KEY = 'kln-onboarding-technical-dismissed-session'

function emitOnboardingStateChange(tourType, step, open) {
  if (typeof window === 'undefined') {
    return
  }
  window.dispatchEvent(
    new CustomEvent('kln:onboarding-state-change', {
      detail: { tourType, step, open },
    })
  )
}

function resolveStepStorageKey(tourType) {
  return tourType === TECHNICAL_TOUR ? TECHNICAL_STEP_STORAGE_KEY : BASIC_STEP_STORAGE_KEY
}

function resolveSeenStorageKey(tourType) {
  return tourType === TECHNICAL_TOUR ? TECHNICAL_SEEN_STORAGE_KEY : BASIC_SEEN_STORAGE_KEY
}

function resolveSessionDismissedKey(tourType) {
  return tourType === TECHNICAL_TOUR
    ? TECHNICAL_SESSION_DISMISSED_KEY
    : BASIC_SESSION_DISMISSED_KEY
}

export function useOnboarding() {
  const [currentTour, setCurrentTour] = useState(() => {
    try {
      const stored = localStorage.getItem(ACTIVE_TOUR_STORAGE_KEY)
      return stored === TECHNICAL_TOUR ? TECHNICAL_TOUR : BASIC_TOUR
    } catch {
      return BASIC_TOUR
    }
  })
  const [open, setOpen] = useState(() => {
    try {
      if (sessionStorage.getItem(ACTIVE_SESSION_OPEN_KEY) === '1') {
        return true
      }
      return (
        !localStorage.getItem(BASIC_SEEN_STORAGE_KEY) &&
        !sessionStorage.getItem(BASIC_SESSION_DISMISSED_KEY)
      )
    } catch {
      return true
    }
  })
  const [currentStep, setCurrentStep] = useState(() => {
    try {
      const stored = Number(localStorage.getItem(resolveStepStorageKey(currentTour)))
      return Number.isInteger(stored) && stored >= 0 ? stored : 0
    } catch {
      return 0
    }
  })

  const close = () => {
    try {
      sessionStorage.removeItem(ACTIVE_SESSION_OPEN_KEY)
      sessionStorage.setItem(resolveSessionDismissedKey(currentTour), '1')
    } catch {
      // ignore storage errors
    }
    setOpen(false)
    emitOnboardingStateChange(currentTour, currentStep, false)
  }

  const complete = () => {
    try {
      localStorage.setItem(resolveSeenStorageKey(currentTour), '1')
      sessionStorage.removeItem(ACTIVE_SESSION_OPEN_KEY)
      sessionStorage.removeItem(resolveSessionDismissedKey(currentTour))
    } catch {
      // ignore storage errors
    }
    setOpen(false)
    emitOnboardingStateChange(currentTour, currentStep, false)
  }

  const reopen = (tourType = BASIC_TOUR) => {
    setCurrentTour(tourType)
    setCurrentStep(0)
    try {
      localStorage.setItem(ACTIVE_TOUR_STORAGE_KEY, tourType)
      localStorage.setItem(resolveStepStorageKey(tourType), '0')
      sessionStorage.setItem(ACTIVE_SESSION_OPEN_KEY, '1')
      sessionStorage.removeItem(resolveSessionDismissedKey(tourType))
    } catch {
      // ignore storage errors
    }
    setOpen(true)
    emitOnboardingStateChange(tourType, 0, true)
  }
  const updateStep = (step) => {
    setCurrentStep(step)
    try {
      localStorage.setItem(ACTIVE_TOUR_STORAGE_KEY, currentTour)
      localStorage.setItem(resolveStepStorageKey(currentTour), String(step))
    } catch {
      // ignore storage errors
    }
    emitOnboardingStateChange(currentTour, step, open)
  }

  return { open, close, complete, reopen, currentStep, currentTour, updateStep }
}
