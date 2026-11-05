> Current study-level release excludes all Mayo studies. The reproduction readers
> pin the clean revision. Superseded study-level objects have been removed from
> HF storage; old commit metadata can remain visible. No Mayo refits are possible from the distributed
> study-level files.

# Paper-v34 association release

The public HF dataset is `RobbieHolland/Glyph-research`. The release
is `fmr_orthogonal_paper_v34_20261104`; the exact published commit is pinned in
`reproduce_tables.py`. Mayo study-level rows have been removed from every activation and label file.
The latest dataset contains 51,331 non-Mayo studies; aggregate Mayo results remain. The obsolete study-level objects are absent from the HF storage inventory and their old file downloads are blocked.

## Audit qualification

This release matches Figure 4 counts, but it is not a complete numerical match
to the paper text. The text also quotes recovered R85 estimates from the retry
variant. See [the audit](REPRODUCIBILITY_AUDIT.md). Matching counts alone did not
establish full paper reproduction. No further HF changes were made by the audit.

## Source selection

Manuscript v34 is the reference. Discovery, Internal Test and Tri-Valley use
the preserved `before_failed_fit_retries_20261027T002031Z` snapshot of the
`corr035_race` k10 orthogonal analysis. Mayo uses the separate, paper-matching
no-laboratory-target/no-laboratory-covariate analysis. No fitting is performed.
The paper PDF hash and source hashes are recorded in the HF association manifest.

An initial HF refresh incorrectly selected the later experimental retry variant
(Internal Test 504, Tri-Valley 652). The paper release supersedes that refresh
with the preserved v34 snapshot; no numerical estimates are edited to force
agreement. Original research files are unchanged.

The full grid has 604,185 tests and 4,463 Discovery associations. Adjusted counts
are **1,198 / 489 / 645 / 643** (Discovery / Internal Test / Tri-Valley / Mayo).
Every modality/cohort count in Figure 4 is checked during both export and
reproduction, in addition to the totals. Later retry fits are excluded from the
first three cohorts. Mayo's recorded rare-class/retry settings remain those of
its paper-specific no-lab analysis.

## Methods and exclusions

Six clinical domains, up to ten concept covariates, correlation exclusion at
|r| ≥ 0.35, seed 42, 100 trees, depth four, default 5×5 cross-fitting, and study
independence define the analysis. The promoted exploratory I26 hardware-exclusion
specification is retained. Per-hypothesis covariates and requested splits are
recorded; the estimator can reduce splits for rare-class support.

Adjusted BH families are 4,463 per site except Mayo's 3,109 imaging/report
targets. Failed fits remain missing and count as p=1 for BH. All Mayo laboratory
statistical fields are null. Original non-lab Mayo unadjusted screening flags
are preserved without consulting excluded laboratory results to reconstruct
q-values. Internal Test/Tri-Valley unadjusted flags retain the original strict
raw-p cutoff convention. Adjusted significance requires q < 0.05 and OR > 1.

## Reproduce

Run `./reproduce.sh` with dataset access. The reader pins the immutable HF
revision, checks association hashes, exact Discovery keys, activation checksums
and schemas, eligible families, recomputed adjusted q-values and pass flags.
It writes eight numeric CSV tables and audit JSON. The v34 comparison must have
zero differences; the script also verifies all Figure 4 modality counts.
`--data-dir DIR` enables offline use. `--skip-activation-check` explicitly skips
activation checks. This reproduces saved association estimates, not patient-level
model fitting or every other result in the manuscript.

## Maintain

Original caches and the manuscript are read-only inputs:

```bash
python scripts/prepare_hf_associations.py \
  --unadjusted-cache /path/to/full/corrected/source-cache.pkl \
  --corrected-results /path/to/preserved/paper-v34/matched_results.csv \
  --mayo-results /path/to/mayo_no_labs/matched_results.csv \
  --paper /path/to/manuscript-v34.pdf \
  --parent-revision CURRENT_HF_SHA \
  --output analysis/NEW_RELEASE
python reproduce_tables.py --data-dir analysis/NEW_RELEASE \
  --skip-activation-check --output-dir analysis/NEW_RELEASE_CHECKS
```

The exporter refuses sources that do not reproduce the v34 modality counts,
mismatched activation membership, or incomplete families. It exports whitelisted
aggregate fields only. After an authorized publication, pin the returned commit
and rerun the reader on that exact remote revision, including activation checks:

```bash
python scripts/publish_hf_associations.py --stage analysis/NEW_RELEASE \
  --parent-revision CURRENT_HF_SHA --record analysis/NEW_RELEASE_COMMIT.json
```

The publisher allows exactly six files, checks that the existing repository is
private and uses parent-commit validation to prevent concurrent overwrites.
Verify remote checksums and confirm activation/study-level blobs remain unchanged.
