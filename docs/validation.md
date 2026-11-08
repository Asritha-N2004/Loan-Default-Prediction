# Validation record — 2026-11-08

## Account and automatic-loading follow-up

Final checks: **28 backend tests passed**, **16 frontend tests passed**, and TypeScript/Vite production build passed. The cloud build audit reported zero known dependency vulnerabilities. The live `cloud-validation.json` now verifies registration, automatic starter preparation, repeat setup without retraining, password login from a fresh browser client, account isolation, all 15 analytical agents, report export and immediate logout revocation. Revocation checks use authoritative Blob metadata to avoid cached delivery misses.

Live browser verification also created a synthetic QA account through the real signup form. Its 2,000-row benchmark and four model baselines appeared automatically without clicking Create benchmark or Train models. Reload and a subsequent sign-out/sign-in restored the same dataset/model identifiers. The QA session was signed out, and the public login page with Create account was left open. Screenshots: `login-page-verified.jpg` and `accounts-autoload-verified.jpg`. Synthetic test credentials were not stored or included in the validation JSON.

## Hosted backend follow-up

Selection-control follow-up: in-page dataset/model menus replace native popup menus. Twelve frontend tests and the production build pass; regression coverage includes click selection, keyboard navigation/Escape, empty-state guidance, outside-click dismissal and matching-model reconciliation when switching datasets.

The disconnected frontend has been replaced by React and FastAPI services at the same Vercel URL. Final backend suite: 22 passed (including private-Blob restoration, signed-session/origin guards, and workspace isolation); frontend suite: seven passed; production build passed. `scripts/verify_cloud.py` completed a live synthetic dataset → training → SHAP → 15-node agent workflow → report/export check and verified reconnection and cross-session isolation. Its output is in `cloud-validation.json`. Browser verification also created/trained a 2,000-row benchmark and reloaded the page to confirm that the saved dataset and model remained selectable. Screenshot: `vercel-backend-fixed.jpg`.

The earlier local milestone record below is retained as history. The Vercel research demo is synthetic-only; local authenticated CSV ingestion remains available. This follow-up does not claim that all master-prompt research/production acceptance criteria are complete.

- Python 3.12.10, Node 24.22.1. Direct dependency versions are pinned in `requirements.txt`; frontend transitive resolutions are in `frontend/package-lock.json`.
- Final `python -m pytest -q`: 18 passed, 13.24 seconds. Full output is `backend-test-results.txt`.
- Final TypeScript/Vite production build: passed. Main JS bundle is about 735 kB uncompressed; code splitting remains future work.
- Final Vitest/React Testing Library suite: 4 passed. Checks initial empty states, reproducible benchmark request, guarded fairness actions, and backend error display.
- Live API and Vite servers launched. The browser created/selected synthetic data, trained all four calibrated models, returned 32.7% modeled default risk for the example financial profile with actual SHAP, ran the five treatment estimators, completed all 15 workflow nodes, and generated a report pending human review. This example probability is model output on synthetic training data, not a real borrower assessment.
- Workflow evidence screenshot: `workflow-verified.jpg`. Node status means tool execution completed; a deliberately withheld fairness analysis without acknowledgment still counts as a successfully executed guard, not a completed fairness audit. Integration tests separately exercised governed fairness calculations.
- The 10-seed causal benchmark was rerun after final changes. DR ATE RMSE remained .0166984; measured predictive logistic ROC AUC remained .6209147 (see JSON for exact values).
- Model and dataset byte-integrity checks, graph-version propagation into agents and shared-key enforcement have regression coverage.
- Windows sandbox blocked asyncio socket-pair creation and Vite output writes. Test/build execution succeeded with elevated tool permissions; no application workaround disabled security checks.
- Docker CLI is installed but the daemon is not running and the Compose plugin is absent. Container and PostgreSQL runtime acceptance are unverified.
- Known dependency warnings: joblib 1.5.3 uses array-shape assignments deprecated in NumPy 2.5; installed Starlette/httpx and anyio/pytest integrations issue deprecations. React Flow's `use client` directive is ignored in the client-only Vite bundle. None caused a failed check. Upstream dependency cleanup remains required before production hardening.

This verifies milestone 1 only. It is not a claim of full master-prompt acceptance, regulatory compliance, causal discovery, production security, external validity, or real intervention effectiveness.
