import { useState } from 'react'

const STORAGE_KEY = 'kln-onboarding-seen'
const STEP_STORAGE_KEY = 'kln-onboarding-step'
const SESSION_DISMISSED_KEY = 'kln-onboarding-dismissed-session'

export function useOnboarding() {
  const [open, setOpen] = useState(() => {
    try {
      return !localStorage.getItem(STORAGE_KEY) && !sessionStorage.getItem(SESSION_DISMISSED_KEY)
    } catch {
      return true
    }
  })
  const [currentStep, setCurrentStep] = useState(() => {
    try {
      const stored = Number(localStorage.getItem(STEP_STORAGE_KEY))
      return Number.isInteger(stored) && stored >= 0 ? stored : 0
    } catch {
      return 0
    }
  })

  const close = () => {
    try {
      sessionStorage.setItem(SESSION_DISMISSED_KEY, '1')
    } catch {
      // ignore storage errors
    }
    setOpen(false)
  }

  const complete = () => {
    try {
      localStorage.setItem(STORAGE_KEY, '1')
      sessionStorage.removeItem(SESSION_DISMISSED_KEY)
    } catch {
      // ignore storage errors
    }
    setOpen(false)
  }

  const reopen = () => {
    setCurrentStep(0)
    try {
      localStorage.setItem(STEP_STORAGE_KEY, '0')
      sessionStorage.removeItem(SESSION_DISMISSED_KEY)
    } catch {
      // ignore storage errors
    }
    setOpen(true)
  }
  const updateStep = (step) => {
    setCurrentStep(step)
    try {
      localStorage.setItem(STEP_STORAGE_KEY, String(step))
    } catch {
      // ignore storage errors
    }
  }

  return { open, close, complete, reopen, currentStep, updateStep }
}
