"""Hypothesis DAG and cross-fitted treatment estimators with explicit identification gates."""
import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import CONFOUNDERS, PROTECTED


def default_graph():
    edges = [(c, v) for c in CONFOUNDERS for v in ['counseling', 'default']]
    edges += [('counseling', 'default'), ('loan_amount', 'monthly_payment'), ('interest_rate', 'monthly_payment'),
              ('term_months', 'monthly_payment'), ('annual_income', 'debt_to_income'),
              ('monthly_payment', 'debt_to_income')]
    return {'nodes': sorted({n for pair in edges for n in pair}), 'edges': [list(e) for e in edges],
            'assumptions': 'Hypothesis DAG for the synthetic benchmark only; not discovered or validated for real borrowers'}


def validate_graph(graph):
    nodes, edges = graph['nodes'], graph['edges']
    if len(set(nodes)) != len(nodes):
        raise ValueError('Duplicate nodes')
    if any(len(e) != 2 or e[0] not in nodes or e[1] not in nodes for e in edges):
        raise ValueError('Edges must connect declared nodes')
    dag = nx.DiGraph()
    dag.add_nodes_from(nodes)
    dag.add_edges_from(edges)
    if not nx.is_directed_acyclic_graph(dag):
        raise ValueError('Causal graph must be acyclic')
    return {'acyclic': True, 'topological_order': list(nx.topological_sort(dag)),
            'ancestors': {n: sorted(nx.ancestors(dag, n)) for n in nodes},
            'descendants': {n: sorted(nx.descendants(dag, n)) for n in nodes},
            'colliders': [{'node': n, 'parents': list(dag.predecessors(n))} for n in nodes if dag.in_degree(n) > 1],
            'warning': 'A valid DAG does not verify its causal assumptions'}


def adjustment_check(graph, treatment, outcome, confounders):
    validate_graph(graph)
    g = nx.DiGraph()
    g.add_nodes_from(graph['nodes'])
    g.add_edges_from(graph['edges'])
    if treatment not in g or outcome not in g or not set(confounders) <= set(g):
        raise ValueError('Treatment, outcome and adjustment variables must appear in DAG')
    if set(confounders) & (nx.descendants(g, treatment) | {treatment, outcome}):
        raise ValueError('Do not adjust for treatment, outcome or post-treatment descendants')
    backdoor = g.copy()
    backdoor.remove_edges_from(list(backdoor.out_edges(treatment)))
    if not nx.is_d_separator(backdoor, {treatment}, {outcome}, set(confounders)):
        raise ValueError('Adjustment set does not block backdoor paths in the supplied DAG')


def _classifier():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))


