"""Local research API. /docs exposes the executable contract."""
import io
import json
import logging
import os
import secrets
import time
import uuid
from typing import Annotated

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from . import causal, database as db, ml, risk
from .config import API_KEY, RUNTIME, CLOUD_DEMO
from .data import BASE, fingerprint, synthetic, validate
from .workflow import run_analysis

logger = logging.getLogger('loan_risk')
PUBLIC_ACCOUNT_PATHS = {'/api/auth/register','/api/auth/login','/api/auth/session','/api/auth/logout','/api/health'}


def authenticate(request: Request):
    if CLOUD_DEMO:
        if request.url.path in PUBLIC_ACCOUNT_PATHS:
            return
        if not getattr(request.state, 'workspace', None):
            raise HTTPException(401, 'Sign in to load your research workspace')
    elif API_KEY:
        supplied = request.headers.get('authorization', '').removeprefix('Bearer ')
        if not secrets.compare_digest(supplied, API_KEY):
            raise HTTPException(401, 'Invalid API key')
    elif request.client is None or request.client.host not in {'127.0.0.1', '::1', 'testclient', 'localhost'}:
        raise HTTPException(403, 'Configure API_KEY for non-loopback access')


app = FastAPI(title='Causal Loan Risk Research', version='0.1.0', dependencies=[Depends(authenticate)])
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:8080').split(','),
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type'])


@app.middleware('http')
async def audit_request(request, call_next):
    started = time.perf_counter()
    workspace_token = file_token = None
    if CLOUD_DEMO and request.url.path.startswith('/api/'):
        from urllib.parse import urlsplit
        from .cloud_session import COOKIE_NAME
        from .cloud_storage import workspace, request_files
        from . import accounts
        origin = request.headers.get('origin')
        if (origin and urlsplit(origin).netloc != request.headers.get('host')) or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse(status_code=403, content={'detail': 'Hosted demo requires same-origin access'})
        account = await run_in_threadpool(accounts.current_account,request.cookies.get(COOKIE_NAME))
        request.state.account = account
        if account:
            request.state.workspace = account['id']
            workspace_token = workspace.set(account['id'])
            file_token = request_files.set(set())
        elif request.url.path not in PUBLIC_ACCOUNT_PATHS:
            return JSONResponse(status_code=401,content={'detail':'Sign in to load your research workspace'},headers={'Cache-Control':'no-store'})
    try:
        response = await call_next(request)
        if request.url.path.startswith('/api/'):
            if not CLOUD_DEMO or (request.method != 'GET' and workspace_token is not None):
                await run_in_threadpool(db.save, 'audit', {'method': request.method, 'path': request.url.path,
                    'status': response.status_code, 'duration_seconds': time.perf_counter()-started})
            logger.info(json.dumps({'path': request.url.path, 'status': response.status_code}))
            response.headers['Cache-Control'] = 'private, no-store'
        return response
    finally:
        if workspace_token is not None:
            workspace.reset(workspace_token)
            request_files.reset(file_token)


@app.exception_handler(ValueError)
async def invalid(_, error):
    return JSONResponse(status_code=422, content={'detail': str(error)})


@app.exception_handler(KeyError)
async def missing(_, error):
    return JSONResponse(status_code=404, content={'detail': 'Record not found'})


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    errors = error.errors()
    if request.url.path.startswith('/api/auth/'):
        errors = [{k:v for k,v in item.items() if k in {'loc','msg','type'}} for item in errors]
    return JSONResponse(status_code=422,content={'detail':json.loads(json.dumps(errors,default=str))})


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Borrower(Strict):
    annual_income: float = Field(gt=0, le=1e8)
    loan_amount: float = Field(gt=0, le=1e8)
    interest_rate: float = Field(ge=0, le=100)
    term_months: int = Field(ge=1, le=600)
    existing_monthly_debt: float = Field(ge=0, le=1e7)
    credit_utilization: float = Field(ge=0, le=1)
    credit_history_years: float = Field(ge=0, le=100)
    employment_years: float = Field(ge=0, le=80)


class DatasetRequest(Strict):
    dataset_id: str


class SyntheticRequest(Strict):
    n: int = Field(default=2000, ge=200, le=50000)
    seed: int = Field(default=42, ge=0, le=2**32-1)


class PredictionRequest(Strict):
    model_id: str
    borrower: Borrower


class ScenarioRequest(PredictionRequest):
    changes: dict[str, float]


class GraphRequest(Strict):
    nodes: list[str] = Field(max_length=100)
    edges: list[tuple[str, str]] = Field(max_length=500)
    assumptions: str = Field(min_length=5, max_length=10000)


class CausalRequest(DatasetRequest):
    graph_id: str | None = None
    treatment: str = 'counseling'
    outcome: str = 'default'
    confounders: list[str] = Field(default_factory=lambda: ['annual_income', 'credit_utilization', 'employment_years'])
    assumptions_confirmed: bool = False


