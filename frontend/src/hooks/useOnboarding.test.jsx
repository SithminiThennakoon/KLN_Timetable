import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useOnboarding } from "./useOnboarding";

describe("useOnboarding", () => {
  beforeEach(() => {
    const localStore = new Map();
    const sessionStore = new Map();
    vi.stubGlobal("localStorage", {
      getItem: (key) => (localStore.has(key) ? localStore.get(key) : null),
      setItem: (key, value) => {
        localStore.set(key, String(value));
      },
      removeItem: (key) => {
        localStore.delete(key);
      },
    });
    vi.stubGlobal("sessionStorage", {
      getItem: (key) => (sessionStore.has(key) ? sessionStore.get(key) : null),
      setItem: (key, value) => {
        sessionStore.set(key, String(value));
      },
      removeItem: (key) => {
        sessionStore.delete(key);
      },
    });
  });

  it("reopens from step 1 instead of the last saved step", () => {
    localStorage.setItem("kln-onboarding-seen", "1");
    localStorage.setItem("kln-onboarding-step", "9");

    const { result } = renderHook(() => useOnboarding());

    expect(result.current.open).toBe(false);
    expect(result.current.currentStep).toBe(9);

    act(() => {
      result.current.reopen();
    });

    expect(result.current.open).toBe(true);
    expect(result.current.currentStep).toBe(0);
    expect(localStorage.getItem("kln-onboarding-step")).toBe("0");
  });

  it("does not mark onboarding as seen when closed temporarily", () => {
    const { result } = renderHook(() => useOnboarding());

    act(() => {
      result.current.close();
    });

    expect(result.current.open).toBe(false);
    expect(localStorage.getItem("kln-onboarding-seen")).toBe(null);
    expect(sessionStorage.getItem("kln-onboarding-dismissed-session")).toBe("1");
  });

  it("marks onboarding as seen only when completed", () => {
    const { result } = renderHook(() => useOnboarding());

    act(() => {
      result.current.complete();
    });

    expect(result.current.open).toBe(false);
    expect(localStorage.getItem("kln-onboarding-seen")).toBe("1");
  });

  it("stays closed for the rest of the browser session after a temporary close", () => {
    sessionStorage.setItem("kln-onboarding-dismissed-session", "1");

    const { result } = renderHook(() => useOnboarding());

    expect(result.current.open).toBe(false);
    expect(localStorage.getItem("kln-onboarding-seen")).toBe(null);
  });
});
