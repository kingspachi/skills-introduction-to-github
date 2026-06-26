# Grandview Professional Corporation — CPA Automation System

A modular toolkit to help automate recurring Canadian accounting/tax workpaper
preparation: **T1, T2, T3, GST/HST, payroll, write-up, and CSRS 4200**
compilation engagements.

> **This is a working foundation, not a finished product.** It gives you a
> validated architecture plus one fully-implemented engine (GST/HST). The other
> engines are config-driven scaffolds ready to be completed module-by-module.

---

## ⚠️ Critical safety notes — read first

1. **No tax figure in this repo is authoritative.** Every rate, bracket, and
   threshold lives in [`config/tax_rates_2025.yaml`](config/tax_rates_2025.yaml)
   and is marked `VERIFY`. **A CPA must confirm each value against the current
   CRA / provincial source before any number is used on a real filing.** The
   engines do the arithmetic; *you* own the inputs and the professional judgment.
2. **This repository is public.** Never commit real client data. `clients/` and
   `workpapers/` are git-ignored (see [`.gitignore`](../.gitignore)). Keep PII,
   SINs, and financial records out of version control entirely.
3. **Outputs are draft workpapers for CPA review**, not signed deliverables.
   Nothing here replaces professional review, sign-off, or CRA filing software.

---

## Architecture

```
grandview/
├── config/                     # All rates & firm settings (the ONLY place numbers live)
│   ├── tax_rates_2025.yaml      # VERIFY-marked rates: brackets, GST/HST, CPP/EI
│   └── firm_config.yaml         # Firm details, output preferences
├── system/
│   ├── scripts/                # Python calculation engines
│   │   ├── common.py            # Shared utils: config, money math, workpaper writer, data adapter
│   │   ├── gst_calculator.py    # ✅ Fully implemented + tested
│   │   ├── payroll_processor.py # Config-driven CPP/EI/tax withholding
│   │   ├── tax_calculator.py    # T1/T2 bracket engine (config-driven)
│   │   ├── bank_rec_engine.py   # Bank reconciliation
│   │   ├── qbo_adapter.py       # QuickBooks data source (reads normalized cache)
│   │   ├── qbo_sync.py          # Bridge: writes the QBO cache from MCP responses
│   │   └── report_generator.py  # Markdown workpaper rendering
│   ├── skills/                 # Automation hooks (portal watch, classify, route, notify)
│   └── prompts/                # LLM prompt templates (Cantonese) for document analysis
├── knowledge_base/             # Reference notes & checklists (verify before relying on)
├── clients/                    # 🔒 git-ignored — client source documents
├── workpapers/                 # 🔒 git-ignored — generated draft workpapers
├── templates/                  # Reusable workpaper templates
└── tests/                      # Unit tests
```

### Design principles
- **Single source of truth for numbers.** Engines never hard-code a rate; they
  read `config/`. Year-end rate updates = edit one file.
- **Pluggable data sources.** `common.DataSource` is an adapter interface with
  two implementations: `FileDataSource` (CSV/Excel/PDF) and
  `QuickBooksDataSource` (reads a normalized cache synced from the QBO MCP).
  Switch via `data_sources.active` in `firm_config.yaml`; engines don't change.
- **Everything is reviewable.** Each engine emits a Markdown workpaper showing
  inputs, the computation, and a QC checklist — so a reviewer can trace it.

---

## Quick start

```bash
cd grandview
python -m pip install -r requirements.txt          # pyyaml, and optionally pandas/openpyxl
python -m pytest tests/                             # run the test suite
python system/scripts/gst_calculator.py --demo      # see a sample GST workpaper
python system/scripts/payroll_processor.py --demo   # see a sample payroll register
python system/scripts/bank_rec_engine.py --demo     # see a sample bank reconciliation
```

## Status

| Component | State |
|-----------|-------|
| Config + shared utilities | ✅ Implemented |
| GST/HST engine + tests | ✅ Implemented |
| Payroll processor (CPP/EI + remittance) | ✅ Implemented + tested |
| T1/T2 tax calculator | 🟡 Config-driven scaffold |
| Bank reconciliation (matching + balance proof) | ✅ Implemented + tested |
| Report generator | ✅ Implemented |
| QuickBooks data source + sync bridge | ✅ Implemented + tested |
| Intake skills (watch/classify/route/notify) | ✅ Implemented + tested |
| Prompt templates | ✅ Drafted (Cantonese) |
| Knowledge base | 🟡 Templates — verify all figures |

See each module's docstring for the next steps to complete it.
