export interface Overview {
  mode: string;
  local?: boolean;
  version: string;
  uptime_seconds?: number;
  settings?: Record<string, unknown>;
  preflight?: Record<string, unknown>;
  signing_keys?: Record<string, unknown>;
  client_matrix?: Array<Record<string, string>>;
  counters?: Record<string, number>;
}

export interface OperationMetric {
  operation_type: string;
  operation_name: string;
  success: number;
  error: number;
  denied: number;
  total: number;
  error_rate: number;
  p50_ms: number | null;
  p95_ms: number | null;
}

export interface MetricsSnapshot {
  uptime_seconds: number;
  operations: OperationMetric[];
  denial_reasons: Record<string, number>;
  rate_limited: Record<string, number>;
  sink_errors: number;
}

export interface TimePoint {
  minute: number;
  calls: number;
  errors: number;
  denied: number;
  p95_ms: number | null;
}

export interface AuditRecord {
  timestamp: string;
  caller_type: string;
  operation_type: string;
  operation_name: string;
  input_data: unknown;
  duration_ms: number | null;
  policy_decision: string;
  policy_reason: string | null;
  operation_status: string;
  error: string | null;
  user_id: string | null;
  session_id: string | null;
  request_id: string | null;
}

export interface LogRecord {
  seq: number;
  timestamp: string;
  level: string;
  logger: string;
  message: string;
}

export interface JsonSchema {
  type?: string | string[];
  description?: string;
  default?: unknown;
  enum?: unknown[];
  properties?: Record<string, JsonSchema>;
  items?: JsonSchema;
  anyOf?: JsonSchema[];
  $ref?: string;
  $defs?: Record<string, JsonSchema>;
  additionalProperties?: boolean | JsonSchema;
  minimum?: number;
  maximum?: number;
  title?: string;
}

export interface SettingsSection {
  key: string;
  title: string;
  description: string;
  apply: "live" | "restart";
  icon: string;
  schema: JsonSchema;
}

export interface Feature {
  key: string;
  title: string;
  description: string;
  category: string;
  apply: "live" | "restart";
  defaults: string[];
}

export interface SettingsSchema {
  sections: SettingsSection[];
  restart_fields: string[];
  features: Feature[];
  profiles: string[];
}

export interface SettingsState {
  path: string;
  exists: boolean;
  writable: boolean;
  data: Record<string, Record<string, unknown>>;
  effective: Record<string, Record<string, unknown>>;
  env_locked: Record<string, string>;
  setup: Record<string, unknown> | null;
  setup_complete: boolean;
  features: string[];
  mode: "local" | "enterprise";
  has_auth_section: boolean;
}

export interface SaveResult {
  saved: string;
  backup: string | null;
  changed: string[];
  applied_live: string[];
  restart_required: string[];
}

export interface ToolInfo {
  name: string;
  enabled: boolean;
  permission: "read" | "write";
  annotations: Record<string, unknown>;
  rate_limit_per_minute: number | null;
  description: string;
}

export interface PluginInfo {
  name: string;
  group: string;
  target: string;
  distribution: string | null;
  version: string | null;
  enabled: boolean;
  loaded: boolean;
  error: string | null;
  tools: string[];
  diagram_types: string[];
}

export interface LintIssue {
  severity: "error" | "warning" | "info";
  code: string;
  target: string;
  message: string;
  fix: string;
}
