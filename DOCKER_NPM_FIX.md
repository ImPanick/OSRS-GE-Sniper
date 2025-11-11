# Docker NPM Install Fix

## Issues Fixed

1. **Added npm timeout configuration** - Prevents hanging on network issues
2. **Added retry logic** - Automatically retries failed downloads
3. **Reduced npm output** - Uses `--progress=false` and `--no-audit` to speed up builds
4. **Better error handling** - Falls back to npm install if npm ci fails
5. **Improved logging** - Shows what's happening during the build

## Changes Made to `docker/dockerfile.frontend`

- Added npm registry configuration with timeouts
- Added retry mechanisms (3 retries, 20s-120s timeouts)
- Added 5-minute fetch timeout
- Reduced verbose output during install
- Added fallback from npm ci to npm install

## How to Test

1. **Clean Docker build cache:**
   ```powershell
   cd docker
   docker compose build --no-cache frontend
   ```

2. **Build with verbose output to see progress:**
   ```powershell
   docker compose build --progress=plain frontend
   ```

3. **If it still hangs, try building just the deps stage:**
   ```powershell
   docker build --target deps -t test-deps -f docker/dockerfile.frontend .
   ```

## Additional Recommendations

### Option 1: Generate package-lock.json (Recommended)

This will make builds much faster. Run this when npm is working:

```powershell
cd frontend
npm install
# This creates package-lock.json
```

Then commit `package-lock.json` to git.

### Option 2: Use BuildKit with better progress

Enable Docker BuildKit for better build output:

```powershell
$env:DOCKER_BUILDKIT=1
$env:COMPOSE_DOCKER_CLI_BUILD=1
cd docker
docker compose build frontend
```

### Option 3: Build with network debugging

If npm install hangs, it might be a network issue. Try:

```powershell
docker compose build --progress=plain frontend 2>&1 | Tee-Object build.log
```

This will show exactly where it's hanging.

## Common Causes of npm Install Hanging

1. **Network timeout** - Fixed with timeout configuration
2. **npm registry issues** - Fixed with explicit registry config
3. **Too much output** - Fixed with --progress=false
4. **Security audit** - Fixed with --no-audit
5. **Missing package-lock.json** - Can be fixed by generating it locally

## Next Steps

1. Try building with the updated Dockerfile
2. If it still hangs, check the build.log for where it stops
3. Consider generating package-lock.json when npm is working
4. Use BuildKit for better progress visibility

