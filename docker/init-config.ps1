# Initialize config.json from config.json.example if it doesn't exist
# PowerShell version for Windows

$ErrorActionPreference = "Stop"

# Get the repository root (parent of docker/ directory)
if ($env:REPO_ROOT) {
    $RepoRoot = $env:REPO_ROOT
} else {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

$ConfigFile = Join-Path $RepoRoot "config.json"
$ConfigExample = Join-Path $RepoRoot "config.json.example"

if (-not (Test-Path $ConfigFile)) {
    if (Test-Path $ConfigExample) {
        Write-Host "📋 config.json not found. Copying from config.json.example..." -ForegroundColor Yellow
        Copy-Item $ConfigExample $ConfigFile
        Write-Host "✅ Created config.json from config.json.example" -ForegroundColor Green
        Write-Host "⚠️  Please edit config.json and set your discord_token and admin_key before starting services." -ForegroundColor Yellow
    } else {
        Write-Host "❌ Error: config.json.example not found at $ConfigExample" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ config.json already exists" -ForegroundColor Green
}

