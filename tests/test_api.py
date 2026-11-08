import io

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.data import synthetic, BASE

client = TestClient(app)


def checked(response):
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope='module')
def project():
    dataset = checked(client.post('/api/data/synthetic', json={'n': 1000, 'seed': 42}))
    model = checked(client.post('/api/prediction/train', json={'dataset_id': dataset['id']}))
    borrower = {k: dataset['preview'][0][k] for k in BASE}
    return dataset, model, borrower


def test_complete_workflow(project):
    d, m, b = project
    prediction = checked(client.post('/api/prediction/predict', json={'model_id': m['id'], 'borrower': b}))
    assert 0 <= prediction['probability'] <= 1
    assert abs(prediction['explanation']['additivity_residual']) < 1e-6
    assert set(m['models']) == {'logistic', 'random_forest', 'gradient_boosting', 'xgboost'}
    assert sum(sum(r) for r in m['models']['logistic']['confusion_matrix']) == 250
    scenario = checked(client.post('/api/counterfactual/generate', json={'model_id': m['id'], 'borrower': b, 'changes': {'term_months': 60}}))
    assert scenario['causal_effect'] is None
    assert scenario['alternative']['term_months'] == 60
    assert scenario['financial_features']['monthly_payment'] > 0
    causal = checked(client.post('/api/causal/estimate', json={'dataset_id': d['id'], 'assumptions_confirmed': True}))
    assert causal['claim_type'] == 'synthetic_benchmark_effect'
    mitigation = checked(client.post('/api/mitigation/evaluate', json={'model_id': m['id'], 'borrower': b, 'causal_estimate_id': causal['id']}))
    assert len(mitigation['recommendations']) == 3
    fair = checked(client.post('/api/fairness/evaluate', json={'model_id': m['id'], 'dataset_id': d['id'], 'governed': True}))
    assert fair['status'] == 'audited'
    graph = checked(client.get('/api/causal/graph/default'))
    graph['assumptions'] = 'Versioned researcher hypothesis used by integration test'
    graph = checked(client.post('/api/causal/graph/create', json=graph))
    run = checked(client.post('/api/agents/run', json={'model_id': m['id'], 'dataset_id': d['id'], 'borrower': b,
        'assumptions_confirmed': True, 'fairness_governed': True, 'graph_id': graph['id']}))
    assert len(run['logs']) == 15
    assert all(log['status'] == 'completed' for log in run['logs']), run['outputs']
    assert run['reflection_count'] <= 3
    assert run['outputs']['evidence']['shap_additivity_verified']
    assert run['outputs']['causal_graph']['assumptions'] == graph['assumptions']
    report = checked(client.post('/api/reports/generate', json={'analysis_id': run['id']}))
    assert report['human_review_status'] == 'pending'
    assert client.get(f"/api/reports/{report['id']}/export").status_code == 200
    assert client.get(f"/api/reports/{report['id']}/export?format=csv").status_code == 200
    assert checked(client.get(f"/api/agents/status/{run['run_id']}"))['id'] == run['id']
    assert checked(client.get('/api/audit'))


def test_protected_changes_and_lineage(project):
    d, m, b = project
    assert client.post('/api/counterfactual/generate', json={'model_id': m['id'], 'borrower': b, 'changes': {'age': 20}}).status_code == 422
    assert client.post('/api/prediction/predict', json={'model_id': m['id'], 'borrower': {**b, 'sex': 'F'}}).status_code == 422
    assert client.post('/api/fairness/evaluate', json={'model_id': m['id'], 'dataset_id': d['id']}).status_code == 422
    other = checked(client.post('/api/data/synthetic', json={'n': 200}))
    assert client.post('/api/fairness/evaluate', json={'model_id': m['id'], 'dataset_id': other['id'], 'governed': True}).status_code == 422


def test_graph_versioning():
    g = checked(client.get('/api/causal/graph/default'))
    first = checked(client.post('/api/causal/graph/create', json=g))
    updated = checked(client.put(f"/api/causal/graph/{first['id']}", json=g))
    assert updated['id'] != first['id'] and updated['parent_id'] == first['id']
    g['edges'].append(['default', 'annual_income'])
    assert client.post('/api/causal/graph/validate', json=g).status_code == 422


def test_upload_schema_and_provenance():
    df, _ = synthetic(200)
    df = df.drop(columns=['audit_group'])
    df['email'] = 'do-not-retain@example.com'
    result = checked(client.post('/api/data/upload', files={'file': ('loans.csv', df.to_csv(index=False), 'text/csv')},
        data={'source': 'Controlled test', 'license': 'Test only', 'target_definition': 'Simulated default'}))
    assert result['provenance']['synthetic'] is False
    assert 'email' not in result['preview'][0]
    assert client.post('/api/data/upload', files={'file': ('bad.csv', 'a,b\n1,2')},
        data={'source': 'test', 'license': 'test', 'target_definition': 'test'}).status_code == 422


def test_no_key_rejects_remote_access():
    remote = TestClient(app, client=('192.0.2.1', 12345))
    assert remote.get('/api/data/datasets').status_code == 403


def test_missing_record():
    assert client.get('/api/data/datasets/no-such-id').status_code == 404


def test_api_key_is_enforced(monkeypatch):
    import backend.app.main as main
    monkeypatch.setattr(main, 'API_KEY', 'test-only-long-research-key')
    assert client.get('/api/data/datasets').status_code == 401
    assert client.get('/api/data/datasets', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.get('/api/data/datasets', headers={'Authorization': 'Bearer test-only-long-research-key'}).status_code == 200


def test_dataset_and_model_integrity(project):
    from backend.app.config import RUNTIME
    d, m, b = project
    path = RUNTIME / f"{d['file_id']}.csv"
    original = path.read_bytes()
    try:
        path.write_bytes(original+b'\n')
        response = client.post('/api/causal/estimate', json={'dataset_id': d['id'], 'assumptions_confirmed': True})
        assert response.status_code == 422 and 'integrity' in response.text
    finally:
        path.write_bytes(original)
    path = RUNTIME / f"{m['artifact_id']}.joblib"
    original = path.read_bytes()
    try:
        path.write_bytes(original+b'tamper')
        response = client.post('/api/prediction/predict', json={'model_id': m['id'], 'borrower': b})
        assert response.status_code == 422 and 'integrity' in response.text
    finally:
        path.write_bytes(original)
