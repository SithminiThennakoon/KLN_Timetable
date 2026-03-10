import { useState } from 'react'

const STORAGE_KEY = 'kln-onboarding-seen'

export function useOnboarding() {
  const [open, setOpen] = useState(() => {
    try {
      return !localStorage.getItem(STORAGE_KEY)
    } catch {
      return true
    }
  })

  const dismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, '1')
    } catch {
      // ignore storage errors
    }
    setOpen(false)
  }

  const reopen = () => setOpen(true)

  return { open, dismiss, reopen }
}
