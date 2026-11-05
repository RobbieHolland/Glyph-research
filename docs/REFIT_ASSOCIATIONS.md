# Refit associations from activations

This repository includes only the MHG pieces needed for association testing:
unadjusted logistic fits, clinical encoding, concept-covariate selection,
orthogonal FMR, missing-data rules and multiple-testing correction. It has no
runtime dependency on MedicalHypothesisGeneration, Hydra, W&B, imaging loaders,
SAE training, AutoInterp or the original filesystem paths.

`reproduction/source_provenance.json` identifies the copied function bodies and
hashes. Numerical functions are copied verbatim. Both the paper-run FMR snapshot
and current MHG routine are explicit, because rare-class support and failed-fit
retries differ. The combined runner defaults to current MHG with failed-fit
retries; it never changes successful first-pass estimates during a retry.

## Distributed cohorts

The cleaned release contains only 51,331 non-Mayo studies. Commands default to
Discovery, Internal Test and Tri-Valley. Mayo study-level inputs are excluded;
its saved aggregate results remain available. Explicit Mayo refitting requests
fail clearly without reading unavailable study-level data.

## What works now

```bash
pip install -r requirements-refit.txt
python refit_associations.py unadjusted \
  --features I26 I76 I87 L84 L108 R85 \
  --outcomes cancer_liver_primary 428.4 \
  --output outputs/unadjusted-probe
```

This fits models from the pinned HF activations and outcome labels. Cached
estimates are only used afterward for comparison. Omit feature/outcome filters
for the full grid. Outputs are resumable, aggregate-only checkpoints; run metadata
records source hashes, package versions, seed, settings and input hashes.
A requested subset never receives a multiple-testing correction as though it
were the entire discovery study.

The unadjusted port uses MHG's actual cohort-specific SDs (ddof=0), calculated
before the outcome-validity filter, and its per-outcome Discovery activation
support gate of 25. Adjusted inputs instead use Discovery means and pandas SDs
(ddof=1)+1e-8. These are distinct conventions in MHG. The generic Glyph package's
train-SD default is not substituted for the MHG unadjusted procedure.

## Full pipeline and missing release inputs

```bash
./reproduce.sh --refit --clinical-data /path/to/clinical_covariates.parquet
```

This computes unadjusted estimates, a fresh Discovery screen, covariate selection,
and adjusted estimates. It checks required inputs before launching a long run.
The current HF release is missing smoking, heavy alcohol use, BMI and recorded
race inputs. Consequently the command currently stops with an explicit list of
missing columns. Seeds cannot reconstruct those variables. The code does not
invent values or silently omit covariates. No additional clinical data were
uploaded as part of this code port.

The supplemental Parquet must have unique public `study_id` keys matching HF.
Required clinical fields are `patient_age`, `patient_sex`, `current_smoker`,
`heavy_alcohol_use`, `recent_bmi`, and the fixed race indicators listed in
`reproduction/covariates.py`. Age/sex already exist in HF. A recorded `Race`/`race`
column can supply the original fixed encoding. Preserve original missing values.
`analysis_order`, unique within each cohort, can preserve original model row
order for exact cross-fitting partitions. A seed without the original row order
does not guarantee the original partitions.

Use `--normalization-file FILE.json` to supply the original aggregate
normalization parameters rather than recomputing them. Accepted format is
`{column: [mean, std]}` or `{column: {mean: ..., std: ...}}`, optionally under
`normalization`. This file contains aggregate statistics only.

For an adjusted-only probe with fixed MHG specifications:

```bash
python refit_associations.py adjusted \
  --clinical-data /path/to/clinical_covariates.parquet \
  --features I26 --outcomes 428.4 \
  --estimator current --retry-failed --selection recorded \
  --output outputs/adjusted-probe
```

`--selection recompute` executes the copied MHG selection code, including the
0.35 absolute-correlation exclusion, modality restrictions and explicit I26
exclusions. `--screen-results FILE` consumes the fresh full-grid screen produced
by the unadjusted runner. Without it, an adjusted-only run explicitly uses the
frozen HF discovery family. `--estimator paper-run` with no `--retry-failed`
retains the older strict cross-fitting policy. Mayo uses the rare-class-capable
no-laboratory analysis routine.

## Mayo and reference limitations

Mayo laboratory rows are not loaded for fitting; lab targets/covariates are
prohibited. Adjusted correction uses only the eligible imaging/report family.
Failed estimates remain NaN and count as p=1 in BH. The fresh unadjusted Mayo
screen uses only non-lab hypotheses. Its correction can differ from the historical
frozen Mayo screening flags, whose original full-family q-values cannot be
reconstructed from the released non-laboratory statistics alone.

The current HF association snapshot matches v34's Figure 4 counts, but v34's text
also quotes recovered estimates from the retry variant. See
[the audit](REPRODUCIBILITY_AUDIT.md). Count agreement alone is not certification
of every estimate or an end-to-end refit. The full clinical input release and
one consistent reference analysis must be resolved before making that claim.

## Validation

```bash
python -m unittest discover -s tests -p 'test_mhg_reproduction.py' -v
```

Nine standalone tests cover original-MHG numerical references, rare-class
policies, complete-case masks, constant covariates, race encoding, modality/Mayo
exclusions full-family correction and an offline adjusted-runner integration. Real-data validation refitted 44 eligible
HF unadjusted models (plus four explicit ineligible Mayo lab rows) and recovered
all odds ratios within 0.002% on the tested cases. Three adjusted probes, using
original prepared MHG inputs solely for local validation, matched the original
cached ORs, confidence intervals and p-values to numerical precision. Those
adjusted probes do not establish HF-only reproduction: HF lacks the clinical
inputs. The entire full-grid study has not been refitted by this validation.
