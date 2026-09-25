/** Admin API client. Bearer = local setup token or an enterprise access token. */

const STORAGE_KEY = "uml-mcp-admin-token";
let memoryToken: string | null = null;

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export function getToken(): string | null {
  if (memoryToken) return memoryToken;
  try {
    memoryToken = sessionStorage.getItem(STORAGE_KEY);
  } catch {
    /* storage blocked: memory only */
  }
  return memoryToken;
}

export function setToken(token: string | null): void {
  memoryToken = token || null;
  try {
    if (token) sessionStorage.setItem(STORAGE_KEY, token);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** Pick up `?token=` from the hash route (never sent to the server) and strip it. */
export function captureTokenFromUrl(): void {
  const [path, query] = window.location.hash.split("?");
  if (!query) return;
  const params = new URLSearchParams(query);
  const token = params.get("token");
  if (!token) return;
  setToken(token);
  params.delete("token");
  const rest = params.toString();
  history.replaceState(null, "", `${window.location.pathname}${path}${rest ? `?${rest}` : ""}`);
}

function detail(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    const d = b.detail ?? b.error_description ?? b.error;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit & { write?: boolean; json?: unknown } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.write) headers.set("X-UML-MCP-Admin", "1");
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const res = await fetch(path, { ...init, headers, body, cache: "no-store" });
  const type = res.headers.get("content-type") || "";
  const parsed: unknown = type.includes("json") ? await res.json().catch(() => null) : await res.text();
  if (!res.ok) throw new ApiError(res.status, detail(parsed, `${res.status} ${res.statusText}`), parsed);
  return parsed as T;
}

export const get = <T,>(path: string) => api<T>(path);
export const put = <T,>(path: string, json: unknown) => api<T>(path, { method: "PUT", json, write: true });
export const post = <T,>(path: string, json: unknown = {}) =>
  api<T>(path, { method: "POST", json, write: true });
/** POST that only reads (preview/validate): no write header needed. */
export const postRead = <T,>(path: string, json: unknown) => api<T>(path, { method: "POST", json });

export function download(filename: string, content: string, type = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
