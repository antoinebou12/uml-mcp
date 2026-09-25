import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { JsonSchema } from "@/lib/types";
import { Field, humanize, normalize } from "./SchemaForm";

const root: JsonSchema = {
  $defs: { Limit: { type: "object", description: "A limit", properties: { rpm: { type: "integer", description: "per minute" } } } },
};

function renderField(props: Partial<React.ComponentProps<typeof Field>> & { schema: JsonSchema }) {
  const onChange = vi.fn();
  render(
    <TooltipProvider>
      <Field path="s.f" name="kroki_server" root={root} value={undefined} effective={undefined} onChange={onChange} {...props} />
    </TooltipProvider>,
  );
  return onChange;
}

describe("normalize", () => {
  it("unwraps nullable anyOf and $ref", () => {
    expect(normalize({ anyOf: [{ type: "string" }, { type: "null" }], description: "d" }, root)).toEqual({
      schema: { type: "string", description: "d" },
      nullable: true,
    });
    expect(normalize({ $ref: "#/$defs/Limit" }, root).schema.properties?.rpm.type).toBe("integer");
    expect(normalize({ type: ["number", "null"] }, root)).toEqual({ schema: { type: "number" }, nullable: true });
  });
  it("humanizes keys", () => {
    expect(humanize("kroki_server")).toBe("Kroki Server");
    expect(humanize("plantuml_server")).toBe("PlantUML Server");
    expect(humanize("otel")).toBe("OTel");
  });
});

describe("Field", () => {
  it("edits strings and clears to default", () => {
    const onChange = renderField({ schema: { type: "string", description: "Kroki URL" }, effective: "https://kroki.io" });
    const input = screen.getByPlaceholderText("https://kroki.io");
    fireEvent.change(input, { target: { value: "http://kroki:8000" } });
    expect(onChange).toHaveBeenLastCalledWith("http://kroki:8000");
    expect(screen.getByText("Kroki URL")).toBeInTheDocument();
  });
  it("clears a file value back to the default", () => {
    const onChange = renderField({ schema: { type: "string" }, value: "http://x" });
    expect(screen.getByText("file")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith(undefined);
  });
  it("renders booleans as switches from the effective value", () => {
    const onChange = renderField({ schema: { type: "boolean" }, effective: true, name: "enabled" });
    const sw = screen.getByRole("switch");
    expect(sw).toHaveAttribute("aria-checked", "true");
    fireEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(false);
  });
  it("locks env-controlled fields", () => {
    renderField({ schema: { type: "string" }, locked: "KROKI_SERVER" });
    expect(screen.getByRole("textbox")).toBeDisabled();
    expect(screen.getByText("KROKI_SERVER")).toBeInTheDocument();
  });
  it("parses numbers, enums and lists", () => {
    const onNum = renderField({ schema: { type: "integer" }, name: "rpm", path: "a" });
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "42" } });
    expect(onNum).toHaveBeenLastCalledWith(42);
  });
  it("handles enum and string lists", () => {
    const onEnum = renderField({ schema: { enum: ["text", "json"] }, name: "format", path: "b" });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "json" } });
    expect(onEnum).toHaveBeenLastCalledWith("json");
  });
  it("splits comma lists", () => {
    const onList = renderField({ schema: { type: "array", items: { type: "string" } }, name: "hosts", path: "c" });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "a.example, b.example" } });
    expect(onList).toHaveBeenLastCalledWith(["a.example", "b.example"]);
  });
});
