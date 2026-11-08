"""Measured benchmark, with multiple seeds for causal bias/RMSE/coverage."""
import json
import sys
import importlib.metadata
import platform
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from backend.app.data import synthetic
from backend.app.causal import estimate
from backend.app.main import generate, train, SyntheticRequest, DatasetRequest


def main():
    dataset = generate(SyntheticRequest(n=2000))
    model = train(DatasetRequest(dataset_id=dataset['id']))
    records = []
    for seed in range(10):
        df, p = synthetic(3000, seed)
        result = estimate(df, assumptions_confirmed=True, synthetic_data=True)
        for method, e in result['estimates'].items():
            truth = p['known_att'] if method in ['matching', 'doubly_robust_att'] else p['known_ate']
            records.append({'seed': seed, 'method': method, 'truth': truth, 'estimate': e['estimate'],
                'error': e['estimate']-truth, 'covered': e['ci95'][0] <= truth <= e['ci95'][1] if e['ci95'] else None})
    summary = {}
    for method in {r['method'] for r in records}:
        rows = [r for r in records if r['method'] == method]
        summary[method] = {'bias': float(np.mean([r['error'] for r in rows])),
            'rmse': float(np.sqrt(np.mean([r['error']**2 for r in rows]))),
            'coverage': float(np.mean([r['covered'] for r in rows])) if rows[0]['covered'] is not None else None,
            'replications': len(rows)}
    result = {'dataset_id': dataset['id'], 'model_id': model['id'], 'n_prediction': 2000, 'n_causal': 3000,
        'generated_at': datetime.now(timezone.utc).isoformat(), 'python_version': platform.python_version(),
        'package_versions': {p: importlib.metadata.version(p) for p in ['numpy', 'scikit-learn', 'scipy', 'xgboost', 'shap', 'langgraph']},
        'predictive_models': model['models'], 'causal_summary': summary, 'causal_replications': records,
        'limitations': ['Synthetic benchmark only', 'Ten seeds do not precisely estimate nominal interval coverage',
                       'DML PLR matches ATE only approximately here because of near-constant simulated effects',
                       'Ablation, external validation, causal forests and longitudinal studies remain unimplemented']}
    out = Path('docs/experiment_results.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'model_id': model['id'], 'causal_summary': summary}, indent=2))


if __name__ == '__main__':
    main()
