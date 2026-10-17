# Pulse API -> Azure Container Apps (PowerShell version of deploy-azure.sh). Idempotent: safe to re-run.
#
# Usage (after `az login`):
#   $env:ANTHROPIC_API_KEY = "sk-ant-..."   # optional; the API falls back to deterministic answers without it
#   powershell -ExecutionPolicy Bypass -File infra\deploy-azure.ps1
#
# Override defaults with env vars: RG, LOCATION, ENV_NAME, APP, ACR_NAME, CORS_ORIGINS.
$ErrorActionPreference = "Stop"

function Cfg($name, $default) { $v = [Environment]::GetEnvironmentVariable($name); if ([string]::IsNullOrEmpty($v)) { $default } else { $v } }
$RG         = Cfg "RG" "pulse-rg"
$LOCATION   = Cfg "LOCATION" "westus2"
$ENV_NAME   = Cfg "ENV_NAME" "pulse-env"
$APP        = Cfg "APP" "pulse-api"
$LOGS       = Cfg "LOGS" "pulse-logs"
$IDENTITY   = Cfg "IDENTITY" "pulse-api-id"
$IMAGE_REPO = Cfg "IMAGE_REPO" "pulse-api"
$CORS       = Cfg "CORS_ORIGINS" "http://localhost:3000"
$API_KEY    = Cfg "ANTHROPIC_API_KEY" ""

$LogFile = Cfg "PULSE_DEPLOY_LOG" (Join-Path $PSScriptRoot "..\deploy.log")

function Log($msg) { $line = "`n==> $msg"; Write-Host $line -ForegroundColor Cyan; Add-Content -Path $LogFile -Value $line }

# Run az, stream output to console + log, fail on non-zero exit.
function Az {
  $out = & az @args 2>&1
  $code = $LASTEXITCODE
  $out | ForEach-Object { $s = "$_"; Write-Host $s; Add-Content -Path $LogFile -Value $s }
  if ($code -ne 0) { throw "az $($args -join ' ') failed with exit code $code" }
  return ($out | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } | ForEach-Object { "$_" }) -join "`n"
}
# Query az quietly; returns trimmed string or "" on failure (used for existence checks).
function AzQ { $out = & az @args 2>$null; if ($LASTEXITCODE -ne 0) { return "" } ; return (($out | ForEach-Object { "$_" }) -join "`n").Trim() }

