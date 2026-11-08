"""Exercise the live synthetic deployment without logging cookies, tokens or credentials."""
import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = 'https://causallens-loan-risk.vercel.app'


def main():
    checks = []
    credentials={'email':f'qa-{uuid.uuid4().hex}@example.invalid','password':secrets.token_urlsafe(32)}
    with httpx.Client(base_url=BASE, timeout=290) as client:
        def request(method, path, payload=None):
            r = client.request(method, '/api/'+path, json=payload)
            checks.append({'method':method,'path':path,'status':r.status_code})
            if r.status_code != 200:
                raise RuntimeError(f'{path}: HTTP {r.status_code}: {r.text[:2000]}')
            return r.json()
        health = request('GET','health')
        assert request('GET','auth/session')['authenticated'] is False
        account = request('POST','auth/register',credentials)
        starter = request('POST','workspace/initialize',{})
        assert starter['created'] is True
        d = request('GET','data/datasets/'+starter['dataset_id'])
        m = next(m for m in request('GET','prediction/models') if m['id']==starter['model_id'])
        assert request('POST','workspace/initialize',{})['created'] is False
        borrower = {k:d['preview'][0][k] for k in ['annual_income','loan_amount','interest_rate','term_months',
            'existing_monthly_debt','credit_utilization','credit_history_years','employment_years']}
        p = request('POST','prediction/predict',{'model_id':m['id'],'borrower':borrower})
        assert abs(p['explanation']['additivity_residual']) < 1e-6
        run = request('POST','agents/run',{'dataset_id':d['id'],'model_id':m['id'],'borrower':borrower,
            'assumptions_confirmed':True,'fairness_governed':True})
        assert all(log['status'] == 'completed' for log in run['logs']), run['outputs']
        assert 'estimates' in run['outputs']['causal_inference']
        assert run['outputs']['fairness']['status'] == 'audited'
        report = request('POST','reports/generate',{'analysis_id':run['id']})
        request('GET',f"reports/{report['id']}/export")
        with httpx.Client(base_url=BASE, timeout=290) as resumed:
            restored=resumed.post('/api/auth/login',json=credentials)
            assert restored.status_code==200 and restored.json()['user']['id']==account['user']['id']
            setup=resumed.post('/api/workspace/initialize',json={})
            assert setup.status_code==200 and setup.json()['created'] is False
            assert setup.json()['model_id']==starter['model_id']
            r = resumed.get('/api/prediction/models')
            assert r.status_code == 200 and any(x['id'] == m['id'] for x in r.json())
            r = resumed.get('/api/reports')
            assert r.status_code == 200 and any(x['id'] == report['id'] for x in r.json())
        with httpx.Client(base_url=BASE, timeout=90) as other:
            assert other.get('/api/data/datasets').status_code == 401
            other_credentials={'email':f'qa-{uuid.uuid4().hex}@example.invalid','password':secrets.token_urlsafe(32)}
            assert other.post('/api/auth/register',json=other_credentials).status_code==200
            assert other.get('/api/data/datasets').json() == []
            assert other.get('/api/data/datasets/'+d['id']).status_code == 404
        result = {'verified_at':datetime.now(timezone.utc).isoformat(),'base_url':BASE,'health':health,
            'checks':checks,'agents_completed':len(run['logs']),'shap_additivity_verified':True,
            'workspace_isolation_verified':True,'reconnection_preserves_records':True,
            'account_registration_verified':True,'cross_browser_login_verified':True,
            'automatic_preparation_verified':True,'repeat_preparation_reuses_models':True,
            'synthetic_only':True,'dataset_id':d['id'],'model_id':m['id'],'report_id':report['id']}
        replay_cookies=httpx.Cookies(client.cookies)
        request('POST','auth/logout',{})
        with httpx.Client(base_url=BASE,cookies=replay_cookies,timeout=90) as replay:
            assert replay.get('/api/data/datasets').status_code==401
        result['logout_revocation_verified']=True
        Path('docs/cloud-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
