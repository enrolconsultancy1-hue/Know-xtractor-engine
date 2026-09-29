import { describe, it, expect, beforeEach, vi } from "vitest";
import { getAuthToken, setAuthToken, api } from "../api";

describe("API client", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("handles token persistence in localStorage", () => {
    expect(getAuthToken()).toBe("");

    setAuthToken("secret-token-123");
    expect(getAuthToken()).toBe("secret-token-123");

    setAuthToken("");
    expect(getAuthToken()).toBe("");
  });

  it("sends Authorization header when token is set", async () => {
    setAuthToken("my-jwt-token");

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: 1, name: "Proj 1" }],
    });
    global.fetch = mockFetch;

    const projects = await api.listProjects();
    expect(projects).toEqual([{ id: 1, name: "Proj 1" }]);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/projects",
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer my-jwt-token",
        }),
      })
    );
  });

  it("formats 401 error with informative message", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: async () => "Unauthorized",
    });

    await expect(api.listProjects()).rejects.toThrow(/401 Unauthorized/);
  });

  it("handles 500 error", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => "Internal Server Error",
    });

    await expect(api.listProjects()).rejects.toThrow(/500: Internal Server Error/);
  });
});
