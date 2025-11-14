# Legacy Code

This directory contains legacy code that is no longer in use.

## Files

- `app_old.py` - Old Flask application with HTML/Jinja/HTMX templates. This has been replaced by the blueprint-based architecture in `app.py` and the Next.js frontend.
- `app_refactored.py` - Intermediate refactored version. Superseded by the current `app.py`.

## Important

**DO NOT USE THESE FILES IN PRODUCTION.**

All UI is now handled by the Next.js frontend (`/frontend`). The Flask backend (`/backend/app.py`) provides JSON APIs only.

