# Glyph research landing page

The public site is static HTML/CSS/JavaScript served by GitHub Pages. It does not
run Python, fetch private datasets, require an API key, or contain patient records.
The expected permanent address is https://robbieholland.github.io/Glyph-research/.

The landing page embeds `atlas-embed.html`; `atlas.html` is the standalone view, both, adapted from Glyph's standalone interactive
explorer. The upstream template and its MIT license are retained in `vendor/`.
The research adapter/theme live in `scripts/atlas-adapter.js` and
`scripts/atlas-theme.css`. The Glyph source repository is unchanged.

## Data and layout

- Fixed, verified seed-1283 paper layout: **342 concepts + 5 clinical anchors**,
  659 original display edges. No UMAP/force layout is fitted in the browser or
  during export. The original fractional coordinates and NetworkX node-size
  mapping are preserved.
- All **141 outcomes** are available individually and grouped by disease family.
  The current aggregate snapshot matches manuscript v34: 604,185 tested pairs,
  4,463 Discovery associations, and 397 high-risk concepts in the wider study.
  The atlas deliberately retains the older 342-concept node set.
- Curated `revised_interpretations.csv` descriptions override original AutoInterp
  text. Original AutoInterp accuracy is hidden for revised descriptions; those
  old report-based scores do not validate new wording.
- Displayed estimates are Discovery unadjusted per-standard-deviation odds ratios.
  Bonferroni correction uses **604,185 tests**, never just the visible node subset.
  Missing/failed estimates remain unavailable. The five clinical anchors have 705 separately computed estimates; their provenance is recorded in `assets/clinical-associations-provenance.json`.
- Patient-level activations, reports, identifiers, CTs, lab histories and model
  checkpoints are never exported. Only aggregate concept/association fields are
  whitelisted. No Mayo laboratory estimates are displayed.

Checksums, counts, interpretation overrides and methods are recorded in
`assets/atlas-provenance.json`. `assets/paper-layout.json` is the exact exported
geometry, and `assets/atlas-data.json` contains the aggregate atlas. The latter's
compact association-array columns are listed in its `association_columns` field.

## Refreshing the aggregate export

Requires pandas and access to the research aggregate files; this is a maintainer
step, not part of GitHub Pages deployment. From the repository root:

```bash
python scripts/build_landing.py \
  --coords /path/to/verified/coords_n=347_umap_all_with_clinical_vars_all.tsv \
  --graph /path/to/verified/graph_n=347_umap_all_with_clinical_vars.json \
  --links /path/to/current/links.pkl \
  --groups /path/to/outcome_disease_groups.csv \
  --interpretations /path/to/revised_interpretations.csv \
  --paper /path/to/manuscript-v34.pdf
```

The verified coordinate folder must also contain `coords_n=283_umap_all.tsv`,
which retains the paper's interpreted/undocumented node designation. The exporter
refuses a different node set, duplicate concept/outcome rows or mismatched v34
study totals. It uses `feature`, the complete canonical association key, rather
than the nullable AutoInterp-join metadata field `feature_id`.

The local manuscript PDF supplies a checksum only. It is **not copied or
published**. The Paper button stays marked forthcoming until a public preprint
URL is provided. Update the button, citation and sharing metadata when it is.

## Browser verification

```bash
pip install playwright
playwright install chromium
python tests/check_landing.py
```

The test starts a loopback-only static server and verifies desktop/mobile layouts,
all 347 nodes/141 outcome controls, color toggles, searchable individual outcome
selection, revised I109 text, all-outcome wheel, CSV export, deep links, pan/zoom
without coordinate drift, empty states and zero external runtime requests/errors.
Screenshots/results are saved in `test-artifacts/` and should not be published.

Local preview: `python -m http.server 8000 --directory docs`.
The interactive atlas also opens directly as a local HTML file.

## Publishing on GitHub Pages

GitHub Pages publishes **only `docs/`** directly from the `main` branch. In
repository Settings → Pages, choose **Deploy from a branch**, then **main** and
**/docs**. A push that updates the site triggers GitHub's built-in Pages build.
The `.nojekyll` marker keeps the site a direct static export. No custom workflow
or workflow-scoped token is required.

No authentication belongs in these files. Use an approved GitHub connection or
normal authenticated Git tooling; never copy tokens from another repository.
If the repo remains private, verify that the account supports Pages from private
repositories and that the deployed site is publicly accessible. Do not change
repository visibility as a side effect of publishing.

