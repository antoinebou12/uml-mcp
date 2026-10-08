import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SessionProvider } from "@/lib/session";
import { ThemeProvider } from "@/lib/theme";
import { TopBar } from "./TopBar";

async function renderTopBar(overview: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(overview), { status: 200, headers: { "content-type": "application/json" } }),
    ),
  );
  render(
    <MemoryRouter>
      <ThemeProvider>
        <TooltipProvider>
          <SessionProvider>
            <TopBar />
          </SessionProvider>
        </TooltipProvider>
      </ThemeProvider>
    </MemoryRouter>,
  );
  // "Running" appears once the overview has loaded and the session mode is known.
  expect(await screen.findByText("Running")).toBeInTheDocument();
}

afterEach(() => vi.unstubAllGlobals());

describe("TopBar", () => {
  it("hosted password mode: sign out form, no token sign-in, no Stop", async () => {
    await renderTopBar({ mode: "password", local: false, version: "1.4.0" });
    expect(screen.getByText("auth: password")).toBeInTheDocument();
    const form = screen.getByTestId("signout-form");
    expect(form).toHaveAttribute("method", "post");
    expect(form).toHaveAttribute("action", "/admin/logout");
    expect(screen.getByTestId("signout-button")).toHaveAttribute("type", "submit");
    expect(screen.queryByTestId("signin-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stop-button")).not.toBeInTheDocument();
  });

  it("local mode keeps the token button and Stop", async () => {
    await renderTopBar({ mode: "none", local: true, version: "1.4.0" });
    expect(screen.getByTestId("signin-button")).toHaveTextContent("Token");
    expect(screen.getByTestId("stop-button")).toBeInTheDocument();
    expect(screen.queryByTestId("signout-form")).not.toBeInTheDocument();
  });

  it("enterprise mode keeps the token sign-in and Stop", async () => {
    await renderTopBar({ mode: "jwt", local: false, version: "1.4.0" });
    expect(screen.getByTestId("signin-button")).toHaveTextContent("Sign in");
    expect(screen.getByTestId("stop-button")).toBeInTheDocument();
    expect(screen.queryByTestId("signout-form")).not.toBeInTheDocument();
  });
});