class FairnessRequest(DatasetRequest):
    model_id: str
    governed: bool = False


class MitigationRequest(PredictionRequest):
    causal_estimate_id: str | None = None


class RunRequest(PredictionRequest):
    dataset_id: str
    graph_id: str | None = None
    assumptions_confirmed: bool = False
    fairness_governed: bool = False


class ReportRequest(Strict):
    analysis_id: str


class Credentials(Strict):
    email: str = Field(min_length=3,max_length=254)
    password: SecretStr = Field(min_length=1,max_length=128)


def require_cloud_accounts():
    if not CLOUD_DEMO:
        raise HTTPException(404,'Account authentication is available on the hosted research deployment')


def account_response(account):
    from .cloud_session import COOKIE_NAME, SESSION_TTL, signed_cookie
    response = JSONResponse({'authenticated':True,'user':account})
    response.set_cookie(COOKIE_NAME,signed_cookie(account['id']),secure=True,httponly=True,
                        samesite='strict',max_age=SESSION_TTL,path='/')
    return response


@app.get('/api/auth/session')
def account_session(request: Request):
    require_cloud_accounts()
    account = getattr(request.state,'account',None)
    return {'authenticated':bool(account),'user':account}


@app.post('/api/auth/register')
def register_account(credentials: Credentials, request: Request):
    require_cloud_accounts()
    from . import accounts
    address = request.headers.get('x-vercel-forwarded-for') or (request.client.host if request.client else 'unknown')
    account = accounts.register(credentials.email,credentials.password.get_secret_value(),address)
    return account_response(account)


@app.post('/api/auth/login')
def login_account(credentials: Credentials, request: Request):
    require_cloud_accounts()
    from . import accounts
    address = request.headers.get('x-vercel-forwarded-for') or (request.client.host if request.client else 'unknown')
    return account_response(accounts.login(credentials.email,credentials.password.get_secret_value(),address))


@app.post('/api/auth/logout')
def logout_account(request: Request):
    require_cloud_accounts()
    from . import accounts
    from .cloud_session import COOKIE_NAME
    accounts.logout(request.cookies.get(COOKIE_NAME))
    response = JSONResponse({'authenticated':False})
    response.delete_cookie(COOKIE_NAME,path='/',secure=True,httponly=True,samesite='strict')
    return response


@app.post('/api/workspace/initialize')
def initialize_workspace(request: Request):
    require_cloud_accounts()
    from . import accounts
    return accounts.initialize_workspace(request.state.workspace,
        lambda:generate(SyntheticRequest(n=2000,seed=42)),
        lambda dataset_id:train(DatasetRequest(dataset_id=dataset_id)))


def ingest(df, provenance):
    quality = validate(df)
    # Drop unrecognized columns, including incidental direct identifiers.
    keep = [c for c in BASE+['default', 'counseling', 'audit_group', 'borrower_id'] if c in df]
    cleaned = df[keep].copy()
    if 'borrower_id' in cleaned:
        # Equality-preserving pseudonyms scoped to this dataset; no raw identifiers retained.
        import hashlib
        salt = secrets.token_bytes(32)
        cleaned['borrower_id'] = [hashlib.sha256(salt+str(v).encode()).hexdigest() for v in cleaned.borrower_id]
    if 'audit_group' in cleaned:
        if cleaned.audit_group.nunique() > 20:
            raise ValueError('audit_group must have at most 20 governed categories')
        # Do not retain identifying category strings supplied in an upload.
        groups = sorted(cleaned.audit_group.dropna().astype(str).unique())
        codes = {v: f'Group {i+1}' for i, v in enumerate(groups)}
        cleaned['audit_group'] = cleaned.audit_group.astype(str).map(codes).fillna('Unknown')
    file_id = str(uuid.uuid4())
    path = RUNTIME / f'{file_id}.csv'
    cleaned.to_csv(path, index=False)
    if CLOUD_DEMO:
        from .cloud_storage import persist_artifact
        persist_artifact(path)
    return db.save('dataset', {'name': provenance['name'], 'file_id': file_id, 'provenance': provenance,
        'content_sha256': __import__('hashlib').sha256(path.read_bytes()).hexdigest(), 'quality': quality,
        'preview': cleaned.head(5).drop(columns=['borrower_id'], errors='ignore').to_dict(orient='records')})


def dataset_frame(dataset_id):
    meta = db.get(dataset_id, 'dataset')
    path = RUNTIME / f"{uuid.UUID(meta['file_id'])}.csv"
    if CLOUD_DEMO:
        from .cloud_storage import fetch_artifact
        fetch_artifact(path)
    if __import__('hashlib').sha256(path.read_bytes()).hexdigest() != meta['content_sha256']:
        raise ValueError('Dataset integrity check failed')
    frame = pd.read_csv(path)
    return meta, frame


