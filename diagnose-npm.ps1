# NPM Diagnostic Script
Write-Host "=== NPM Diagnostic Script ===" -ForegroundColor Cyan
Write-Host ""

# Check Node and NPM versions
Write-Host "1. Node/NPM Versions:" -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    $npmVersion = npm --version
    Write-Host "   Node: $nodeVersion" -ForegroundColor Green
    Write-Host "   NPM:  $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "   ERROR: Node/NPM not found in PATH" -ForegroundColor Red
    exit 1
}

# Check execution policy
Write-Host "`n2. PowerShell Execution Policy:" -ForegroundColor Yellow
$policies = Get-ExecutionPolicy -List
$policies | Format-Table -AutoSize

# Check PATH
Write-Host "`n3. Node/NPM in PATH:" -ForegroundColor Yellow
$nodePath = (Get-Command node -ErrorAction SilentlyContinue).Source
$npmPath = (Get-Command npm -ErrorAction SilentlyContinue).Source
if ($nodePath) {
    Write-Host "   Node: $nodePath" -ForegroundColor Green
} else {
    Write-Host "   Node: NOT FOUND" -ForegroundColor Red
}
if ($npmPath) {
    Write-Host "   NPM:  $npmPath" -ForegroundColor Green
} else {
    Write-Host "   NPM:  NOT FOUND" -ForegroundColor Red
}

# Check npm config
Write-Host "`n4. NPM Configuration:" -ForegroundColor Yellow
Write-Host "   Prefix: $(npm config get prefix)"
Write-Host "   Cache:  $(npm config get cache)"
Write-Host "   Registry: $(npm config get registry)"

# Check permissions
Write-Host "`n5. Directory Permissions:" -ForegroundColor Yellow
$npmPrefix = npm config get prefix
$npmCache = npm config get cache
$testDirs = @($npmPrefix, $npmCache, "$PWD\frontend")
foreach ($dir in $testDirs) {
    if (Test-Path $dir) {
        $acl = Get-Acl $dir
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $hasAccess = $acl.Access | Where-Object { $_.IdentityReference -eq $currentUser -and $_.FileSystemRights -match "Write|FullControl" }
        if ($hasAccess) {
            Write-Host "   $dir : OK" -ForegroundColor Green
        } else {
            Write-Host "   $dir : PERMISSION ISSUE" -ForegroundColor Red
        }
    } else {
        Write-Host "   $dir : NOT FOUND" -ForegroundColor Yellow
    }
}

# Check for long path issues
Write-Host "`n6. Long Path Support:" -ForegroundColor Yellow
$longPathEnabled = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -ErrorAction SilentlyContinue).LongPathsEnabled
if ($longPathEnabled) {
    Write-Host "   Long Paths: ENABLED" -ForegroundColor Green
} else {
    Write-Host "   Long Paths: DISABLED (may cause issues)" -ForegroundColor Yellow
}

# Test npm connectivity
Write-Host "`n7. NPM Registry Connectivity:" -ForegroundColor Yellow
try {
    $pingResult = npm ping 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Registry: CONNECTED" -ForegroundColor Green
    } else {
        Write-Host "   Registry: CONNECTION FAILED" -ForegroundColor Red
        Write-Host "   Error: $pingResult" -ForegroundColor Red
    }
} catch {
    Write-Host "   Registry: ERROR - $_" -ForegroundColor Red
}

# Check for antivirus/common blockers
Write-Host "`n8. Common Issue Checks:" -ForegroundColor Yellow
$nodeModulesPath = "$PWD\frontend\node_modules"
if (Test-Path $nodeModulesPath) {
    Write-Host "   node_modules exists: YES" -ForegroundColor Yellow
    $fileCount = (Get-ChildItem -Path $nodeModulesPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host "   Files in node_modules: $fileCount" -ForegroundColor Cyan
} else {
    Write-Host "   node_modules exists: NO" -ForegroundColor Green
}

# Try a test npm command
Write-Host "`n9. Test NPM Command:" -ForegroundColor Yellow
try {
    $testResult = npm list --depth=0 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   npm list: SUCCESS" -ForegroundColor Green
    } else {
        Write-Host "   npm list: FAILED" -ForegroundColor Red
        Write-Host "   Output: $testResult" -ForegroundColor Red
    }
} catch {
    Write-Host "   npm list: ERROR - $_" -ForegroundColor Red
}

Write-Host "`n=== Diagnostic Complete ===" -ForegroundColor Cyan
Write-Host "Please share the output above, especially any RED errors." -ForegroundColor Yellow

