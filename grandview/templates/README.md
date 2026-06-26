# Templates

Reusable, non-confidential templates.

- `sample_transactions.csv` — the column format the file-based `DataSource`
  expects. Copy into `clients/<client>/<period>.csv` (git-ignored) and replace
  with real data. Required columns: `date, description, amount`. Optional:
  `account, tax_code` (`standard` / `zero` / `exempt` / `out`).