def matching_model(model_id, dataset_id):
    model = db.get(model_id, 'model')
    if model['dataset_id'] != dataset_id:
        raise ValueError('Model and dataset lineage do not match')
    return model


@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': app.version,
        'mode': 'synthetic_research_demo' if CLOUD_DEMO else 'research_decision_support',
        'authentication': 'account_session_cookie' if CLOUD_DEMO else 'api_key' if API_KEY else 'loopback_only',
        'persistence': 'private_vercel_blob' if CLOUD_DEMO else 'sqlalchemy'}


@app.post('/api/data/synthetic')
def generate(request: SyntheticRequest):
    if CLOUD_DEMO and (request.n > 3000 or len(db.listing('dataset', 0, 5)) >= 5):
        raise ValueError('Hosted demo allows up to 3,000 rows and five datasets per browser workspace')
    df, provenance = synthetic(request.n, request.seed)
    return ingest(df, provenance)


@app.post('/api/data/upload')
async def upload(file: UploadFile = File(...), source: str = Form(...), license: str = Form(...),
                 target_definition: str = Form(...), audit_use_authorized: bool = Form(False)):
    if CLOUD_DEMO:
        raise HTTPException(403, 'CSV upload is disabled in the hosted synthetic demo; use the authenticated local deployment for private borrower data')
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise ValueError('Upload a UTF-8 CSV file with the documented schema')
    content = await file.read(10*1024*1024+1)
    if len(content) > 10*1024*1024:
        raise HTTPException(413, 'Maximum CSV size is 10 MiB')
    try:
        frame = pd.read_csv(io.BytesIO(content))
    except Exception as error:
        raise ValueError('Invalid UTF-8 CSV') from error
    if len(frame) > 50000:
        raise ValueError('Maximum 50,000 rows')
    if 'audit_group' in frame and not audit_use_authorized:
        raise ValueError('Explicit authorization required to retain fairness audit attributes')
    return ingest(frame, {'name': 'Uploaded loan dataset', 'source': source[:2000], 'license': license[:1000],
        'target': target_definition[:2000], 'synthetic': False, 'upload_sha256': __import__('hashlib').sha256(content).hexdigest(),
        'limitations': ['Uploader-defined provenance is not independently verified']})


