import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, resolveApiBaseUrl } from "./apiClient";


describe("apiClient", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: {
        get: () => "application/json",
      },
      json: async () => ({ ok: true }),
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    global.fetch = originalFetch;
  });

  it("uses the configured production api base url", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com/api/");

    await apiClient.get("/v2/dataset");

    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.example.com/api/v2/dataset",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("falls back to the local relative api path", () => {
    expect(resolveApiBaseUrl({})).toBe("/api");
  });
});
