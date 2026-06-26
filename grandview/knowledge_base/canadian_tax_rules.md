# Canadian Tax Rules — Reference Notes

> ⚠️ **Verify everything here against the current CRA source before relying on
> it.** This file is a structured checklist of *topics and where to look*, not a
> source of authoritative numbers. Numeric rates live (verified) in
> `config/tax_rates_2025.yaml`, not here.

## How to use
For each topic: confirm the current-year rule on the linked CRA page, record the
confirmation date, and only then treat it as settled for an engagement.

---

## Personal (T1)
- Tax brackets & rates (federal + provincial) → config; verify on CRA.
- Basic personal amount (note: may be income-tested) → verify.
- Common slips to collect: T4, T4A, T5, T3, T5008, T2202, RRSP receipts.
- Common credits/deductions: RRSP, childcare, medical, donations, tuition,
  disability — each has eligibility limits; **confirm per client**.
- CRA: https://www.canada.ca/en/revenue-agency/services/tax/individuals.html

## Corporate (T2)
- Small business deduction (SBD), small-business limit, associated-corp sharing.
- Active business income vs aggregate investment income split.
- Schedule 1 adjustments (e.g. meals & entertainment 50%, CCA, reserves,
  non-deductible items).
- Refundable taxes / RDTOH and integration — out of scope for the simple engine;
  flag for manual schedules.
- CRA: https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/corporations.html

## Trusts (T3)
- Filing obligations and the expanded trust reporting rules — **verify current
  requirements** as these have changed in recent years.
- CRA: https://www.canada.ca/en/revenue-agency/services/tax/trust-administrators.html

## Foreign / treaty considerations
- Residency determination drives taxation — confirm factual vs deemed residency.
- Foreign income reporting (e.g. T1135 for specified foreign property over the
  threshold) — **verify threshold and form requirements**.
- Tax treaties: Canada has bilateral treaties that can change withholding rates,
  tie-breaker residency, and relief from double taxation. **Always read the
  specific treaty article for the country involved** before concluding; do not
  generalize. Foreign tax credits may apply.
- CRA treaties index: https://www.canada.ca/en/department-finance/programs/tax-policy/tax-treaties.html

## Change of use (real property)
- A change in use of property (e.g. principal residence → rental, or rental →
  personal) is generally a **deemed disposition at FMV**, which can trigger a
  capital gain.
- Elections may be available (e.g. subsection 45(2) / 45(3)) to defer recognition
  in certain cases, subject to conditions and time limits.
- Principal residence exemption interactions are involved — **confirm facts,
  FMV at change date, and whether an election applies; document the analysis**.
- This is a high-judgment area: flag for CPA review, do not auto-compute.
- CRA: https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/principal-residence-other-real-estate/changing-part-your-principal-residence-rental-business-property-vice-versa.html

## CSRS 4200 (Compilation engagements)
- Compilations now require a basis-of-accounting note and a compilation report
  under CSRS 4200 — confirm engagement acceptance, independence considerations,
  and the required report wording per current CPA Canada guidance.
