# CausalLens — causality-aware loan risk research

Full-stack Vercel research demo: https://causallens-loan-risk.vercel.app. Create an account or sign in; the synthetic benchmark and four trained models load automatically. The same account restores its workspace across browsers. React and Python run together with private Blob persistence. The hosted demo supports synthetic data; authenticated CSV ingestion remains available locally. See [accounts](docs/accounts.md) and [Vercel deployment](docs/vercel-deployment.md).

An executable first milestone of **A Causality-Aware Multi-Agent Framework for Explainable Loan Default Prediction and Risk Mitigation**. The platform combines calibrated supervised models, hypothesis DAGs, identified-under-assumptions population estimates, predictive scenarios, fairness auditing, and deterministic analytical agents. No paid LLM API is needed.

This is research decision-support software. It never approves or rejects a loan, changes pricing, restructures debt, or executes transactions. All reports have human review pending. Milestone 1 is not a finished production lending platform; see [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md).

## Run locally

Python **3.12** was used for validation. The code requires Python 3.11+; dependency availability on other Python versions is not verified. Node 24 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The frontend proxies `/api` to port 8000. The API contract is at http://127.0.0.1:8000/docs. No API key permits loopback clients only. For authenticated access, set `API_KEY` in the backend process and enter the same key under **API connection** in the interface. Keys are held in React memory, not browser storage. Environment variables are read from the process; `.env` is not automatically loaded by Python.

On this host, npm was absent from PATH. An official npm CLI was downloaded into ignored `runtime/tools/package`; the verified fallback from the project root is `node runtime/tools/package/bin/npm-cli.js --prefix frontend run dev`. A standard Node installation includes npm and can use the commands above. Port 5173 was occupied during testing, so the verified preview selected port 5174 automatically.

1. Create the synthetic benchmark, then train the four model baselines.
2. Select the resulting model version and enter a financial profile in Borrower analysis.
3. Inspect the DAG and acknowledge identification assumptions in Causal laboratory before estimating counseling effects.
4. Compare hypothetical financial changes in Scenario studio.
5. Acknowledge governed audit use before evaluating fairness.
6. Run the LangGraph workflow in Agent execution and generate an evidence report.

## Dataset contract

Upload UTF-8 CSV with numeric columns:

`annual_income, loan_amount, interest_rate, term_months, existing_monthly_debt, credit_utilization, credit_history_years, employment_years, default`

Income, debt and principal must use one currency consistently. Interest is annual percentage, e.g. `12`; utilization is a fraction, e.g. `0.65`. Outcome is binary 0/1 with a documented horizon. Optional: `borrower_id`, binary `counseling`, governed categorical `audit_group` (at most 20 categories). Missing mandatory values are rejected for explicit cleaning. Protected fields and unknown columns are excluded from stored predictors. Direct borrower IDs are pseudonymized, audit labels recoded. Do not upload personal identifiers or real customer data into this research build.

Repeated borrowers and timestamped datasets are rejected until longitudinal/temporal adapters are available. A source, license and target definition are mandatory for uploads, but uploader statements are not independently verified. Public-dataset adapters/downloaders are not yet implemented; no real-world datasets are bundled. The synthetic generator is explicit simulation, never represented as observed borrower data.

## Reproducible commands

```powershell
python scripts/generate_synthetic_data.py
python scripts/train_models.py <dataset_id_printed_above>
python scripts/run_experiments.py
python -m pytest -q
cd frontend
npm run build
npm test
```

Experiment output is saved to `docs/experiment_results.json`; analytical datasets, model artifacts and SQLite snapshots are in ignored `runtime/`. Training runs use fixed seeds, a stratified holdout, and three-fold sigmoid calibration inside training only. Logistic regression is the predeclared default; final holdout performance is not used to choose a winner. Runtime joblib files are trusted server-generated artifacts; never replace them with untrusted files.

## Project layout

```text
backend/app/
  main.py        FastAPI endpoints, request schemas, upload and lineage checks
  data.py        validation, synthetic DGP and financial feature engineering
  ml.py          four calibrated models, evaluation, SHAP, permutation and PDP
  causal.py      hypothesis DAG, adjustment checks, IPW, AIPW, ATT, matching, PLR DML
  risk.py        constrained scenarios, mitigation ranking and fairness
  workflow.py    typed LangGraph supervisor, specialists, reflection and evidence
  database.py    SQLAlchemy append-only application snapshots and lineage
frontend/src/    React/TypeScript connected research workspace
scripts/        synthetic generation, training and measured experiments
tests/          analytical and complete API workflow tests
docs/           methodologies, architecture and actual experimental results
```

## API example

```powershell
$d = Invoke-RestMethod http://127.0.0.1:8000/api/data/synthetic -Method Post -ContentType application/json -Body '{"n":2000,"seed":42}'
$body = @{dataset_id=$d.id} | ConvertTo-Json
$m = Invoke-RestMethod http://127.0.0.1:8000/api/prediction/train -Method Post -ContentType application/json -Body $body
```

All requested analytical route families exist. Extra endpoints: `/api/data/synthetic`, `/api/causal/graph/default`, `/api/audit`, and JSON/CSV report export. Request models are strict Pydantic schemas. Responses are JSON snapshots; dedicated response schemas remain pending. Lists use bounded offset/limit pagination. Runs execute synchronously and return completed/partial snapshots. Both the start-run ID and result ID work for run lookups.

## Container configuration

Set strong `API_KEY` and `POSTGRES_PASSWORD` values in `.env` (use a URL-safe database password), then:

```powershell
docker compose up --build
```

The intended UI address is http://localhost:8080, with PostgreSQL and artifact volumes. Compose requires both secrets; there are no default passwords. Dockerfiles and Compose are provided, but container execution is not verified when Docker Desktop/daemon is unavailable. This configuration has no TLS termination, multi-user identity, RBAC or automatic retention. Do not expose it as a production service.

Host validation found both an unavailable Docker daemon and a missing Compose plugin. Install/start Docker Desktop with Compose before testing the container configuration. Local Python/React execution was verified independently.

## Research limits

Synthetic metrics do not establish financial utility. At the illustrative 0.5 threshold, the measured benchmark can have zero positive predictions, which is visible as zero recall/F1; threshold utility must be designed and validated separately. SHAP is predictive, DAG edges are hypotheses, observational ATEs are exploratory, and predictive scenarios are not causal counterfactuals. No individual treatment effect is identified. The mitigation engine never adds a population ATE to an individual's modeled probability.

Remaining work includes external datasets and licenses, temporal/group validation, richer robustness and ablation studies, causal forests/DiD where justified, protected-proxy analysis, fairness uncertainty, PDF reports, role-based human review, durable resumable execution, production security, database migrations and Docker validation.
