#!/usr/bin/env bash
# Creates an Entra app + service principal that GitHub Actions can log in as via OIDC (no secrets stored),
# scoped to the Pulse resource group and ACR. Run AFTER deploy-azure.sh.
#
# Usage:
#   ./infra/setup-github-oidc.sh <owner>/<repo>      # or omit to detect via `gh repo view`
#   ACR_NAME=pulseacrXXXX ./infra/setup-github-oidc.sh owner/repo   # if you overrode ACR_NAME in deploy
set -euo pipefail

RG="${RG:-pulse-rg}"
APP="${APP:-pulse-api}"
AAD_APP_NAME="${AAD_APP_NAME:-pulse-github-actions}"
BRANCH="${BRANCH:-main}"

REPO="${1:-${GITHUB_REPO:-}}"
if [[ -z "$REPO" ]]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
fi
if [[ -z "$REPO" || "$REPO" != */* ]]; then
  echo "usage: $0 <owner>/<repo>" >&2
  exit 1
fi

SUB_ID="$(az account show --query id -o tsv)"
TENANT_ID="$(az account show --query tenantId -o tsv)"
ACR_NAME="${ACR_NAME:-pulseacr$(printf '%s' "${SUB_ID//-/}" | cut -c1-8)}"
RG_ID="$(az group show -n "$RG" --query id -o tsv)"
ACR_ID="$(az acr show -n "$ACR_NAME" -g "$RG" --query id -o tsv)"

echo "==> Entra app registration: $AAD_APP_NAME"
CLIENT_ID="$(az ad app list --display-name "$AAD_APP_NAME" --query "[0].appId" -o tsv)"
if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID="$(az ad app create --display-name "$AAD_APP_NAME" --query appId -o tsv)"
fi

echo "==> Service principal"
SP_OID="$(az ad sp show --id "$CLIENT_ID" --query id -o tsv 2>/dev/null || true)"
if [[ -z "$SP_OID" ]]; then
  SP_OID="$(az ad sp create --id "$CLIENT_ID" --query id -o tsv)"
fi

echo "==> Federated credential for repo:$REPO:ref:refs/heads/$BRANCH"
FC_NAME="github-${BRANCH//\//-}"
if [[ "$(az ad app federated-credential list --id "$CLIENT_ID" --query "[?name=='$FC_NAME'] | length(@)" -o tsv)" == "0" ]]; then
  az ad app federated-credential create --id "$CLIENT_ID" -o none --parameters "{
    \"name\": \"$FC_NAME\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:$REPO:ref:refs/heads/$BRANCH\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"
fi

ensure_role() { # role scope
  if [[ "$(az role assignment list --assignee "$SP_OID" --role "$1" --scope "$2" --query "length(@)" -o tsv)" == "0" ]]; then
    az role assignment create --assignee-object-id "$SP_OID" --assignee-principal-type ServicePrincipal \
      --role "$1" --scope "$2" -o none
  fi
}
echo "==> Role assignments (Contributor on $RG, AcrPush on $ACR_NAME)"
ensure_role Contributor "$RG_ID"
ensure_role AcrPush "$ACR_ID"

cat <<EOF

==> Done. Set these on GitHub (copy-paste; requires gh CLI authenticated):

gh secret set AZURE_CLIENT_ID       --repo $REPO --body "$CLIENT_ID"
gh secret set AZURE_TENANT_ID       --repo $REPO --body "$TENANT_ID"
gh secret set AZURE_SUBSCRIPTION_ID --repo $REPO --body "$SUB_ID"
gh variable set ACR_NAME            --repo $REPO --body "$ACR_NAME"
gh variable set RESOURCE_GROUP      --repo $REPO --body "$RG"
gh variable set CONTAINER_APP       --repo $REPO --body "$APP"

(Role assignments can take a minute or two to propagate before the first workflow run succeeds.)
EOF
