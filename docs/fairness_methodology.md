# Fairness methodology

The governed `audit_group` column is used only for held-out audit calculations and never as a predictor. Uploads require explicit audit authorization; category labels are recoded to avoid retaining identifying labels. Groups below 30 test records are suppressed. A missing denominator yields null, not zero. No individual sensitive information is displayed by the audit.

Selection rate is explicitly the fraction **not flagged high risk at p >= .5**; it is not an approval rate. Demographic parity difference is max-minus-min of this rate. Equal opportunity difference uses recall for default-positive outcomes. Equalized odds difference is the maximum TPR or FPR gap. Per-group recall, FPR, FNR, Brier, mean prediction, default prevalence and calibration-in-the-large gap are reported.

The benchmark may predict no positives at .5, making flag-rate disparities uninformative; calibration and ranking performance still need examination. The audit does not prove absence of discrimination, legal compliance, fairness of mitigation or absence of proxy effects. Missingness, historical labels, aggregation and small groups can mask disparities. Confidence intervals, intersectional analysis, proxy detection and recommendation-level auditing remain unimplemented. No single metric is a fairness certificate.
