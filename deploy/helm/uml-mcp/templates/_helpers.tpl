{{- define "uml-mcp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "uml-mcp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "uml-mcp.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{ include "uml-mcp.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "uml-mcp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "uml-mcp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "uml-mcp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "uml-mcp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "uml-mcp.authEnabled" -}}
{{- if ne .Values.auth.mode "none" }}true{{ end }}
{{- end }}

{{- define "uml-mcp.secretName" -}}
{{- default (printf "%s-auth" (include "uml-mcp.fullname" .)) .Values.auth.existingSecret }}
{{- end }}

{{/* auth.json rendered into the ConfigMap (never contains secrets). */}}
{{- define "uml-mcp.authConfig" -}}
{{- $entra := dict "tenant_id" .Values.auth.entra.tenantId "client_id" .Values.auth.entra.clientId "cloud" .Values.auth.entra.cloud "token_versions" .Values.auth.entra.tokenVersions }}
{{- if .Values.auth.entra.appIdUri }}{{- $_ := set $entra "app_id_uri" .Values.auth.entra.appIdUri }}{{- end }}
{{- $cfg := dict "mode" .Values.auth.mode "resource_url" .Values.auth.resourceUrl "preflight" .Values.auth.preflight "admin_ui" .Values.admin.enabled }}
{{- if .Values.auth.entra.tenantId }}{{- $_ := set $cfg "entra" $entra }}{{- end }}
{{- mergeOverwrite $cfg (deepCopy .Values.auth.config) | toPrettyJson }}
{{- end }}
