import { Lock, RotateCcw } from "lucide-react";
import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import type { JsonSchema } from "@/lib/types";
import { cn } from "@/lib/utils";

type Value = unknown;

/** Resolve $ref and nullable anyOf so each field has one concrete schema. */
export function normalize(schema: JsonSchema, root: JsonSchema): { schema: JsonSchema; nullable: boolean } {
  let s = schema;
  if (s.$ref) {
    const name = s.$ref.split("/").pop() ?? "";
    s = { ...(root.$defs?.[name] ?? {}), description: schema.description ?? root.$defs?.[name]?.description };
  }
  if (s.anyOf) {
    const nonNull = s.anyOf.filter((x) => x.type !== "null");
    const nullable = nonNull.length < s.anyOf.length;
    if (nonNull.length === 1) {
      const inner = normalize(nonNull[0], root);
      return { schema: { ...inner.schema, description: s.description ?? inner.schema.description }, nullable };
    }
    return { schema: { ...s, type: "json" }, nullable };
  }
  if (Array.isArray(s.type)) {
    const t = s.type.filter((x) => x !== "null");
    return { schema: { ...s, type: t[0] }, nullable: s.type.includes("null") };
  }
  return { schema: s, nullable: false };
}

export function humanize(key: string): string {
  const WORDS: Record<string, string> = { Url: "URL", Otel: "OTel", Plantuml: "PlantUML", Http: "HTTP", Ms: "ms", Mcp: "MCP", Id: "ID", Ip: "IP" };
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\b(Url|Otel|Plantuml|Http|Ms|Mcp|Id|Ip)\b/g, (w) => WORDS[w] ?? w);
}

interface FieldProps {
  path: string;
  name: string;
  schema: JsonSchema;
  root: JsonSchema;
  value: Value;
  effective: Value;
  onChange: (v: Value) => void;
  locked?: string;
  restart?: boolean;
  disabled?: boolean;
}

function JsonField({ value, onChange, disabled, id }: { value: Value; onChange: (v: Value) => void; disabled?: boolean; id: string }) {
  const [text, setText] = React.useState(() => (value === undefined ? "" : JSON.stringify(value, null, 2)));
  const [bad, setBad] = React.useState(false);
  return (
    <Textarea
      id={id}
      className={cn("font-mono text-xs", bad && "border-destructive")}
      value={text}
      disabled={disabled}
      rows={Math.min(8, Math.max(2, text.split("\n").length))}
      onChange={(e) => {
        setText(e.target.value);
        if (!e.target.value.trim()) { setBad(false); onChange(undefined); return; }
        try { onChange(JSON.parse(e.target.value)); setBad(false); } catch { setBad(true); }
      }}
    />
  );
}

export function Field({ path, name, schema: raw, root, value, effective, onChange, locked, restart, disabled }: FieldProps) {
  const { schema } = normalize(raw, root);
  const id = `f-${path}`;
  const isDisabled = disabled || Boolean(locked);
  const type = schema.enum ? "enum" : schema.type;
  const placeholder = effective === undefined || effective === null ? "default" : String(typeof effective === "object" ? JSON.stringify(effective) : effective);

  if (type === "object" && schema.properties) {
    return (
      <fieldset className="col-span-full rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">{humanize(name)}</legend>
        {schema.description && <p className="mb-3 text-xs text-muted-foreground">{schema.description}</p>}
        <div className="grid gap-4 sm:grid-cols-2">
          {Object.entries(schema.properties).map(([k, sub]) => (
            <Field
              key={k}
              path={`${path}.${k}`}
              name={k}
              schema={sub}
              root={root}
              value={(value as Record<string, Value> | undefined)?.[k]}
              effective={(effective as Record<string, Value> | undefined)?.[k]}
              disabled={disabled}
              onChange={(v) => {
                const next = { ...((value as Record<string, Value>) ?? {}) };
                if (v === undefined) delete next[k]; else next[k] = v;
                onChange(Object.keys(next).length ? next : undefined);
              }}
            />
          ))}
        </div>
      </fieldset>
    );
  }

  let control: React.ReactNode;
  if (type === "boolean") {
    const checked = Boolean(value ?? effective ?? schema.default);
    control = <Switch id={id} checked={checked} disabled={isDisabled} onCheckedChange={(v) => onChange(v)} />;
  } else if (type === "enum") {
    control = (
      <NativeSelect id={id} value={String(value ?? "")} disabled={isDisabled} onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value)}>
        <option value="">default ({String(effective ?? schema.default ?? "–")})</option>
        {schema.enum!.map((opt) => <option key={String(opt)} value={String(opt)}>{String(opt)}</option>)}
      </NativeSelect>
    );
  } else if (type === "integer" || type === "number") {
    control = (
      <Input id={id} type="number" inputMode="decimal" value={value === undefined || value === null ? "" : String(value)}
        placeholder={placeholder} disabled={isDisabled} min={schema.minimum} max={schema.maximum}
        step={type === "integer" ? 1 : "any"}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} />
    );
  } else if (type === "array" && (schema.items?.type === "string" || schema.items?.enum)) {
    control = (
      <Input id={id} value={Array.isArray(value) ? value.join(", ") : ""} placeholder={Array.isArray(effective) ? effective.join(", ") || "none" : placeholder}
        disabled={isDisabled}
        onChange={(e) => {
          const items = e.target.value.split(",").map((x) => x.trim()).filter(Boolean);
          onChange(e.target.value.trim() === "" ? undefined : items);
        }} />
    );
  } else if (type === "string") {
    control = <Input id={id} value={value === undefined || value === null ? "" : String(value)} placeholder={placeholder} disabled={isDisabled}
      onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value)} />;
  } else {
    control = <JsonField id={id} value={value} onChange={onChange} disabled={isDisabled} />;
  }

  const wide = type === "json" || type === "object" || (type === "array" && !schema.items?.type);
  return (
    <div className={cn("flex flex-col gap-1.5", wide && "col-span-full", type === "boolean" && "justify-between rounded-lg border p-3 sm:flex-row sm:items-center")} data-field={path}>
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <Label htmlFor={id}>{humanize(name)}</Label>
          {locked && (
            <Tooltip content={`Set by environment variable ${locked}; environment wins over the file.`}>
              <Badge variant="warning"><Lock />{locked}</Badge>
            </Tooltip>
          )}
          {restart && <Badge variant="outline"><RotateCcw />restart</Badge>}
          {value !== undefined && !locked && <Badge variant="secondary">file</Badge>}
        </div>
        {schema.description && <p className="text-xs text-muted-foreground">{schema.description}</p>}
      </div>
      {control}
    </div>
  );
}
