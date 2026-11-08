# Mitigation methodology

```mermaid
flowchart TD
  Profile --> Candidates[Voluntary debt management, term review, verified income support]
  Candidates --> Simulate[Evaluate predictive scenarios]
  Simulate --> Screen[Screen financial constraints]
  Screen --> Rank[Risk, affordability and lifetime cost ranking]
  Rank --> Sensitivity[Compare alternative risk weights]
  Sensitivity --> Review[Present evidence and adverse consequences for human review]
  Causal[Population counseling estimate] --> Separate[Separate evidence panel, no individual extrapolation]
  Separate --> Review
```

The rank is `0.5 * predicted_probability_reduction + 0.3 * PTI_improvement - 0.2 * positive_repayment_cost_change/annual_income`, with feasible options first. Weight sensitivity compares risk weights .25/.5/.75 while retaining the cost penalty. Units and weights are transparent design choices, not an empirically optimized welfare objective. Ranking is not execution or proof of benefit.

Term extension includes lifetime interest cost. Debt reduction requires resources and may incur fees; income support requires actual eligibility. None is assumed achievable. Population counseling evidence, when available with matching dataset lineage, remains a separate ATE with diagnostics and claim scope. It is not evidence for the three different modeled interventions. No default denial or pricing increase recommendation is generated. Real intervention data and operational review are necessary before policies can be evaluated causally.