def estimate(df: pd.DataFrame, treatment='counseling', outcome='default', confounders=None,
             graph=None, assumptions_confirmed=False, synthetic_data=False):
    confounders = confounders or CONFOUNDERS
    if not assumptions_confirmed:
        raise ValueError('Explicit identification-assumption acknowledgement is required')
    if not confounders or len(set(confounders)) != len(confounders):
        raise ValueError('Provide a unique, justified pre-treatment adjustment set')
    if set(confounders) & set(PROTECTED):
        raise ValueError('Governed protected-attribute causal adjustment is not supported')
    adjustment_check(graph or default_graph(), treatment, outcome, confounders)
    cols = confounders + [treatment, outcome]
    if not set(cols) <= set(df) or df[cols].isna().any().any():
        raise ValueError('Treatment, outcome and confounders must be complete')
    if not all(pd.api.types.is_numeric_dtype(df[c]) for c in cols) or not np.isfinite(df[cols].to_numpy()).all():
        raise ValueError('Causal columns must be finite numeric values')
    t, y = df[treatment].to_numpy(dtype=float), df[outcome].to_numpy(dtype=float)
    if set(np.unique(t)) != {0, 1} or set(np.unique(y)) != {0, 1}:
        raise ValueError('Binary treatment and binary outcome with both classes are required')
    cells = pd.crosstab(t, y).reindex(index=[0, 1], columns=[0, 1], fill_value=0)
    if len(df) < 200 or cells.to_numpy().min() < 10:
        raise ValueError('At least 200 rows and 10 observations per treatment/outcome cell required')
    X = df[confounders].to_numpy(dtype=float)
    e, m0, m1 = np.zeros(len(t)), np.zeros(len(t)), np.zeros(len(t))
    strata = (2*t+y).astype(int)
    for tr, te in StratifiedKFold(3, shuffle=True, random_state=42).split(X, strata):
        ps = _classifier().fit(X[tr], t[tr])
        e[te] = ps.predict_proba(X[te])[:, 1]
        for arm, target in [(0, m0), (1, m1)]:
            arm_idx = tr[t[tr] == arm]
            target[te] = _classifier().fit(X[arm_idx], y[arm_idx]).predict_proba(X[te])[:, 1]
    overlap = float(np.mean((e > .05) & (e < .95)))
    if overlap < .9:
        raise ValueError('Insufficient overlap: fewer than 90% of propensities in (0.05, 0.95); effect withheld')
    raw_e = e.copy()
    e = np.clip(e, .025, .975)
    ipw = t*y/e - (1-t)*y/(1-e)
    dr = m1 - m0 + t*(y-m1)/e - (1-t)*(y-m0)/(1-e)
    pt = float(t.mean())
    att_score = (t*(y-m0) - (1-t)*e/(1-e)*(y-m0))/pt
    # PLR DML estimand: overlap-weighted constant-effect projection, not generally ATE.
    m = e*m1 + (1-e)*m0
    v = t-e
    theta = float(np.mean(v*(y-m))/np.mean(v*v))
    influence = v*((y-m)-theta*v)/np.mean(v*v)
    def result(scores, estimand):
        value = float(np.mean(scores))
        se = float(np.std(scores, ddof=1)/np.sqrt(len(scores)))
        return {'estimate': value, 'standard_error': se, 'ci95': [value-1.96*se, value+1.96*se], 'estimand': estimand}
    estimates = {'ipw': result(ipw, 'ATE'), 'doubly_robust': result(dr, 'ATE'),
                 'doubly_robust_att': result(att_score, 'ATT')}
    # ATT ratio-estimator influence accounts for estimated treatment prevalence.
    att_value = estimates['doubly_robust_att']['estimate']
    att_if = att_score - t/pt*att_value
    att_se = float(np.std(att_if, ddof=1)/np.sqrt(len(t)))
    estimates['doubly_robust_att'].update(standard_error=att_se, ci95=[att_value-1.96*att_se, att_value+1.96*att_se])
    se = float(np.std(influence, ddof=1)/np.sqrt(len(t)))
    estimates['dml_plr'] = {'estimate': theta, 'standard_error': se, 'ci95': [theta-1.96*se, theta+1.96*se],
                             'estimand': 'Overlap-weighted partially linear projection; ATE only under constant-effect assumptions'}
    # Matching with replacement, on propensity log-odds, and an explicit caliper.
    logits = np.log(e/(1-e))
    control_idx, treated_idx = np.where(t == 0)[0], np.where(t == 1)[0]
    nn = NearestNeighbors(n_neighbors=1).fit(logits[control_idx, None])
    distance, neighbor = nn.kneighbors(logits[treated_idx, None])
    matched = distance[:, 0] <= .2*np.std(logits)
    diff = y[treated_idx[matched]] - y[control_idx[neighbor[matched, 0]]]
    estimates['matching'] = {'estimate': float(np.mean(diff)) if len(diff) else None, 'estimand': 'ATT among caliper-matched treated',
                             'matched_treated': int(matched.sum()), 'ci95': None,
                             'limitation': 'No naive CI: reuse of controls induces dependence'}
    weights = t/e + (1-t)/(1-e)
    def smd(a, b, wa=None, wb=None):
        scale = np.sqrt((np.var(a, axis=0)+np.var(b, axis=0))/2)
        return ((np.average(a, axis=0, weights=wa)-np.average(b, axis=0, weights=wb))/np.maximum(scale, 1e-10)).tolist()
    before = smd(X[t == 1], X[t == 0])
    after = smd(X[t == 1], X[t == 0], weights[t == 1], weights[t == 0])
    balance_ok = max(abs(v) for v in after) < .1
    return {'treatment': treatment, 'outcome': outcome, 'confounders': confounders, 'n': len(df),
        'claim_type': 'synthetic_benchmark_effect' if synthetic_data else 'exploratory_observational_estimate',
        'identification': 'Conditional on supplied DAG and untestable exchangeability; acknowledgement is not proof',
        'estimates': estimates, 'diagnostics': {'overlap_fraction': overlap, 'propensity_range': [float(raw_e.min()), float(raw_e.max())],
            'clipped_fraction': float(np.mean(raw_e != e)), 'effective_sample_size': float(weights.sum()**2/(weights**2).sum()),
            'ess_by_arm': {str(a): float(weights[t == a].sum()**2/(weights[t == a]**2).sum()) for a in [0, 1]},
            'balance': [{'feature': c, 'smd_before': float(b), 'smd_after': float(a)} for c, b, a in zip(confounders, before, after)],
            'balance_pass': balance_ok},
        'sensitivity': [{'assumed_additive_bias': b, 'adjusted_ate': float(dr.mean()-b)} for b in [-.1, -.05, 0, .05, .1]],
        'assumptions': ['Consistency / well-defined treatment', 'No interference', 'Positivity', 'No unmeasured confounding',
                        'Confounders measured before treatment', 'No selection bias'],
        'limitations': ['Sensitivity is an illustrative additive-bias grid, not a formal robustness certificate',
            'Intervals are asymptotic cross-fit influence-function intervals', 'No individual causal effect is identified',
            'No real-world intervention effectiveness is established', 'Inspect balance and specification sensitivity before interpretation']}
