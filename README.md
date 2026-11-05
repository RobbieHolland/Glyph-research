# Glyph research

Project website and evidence review for **Glyph: An Interpretability Engine for AI-Driven Scientific Discovery in Clinical Data**.

## Explore

- [Interactive research website](https://robbieholland.github.io/Glyph-research/)
- [Evidence review](docs/evidence/)
- [Figures](docs/figures/)

## Related resources

- [Glyph software package](https://pypi.org/project/glyph-discovery/)
- [Pretrained SAE checkpoints and concept interpretations](https://huggingface.co/RobbieHolland/Glyph-research)

This repository does not contain patient-level data or model weights.

## Preview locally

```bash
python3 -m http.server 8000 --directory docs
```

Open <http://localhost:8000/>.

## Reproduce the association tables

The private [Glyph research dataset](https://huggingface.co/datasets/RobbieHolland/Glyph-research) contains the frozen concept activations and versioned aggregate association results. After obtaining dataset access, run:

```bash
./reproduce.sh
```

The reproduction script pins the **paper-v34 FMR orthogonal** release. It verifies input checksums, Discovery membership, activation schemas and full-family BH correction, then writes numeric association and adjusted tables, tested denominators, failed-fit counts, thresholds and a comparison with manuscript v34 to `outputs/`. `--data-dir DIR` uses already downloaded files; `--revision HASH` explicitly selects another compatible corrected release.

The release contains 604,185 tested pairs and 4,463 Discovery associations. Adjusted counts match manuscript v34: 1,198 Discovery, 489 Internal Test, 645 Tri-Valley and 643 Mayo. The script verifies every modality/cohort count in Figure 4 and fails on a mismatch. This uses the preserved paper snapshot, excluding the later experimental retry variant that gives 504 and 652.

Mayo evaluates only 3,109 imaging/report hypotheses with no laboratory covariates. All Mayo laboratory statistical fields are null. Original Mayo imaging/report unadjusted screening flags are retained; historical q-values are not reconstructed using excluded laboratory results. The distributed activation, outcome and survival-label files exclude all Mayo studies. Mayo results are aggregate-only; refitting defaults to Discovery, Internal Test and Tri-Valley.

These tables replay saved estimates; they do not refit patient-level models. **Audit limitation:** matching these totals does not reproduce every estimate quoted in v34: its text includes some retry-recovered estimates absent from this snapshot. See [the reproducibility audit](docs/REPRODUCIBILITY_AUDIT.md). [Release maintenance and provenance](docs/HF_ASSOCIATIONS.md) describes the settings, exploratory I26 specification and update procedure.

## Refit from activations

A small standalone port of the MHG association code is included; it does not
require the original repository. For a working HF-only unadjusted probe:

```bash
pip install -r requirements-refit.txt
python refit_associations.py unadjusted --features I26 L108 R85 \
  --outcomes cancer_liver_primary 428.4 --output outputs/unadjusted-probe
```

`./reproduce.sh --refit --clinical-data FILE.parquet` runs the full refitting
pipeline. **It currently requires supplemental clinical inputs missing from HF:**
smoking, alcohol, BMI and recorded race. It checks this before fitting, preserves
missingness, and never replaces missing covariates with zero.
[Commands, input schema, scientific settings and validation](docs/REFIT_ASSOCIATIONS.md).

## Study-level data scope

The cleaned HF files contain 51,331 non-Mayo studies. All 14,199 Mayo study rows have been removed from the three activation matrices, outcome labels and survival labels. Aggregate Mayo associations are retained; their underlying study-level data are not distributed. Earlier contaminated dataset history requires explicit permanent-history-removal approval.
