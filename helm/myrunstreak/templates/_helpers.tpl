{{- define "myrunstreak.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "myrunstreak.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "myrunstreak.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "myrunstreak.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "myrunstreak.selectorLabels" -}}
app.kubernetes.io/name: {{ include "myrunstreak.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