@app.get('/api/data/datasets')
def datasets(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    return db.listing('dataset', offset, limit)


@app.get('/api/data/datasets/{dataset_id}')
def dataset(dataset_id: str):
    return db.get(dataset_id, 'dataset')


@app.get('/api/data/quality/{dataset_id}')
def quality(dataset_id: str):
    return db.get(dataset_id, 'dataset')['quality']


@app.post('/api/prediction/train')
def train(request: DatasetRequest):
    if CLOUD_DEMO and len(db.listing('model', 0, 3)) >= 3:
        raise ValueError('Hosted demo allows three model versions per browser workspace')
    _, frame = dataset_frame(request.dataset_id)
    return db.save('model', ml.train(frame, request.dataset_id), request.dataset_id)


@app.get('/api/prediction/models')
def models(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    return db.listing('model', offset, limit)


@app.post('/api/prediction/predict')
def predict(request: PredictionRequest):
    model = db.get(request.model_id, 'model')
    return db.save('prediction', ml.predict(model, request.borrower.model_dump()), request.model_id)


@app.get('/api/prediction/{prediction_id}')
def prediction(prediction_id: str):
    return db.get(prediction_id, 'prediction')


@app.post('/api/causal/graph/create')
def graph_create(request: GraphRequest):
    g = request.model_dump()
    return db.save('graph', {**g, 'validation': causal.validate_graph(g)})


@app.get('/api/causal/graph/default')
def graph_default():
    return causal.default_graph()


@app.post('/api/causal/graph/validate')
def graph_validate(request: GraphRequest):
    return causal.validate_graph(request.model_dump())


@app.get('/api/causal/graph/{graph_id}')
def graph_get(graph_id: str):
    return db.get(graph_id, 'graph')


@app.put('/api/causal/graph/{graph_id}')
def graph_update(graph_id: str, request: GraphRequest):
    db.get(graph_id, 'graph')
    g = request.model_dump()
    return db.save('graph', {**g, 'validation': causal.validate_graph(g)}, graph_id)


@app.post('/api/causal/estimate')
def estimate(request: CausalRequest):
    meta, frame = dataset_frame(request.dataset_id)
    graph = db.get(request.graph_id, 'graph') if request.graph_id else causal.default_graph()
    result = causal.estimate(frame, treatment=request.treatment, outcome=request.outcome, confounders=request.confounders,
        graph=graph, assumptions_confirmed=request.assumptions_confirmed, synthetic_data=meta['provenance']['synthetic'])
    return db.save('causal', {**result, 'dataset_id': request.dataset_id, 'graph_snapshot': graph}, request.dataset_id)


@app.get('/api/causal/estimates/{estimate_id}')
def causal_get(estimate_id: str):
    return db.get(estimate_id, 'causal')


@app.post('/api/causal/diagnostics')
def diagnostics(request: CausalRequest):
    return estimate(request)['diagnostics']


@app.post('/api/counterfactual/generate')
def counterfactual(request: ScenarioRequest):
    result = risk.scenario(db.get(request.model_id, 'model'), request.borrower.model_dump(), request.changes)
    return db.save('counterfactual', result, request.model_id)


@app.get('/api/counterfactual/{scenario_id}')
def counterfactual_get(scenario_id: str):
    return db.get(scenario_id, 'counterfactual')


@app.post('/api/mitigation/evaluate')
def mitigation(request: MitigationRequest):
    model = db.get(request.model_id, 'model')
    effect = db.get(request.causal_estimate_id, 'causal') if request.causal_estimate_id else None
    if effect and effect['dataset_id'] != model['dataset_id']:
        raise ValueError('Causal evidence and predictive model must share dataset lineage')
    return db.save('mitigation', risk.mitigate(model, request.borrower.model_dump(), effect), request.model_id)


@app.get('/api/mitigation/recommendations/{analysis_id}')
def recommendations(analysis_id: str):
    return db.get(analysis_id, 'mitigation')


@app.post('/api/fairness/evaluate')
def fairness(request: FairnessRequest):
    _, df = dataset_frame(request.dataset_id)
    model = matching_model(request.model_id, request.dataset_id)
    return db.save('fairness', risk.fairness(df, model, request.governed), request.model_id)


@app.get('/api/fairness/{evaluation_id}')
def fairness_get(evaluation_id: str):
    return db.get(evaluation_id, 'fairness')


@app.post('/api/agents/run')
def agents(request: RunRequest):
    _, df = dataset_frame(request.dataset_id)
    model = matching_model(request.model_id, request.dataset_id)
    run = db.save('run', {'status': 'started', 'dataset_id': request.dataset_id, 'model_id': request.model_id}, request.model_id)
    graph = db.get(request.graph_id, 'graph') if request.graph_id else causal.default_graph()
    result = run_analysis({**request.model_dump(), 'graph': graph, 'run_id': run['id']}, df, model)
    completed = db.save('run_result', {'run_id': run['id'], 'outputs': result['outputs'], 'logs': result['logs'],
        'status': result['outputs']['reporting'].get('completion', 'partial'), 'reflection_count': result['reflection_count']}, run['id'])
    return completed


def result_for(run_id):
    # Results are addressed by their snapshot ID in milestone 1.
    result = db.get(run_id)
    if result['kind'] == 'run_result':
        return result
    if result['kind'] == 'run':
        for r in db.listing('run_result', 0, 10000):
            if r['run_id'] == run_id:
                return r
        return result
    raise KeyError('Run not found')


@app.get('/api/agents/status/{run_id}')
def status(run_id: str):
    return result_for(run_id)


@app.get('/api/agents/logs/{run_id}')
def logs(run_id: str):
    return result_for(run_id).get('logs', [])


@app.get('/api/reflection/{analysis_id}')
def reflection(analysis_id: str):
    return result_for(analysis_id)['outputs']['reflection']


@app.get('/api/explanations/{analysis_id}')
def explanations(analysis_id: str):
    return result_for(analysis_id)['outputs']['explanation']


@app.post('/api/reports/generate')
def report(request: ReportRequest):
    result = result_for(request.analysis_id)
    if 'outputs' not in result:
        raise ValueError('Analysis is not complete')
    return db.save('report', {'analysis_id': result['id'], 'report': result['outputs'],
        'evidence_log': result['logs'], 'human_review_status': 'pending'}, result['id'])


@app.get('/api/reports')
def reports(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    return db.listing('report', offset, limit)


@app.get('/api/reports/{report_id}/export')
def export(report_id: str, format: str = Query('json', pattern='^(json|csv)$')):
    saved = db.get(report_id, 'report')
    if format == 'csv':
        # Only structured numeric evidence; avoid user-provided strings/formula injection.
        p = saved['report'].get('prediction', {})
        content = pd.DataFrame([{'default_probability': p.get('probability'), 'human_review_required': True}]).to_csv(index=False)
        return Response(content, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="risk-report.csv"'})
    return Response(json.dumps(saved, indent=2), media_type='application/json', headers={'Content-Disposition': 'attachment; filename="risk-report.json"'})


@app.get('/api/audit')
def audit(offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    return db.listing('audit', offset, limit)
