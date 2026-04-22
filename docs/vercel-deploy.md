# Vercel Deployment (B Plan, In Progress)

This branch starts the "full deployment" migration to Vercel with a phased approach.

## Current Phase

Phase 1 is implemented:

- Added a serverless entrypoint: `api/index.py`
- Added FastAPI app: `codex2gpt/serverless_app.py`
- Added Vercel config: `vercel.json`
- Added Python dependency file: `requirements.txt`
- Migrated these routes to serverless:
  - `GET /`
  - `POST /auth/login`
  - `DELETE /auth/login`
  - `GET /auth/status`
  - `GET /admin/api-keys`
  - `POST /admin/api-keys`
  - `DELETE /admin/api-keys/{key_id}`

All other routes currently return `501 not_implemented` in serverless mode.

## Deploy

1. Install Vercel CLI and login.
2. Link this project to a Vercel project.
3. Configure environment variables in Vercel dashboard.
4. Deploy.

## Required Environment Variables

At minimum:

- `LITE_DASHBOARD_FORCE_LOGIN=1`
- `LITE_DASHBOARD_LOCAL_BYPASS=0`
- `LITE_DASHBOARD_PASSWORD=<your-password>`
- `LITE_API_KEY_REQUIRED=1`

## Important Limitation (Current Phase)

This project still uses sqlite and local files for runtime state.
On Vercel, local filesystem is ephemeral, so this is not production-safe yet.

## Next Steps

1. Move runtime state from local sqlite to managed Postgres.
2. Move account/runtime files to managed storage.
3. Port `/v1/*` proxy routes from `BaseHTTPRequestHandler` into FastAPI.
4. Add integration tests for serverless endpoints.