Set-Content -Path $LogFile -Value "Pulse deploy started $(Get-Date -Format o)"
try {
  $SUB_ID = AzQ account show --query id -o tsv
  if (-not $SUB_ID) { throw "Not logged in to Azure. Run 'az login' first." }
  $ACR_NAME = Cfg "ACR_NAME" ("pulseacr" + ($SUB_ID -replace "-", "").Substring(0, 8))
  $REPO_ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
  $TAG = (& git -C $REPO_ROOT rev-parse --short HEAD 2>$null)
  if (-not $TAG) { $TAG = Get-Date -Format "yyyyMMddHHmmss" }
  $TAG = "$TAG".Trim()

  Log "Subscription $SUB_ID | RG $RG | $LOCATION | ACR $ACR_NAME | tag $TAG"

  Log "Ensuring containerapp CLI extension + resource providers"
  Az extension add --name containerapp --upgrade --only-show-errors -y | Out-Null
  foreach ($ns in "Microsoft.App", "Microsoft.OperationalInsights", "Microsoft.ContainerRegistry") {
    $state = AzQ provider show -n $ns --query registrationState -o tsv
    if ($state -ne "Registered") { Log "Registering $ns"; Az provider register -n $ns --wait | Out-Null }
  }

  Log "Resource group"
  Az group create -n $RG -l $LOCATION -o none | Out-Null

  Log "Container registry (Basic, admin disabled)"
  if (-not (AzQ acr show -n $ACR_NAME -g $RG --query id -o tsv)) {
    Az acr create -n $ACR_NAME -g $RG -l $LOCATION --sku Basic --admin-enabled false -o none | Out-Null
  }
  $ACR_ID = AzQ acr show -n $ACR_NAME -g $RG --query id -o tsv
  $ACR_SERVER = AzQ acr show -n $ACR_NAME -g $RG --query loginServer -o tsv

  Log "User-assigned identity with AcrPull"
  Az identity create -n $IDENTITY -g $RG -l $LOCATION -o none | Out-Null
  $UAI_ID = AzQ identity show -n $IDENTITY -g $RG --query id -o tsv
  $UAI_PRINCIPAL = AzQ identity show -n $IDENTITY -g $RG --query principalId -o tsv
  $existing = AzQ role assignment list --assignee $UAI_PRINCIPAL --scope $ACR_ID --role AcrPull --query "length(@)" -o tsv
  if ($existing -ne "1" -and $existing -notmatch "^[1-9]") {
    Az role assignment create --assignee-object-id $UAI_PRINCIPAL --assignee-principal-type ServicePrincipal --role AcrPull --scope $ACR_ID -o none | Out-Null
    Log "Waiting 45s for the role assignment to propagate"
    Start-Sleep -Seconds 45
  }

  Log "Building image in ACR from repo root (api/Dockerfile) - this takes a few minutes"
  $IMAGE = "$ACR_SERVER/${IMAGE_REPO}:$TAG"
  Push-Location $REPO_ROOT
  try { Az acr build -r $ACR_NAME -f api/Dockerfile -t "${IMAGE_REPO}:$TAG" -t "${IMAGE_REPO}:latest" . | Out-Null }
  finally { Pop-Location }

  Log "Log Analytics workspace + Container Apps environment"
  if (-not (AzQ containerapp env show -n $ENV_NAME -g $RG --query id -o tsv)) {
    Az monitor log-analytics workspace create -n $LOGS -g $RG -l $LOCATION -o none | Out-Null
    $LOGS_ID = AzQ monitor log-analytics workspace show -n $LOGS -g $RG --query customerId -o tsv
    $LOGS_KEY = AzQ monitor log-analytics workspace get-shared-keys -n $LOGS -g $RG --query primarySharedKey -o tsv
    Az containerapp env create -n $ENV_NAME -g $RG -l $LOCATION --logs-workspace-id $LOGS_ID --logs-workspace-key $LOGS_KEY -o none | Out-Null
  }

  $envVars = @("CORS_ORIGINS=$CORS")
  $secretArgs = @()
  if ($API_KEY) {
    $secretArgs = @("--secrets", "anthropic-api-key=$API_KEY")
    $envVars += "ANTHROPIC_API_KEY=secretref:anthropic-api-key"
  } else {
    Log "ANTHROPIC_API_KEY not set - the API will use its deterministic fallback answers (add the key later)"
  }

  if (-not (AzQ containerapp show -n $APP -g $RG --query id -o tsv)) {
    Log "Creating container app $APP"
    $createArgs = @("containerapp", "create", "-n", $APP, "-g", $RG, "--environment", $ENV_NAME,
      "--image", $IMAGE, "--user-assigned", $UAI_ID, "--registry-server", $ACR_SERVER, "--registry-identity", $UAI_ID,
      "--ingress", "external", "--target-port", "8000",
      "--min-replicas", "1", "--max-replicas", "2", "--cpu", "0.5", "--memory", "1Gi") + $secretArgs + @("--env-vars") + $envVars + @("-o", "none")
    Az @createArgs | Out-Null
  } else {
    Log "Updating container app $APP"
    if ($API_KEY) { Az containerapp secret set -n $APP -g $RG @secretArgs -o none | Out-Null }
    Az containerapp registry set -n $APP -g $RG --server $ACR_SERVER --identity $UAI_ID -o none | Out-Null
    Az containerapp ingress enable -n $APP -g $RG --type external --target-port 8000 -o none | Out-Null
    $updateArgs = @("containerapp", "update", "-n", $APP, "-g", $RG, "--image", $IMAGE,
      "--min-replicas", "1", "--max-replicas", "2", "--cpu", "0.5", "--memory", "1Gi", "--set-env-vars") + $envVars + @("-o", "none")
    Az @updateArgs | Out-Null
  }

  $FQDN = AzQ containerapp show -n $APP -g $RG --query properties.configuration.ingress.fqdn -o tsv
  Log "Done"
  $summary = @"
API URL:        https://$FQDN
Health check:   https://$FQDN/health
ACR_NAME:       $ACR_NAME
Vercel env:     NEXT_PUBLIC_API_URL=https://$FQDN
PULSE_DEPLOY_STATUS=SUCCESS
"@
  Write-Host $summary -ForegroundColor Green
  Add-Content -Path $LogFile -Value $summary
}
catch {
  $msg = "PULSE_DEPLOY_STATUS=FAILED: $($_.Exception.Message)"
  Write-Host $msg -ForegroundColor Red
  Add-Content -Path $LogFile -Value $msg
  exit 1
}
