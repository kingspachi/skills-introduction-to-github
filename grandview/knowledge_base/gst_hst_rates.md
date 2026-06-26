# GST/HST — Reference Notes

> ⚠️ Rates change. The authoritative, engine-used values live in
> `config/tax_rates_2025.yaml` and must be CPA-verified. Treat the table below
> as a *structure to confirm*, not a settled source.

## Place-of-supply principle
GST/HST is generally charged based on the **place of supply**, not where the
vendor is located. Confirm the place-of-supply rules for each supply type
(goods, services, intangibles, real property differ).

## Combined rate by province (CONFIRM against CRA each period)
| Province | Type | Notes (verify) |
|----------|------|----------------|
| AB, BC, MB, SK, NT, NU, YT | GST only | Provincial sales tax (PST/RST), where it applies, is filed separately and is **not** a CRA GST/HST filing. |
| ON, NB, NL, NS, PE | HST | Combined federal + provincial; rate varies by province. |
| QC | GST | QST is administered by Revenu Québec — **out of scope** for this engine. |

> Do not hard-code the percentages from memory — pull current values from the
> CRA "charge and collect" page and record them in config.
> https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses.html

## Taxable categories
- **Standard-rated**: full GST/HST applies.
- **Zero-rated** (0%): e.g. basic groceries, certain exports — ITCs still
  available. Excluded from the taxable base in our engine.
- **Exempt**: e.g. certain health, education, financial services — **no ITCs**.
- **Out-of-scope**: not a supply.

## Input Tax Credits (ITCs)
- Must be supported by valid documentation (invoice requirements scale with
  amount). Confirm eligibility and documentation before claiming.

## Quick Method
- Some small businesses can elect the Quick Method, which uses a remittance rate
  on tax-included sales instead of tracking every ITC. **Rate depends on business
  type and province — look it up; never guess.** Our engine's `quick_method`
  config is disabled until populated and verified.

## Filing
- Confirm filing frequency (annual/quarterly/monthly), due dates, and any
  instalment requirements per client.
