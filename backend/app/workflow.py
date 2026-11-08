"""Executable LangGraph analytical agents, bounded reflection and persisted checkpoints."""
import time
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from . import causal, database as db, ml, risk
from .data import BASE, engineer, validate


class AnalysisState(TypedDict, total=False):
    dataset_id: str
    model_id: str
    borrower: dict
    assumptions_confirmed: bool
    fairness_governed: bool
    graph: dict
    run_id: str
    outputs: dict
    logs: list[dict]
    reflection_count: int


NAMES = ['data', 'supervisor', 'prediction', 'financial', 'causal_graph', 'explainability', 'fairness',
         'causal_inference', 'counterfactual', 'mitigation', 'evidence', 'reflection', 'aggregation', 'explanation', 'reporting']


def run_analysis(state: AnalysisState, df, model):
    def action(name, s):
        o = s['outputs']
        borrower = s['borrower']
        if name == 'data':
            return validate(df)
        if name == 'supervisor':
            return {'plan': NAMES[2:], 'causal_route': 'estimate' if s['assumptions_confirmed'] else 'withhold', 'max_reflection_cycles': 3}
        if name == 'prediction':
            return ml.predict(model, borrower, explain=False)
        if name == 'financial':
            f = engineer(__import__('pandas').DataFrame([borrower])).iloc[0]
            return {'indicators': {k: float(f[k]) for k in ['monthly_payment', 'debt_to_income', 'payment_to_income', 'loan_to_income']},
                    'stress_flags': ['Debt ratio exceeds illustrative 40% screen'] if f.debt_to_income > .4 else []}
        if name == 'causal_graph':
            g = s.get('graph') or causal.default_graph()
            return {**g, 'validation': causal.validate_graph(g)}
        if name == 'explainability':
            return ml.predict(model, borrower, explain=True)['explanation']
        if name == 'fairness':
            return risk.fairness(df, model, governed=s['fairness_governed']) if s['fairness_governed'] else {'status': 'withheld', 'reason': 'Governed audit use not acknowledged'}
        if name == 'causal_inference':
            if not s['assumptions_confirmed']:
                return {'status': 'withheld', 'reason': 'Identification assumptions not acknowledged'}
            return causal.estimate(df, graph=o['causal_graph'], assumptions_confirmed=True,
                                   synthetic_data=db.get(s['dataset_id'])['provenance'].get('synthetic', False))
        if name == 'counterfactual':
            return risk.scenario(model, borrower, {'existing_monthly_debt': borrower['existing_monthly_debt']*.8})
        if name == 'mitigation':
            c = o.get('causal_inference', {})
            return risk.mitigate(model, borrower, c if 'estimates' in c else None)
        if name == 'evidence':
            explanation = o.get('explainability', {})
            return {'model_dataset_match': model['dataset_id'] == s['dataset_id'],
                'shap_additivity_verified': abs(explanation.get('additivity_residual', 1)) < 1e-6,
                'failed_agents': [k for k, v in o.items() if v.get('status') == 'error'],
                'missing_evidence': ['Real-world intervention validation', 'External validation', 'Governed human sign-off'],
                'causal_claim_scope': o.get('causal_inference', {}).get('claim_type', 'withheld')}
        if name == 'reflection':
            warnings = ['Predictive attributions do not establish causation', 'Scenario risk changes are not intervention effects']
            c = o.get('causal_inference', {})
            if c.get('diagnostics', {}).get('balance_pass') is False:
                warnings.append('Post-weighting imbalance remains; causal interpretation requires revision')
            if o['evidence']['failed_agents']:
                warnings.append('Report incomplete: one or more analytical agents failed')
            return {'cycle': s.get('reflection_count', 0)+1, 'critiques': warnings,
                    'actionable_reanalysis': False, 'human_review_required': True,
                    'reason': 'Remaining limitations require external evidence or human review, not repeated identical computations'}
        if name == 'aggregation':
            return {'default_probability': o.get('prediction', {}).get('probability'),
                'financial': o.get('financial'), 'fairness_status': o.get('fairness', {}).get('status'),
                'causal_evidence': o.get('causal_inference', {}).get('claim_type', 'withheld'),
                'data_quality': o.get('data'), 'universal_score': None, 'human_review_required': True}
        if name == 'explanation':
            p = o.get('prediction', {}).get('probability')
            return {'text': f'Estimated default probability: {p:.1%}. ' if p is not None else 'Prediction unavailable. ',
                    'predictive_evidence': o.get('explainability'), 'causal_evidence': o.get('causal_inference'),
                    'limitations': o['reflection']['critiques'], 'human_review_status': 'pending'}
        if name == 'reporting':
            return {'title': 'Causality-aware loan risk analysis', 'analysis_id': s['run_id'],
                'summary': o['aggregation'], 'explanation': o['explanation'], 'human_review_status': 'pending',
                'completion': 'partial' if o['evidence']['failed_agents'] else 'completed'}
        raise ValueError('Unknown agent')

    def node(name):
        def execute(s):
            start = time.perf_counter()
            try:
                value = action(name, s)
                status = 'completed'
            except Exception as exc:
                value = {'status': 'error', 'error': str(exc), 'human_review_required': True}
                status = 'error'
            elapsed = time.perf_counter()-start
            saved = db.save('agent_output', {'agent': name, 'status': status, 'duration_seconds': elapsed,
                'output': value, 'input_references': {'dataset_id': s['dataset_id'], 'model_id': s['model_id']}}, s['run_id'])
            update = {'outputs': {**s['outputs'], name: value},
                'logs': s['logs']+[{'agent': name, 'status': status, 'duration_seconds': elapsed, 'evidence_id': saved['id']}]}
            if name == 'reflection':
                update['reflection_count'] = s.get('reflection_count', 0)+1
            return update
        return execute
    builder = StateGraph(AnalysisState)
    for name in NAMES:
        builder.add_node(name, node(name))
    builder.add_edge(START, NAMES[0])
    for first, second in zip(NAMES, NAMES[1:]):
        if first != 'reflection':
            builder.add_edge(first, second)
    def reflection_route(s):
        return 'evidence' if s['outputs']['reflection'].get('actionable_reanalysis') and s['reflection_count'] < 3 else 'aggregation'
    builder.add_conditional_edges('reflection', reflection_route)
    builder.add_edge(NAMES[-1], END)
    graph = builder.compile(checkpointer=InMemorySaver())
    return graph.invoke({**state, 'outputs': {}, 'logs': [], 'reflection_count': 0},
                         config={'configurable': {'thread_id': state['run_id']}, 'recursion_limit': 40})
