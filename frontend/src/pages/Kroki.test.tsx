import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Kroki from "./Kroki";

const STATUS = {
  mode: "local",
  kroki: {
    url: "http://127.0.0.1:8001",
    reachable: true,
    version: "0.32.1",
    error: null,
    companions: {
      mermaid: { ok: true, detail: "ok" },
      bpmn: { ok: false, detail: "HTTP 500: companion down" },
    },
  },
  docker: {
    docker: true,
    detail: "Docker 29",
    compose_file: "/x/compose.yml",
    url: "http://127.0.0.1:8001",
    containers: [{ service: "kroki", state: "running", status: "Up", image: "yuzutech/kroki" }],
    command: "uml-mcp kroki up --use",
  },
};
const CATALOG = {
  types: [
    { name: "mermaid", backend: "mermaid", description: "Mermaid", formats: ["svg", "png"], example: "graph TD; A-->B" },
    { name: "d2", backend: "d2", description: "D2", formats: ["svg"], example: "a -> b" },
  ],
};

function mockFetch(render: unknown) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const body = url.endsWith("/catalog") ? CATALOG : url.endsWith("/render") ? render : STATUS;
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  }));
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("Kroki page", () => {
  it("shows health per companion and renders a preview", async () => {
    const calls = mockFetch({ content_base64: btoa("<svg/>"), mime_type: "image/svg+xml", url: "http://k/x", playground: "https://mermaid.live/edit#x", source: "kroki", render_ms: 12 });
    render(<Kroki />);
    expect(await screen.findByTestId("kroki-companion-mermaid")).toHaveTextContent("ok");
    expect(screen.getByTestId("kroki-companion-bpmn")).toHaveTextContent("companion down");
    expect(screen.getByText("v0.32.1")).toBeInTheDocument();

    const code = await screen.findByTestId("kroki-code");
    expect(code).toHaveValue("graph TD; A-->B");
    fireEvent.click(screen.getByTestId("kroki-render"));
    const img = await screen.findByTestId("kroki-preview");
    expect(img.getAttribute("src")).toBe(`data:image/svg+xml;base64,${btoa("<svg/>")}`);
    expect(screen.getByTestId("kroki-playground")).toHaveAttribute("href", "https://mermaid.live/edit#x");

    const req = calls.find((c) => c.url.endsWith("/render"))!;
    expect(new Headers(req.init?.headers).get("X-UML-MCP-Admin")).toBe("1");
    expect(JSON.parse(String(req.init?.body))).toEqual({ diagram_type: "mermaid", code: "graph TD; A-->B", output_format: "svg" });
  });

  it("switching type loads its example; errors are shown", async () => {
    mockFetch({ error: "Error 400: syntax error" });
    render(<Kroki />);
    fireEvent.change(await screen.findByTestId("kroki-type"), { target: { value: "d2" } });
    expect(screen.getByTestId("kroki-code")).toHaveValue("a -> b");
    fireEvent.click(screen.getByTestId("kroki-render"));
    await waitFor(() => expect(screen.getByTestId("kroki-error")).toHaveTextContent("syntax error"));
    expect(screen.queryByTestId("kroki-preview")).toBeNull();
  });
});
