# Actual experiments

Reproduce with `python scripts/run_experiments.py`. Raw measured output, seeds, model metrics and causal replication-level errors are in `experiment_results.json`. These are project-generated simulations, not public lending data.

The predictive experiment uses 2,000 simulated rows, seed 42, 1,500 training / 500 held-out rows and three-fold calibration. The default classifier is predeclared logistic regression.

| Calibrated model | ROC AUC | PR AUC | Brier | Recall at .5 | F1 at .5 |
|---|---:|---:|---:|---:|---:|
| Logistic | .6209 | .3163 | .1725 | .000 | .000 |
| Random forest | .5920 | .3171 | .1733 | .000 | .000 |
| Gradient boosting | .5952 | .2918 | .1755 | .000 | .000 |
| XGBoost | .6031 | .2996 | .1737 | .000 | .000 |

The .5 threshold produces no positive predictions here. These values do not support a claim of useful default detection at that threshold. The generator has deliberately limited signal and a low event rate; discrimination and decision utility need a separate design.

Causal experiments use 3,000 rows per replication for seeds 0–9. The known ATE is approximately -.08, with slight clipping-induced heterogeneity. ATT truth is evaluated on treated records. Matching targets matched treated, so full-treated ATT error is only an approximate benchmark if caliper exclusions occur. PLR DML is compared to ATE here under the approximately constant effect; it is not generally an ATE estimator.

| Estimator | Bias | RMSE | Interval coverage over 10 seeds |
|---|---:|---:|---:|
| IPW ATE | .00180 | .01695 | 10/10 |
| Doubly robust ATE | .00173 | .01670 | 10/10 |
| Doubly robust ATT | .00245 | .01819 | 10/10 |
| Matching | .00010 | .02568 | Not estimated |
| PLR DML projection | .00199 | .01737 | 10/10 |

Ten replications are insufficient to characterize nominal 95% coverage reliably. No statistical superiority claim is made. Intervals, assumptions and balance diagnostics remain necessary for every analysis. Good recovery in this simple DGP does not demonstrate robustness to hidden confounding, poor overlap, misspecified outcomes, temporal shifts or real-world interventions.

Implemented: supervised baselines, executable explanations, synthetic estimator recovery, and an integrated deterministic causal-aware workflow. Not conducted: conventional vs noncausal-agent vs full-framework benefit comparison, component ablations, resource profiling, causal forests/CATE, external/temporal stability and real intervention effectiveness experiments. Future research should use repeated richer DGPs, negative controls, specification sweeps, formal sensitivity, externally licensed data and preregistered utility/fairness objectives.
