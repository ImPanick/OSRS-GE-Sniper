# Standalone update script for OSRS GE Sniper (PowerShell)
# This script pulls the latest code from GitHub and restarts Docker services

Write-Host "🔄 OSRS GE Sniper - Auto Updater" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in a git repo
if (-not (Test-Path ".git")) {
    Write-Host "❌ Error: Not a git repository" -ForegroundColor Red
    Write-Host "Please run this script from the repository root" -ForegroundColor Red
    exit 1
}

# Get current commit
$currentCommit = (git rev-parse HEAD).Substring(0, 8)
Write-Host "📌 Current commit: $currentCommit" -ForegroundColor Yellow
Write-Host ""

# Stash any local changes
Write-Host "📦 Stashing local changes..." -ForegroundColor Cyan
git stash 2>&1 | Out-Null
Write-Host ""

# Fetch latest changes
Write-Host "⬇️  Fetching latest changes from GitHub..." -ForegroundColor Cyan
git fetch origin
Write-Host ""

# Check current branch
$branch = git rev-parse --abbrev-ref HEAD
Write-Host "🌿 Current branch: $branch" -ForegroundColor Yellow
Write-Host ""

# Pull latest changes
Write-Host "⬇️  Pulling latest changes..." -ForegroundColor Cyan
git pull origin $branch
Write-Host ""

# Get new commit
$newCommit = (git rev-parse HEAD).Substring(0, 8)
Write-Host "📌 New commit: $newCommit" -ForegroundColor Yellow
Write-Host ""

$currentFullCommit = git rev-parse HEAD
$newFullCommit = git rev-parse HEAD

if ($currentCommit -eq $newCommit) {
    Write-Host "✅ Already up to date!" -ForegroundColor Green
    exit 0
}

Write-Host "✅ Code updated successfully!" -ForegroundColor Green
Write-Host ""

# Check if Docker Compose is available
if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    if (Test-Path "docker\docker-compose.yml") {
        Write-Host "🐳 Restarting Docker services..." -ForegroundColor Cyan
        Set-Location docker
        docker-compose up -d --build
        Set-Location ..
        Write-Host ""
        Write-Host "✅ Docker services restarted!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  docker-compose.yml not found, skipping Docker restart" -ForegroundColor Yellow
    }
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    if (Test-Path "docker\docker-compose.yml") {
        Write-Host "🐳 Restarting Docker services..." -ForegroundColor Cyan
        Set-Location docker
        docker compose up -d --build
        Set-Location ..
        Write-Host ""
        Write-Host "✅ Docker services restarted!" -ForegroundColor Green
    } else {
        Write-Host "⚠️  docker-compose.yml not found, skipping Docker restart" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  Docker not found, skipping Docker restart" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Update complete!" -ForegroundColor Green

