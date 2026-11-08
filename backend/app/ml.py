"""Calibrated supervised baselines. Holdout is never used to select a winner."""
import uuid
import hashlib

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance, partial_dependence
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss, confusion_matrix,
    f1_score, log_loss, precision_score, recall_score, roc_auc_score, roc_curve, precision_recall_curve)
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from .config import RUNTIME, SEED, CLOUD_DEMO
from .data import FEATURES, engineer, validate


def metrics(y, p):
    pred = p >= .5
    frac, mean = calibration_curve(y, p, n_bins=8, strategy='quantile')
    fpr, tpr, _ = roc_curve(y, p)
    precision, recall, _ = precision_recall_curve(y, p)
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(np.mean(bins == b) * abs(np.mean(y[bins == b]) - np.mean(p[bins == b])) for b in np.unique(bins))
    return {'accuracy': float(accuracy_score(y, pred)), 'precision': float(precision_score(y, pred, zero_division=0)),
        'recall': float(recall_score(y, pred, zero_division=0)), 'f1': float(f1_score(y, pred, zero_division=0)),
        'roc_auc': float(roc_auc_score(y, p)), 'pr_auc': float(average_precision_score(y, p)),
        'brier': float(brier_score_loss(y, p)), 'log_loss': float(log_loss(y, p)), 'ece': float(ece),
        'confusion_matrix': confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        'calibration': {'predicted': mean.tolist(), 'observed': frac.tolist()},
        'roc': {'fpr': fpr.tolist(), 'tpr': tpr.tolist()}, 'pr': {'precision': precision.tolist(), 'recall': recall.tolist()}}


def train(df: pd.DataFrame, dataset_id: str):
    validate(df)
    if len(df) < 200 or df.default.value_counts().min() < 20 or df.default.nunique() != 2:
        raise ValueError('Training requires 200 rows and at least 20 observations of each outcome')
    if df[FEATURES[:8]].duplicated().any():
        raise ValueError('Duplicate predictor records must be resolved before splitting')
    frame = engineer(df)
    train_idx, test_idx = train_test_split(np.arange(len(df)), test_size=.25, stratify=df.default, random_state=SEED)
    X, y = frame[FEATURES], frame.default
    estimators = {
        'logistic': make_pipeline(StandardScaler(), LogisticRegression(max_iter=1500, random_state=SEED)),
        'random_forest': RandomForestClassifier(n_estimators=100, min_samples_leaf=8, n_jobs=1, random_state=SEED),
        'gradient_boosting': GradientBoostingClassifier(n_estimators=80, max_depth=2, random_state=SEED),
        'xgboost': XGBClassifier(n_estimators=80, max_depth=2, learning_rate=.06, n_jobs=1, random_state=SEED),
    }
    models, comparison = {}, {}
    for name, estimator in estimators.items():
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=SEED)
        model = CalibratedClassifierCV(estimator, cv=cv, method='sigmoid', ensemble=True)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        p = model.predict_proba(X.iloc[test_idx])[:, 1]
        models[name] = model
        comparison[name] = metrics(y.iloc[test_idx].to_numpy(), p)
    # Predeclared default prevents optimizing on the final holdout.
    selected = 'logistic'
    model = models[selected]
    importance = permutation_importance(model, X.iloc[test_idx], y.iloc[test_idx], scoring='neg_brier_score',
                                        n_repeats=3, random_state=SEED)
    model_id = str(uuid.uuid4())
    artifact = {'models': models, 'selected': selected, 'dataset_id': dataset_id,
                'background': X.iloc[train_idx].sample(min(30, len(train_idx)), random_state=SEED),
                'test_idx': test_idx, 'train_idx': train_idx}
    artifact_path = RUNTIME / f'{model_id}.joblib'
    joblib.dump(artifact, artifact_path)
    if CLOUD_DEMO:
        from .cloud_storage import persist_artifact
        persist_artifact(artifact_path)
    pdp = partial_dependence(model, X.iloc[test_idx], features=['credit_utilization'], grid_resolution=12)
    return {'artifact_id': model_id, 'artifact_sha256': hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
            'dataset_id': dataset_id, 'selected': selected, 'models': comparison,
            'selection_rule': 'Predeclared logistic baseline; no holdout model selection',
            'split': {'train': len(train_idx), 'test': len(test_idx), 'seed': SEED, 'calibration_folds': 3},
            'permutation_importance': [{'feature': c, 'mean': float(v), 'std': float(s)} for c, v, s in zip(FEATURES, importance.importances_mean, importance.importances_std)],
            'partial_dependence': {'feature': 'credit_utilization', 'grid': pdp['grid_values'][0].tolist(), 'average': pdp['average'][0].tolist()},
            'limitations': ['Synthetic data is not evidence of real lending performance', 'Fold dispersion is not a calibrated individual confidence interval',
                             'Attributions describe predictions, not causal effects', 'Threshold 0.5 is illustrative, not a lending policy']}


def load_model(metadata):
    # Artifact paths are server-generated UUIDs; never deserialize client files.
    artifact_id = str(uuid.UUID(metadata['artifact_id']))
    path = RUNTIME / f'{artifact_id}.joblib'
    if CLOUD_DEMO:
        from .cloud_storage import fetch_artifact
        fetch_artifact(path)
    if not metadata.get('artifact_sha256'):
        raise ValueError('Legacy model artifact has no integrity record; retrain this dataset')
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['artifact_sha256']:
        raise ValueError('Model artifact integrity check failed')
    return joblib.load(path)


def predict(metadata, borrower: dict, explain: bool = True):
    frame = pd.DataFrame([borrower])
    validate(frame, training=False)
    x = engineer(frame)[FEATURES]
    artifact = load_model(metadata)
    model = artifact['models'][artifact['selected']]
    p = float(model.predict_proba(x)[0, 1])
    folds = [float(m.predict_proba(x)[0, 1]) for m in model.calibrated_classifiers_]
    out = {'probability': p, 'risk_category': 'high' if p >= .5 else 'moderate' if p >= .2 else 'low',
           'model_id': metadata['id'], 'financial_features': x.iloc[0].to_dict(),
           'uncertainty': {'fold_min': min(folds), 'fold_max': max(folds), 'label': 'Calibration-fold dispersion; not a confidence interval'},
           'human_review_required': True, 'claim_type': 'predictive_association'}
    if explain:
        import shap
        def function(values):
            return model.predict_proba(pd.DataFrame(values, columns=FEATURES))[:, 1]
        explainer = shap.Explainer(function, artifact['background'], algorithm='permutation', seed=SEED)
        explanation = explainer(x, max_evals=2 * len(FEATURES) * 5 + 1)
        out['explanation'] = {'method': 'Permutation SHAP on calibrated probability',
            'baseline': float(explanation.base_values[0]),
            'contributions': [{'feature': c, 'value': float(v)} for c, v in zip(FEATURES, explanation.values[0])],
            'additivity_residual': float(p - explanation.base_values[0] - explanation.values[0].sum()),
            'limitations': 'Marginal feature masking can generate dependent-feature combinations; not causal attribution'}
    return out
