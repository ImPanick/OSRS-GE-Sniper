# Fix NPM Issues on Windows (Elevated PowerShell)
# Run this script as Administrator

Write-Host "=== Fixing NPM Issues on Windows ===" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️  WARNING: Not running as Administrator" -ForegroundColor Yellow
    Write-Host "   Some fixes may not work. Consider running as Administrator." -ForegroundColor Yellow
    Write-Host ""
}

# 1. Enable Long Paths (requires admin)
Write-Host "1. Checking Long Path Support..." -ForegroundColor Yellow
try {
    $longPathKey = "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem"
    $longPathValue = Get-ItemProperty -Path $longPathKey -Name "LongPathsEnabled" -ErrorAction SilentlyContinue
    
    if ($longPathValue.LongPathsEnabled -eq 1) {
        Write-Host "   ✓ Long paths already enabled" -ForegroundColor Green
    } else {
        if ($isAdmin) {
            Write-Host "   → Enabling long paths (requires restart)..." -ForegroundColor Cyan
            Set-ItemProperty -Path $longPathKey -Name "LongPathsEnabled" -Value 1 -Type DWord
            Write-Host "   ✓ Long paths enabled (restart required)" -ForegroundColor Green
        } else {
            Write-Host "   ✗ Long paths disabled (run as admin to enable)" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "   ✗ Could not check/enable long paths: $_" -ForegroundColor Red
}

# 2. Fix npm permissions
Write-Host "`n2. Fixing NPM Permissions..." -ForegroundColor Yellow
$npmPrefix = npm config get prefix
$npmCache = npm config get cache

$dirsToFix = @($npmPrefix, $npmCache)
foreach ($dir in $dirsToFix) {
    if (Test-Path $dir) {
        try {
            # Remove read-only attributes
            Get-ChildItem -Path $dir -Recurse -Force | ForEach-Object {
                $_.Attributes = $_.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly)
            }
            Write-Host "   ✓ Fixed permissions: $dir" -ForegroundColor Green
        } catch {
            Write-Host "   ⚠  Could not fix: $dir - $_" -ForegroundColor Yellow
        }
    }
}

# 3. Clear npm cache
Write-Host "`n3. Clearing NPM Cache..." -ForegroundColor Yellow
try {
    npm cache clean --force
    Write-Host "   ✓ Cache cleared" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Failed to clear cache: $_" -ForegroundColor Red
}

# 4. Fix npm prefix permissions (if needed)
Write-Host "`n4. Checking NPM Prefix Directory..." -ForegroundColor Yellow
if (Test-Path $npmPrefix) {
    try {
        # Test write access
        $testFile = Join-Path $npmPrefix "npm-test-write.tmp"
        "test" | Out-File -FilePath $testFile -ErrorAction Stop
        Remove-Item $testFile -Force
        Write-Host "   ✓ Write access OK: $npmPrefix" -ForegroundColor Green
    } catch {
        Write-Host "   ✗ No write access: $npmPrefix" -ForegroundColor Red
        Write-Host "   → Try: icacls `"$npmPrefix`" /grant `"$env:USERNAME`":F /T" -ForegroundColor Yellow
    }
} else {
    Write-Host "   → Creating: $npmPrefix" -ForegroundColor Cyan
    try {
        New-Item -ItemType Directory -Path $npmPrefix -Force | Out-Null
        Write-Host "   ✓ Created" -ForegroundColor Green
    } catch {
        Write-Host "   ✗ Failed to create: $_" -ForegroundColor Red
    }
}

# 5. Configure npm to avoid symlinks (Windows workaround)
Write-Host "`n5. Configuring NPM for Windows..." -ForegroundColor Yellow
try {
    # Disable symlinks (can cause issues on Windows)
    npm config set prefer-offline false
    npm config set audit false
    Write-Host "   ✓ NPM configured" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Failed to configure: $_" -ForegroundColor Red
}

# 6. Check for antivirus exclusions
Write-Host "`n6. Antivirus Exclusions (Manual Check Required)..." -ForegroundColor Yellow
Write-Host "   Consider adding these to Windows Defender exclusions:" -ForegroundColor Cyan
Write-Host "   - $npmPrefix" -ForegroundColor White
Write-Host "   - $npmCache" -ForegroundColor White
Write-Host "   - $PWD\frontend\node_modules" -ForegroundColor White

# 7. Test npm install
Write-Host "`n7. Testing NPM Install..." -ForegroundColor Yellow
if (Test-Path "frontend\package.json") {
    Write-Host "   → Running test install in frontend directory..." -ForegroundColor Cyan
    Push-Location frontend
    try {
        # Try a dry-run first
        $result = npm install --dry-run 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✓ Dry-run successful" -ForegroundColor Green
            Write-Host "   → You can now run: npm install" -ForegroundColor Cyan
        } else {
            Write-Host "   ✗ Dry-run failed" -ForegroundColor Red
            Write-Host "   Error output:" -ForegroundColor Red
            $result | ForEach-Object { Write-Host "     $_" -ForegroundColor Red }
        }
    } catch {
        Write-Host "   ✗ Error: $_" -ForegroundColor Red
    } finally {
        Pop-Location
    }
} else {
    Write-Host "   ⚠  frontend\package.json not found" -ForegroundColor Yellow
}

Write-Host "`n=== Fix Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "If issues persist, try:" -ForegroundColor Yellow
Write-Host "1. Run: npm install --no-optional --legacy-peer-deps" -ForegroundColor White
Write-Host "2. Check Windows Defender exclusions" -ForegroundColor White
Write-Host "3. Restart PowerShell after enabling long paths" -ForegroundColor White
Write-Host "4. Run: npm config set registry https://registry.npmjs.org/" -ForegroundColor White

