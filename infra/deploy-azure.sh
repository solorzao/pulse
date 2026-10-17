#!/usr/bin/env bash
# Pulse API -> Azure Container Apps. Idempotent: safe to re-run (it updates instead of failing).
#
# Usage (from anywhere, after `az login`):
#   export ANTHROPIC_API_KEY=sk-ant-...        # optional; API falls back to deterministic answers without it
#   export CORS_ORIGINS=https://pulse.vercel.app  # optional; localhost + *.vercel.app are already allowed by the API
#   ./infra/deploy-azure.sh
#
# Override any variable below via env, e.g. LOCATION=eastus ACR_NAME=myacr123 ./infra/deploy-azure.sh
set -euo pipefail

# ---------- config ----------
RG="${RG:-pulse-rg}"
LOCATION="${LOCATION:-westus2}"
ENV_NAME="${ENV_NAME:-pulse-env}"
APP="${APP:-pulse-api}"
LOGS="${LOGS:-pulse-logs}"
IDENTITY="${IDENTITY:-pulse-api-id}"           # user-assigned identity used to pull from ACR
IMAGE_REPO="${IMAGE_REPO:-pulse-api}"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

SUB_ID="$(az account show --query id -o tsv)"
# ACR names are global + alphanumeric. Default is stable per subscription (same name on every re-run).
ACR_NAME="${ACR_NAME:-pulseacr$(printf '%s' "${SUB_ID//-/}" | cut -c1-8)}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="${TAG:-$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"

log() { printf '\n==> %s\n' "$*"; }

log "Subscription $SUB_ID | RG $RG | $LOCATION | ACR $ACR_NAME | tag $TAG"

# ---------- prerequisites ----------
log "Ensuring containerapp CLI extension + resource providers"
az extension add --name containerapp --upgrade --only-show-errors -y >/dev/null
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry; do
  state="$(az provider show -n "$ns" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)"
  if [[ "$state" != "Registered" ]]; then
    echo "registering $ns ..."
    az provider register -n "$ns" --wait
  fi
done

# ---------- resource group ----------
log "Resource group"
az group create -n "$RG" -l "$LOCATION" -o none

# ---------- container registry ----------
log "Container registry (Basic, admin disabled)"
if ! az acr show -n "$ACR_NAME" -g "$RG" -o none 2>/dev/null; then
  az acr create -n "$ACR_NAME" -g "$RG" -l "$LOCATION" --sku Basic --admin-enabled false -o none
fi
ACR_ID="$(az acr show -n "$ACR_NAME" -g "$RG" --query id -o tsv)"
ACR_SERVER="$(az acr show -n "$ACR_NAME" -g "$RG" --query loginServer -o tsv)"

# ---------- pull identity (managed identity, no registry passwords) ----------
log "User-assigned identity with AcrPull"
az identity create -n "$IDENTITY" -g "$RG" -l "$LOCATION" -o none
UAI_ID="$(az identity show -n "$IDENTITY" -g "$RG" --query id -o tsv)"
UAI_PRINCIPAL="$(az identity show -n "$IDENTITY" -g "$RG" --query principalId -o tsv)"
existing="$(az role assignment list --assignee "$UAI_PRINCIPAL" --scope "$ACR_ID" --role AcrPull --query "length(@)" -o tsv)"
if [[ "$existing" == "0" ]]; then
  az role assignment create --assignee-object-id "$UAI_PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role AcrPull --scope "$ACR_ID" -o none
  echo "waiting 45s for role assignment to propagate..."
  sleep 45
fi

# ---------- build image in the cloud (no local docker needed) ----------
log "Building image in ACR from repo root (api/Dockerfile)"
IMAGE="$ACR_SERVER/$IMAGE_REPO:$TAG"
( cd "$REPO_ROOT" && az acr build -r "$ACR_NAME" -f api/Dockerfile \
    -t "$IMAGE_REPO:$TAG" -t "$IMAGE_REPO:latest" . )

# ---------- Log Analytics + Container Apps environment ----------
log "Log Analytics workspace + Container Apps environment"
if ! az containerapp env show -n "$ENV_NAME" -g "$RG" -o none 2>/dev/null; then
  az monitor log-analytics workspace create -n "$LOGS" -g "$RG" -l "$LOCATION" -o none
  LOGS_ID="$(az monitor log-analytics workspace show -n "$LOGS" -g "$RG" --query customerId -o tsv)"
  LOGS_KEY="$(az monitor log-analytics workspace get-shared-keys -n "$LOGS" -g "$RG" --query primarySharedKey -o tsv)"
  az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" \
    --logs-workspace-id "$LOGS_ID" --logs-workspace-key "$LOGS_KEY" -o none
fi

# ---------- container app (create or update) ----------
ENV_VARS=("CORS_ORIGINS=$CORS_ORIGINS")
SECRET_ARGS=()
if [[ -n "$ANTHROPIC_API_KEY" ]]; then
  SECRET_ARGS=(--secrets "anthropic-api-key=$ANTHROPIC_API_KEY")
  ENV_VARS+=("ANTHROPIC_API_KEY=secretref:anthropic-api-key")
else
  echo "WARN: ANTHROPIC_API_KEY not set - existing secret (if any) is kept; API uses its deterministic fallback otherwise."
fi

if ! az containerapp show -n "$APP" -g "$RG" -o none 2>/dev/null; then
  log "Creating container app $APP"
  az containerapp create -n "$APP" -g "$RG" --environment "$ENV_NAME" \
    --image "$IMAGE" \
    --user-assigned "$UAI_ID" --registry-server "$ACR_SERVER" --registry-identity "$UAI_ID" \
    --ingress external --target-port 8000 \
    --min-replicas 1 --max-replicas 2 --cpu 0.5 --memory 1Gi \
    ${SECRET_ARGS[@]+"${SECRET_ARGS[@]}"} \
    --env-vars "${ENV_VARS[@]}" \
    -o none
else
  log "Updating container app $APP"
  if [[ -n "$ANTHROPIC_API_KEY" ]]; then
    az containerapp secret set -n "$APP" -g "$RG" "${SECRET_ARGS[@]}" -o none
  fi
  az containerapp registry set -n "$APP" -g "$RG" --server "$ACR_SERVER" --identity "$UAI_ID" -o none
  az containerapp ingress enable -n "$APP" -g "$RG" --type external --target-port 8000 -o none
  az containerapp update -n "$APP" -g "$RG" \
    --image "$IMAGE" \
    --min-replicas 1 --max-replicas 2 --cpu 0.5 --memory 1Gi \
    --set-env-vars "${ENV_VARS[@]}" \
    -o none
fi

FQDN="$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"

log "Done"
cat <<EOF
API URL:        https://$FQDN
Health check:   curl https://$FQDN/health
ACR_NAME:       $ACR_NAME   (export ACR_NAME=$ACR_NAME for setup-github-oidc.sh)
Vercel env:     NEXT_PUBLIC_API_URL=https://$FQDN
EOF