The landing page is the public-facing research atlas, not a claim that all of the
original research pipeline has already been released. The existing evidence
reviews are retained as earlier exploratory material and linked accordingly.


The interactive risk wheels follow `Analysis/run/subfigures/common.py` in the
research source: fixed disease-family order, 0.15-radian group gaps, spoke widths
at 80% of each outcome slot, square-root `max(OR, 1) - 1` radial mapping, and a
white center labelled with the concept ID. Pale spokes are nonsignificant.
This is a visual match to the paper wheels; the site still displays its exported
Discovery unadjusted estimates. Only higher-risk estimates (OR > 1) appear in spoke hover and
the association table; CSV exports retain all available estimates. Group positions include all 141 outcomes even when an
estimate is unavailable.


Neighborhood regions follow the main labels in manuscript v34 Figure 2: Liver,
Cancer, Musculoskeletal & orthopedic, Cardiovascular, Kidney, Inflammatory markers,
and Cholesterol. `scripts/build_regions.py` records the curated semantic anchor
IDs. Shapely fits a convex envelope with a rounded margin; SVG quadratic segments
soften the outline. These annotations describe approximate spatial neighborhoods,
not exclusive membership or inferred disease labels. They sit below edges and
nodes, with a separate pointer-transparent label layer, and can be toggled off.
`assets/concept-regions.json` records every anchor and polygon for review.
The maintainer export now also requires Shapely.


Two frozen paper timelines (HFpEF and sepsis) follow the atlas. Refresh with:

```bash
python scripts/build_timelines.py --source-root /path/to/experiments/current/timelines
```

The builder preserves the paper SVG points, intervals and annotation placement;
adds accessible marker/reference targets; and exports only aggregate estimate
and bibliographic fields from the frozen Plotly custom data. No Plotly runtime,
cohort inputs or external runtime requests are required. Reference URLs are
restricted to PubMed/DOI links. Source hashes are in `assets/timelines/provenance.json`.
These timelines use clinically adjusted estimates, while the concept atlas uses
its exported unadjusted estimates. Timeline literature points are estimates for
reconstructed markers in the study cohort, not the effect estimates reported by
the cited papers. Study and atlas methods now live in `about.html`.


Seven smaller interpretation-supported neighborhoods supplement the seven main
paper regions: post-surgical bowel changes; fluid collections/abscesses;
pancreatic/biliary changes; tubes/drains; fluid accumulation; cholestasis; and
venous thrombosis. These use a smaller rounded margin and lighter outlines.
Their semantic anchors and approximate status are recorded in the region export.
Patient age has a separate persistent annotation for the clinical anchor.
Timeline-to-graph jumps center and zoom to the selected concept and add a distinct
selection ring and concept ID. Reset view restores the initial map and hides it.


Clinical-variable association wheels are computed by
`scripts/compute_clinical_associations.py`, extracting the original pure
`fit_isolated_model` method via AST rather than importing the full fitting
pipeline (which would write original-repository caches). Canonical study
membership and outcome-specific population counts are checked before fitting.
All 705 clinical/outcome combinations produced finite estimates. Internal
aggregate fit outputs and normalization/provenance are in
`analysis/clinical_variables/`; only aggregate CSVs and public provenance are
exported under `docs/assets/`. Clinical results use a 604,890-test correction;
frozen concept results remain unchanged. The `--clinical-associations` option
of the atlas exporter merges those results; keep `outcome_mapping.csv` and
`provenance.json` beside the supplied CSV.

For the live page, run `python scripts/build_progressive_atlas.py` after any
atlas export/clinical merge. It builds `atlas-embed.html`, a roughly 400 KB
graph-first shell, plus eight association chunks. The original `atlas.html`
remains the complete offline standalone. The graph paints first, supports
hover/search/zoom immediately, and hydrates association data afterward.
Disease controls enable when all association chunks are ready; clicking a
concept prioritizes its chunk. The sidebar stays open after the first selection.


The landing page now uses a sticky, scroll-guided sequence defined by `.story-step`
elements: sepsis overview, I76, and CKD stage III/L84. Associations hydrate before
the initial disease preset is applied. The guided bridge passes plain scrolling
over the graph to the page; explicit node/control interactions pause the guide.
“Explore freely” pauses it; “Resume scroll guide” reapplies the active scene.
Manual display controls live under a collapsed menu. The sidebar persists after
clearing a selection. Reload navigation clears transient concept/hash state and
returns to the page top. Prefer reduced motion when the browser requests it.


