# Prediction methodology

An allowlist admits eight baseline financial variables and four deterministic ratios/payments. Counseling is excluded from the predictive model: it is analyzed separately as an intervention exposure. Protected/audit attributes, borrower IDs, outcomes and arbitrary uploaded columns are not predictors. This means the prediction is a historical mixture across counseling assignments, not an untreated potential outcome.

The amortized payment uses monthly rate `annual_percent/1200` and handles zero-interest loans as principal divided by months. DTI is existing obligations plus loan payment, divided by monthly income; PTI uses loan payment alone; loan-to-income is principal divided by annual income. Rates and units are explicit. Default horizon is uploader-defined and recorded, not inferred.

A seeded 75/25 stratified split precedes fitting. Repeated predictor rows, repeated borrower IDs and timestamped datasets are rejected rather than silently permitting leakage. Each baseline is calibrated with sigmoid calibration across three shuffled stratified folds within training. Scaling for logistic regression is inside each pipeline/fold. RF, gradient boosting and XGBoost are calibrated comparators. Logistic regression is predeclared for inference; no holdout winner selection occurs. No tuning or resampling is claimed.

Metrics: accuracy, precision, recall, F1, ROC AUC, average precision/PR AUC, Brier, log loss, ten-bin expected calibration error, confusion matrix, calibration points, ROC/PR coordinates. At threshold .5 the synthetic benchmark produces zero recall; this is a real measured limitation, not omitted. No threshold is a loan decision rule.

Explanations use actual permutation SHAP over the calibrated probability, with 30 training background rows and reproducible permutations. Baseline plus contributions is checked against the prediction. Marginal masking can produce inconsistent dependent-feature combinations, so explanations are not structural causal attributions. Global three-repeat permutation importance uses holdout negative Brier scoring. Utilization partial dependence is computed. Fold dispersion measures calibration ensemble variation, not calibrated individual uncertainty. ICE, stability/consistency metrics and external validation are pending.

Reference: [scikit-learn calibration](https://scikit-learn.org/stable/modules/calibration.html).
