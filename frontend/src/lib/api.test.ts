import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, captureTokenFromUrl, getToken, setToken } from "./api";

afterEach(() => {
  setToken(null);
  vi.restoreAllMocks();
});

describe("api client", () => {
  it("captures the setup token from the hash and strips it", () => {
    history.replaceState(null, "", "/admin/#/setup?token=abc&x=1");
    captureTokenFromUrl();
    expect(getToken()).toBe("abc");
    expect(window.location.hash).toBe("#/setup?x=1");
  });

  it("sends bearer + write header and surfaces API errors", async () => {
    setToken("tok");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "nope" }), { status: 403, headers: { "content-type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/admin/api/settings", { method: "PUT", json: {}, write: true })).rejects.toMatchObject({
      status: 403,
      message: "nope",
    });
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok");
    expect(headers.get("X-UML-MCP-Admin")).toBe("1");
    expect(new ApiError(1, "m", null)).toBeInstanceOf(Error);
  });
});
