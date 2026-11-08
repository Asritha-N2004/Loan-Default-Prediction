# Full-stack Vercel deployment

Production: https://causallens-loan-risk.vercel.app
Team: Resume_Projects (`resum-projects`). Project: `causallens-loan-risk`.

## Backend connection resolved

The original frontend-only deployment displayed “Backend connection required.” The replacement deployment uses Vercel Services: Vite/React serves the interface, FastAPI handles `/api/*`, and both share one origin. The browser starts with Sign in/Create account. A signed account cookie restores the same workspace across browsers; no external backend URL or bearer key needs to be entered for this hosted demo. First sign-in prepares the benchmark and all four trained baselines automatically. Later visits reuse them. See `accounts.md` for authentication and setup details.

Private Vercel Blob storage retains dataset CSVs, model artifacts and immutable analysis snapshots. Temporary function files are only a cache. Artifacts are retrieved before use and checked against recorded SHA-256 digests. Snapshot keys are scoped to the authenticated account UUID. Another account cannot access them by copying a record ID; signing in to the same account in another browser restores them. Store credentials and the cookie-signing secret remain server-side.

The local deployment still uses SQLAlchemy/SQLite or PostgreSQL and the original key/loopback authentication. Its authenticated CSV upload feature is unchanged.

## Hosted research scope

The hosted demo uses synthetic data only. It runs actual calibrated prediction, SHAP, causal estimation, scenarios, mitigation comparisons, fairness evaluation, all analytical agents, reflection, reports and exports. It does not make lending decisions.

Limits per account workspace: up to five datasets, at most 3,000 rows per dataset, and three model versions. CSV upload is disabled on the hosted backend. Use simulated financial profiles; private customer data belongs in an appropriately authenticated deployment. Clearing cookies signs you out; sign in with the same email/password to restore the workspace. Password recovery is not yet implemented. The underlying synthetic objects persist until explicitly managed; automatic retention/deletion remains future work.

Private Blob is an append-only object repository, not the proposed normalized relational production database. Snapshot and kind-index writes are separate immutable operations rather than one transaction. Interrupted writes can leave orphaned objects. Mutation requests and agent outputs are audited; read requests are logged without creating extra Blob audit objects. Public-demo abuse controls and identity/retention management are not production-complete.

## Configuration

Root `vercel.json` defines the two services and routes API requests before the frontend catch-all. The frontend build receives public flags `VITE_API_BASE_URL=/` and `VITE_CLOUD_DEMO=1`. The backend reads `CLOUD_DEMO=1`, `CLOUD_SESSION_SECRET`, and its private store binding. These backend values are configured in Vercel, never embedded in frontend code.

`backend/requirements.txt` pins runtime dependencies and uses `xgboost-cpu` to avoid GPU dependency size. `backend/.python-version` selects Python 3.12. Root `.vercelignore` excludes local databases, credentials, environment files, runtime artifacts, tests, docs, caches and node_modules.

Deploy the **project root**, not just the frontend:

```powershell
vercel deploy . --scope resum-projects --project causallens-loan-risk --prod --yes
```

On this host:

```powershell
node runtime/vercel-cli/node_modules/vercel/dist/vc.js --global-config runtime/vercel-auth --scope resum-projects deploy . --project causallens-loan-risk --prod --yes
```

Deploying only `frontend/` would revert to the earlier disconnected interface. No paid plan upgrade or access-protection removal was used.

## Verification

- 22 backend tests passed, including Blob persistence after losing local artifact files, signed-cookie validation, origin checks, private-upload guards, and workspace isolation.
- Seven frontend tests and TypeScript/Vite production build passed.
- `python scripts/verify_cloud.py` exercised the live deployment: dataset creation, four-model training, SHAP, all 15 agent nodes including causal/fairness estimation, report generation/export, reconnect persistence and cross-session isolation. Its measured result is saved in `docs/cloud-validation.json` without cookies or credentials.
- The earlier dependency advisories were patched with Vite 7.3.7 and Vitest 4.1.12; the cloud build audit reports zero known vulnerabilities. Large-bundle and React Flow directive warnings remain non-fatal.

References: [Vercel Services](https://vercel.com/docs/services), [Private Blob storage](https://vercel.com/docs/vercel-blob/private-storage), [Python runtime](https://vercel.com/docs/functions/runtimes/python).
