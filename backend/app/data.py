"""Explicit synthetic benchmark, schema validation and origination-time financial features."""
import hashlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.special import expit

FEATURES = ['annual_income', 'loan_amount', 'interest_rate', 'term_months',
            'existing_monthly_debt', 'credit_utilization', 'credit_history_years',
            'employment_years', 'monthly_payment', 'debt_to_income', 'payment_to_income', 'loan_to_income']
BASE = FEATURES[:8]
CONFOUNDERS = ['annual_income', 'credit_utilization', 'employment_years']
PROTECTED = ['audit_group', 'age', 'sex', 'gender', 'race', 'ethnicity', 'religion', 'disability', 'marital_status']


def synthetic(n: int = 2000, seed: int = 42) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    income = np.clip(rng.lognormal(np.log(55000), .42, n), 15000, 200000)
    utilization = rng.uniform(.05, .95, n)
    employment = rng.uniform(0, 20, n)
    e = expit(-.2 + .8 * utilization - .000008 * income - .03 * employment)
    treatment = rng.binomial(1, e)
    p0 = expit(-1 + 2 * utilization - .000012 * income - .04 * employment)
    p1 = np.clip(p0 - .08, .001, .999)
    outcome = rng.binomial(1, np.where(treatment == 1, p1, p0))
    df = pd.DataFrame({'borrower_id': [f'SYN-{i:06}' for i in range(n)], 'annual_income': income,
        'loan_amount': rng.uniform(3000, 45000, n), 'interest_rate': rng.uniform(4, 25, n),
        'term_months': rng.choice([24, 36, 48, 60], n), 'existing_monthly_debt': rng.uniform(0, 1600, n),
        'credit_utilization': utilization, 'credit_history_years': rng.uniform(1, 25, n),
        'employment_years': employment, 'counseling': treatment, 'default': outcome,
        'audit_group': rng.choice(['A', 'B'], n)})
    return df, {'name': 'Synthetic counseling benchmark', 'source': 'Local structural data-generating process; not real borrowers',
                'license': 'Project-generated synthetic data', 'synthetic': True, 'seed': seed, 'dgp_version': 1,
                'target': 'Simulated default after counseling assignment',
                'known_ate': float(np.mean(p1 - p0)), 'known_att': float(np.mean((p1-p0)[treatment == 1])),
                'confounders': CONFOUNDERS, 'treatment': 'counseling',
                'assumptions': ['Consistency', 'No interference', 'All treatment/outcome common causes observed', 'Positivity'],
                'retrieved_at': datetime.now(timezone.utc).isoformat()}


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    r = x.interest_rate / 1200
    principal = x.loan_amount
    months = x.term_months
    x['monthly_payment'] = np.where(r == 0, principal / months,
        principal * r / (1 - (1 + r) ** -months).replace(0, np.nan))
    x['payment_to_income'] = x.monthly_payment / (x.annual_income / 12)
    x['debt_to_income'] = (x.existing_monthly_debt + x.monthly_payment) / (x.annual_income / 12)
    x['loan_to_income'] = x.loan_amount / x.annual_income
    return x


def validate(df: pd.DataFrame, training: bool = True) -> dict:
    required = BASE + (['default'] if training else [])
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f'Missing columns: {missing}')
    if len(df) == 0:
        raise ValueError('Dataset is empty')
    for col in required:
        if not pd.api.types.is_numeric_dtype(df[col]) or not np.isfinite(df[col].dropna()).all():
            raise ValueError(f'{col} must contain finite numeric values')
        if df[col].isna().any():
            raise ValueError(f'{col} has missing values; explicitly clean before ingestion')
    bounds = {'annual_income': (1, 1e8), 'loan_amount': (1, 1e8), 'interest_rate': (0, 100),
              'term_months': (1, 600), 'existing_monthly_debt': (0, 1e7), 'credit_utilization': (0, 1),
              'credit_history_years': (0, 100), 'employment_years': (0, 80)}
    for col, (low, high) in bounds.items():
        if not df[col].between(low, high).all():
            raise ValueError(f'{col} must be between {low} and {high}; rates are percent, utilization is a fraction')
    if not (df.term_months % 1 == 0).all():
        raise ValueError('term_months must be an integer number of months')
    if training and not set(df.default.unique()).issubset({0, 1}):
        raise ValueError('default must be binary 0/1')
    q = {'rows': len(df), 'columns': len(df.columns), 'missing': {c: int(v) for c, v in df.isna().sum().items()},
         'duplicate_rows': int(df.duplicated().sum()), 'warnings': [],
         'predictors': FEATURES, 'excluded_columns': sorted(set(df.columns) - set(BASE) - {'default'}),
         'outliers': {c: int(((df[c] < df[c].quantile(.25) - 1.5*(df[c].quantile(.75)-df[c].quantile(.25))) |
                              (df[c] > df[c].quantile(.75) + 1.5*(df[c].quantile(.75)-df[c].quantile(.25)))).sum()) for c in BASE}}
    if 'borrower_id' in df and df.borrower_id.duplicated().any():
        raise ValueError('Repeated borrower IDs require a longitudinal adapter; not supported in this milestone')
    if any(c in df for c in ['issue_date', 'timestamp', 'origination_date']):
        raise ValueError('Timestamped data requires chronological validation; temporal adapter is not yet implemented')
    if any(c in df for c in ['recoveries', 'total_pymnt', 'last_pymnt_amnt', 'loan_status']):
        q['warnings'].append('Post-outcome columns excluded by predictor allowlist')
    if 'borrower_id' not in df:
        q['warnings'].append('No borrower ID: repeated borrowers cannot be detected')
    q['warnings'].append('Origination timing and proxy discrimination require researcher review')
    return q


def fingerprint(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
