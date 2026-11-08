import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from . import ml
from .data import BASE, engineer, validate

MUTABLE = {'annual_income', 'loan_amount', 'interest_rate', 'term_months', 'existing_monthly_debt', 'credit_utilization'}


def scenario(model, borrower, changes):
    if not changes or not set(changes) <= MUTABLE:
        raise ValueError(f'Only actionable scenario features are allowed: {sorted(MUTABLE)}')
    original = ml.predict(model, borrower, explain=False)
    changed = {**borrower, **changes}
    validate(pd.DataFrame([changed]), training=False)
    financial = engineer(pd.DataFrame([changed])).iloc[0]
    constraints = []
    if financial.debt_to_income > .6:
        constraints.append('Total monthly debt exceeds 60% of monthly income')
    if changed['annual_income'] > borrower['annual_income']*1.2:
        constraints.append('Income increase exceeds scenario planning bound of 20%')
    if changed['term_months'] > 120:
        constraints.append('Term exceeds planning bound of 120 months')
    alternative = ml.predict(model, changed, explain=False)
    def total_paid(b):
        return float(engineer(pd.DataFrame([b])).monthly_payment.iloc[0]*b['term_months'])
    return {'claim_type': 'predictive_counterfactual', 'original_probability': original['probability'],
        'alternative_probability': alternative['probability'], 'difference': alternative['probability']-original['probability'],
        'original': {k: borrower[k] for k in BASE}, 'alternative': {k: changed[k] for k in BASE}, 'changes': changes,
        'financial_features': alternative['financial_features'], 'model_id': model['id'],
        'total_repayment_change': total_paid(changed)-total_paid(borrower),
        'feasible': not constraints, 'constraint_violations': constraints,
        'uncertainty': alternative['uncertainty'], 'causal_effect': None,
        'limitations': ['Feasibility is a planning screen, not proof of achievability',
                       'Correlated dependent ratios are recalculated', 'No causal effect is implied',
                       'Changes require consent, operational assessment and human review']}


def mitigate(model, borrower, causal_result=None):
    candidates = [
        ('Voluntary debt management', {'existing_monthly_debt': borrower['existing_monthly_debt']*.8}, 'Requires affordable debt repayment resources; may incur fees'),
        ('Repayment term review', {'term_months': min(borrower['term_months']+12, 120)}, 'Longer terms can increase lifetime interest'),
        ('Verified income support', {'annual_income': borrower['annual_income']*1.1}, 'Availability and eligibility must be verified'),
    ]
    results = []
    old_payment = engineer(pd.DataFrame([borrower])).payment_to_income.iloc[0]
    for name, change, burden in candidates:
        item = scenario(model, borrower, change)
        affordability_gain = float(old_payment-item['financial_features']['payment_to_income'])
        reduction = item['original_probability']-item['alternative_probability']
        cost_penalty = max(item['total_repayment_change'], 0)/max(borrower['annual_income'], 1)
        item.update(name=name, adverse_consequences=burden, evidence_strength='Predictive scenario only; no matched causal intervention evidence',
                    affordability_gain=affordability_gain, cost_penalty=cost_penalty,
                    rank_score=.5*reduction+.3*affordability_gain-.2*cost_penalty,
                    human_review_required=True, fairness='Requires population audit; individual simulation cannot establish fairness')
        results.append(item)
    results.sort(key=lambda x: (x['feasible'], x['rank_score']), reverse=True)
    causal_evidence = None
    if causal_result:
        causal_evidence = {'intervention': causal_result['treatment'], 'estimand': 'Population ATE; not individual probability change',
            'estimate': causal_result['estimates']['doubly_robust'], 'claim_type': causal_result['claim_type'],
            'diagnostics': causal_result['diagnostics'], 'human_review_required': True}
    return {'recommendations': results, 'causal_evidence_separate': causal_evidence,
        'ranking': {'risk_reduction': .5, 'affordability_gain': .3, 'repayment_cost_penalty': -.2},
        'ranking_sensitivity': {str(w): [r['name'] for r in sorted(results, key=lambda r: (r['feasible'], w*(r['original_probability']-r['alternative_probability'])+(1-w)*r['affordability_gain']-.2*r['cost_penalty']), reverse=True)] for w in [.25, .5, .75]},
        'execution': 'Decision support only; no financial action is executed'}


def fairness(df, model, governed=False):
    if not governed:
        raise ValueError('Governed fairness-audit attribute use must be explicitly acknowledged')
    if 'audit_group' not in df:
        return {'status': 'unavailable', 'reason': 'No governed audit_group column', 'groups': []}
    artifact = ml.load_model(model)
    idx = artifact['test_idx']
    frame = engineer(df).iloc[idx]
    p = artifact['models'][artifact['selected']].predict_proba(frame[ml.FEATURES])[:, 1]
    y = frame.default.to_numpy()
    groups = frame.audit_group.fillna('unknown').astype(str).to_numpy()
    output = []
    def ratio(a, b):
        return float(a/b) if b else None
    for g in sorted(set(groups)):
        mask = groups == g
        if int(mask.sum()) < 30:
            output.append({'group': g, 'n': int(mask.sum()), 'suppressed': True, 'reason': 'Fewer than 30 holdout records'})
            continue
        actual, pred = y[mask], p[mask] >= .5
        tp = int(((actual == 1) & pred).sum())
        fp = int(((actual == 0) & pred).sum())
        fn = int(((actual == 1) & ~pred).sum())
        tn = int(((actual == 0) & ~pred).sum())
        output.append({'group': g, 'n': int(mask.sum()), 'suppressed': False,
            'high_risk_flag_rate': float(pred.mean()), 'selection_rate': float((~pred).mean()),
            'recall': ratio(tp, tp+fn), 'false_positive_rate': ratio(fp, fp+tn), 'false_negative_rate': ratio(fn, fn+tp),
            'brier': float(brier_score_loss(actual, p[mask])), 'calibration_gap': float(p[mask].mean()-actual.mean()),
            'actual_default_rate': float(actual.mean()), 'mean_predicted_probability': float(p[mask].mean())})
    available = [g for g in output if not g['suppressed']]
    def gap(key):
        values = [g[key] for g in available if g[key] is not None]
        return float(max(values)-min(values)) if len(values) >= 2 else None
    eo = [gap('recall'), gap('false_positive_rate')]
    return {'status': 'audited' if len(available) >= 2 else 'insufficient_groups', 'groups': output,
        'demographic_parity_difference': gap('selection_rate'), 'equal_opportunity_difference': gap('recall'),
        'equalized_odds_difference': max(eo) if all(x is not None for x in eo) else None,
        'selection_definition': 'Illustrative non-high-risk flag (p < 0.5), never approval',
        'limitations': ['Descriptive holdout disparities, not legal compliance findings', 'No uncertainty intervals or intersectional audit in milestone 1',
                       'Small groups suppressed; missing outcome-class denominators return null', 'Predictor exclusion does not rule out proxies']}
