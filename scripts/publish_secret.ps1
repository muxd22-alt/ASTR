param(
    [string]$Repo = "muxd22-alt/ASTR",
    [string]$File = "profiles.local/profiles.json"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "Python venv not found at $py. Create it with: python -m venv .venv"
}

if (-not (Test-Path $File)) {
    throw "Data file not found: $File. Copy profiles.local/profiles.template.json first."
}

Write-Host "==> Validating $File"
& $py -m astromind validate --file $File
if ($LASTEXITCODE -ne 0) {
    throw "Validation failed. Fix the file before publishing the secret."
}

Write-Host "==> Encoding profiles"
$previousEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$encoded = (& $py -m astromind encode --file $File 2>$null | Out-String).Trim()
$ErrorActionPreference = $previousEap
if (-not $encoded) {
    throw "Encoding failed."
}

if ($env:GH_TOKEN) {
    $token = $env:GH_TOKEN.Trim()
} else {
    $env:GIT_TERMINAL_PROMPT = "0"
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $credInput = "protocol=https`nhost=github.com`n`n"
    $cred = $credInput | git credential fill 2>$null
    $ErrorActionPreference = $previousEap
    $token = (($cred | Where-Object { $_ -like "password=*" }) -replace "^password=", "").Trim()
}
if (-not $token) {
    throw "No GitHub token found. Set GH_TOKEN or sign in with Git Credential Manager."
}

$headers = @{
    Authorization          = "Bearer $token"
    "User-Agent"           = "astromind-publish"
    "Accept"               = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Write-Host "==> Fetching repository public key"
$publicKey = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/actions/secrets/public-key" -Headers $headers

$env:ASTROMIND_PK = $publicKey.key
$env:ASTROMIND_SECRET = $encoded
$sealed = & $py -c "import os, base64; from nacl import public; pk = public.PublicKey(base64.b64decode(os.environ['ASTROMIND_PK'])); box = public.SealedBox(pk); print(base64.b64encode(box.encrypt(os.environ['ASTROMIND_SECRET'].encode('utf-8'))).decode())"
Remove-Item Env:\ASTROMIND_PK, Env:\ASTROMIND_SECRET -ErrorAction SilentlyContinue

if (-not $sealed) {
    throw "Encryption failed. Install the helper with: .\.venv\Scripts\python.exe -m pip install pynacl"
}

$payload = @{
    encrypted_value = ($sealed | Out-String).Trim()
    key_id          = $publicKey.key_id
} | ConvertTo-Json -Compress

Write-Host "==> Updating secret ASTROMIND_PROFILES in $Repo"
$uri = "https://api.github.com/repos/$Repo/actions/secrets/ASTROMIND_PROFILES"
Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $payload -ContentType "application/json" | Out-Null

Write-Host "Done. Secret ASTROMIND_PROFILES is up to date."
