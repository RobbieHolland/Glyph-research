# Reproducibility audit, 4 November 2026

Saved-table reproduction works. Full adjusted refitting from HF alone does not
yet work. Matching summary counts was insufficient to certify all paper results.

| Finding | Evidence | Consequence |
| --- | --- | --- |
| Missing adjustment inputs | HF outcomes has age/sex but no smoking, alcohol, BMI or recorded-race fields required by the fitted specifications. | Exact adjusted refits need a supplemental release with original missingness and row order. |
| Two MHG numerical result sets appear in v34 | Figure 4 totals are 1,198 / 489 / 645 / 643. R85–primary liver cancer ORs 2.13 (Internal Test) and 1.79 (Tri-Valley) occur in the retry-completed results, while the count-matching snapshot has NaN for those estimates. Retry-completed totals are 1,198 / 504 / 652 / 643. | The paper's totals and quoted recovered estimates need a single regenerated reference. Current HF matches the totals, not all individual values. |
| Different unadjusted normalization | MHG normalizes within cohort; generic public Glyph 0.2.0 uses Discovery SDs. In a real HF probe, I26–HFpEF Internal Test OR was 2.38 with the MHG convention and 2.77 with package defaults. | A dedicated MHG refit runner is necessary; generic defaults do not reproduce reported per-SD ORs. |
| Different adjustment defaults | Public Glyph 0.2.0 defaults to depth 2; MHG uses depth 4 and hypothesis-specific concept covariates. | Naming the same FMR score and seed does not align the complete analysis. |
| Threshold-table mismatch | V34 Table 3 lists raw-p cutoffs 0.0224 / 0.0106 / 0.00950 / 0.0146. Recomputed cutoffs for its count-matching released results are 0.0134107 / 0.00628322 / 0.00748340 / 0.0125327. | The manuscript threshold table also needs checking against the chosen full analysis output. |
| Discovery label ambiguity | HF separates 15,331 Discovery and 5,060 Internal Validation studies; some figures label Discovery n=20,391. The fitted Discovery results use the 15,331-study analysis split. | Documentation must distinguish the combined institutional cohort from the fitted Discovery split. |
| Historical Mayo screen | Frozen non-lab screening flags are retained, while its original full-family q-values are unavailable after withholding lab statistics. | A fresh non-lab-only screen can differ; do not claim those historical flags were independently regenerated. |
| Access and publication | Dataset is private; the research repository URL returned HTTP 404 anonymously during the audit. Newly ported code is local until published. | Reader access and code publication must be addressed separately from local execution. |

## What was changed

Only the MHG numerical association components were ported to `reproduction/`,
plus refit runners, dependencies and tests. Source bodies are versioned and
hashed. No original MHG/Glyph code or data were modified. No HF data were changed
by this code port or audit. The current HF revision remains
`fce45fd778b29e50510151a1b692e65b02ee4f0d`.

## Verification artifacts

- `analysis/refit_audit_20261104/audit.json`: published-package/HF-only probes,
  schemas and missing covariates; no Mayo lab rows loaded.
- `analysis/refit_audit_20261104/unadjusted_refit_comparisons.csv`: aggregate
  numerical comparisons for 44 hypotheses under two normalization conventions.
- `analysis/mhg_refit_probe_20261104/comparison.csv`: 44 actual fits using the
  ported MHG unadjusted method, with four explicitly ineligible Mayo lab rows.
- `analysis/refit_audit_20261104/mhg_adjusted_parity.json`: three adjusted probes
  on original prepared MHG inputs, matching the original cached estimates.
- `tests/fixtures/mhg_fmr_reference.json`: synthetic outputs generated from the
  original MHG functions, used by standalone tests without private data.

Only representative models were refitted. No claim is made that the full grid
has been rerun or that every figure/statistic in the manuscript is reproducible.