The hero provides Primary liver cancer and All outcomes shortcuts. Pending
shortcut actions wait for association hydration. Manual exploration has its own
sticky explanatory text so the guided sepsis narrative is hidden when another
outcome is selected. Guided camera movement eases over 700 ms, stops on manual
input, and honors reduced-motion preferences. A thin progress line follows page
scroll. Concept identifiers and interpretations share one sidebar heading, with
identifier/wheel-center colors following the original modality palette.


Guided transitions now use a visible zoom journey: focused views pull back to
the full graph (650 ms), hold briefly (100 ms), then zoom into the next concept
(950 ms). Scale interpolates logarithmically with cubic easing. Opening the
sidebar animates matching grid tracks so the stage does not jump in width.
Reduced-motion preferences bypass these transitions; manual input cancels them.


The guided camera now follows scroll position continuously rather than jumping
between timed scene triggers: full graph -> I76 close-up -> pan to L84 at the
same zoom -> full graph. A 110 ms follower smooths large scroll jumps. Scene
content changes independently of camera position. Manual exploration cancels
the follower. Hero shortcuts include liver cancer, HFpEF, CKD stage III and the
full outcome picker, directly below the resource buttons.


The final overview keyframe occurs before the sticky graph's release edge.
Guided scrolling holds at that edge while the camera follower completes its
final pullback, then resumes the queued scroll. Mouse wheel, iframe-forwarded
wheel input, keyboard/touch/scrollbar overshoots are covered. Upward scrolling
and manual exploration cancel the held scroll; data loading does not gate the
page. The iframe reports actual camera completion rather than using a timeout.


The current scientific story is built by `python scripts/build_story.py` from
the frozen atlas: primary liver cancer -> L108/cholestasis with R85 and I87
context -> CKD stage III/L84 -> HFpEF/I26 -> full graph. Effect-size readouts
are read directly from aggregate associations and require significant source
estimates. The L108 scene highlights neighboring report/imaging concepts as
well as the selected lab concept, without changing coordinates or statistics.
Rebuild the progressive atlas after updating the renderer adapter.


Walkthrough copy is limited to a heading and one short finding, plus the saved
effect readout where useful. Repeated scroll/color explanations were removed.
The sidebar's initial opening now follows the first camera leg's scroll progress
and the same follower, instead of beginning a separate timed resize when the
next scene becomes active. This removes the mid-zoom viewport change.


The scroll story opens with heart-failure and sepsis overlays at the full-map
view, narrows to primary liver cancer, then continues through the existing liver
and heart-failure concept sequence. `data-outcomes` carries the opening pair;
subsequent `data-outcome` values retain the single-disease behavior. Literature
Read paper buttons use a small inline outline SVG; their destinations are unchanged.


The opening now uses three distinct full-map scenes: sepsis, HFpEF, then primary
liver cancer, before the original liver-concept zoom. Preview assets use a
version query and the local port-8765 server disables caching during review.

Literature marker dialogs display the verified rule used in this cohort, source
adaptations, and an expandable exact encoding before training-SD normalization.
`assets/timelines/marker-rules.json` contains the 34 displayed rules, validated
against the frozen Plotly source notes and rule-code checksums. The timeline
builder refuses missing or mismatched definitions instead of inventing a rule.
Only formulas and aggregate metadata are included; estimates and original SVG
geometry are unchanged. No patient-level inputs are read during these updates.


Zoom scenes now include short user-style questions, with verified marker readouts.
The renal segment retains its HFpEF endpoint and highlights L84, L62 and L87;
all three have significant higher-odds HFpEF associations in the exported data.
Overview copy states the 1–4-year post-CT window. Outcome tables initially show
three rows with Bonferroni p-values; Show more reveals the unchanged full table,
and exports still retain every association.


I87 now uses the author's revised description: "Hepatobiliary pattern correlated
with a surgically absent gallbladder." The source revision CSV and HF model/data
annotations are synchronized. Original AutoInterp scores are not displayed as
validation of this new wording. Association estimates and geometry are unchanged.

Disease shortcut buttons no longer scroll the document to the graph's start.
Scrolling the details panel switches to manual exploration while keeping the
page position fixed. The HFpEF zoom highlights I26, I109, R21 and R204, each with
an existing significant higher-odds association. The top cue says Scroll to explore.


Search, reset and help live beside the disease shortcuts above the embedded
network. Clinical variables are searchable by name and aliases, with exact
names ranked ahead of incidental description matches. Scrolling headings and
prompt disease names use the same outcome hues as the network. Region labels
are positioned against the nearest curved boundary at display time.
