import numpy as np
import pandas as pd
import pytest

from backend.app.data import synthetic, validate, engineer, BASE
from backend.app.causal import default_graph, validate_graph, estimate, adjustment_check


def test_dgp_reproducibility_and_target():
    a, pa = synthetic(1000)
    b, pb = synthetic(1000)
    pd.testing.assert_frame_equal(a, b)
    assert -.081 < pa['known_ate'] < -.075
    assert set(a.default) == {0, 1}


def test_amortization_and_dependencies():
    df, _ = synthetic(200)
    df['interest_rate'] = 0.
    f = engineer(df)
    np.testing.assert_allclose(f.monthly_payment, df.loan_amount/df.term_months)
    np.testing.assert_allclose(f.debt_to_income, (f.monthly_payment+df.existing_monthly_debt)/(df.annual_income/12))


@pytest.mark.parametrize('column,value', [('annual_income', 0), ('credit_utilization', 75), ('default', 2), ('loan_amount', np.inf)])
def test_invalid_data(column, value):
    df, _ = synthetic(200)
    df[column] = value
    with pytest.raises(ValueError):
        validate(df)


def test_repeated_and_timestamped_borrowers_rejected():
    df, _ = synthetic(200)
    with pytest.raises(ValueError, match='Repeated'):
        validate(pd.concat([df, df]))
    df['issue_date'] = '2020-01-01'
    with pytest.raises(ValueError, match='chronological'):
        validate(df)


def test_dag_and_adjustment():
    g = default_graph()
    assert validate_graph(g)['acyclic']
    with pytest.raises(ValueError, match='backdoor'):
        adjustment_check(g, 'counseling', 'default', ['annual_income'])
    g['edges'].append(['default', 'annual_income'])
    with pytest.raises(ValueError, match='acyclic'):
        validate_graph(g)


def test_causal_recovery_and_identification_gate():
    df, meta = synthetic(10000, 7)
    with pytest.raises(ValueError, match='acknowledgement'):
        estimate(df)
    result = estimate(df, assumptions_confirmed=True, synthetic_data=True)
    assert result['diagnostics']['overlap_fraction'] > .95
    assert abs(result['estimates']['doubly_robust']['estimate']-meta['known_ate']) < .03
    assert result['estimates']['matching']['ci95'] is None
    assert 'projection' in result['estimates']['dml_plr']['estimand']


def test_no_post_treatment_adjustment():
    g = default_graph()
    g['nodes'].append('mediator')
    g['edges'] += [['counseling', 'mediator'], ['mediator', 'default']]
    with pytest.raises(ValueError, match='post-treatment'):
        adjustment_check(g, 'counseling', 'default', ['mediator'])
