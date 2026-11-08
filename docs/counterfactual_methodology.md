# Counterfactual methodology

```mermaid
flowchart LR
  Borrower --> Validate[Validate original inputs]
  Validate --> Changes[Allow only mutable financial changes]
  Changes --> Recalculate[Recalculate payment, DTI, PTI and loan-to-income]
  Recalculate --> Feasibility[Planning constraints and repayment cost]
  Feasibility --> Compare[Compare calibrated model probabilities]
  Compare --> Label[Predictive hypothetical, no causal claim]
```

Only income, loan amount, interest, term, existing obligations and utilization can be changed. Protected fields and immutable history are forbidden intervention targets. Derived ratios are recomputed, not independently edited. The engine screens total debt above 60% of monthly income, income increases above 20%, and terms above 120 months. These are transparent research planning bounds, not regulatory or lending standards. A passed screen does not show affordability or achievability.

Scenario outputs retain original/alternative conditions, probability differences, financial dependencies, total contractual repayment change, feasibility, limitations and fold dispersion. No individual causal effect is produced. A separate population counseling estimate is available in causal analysis; it is not added to an individual's modeled default probability. Structural individual counterfactual inference is not implemented.
