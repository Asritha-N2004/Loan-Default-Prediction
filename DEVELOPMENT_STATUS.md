# Development status

Updated 2026-11-08. Milestone 1: local analytical core and connected research UI. The full master prompt is **not complete**.

## Vercel backend fix

Account follow-up: hosted Sign in/Create account UI and real private account records are implemented, with scrypt password hashing, expiring/revocable secure cookies, bounded authentication attempts, and account-scoped persistence. First login automatically prepares the 2,000-row benchmark and four model baselines; subsequent visits and other-browser logins reuse the saved workspace. Setup is guarded by a leased lock and durable starter reference. The dashboard waits until it is ready. Tests: 28 backend and 16 frontend passed; build passed. Email verification/recovery, MFA, account deletion and production identity governance remain absent. See `docs/accounts.md`.

Dataset-selection follow-up: native dataset/model dropdowns were replaced by accessible in-page menus for embedded/mobile browsers. Existing datasets and matching models are selected automatically on initial load; switching datasets reconciles model lineage. Empty workspaces show the required next action. TypeScript/Vite build and 12 frontend tests passed, including pointer/keyboard menu use and dataset-to-model switching.

The full-stack synthetic research demo is deployed in `resum-projects/causallens-loan-risk` at https://causallens-loan-risk.vercel.app. React and FastAPI are separate services behind the same domain. Private Vercel Blob stores immutable analytical snapshots, dataset CSVs, and model artifacts. Temporary function files are a cache; artifacts are retrieved from durable storage before use. Signed HttpOnly account cookies isolate workspaces and restore them across browsers. No manual backend URL or API key is required for the hosted synthetic demo.

The live HTTPS check created a dataset, trained four calibrated models, ran SHAP prediction, executed all 15 agents with causal/fairness analysis, generated/exported a report, reconnected to saved records, and verified that a different session could not read them. Results are in `docs/cloud-validation.json`. Validation: 22 backend tests, seven frontend tests, and production build passed. Cloud SDK uses the CPU-only XGBoost distribution and a private store. Uploaded credentials, local runtime data, and environment files are excluded from deployments.

Hosted constraints: synthetic datasets only, at most 3,000 rows / five datasets / three model versions per browser workspace; CSV ingestion is disabled remotely. Clearing cookies signs out; the same account can sign in again to restore its workspace. Blob is an append-only object repository, not the full normalized PostgreSQL schema or a multi-record transaction system. Rate-limiting hardening, authenticated user accounts, retention/deletion workflows and real-data production approval remain future work. Local authenticated CSV workflows remain available.

## Implementation plan and phase ledger

| Phase | Milestone 1 delivery | Remaining acceptance work |
|---|---|---|
| 1 Inspect/init | Empty repository inspected; modular Python/React project initialized | None for initialization |
| 2 Database/ingestion | SQLAlchemy SQLite snapshots, PostgreSQL URL support, CSV/provenance validation | Full normalized schema, migrations, production PostgreSQL verification |
| 3 Financial features | Amortized payment, DTI, PTI, loan-to-income; dependencies recalculated | Dataset-specific adapters and missingness policy |
| 4 Prediction | Logistic, RF, gradient boosting, XGBoost; train-only CV calibration, holdout metrics | Temporal/group CV, tuning, threshold/utility study, imbalance experiments |
| 5 Explainability | Actual permutation SHAP, permutation importance, utilization PDP | ICE and attribution stability experiments |
| 6 Graph | NetworkX DAG checks, backdoor adjustment test, editable/versioned graph API/UI | Researcher evidence metadata per node/edge and discovery evaluation |
| 7 Causal inference | Cross-fit propensity, IPW ATE, DR ATE/ATT, propensity matching, PLR DML, overlap/balance/ESS/intervals | DoWhy/EconML adapters, formal sensitivity, CATE forests, DiD when valid |
| 8 Counterfactuals | Model scenarios, mutable-feature restrictions, financial recomputation, feasibility screen | Structural individual counterfactuals and richer constraint optimization |
| 9 Mitigation | Three supportive scenarios, cost/affordability/risk ranking, weight sensitivity | Causal policy optimization with applicable intervention data |
| 10 Fairness | Holdout DP/EO/equalized odds, group rates and calibration; small groups suppressed | Intervals, intersections, proxy study, recommendation-level audit |
| 11 Agents | 14 deterministic specialists plus supervisor execute actual tools | Richer independent critique and typed per-agent response schemas |
| 12 LangGraph | Typed state, conditional reflection routing, in-memory checkpoints, persisted outputs/timings | Parallel fan-out, durable resume, worker queue, timeouts/retry policy |
| 13 Reflection | SHAP additivity/lineage/error verification, scope critique, max-three routing | Evidence-backed corrective reanalysis; current critique exits after one cycle |
| 14 Frontend | Eight integrated workspaces covering the main workflows | Full 14-page design, richer charts and browser acceptance coverage |
| 15 Experiments | Four predictive baselines; ten-seed causal bias/RMSE/coverage | Noncausal agent baseline, ablations, temporal and external robustness |
| 16 Tests/deploy/docs | Unit/API tests, frontend build/test configuration, local commands, Docker assets | Final test results below; Docker daemon validation; production deployment |

## Governance implemented

Predictor allowlist, sensitive-feature exclusion, guarded audit use, input validation, loopback-only default or constant-time bearer-key checks, upload size/type limits, pseudonymization, dataset integrity hashes, append-only application snapshots, model/dataset lineage gates, audit records, hypothetical-vs-causal labels, human-review-pending reports. These are research safeguards, not production certification.

## Explicitly absent

Users/roles/password authentication, multi-tenant authorization, protected identity storage, TLS, encryption at rest, retention/deletion policies, tamper-proof database enforcement, background jobs, persistent LangGraph resume, PDF export, public dataset downloads, notebooks, true structural individual counterfactuals, formal unmeasured-confounding sensitivity, complete ablation study. No claim of all final acceptance criteria passing.

## Validation ledger

Measured experiments are in `docs/experiment_results.json`. Final verification: **18 backend tests passed** in 13.24 seconds; **4 React tests passed**; TypeScript checking and Vite production build passed. Raw backend output is retained in `docs/backend-test-results.txt`. Tests cover the complete workflow, graph versioning/adjustment/lineage, causal recovery, attribution additivity, forbidden scenario targets, upload provenance/PII exclusion, authentication, dataset/model integrity and financial calculations. Live browser verification trained four models, predicted a borrower with actual SHAP, ran causal estimation, executed all 15 graph nodes, and generated a human-review-pending report. `docs/workflow-verified.jpg` preserves this observed run. Both compact/mobile and desktop layout paths were inspected.

Docker runtime remains unverified: Docker CLI 29.9.3 exists, the daemon pipe does not, and `docker compose` is not installed. No deployment success is claimed. Frontend build reports a large-bundle warning and an ignored React Flow `use client` directive. Backend tests report upstream Starlette/pytest deprecations and a repeated joblib/NumPy 2.5 array-shape deprecation. These warnings did not fail execution; dependency migration remains needed.
