{{/*
Nome do chart.
*/}}
{{- define "wolfpack-control-plane.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Nome completo, truncado em 63 caracteres (limite de DNS do Kubernetes).
*/}}
{{- define "wolfpack-control-plane.fullname" -}}
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

{{/*
Nome e versao do chart para rotulos.
*/}}
{{- define "wolfpack-control-plane.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Rotulos comuns.
*/}}
{{- define "wolfpack-control-plane.labels" -}}
helm.sh/chart: {{ include "wolfpack-control-plane.chart" . }}
{{ include "wolfpack-control-plane.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Rotulos de selecao base.
*/}}
{{- define "wolfpack-control-plane.selectorLabels" -}}
app.kubernetes.io/name: {{ include "wolfpack-control-plane.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Nome da service account.
*/}}
{{- define "wolfpack-control-plane.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "wolfpack-control-plane.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Nomes dos componentes internos baseados em docker-compose.production.yml.
*/}}
{{- define "wolfpack-control-plane.backendName" -}}
{{- printf "%s-backend" (include "wolfpack-control-plane.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "wolfpack-control-plane.frontendName" -}}
{{- printf "%s-frontend" (include "wolfpack-control-plane.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "wolfpack-control-plane.postgresHost" -}}
{{- if .Values.postgres.enabled }}
{{- printf "%s-postgres" (include "wolfpack-control-plane.fullname" .) }}
{{- else }}
{{- .Values.externalDatabase.host }}
{{- end }}
{{- end }}

{{- define "wolfpack-control-plane.clickhouseHost" -}}
{{- if .Values.clickhouse.enabled }}
{{- printf "%s-clickhouse" (include "wolfpack-control-plane.fullname" .) }}
{{- else }}
{{- .Values.externalClickhouse.host }}
{{- end }}
{{- end }}

{{- define "wolfpack-control-plane.inngestPostgresHost" -}}
{{- if .Values.inngestPostgres.enabled }}
{{- printf "%s-inngest-postgres" (include "wolfpack-control-plane.fullname" .) }}
{{- else }}
{{- .Values.externalInngestDatabase.host }}
{{- end }}
{{- end }}

{{- define "wolfpack-control-plane.redisHost" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis:6379" (include "wolfpack-control-plane.fullname" .) }}
{{- else }}
{{- .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{- define "wolfpack-control-plane.minioHost" -}}
{{- if .Values.minio.enabled }}
{{- printf "http://%s-minio:9000" (include "wolfpack-control-plane.fullname" .) }}
{{- else }}
{{- .Values.externalMinio.endpoint }}
{{- end }}
{{- end }}

{{- define "wolfpack-control-plane.qdrantHost" -}}
{{- if .Values.qdrant.enabled }}
{{- printf "http://%s-qdrant:6333" (include "wolfpack-control-plane.fullname" .) }}
{{- else }}
{{- .Values.externalQdrant.url }}
{{- end }}
{{- end }}

{{- define "wolfpack-control-plane.inngestHost" -}}
{{- if .Values.inngest.enabled }}
{{- printf "http://%s-inngest:8288" (include "wolfpack-control-plane.fullname" .) }}
{{- else }}
{{- .Values.externalInngest.url }}
{{- end }}
{{- end }}
