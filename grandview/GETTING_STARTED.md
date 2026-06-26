# Getting Started — Grandview CPA Automation

A step-by-step guide for staff to set up and run the system. No deep Python
knowledge required — follow the commands as written.

> ⚠️ **Before you start, read the two rules that never bend:**
> 1. **No tax number is trusted until a CPA verifies it.** Rates live in
>    `config/tax_rates_2025.yaml` and ship marked `verified: false`. The engines
>    refuse to run on unverified rates. This is intentional.
> 2. **Never put real client data in the repository.** `clients/` and
>    `workpapers/` are git-ignored. Keep SINs, financials, and PII out of git.

---

## 1. One-time setup

You need **Python 3.11 or newer**. Check:

```bash
python --version
```

Then install the dependencies (from the `grandview/` folder):

```bash
cd grandview
python -m pip install -r requirements.txt
```

## 2. Confirm everything works

```bash
python -m pytest tests/
```

You should see something like `37 passed`. If so, the system is healthy.

Now look at the three live demos — they use **fake** numbers and print a sample
workpaper, so they're safe to run anytime:

```bash
python system/scripts/gst_calculator.py --demo
python system/scripts/payroll_processor.py --demo
python system/scripts/bank_rec_engine.py --demo
```

---

## 3. Verify the rates (a CPA must do this once per year)

Open `config/tax_rates_2025.yaml`. For each section (GST/HST, payroll, personal,
corporate):

1. Look up the current figure on the linked CRA `source:` page.
2. Replace the placeholder value.
3. Set that section's `verified: true`.
4. Fill in `last_reviewed_by` and `last_reviewed_date` at the top.

Until a section says `verified: true`, any engine using it will stop with an
`UnverifiedRatesError` — that's the safety net working.

---

## 4. Run a real engagement (file-based)

This is the everyday workflow using CSV exports.

**a) Put the client's transactions in place.** Copy the template and fill it in:

```bash
mkdir -p clients/ACME
cp templates/sample_transactions.csv clients/ACME/2025-Q1.csv
# edit clients/ACME/2025-Q1.csv with the real data
```

Required columns: `date, description, amount`. Optional: `account, tax_code`
(`standard` / `zero` / `exempt` / `out`). (This file is git-ignored.)

**b) Generate a workpaper.** For example, a GST return — a short script:

```python
# run from grandview/ :  python -
import sys; sys.path.insert(0, "system/scripts")
from common import FileDataSource
import gst_calculator

txns = FileDataSource().transactions("ACME", "2025-Q1")
# The `kind` column (sale/purchase) drives the split:
sales = [t for t in txns if t.raw.get("kind") == "sale"]
purchases = [t for t in txns if t.raw.get("kind") == "purchase"]
result = gst_calculator.compute_gst(sales, purchases, "ON")   # needs verified rates
wp = gst_calculator.build_workpaper("ACME", "2025-Q1", result)
path = wp.save()                  # writes to workpapers/ (git-ignored)
print("Workpaper written:", path)
```

The draft workpaper lands in `workpapers/` for CPA review and sign-off.

---

## 5. Run from QuickBooks instead of CSVs

The engines can read QuickBooks data through a **normalized cache** that a sync
step fills. Because QuickBooks is reached through MCP tools (which only the
Claude agent / a server integration can call), the flow is:

1. **Sync** — ask the agent to pull the period's data from QuickBooks and write
   the cache, or run a server integration that does the same. It produces
   `clients/<client>/qbo_<period>.json`.
2. **Switch the source** — in `config/firm_config.yaml` set:
   ```yaml
   data_sources:
     active: "quickbooks"
   ```
3. **Run the engine** exactly as in step 4 — `get_data_source()` now returns the
   QuickBooks adapter and the rest is identical.

> The QuickBooks field mappings in `system/scripts/qbo_adapter.py` are marked
> `CONFIRM` until checked against a real response — do that once before relying
> on QBO-sourced numbers.

---

## 6. Optional: watch a folder for new uploads

`watch_client_portal` scans `clients/` for new files, classifies each, routes it
to the right workflow, and logs a notification for the CPA:

```bash
python system/skills/watch_client_portal.py --once     # single scan
python system/skills/watch_client_portal.py            # keep watching
```

Low-confidence or unknown documents are flagged `URGENT` for manual triage — it
never auto-files anything.

---

## 7. Where things live

| You want to… | Go to |
|--------------|-------|
| Update tax rates | `config/tax_rates_2025.yaml` |
| Change firm/output settings | `config/firm_config.yaml` |
| See how an engine works | `system/scripts/` |
| Use the LLM analysis prompts | `system/prompts/` (Cantonese) |
| Read reference notes | `knowledge_base/` |
| Find generated workpapers | `workpapers/` (git-ignored) |

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `UnverifiedRatesError` | The rates section isn't `verified: true` yet (step 3). |
| `ConfigError: PyYAML is required` | Run `pip install -r requirements.txt`. |
| `No transaction file found` | Check the path: `clients/<client>/<period>.csv`. |
| `No QBO cache found` | Run the sync step first (section 5). |
| `KeyError` on a province | Add and verify that province's rate in the config. |

When in doubt, re-run `python -m pytest tests/` — green means the code is fine
and the issue is data/config.
