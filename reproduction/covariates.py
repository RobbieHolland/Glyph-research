"""Consistent clinical covariates for adjusted-association runs across sites."""
import pandas as pd


RACE_LEVELS = ('White', 'Asian', 'Black', 'Native American', 'Other',
               'Pacific Islander', 'Unknown', 'Missing')
# White is the reference; unknown and missing are explicitly represented.
RACE_CONFOUNDERS = tuple(f'race_{level}' for level in RACE_LEVELS[1:])
CLINICAL_CONFOUNDERS = ('patient_age', 'patient_sex', 'current_smoker',
                        'heavy_alcohol_use', 'recent_bmi') + RACE_CONFOUNDERS


def add_race_covariates(frame):
    """Return a copy with a fixed race encoding, including Mayo's label aliases.

    Preserve the recorded categories; do not infer race or merge Other with
    Unknown. Fail on unexpected labels rather than silently recoding them.
    """
    source = 'Race' if 'Race' in frame else 'race' if 'race' in frame else None
    if source is None:
        raise ValueError('Race adjustment requires a Race or race source column.')
    raw = frame[source].astype('string').str.strip()
    lookup = {level.casefold(): level for level in RACE_LEVELS}
    lookup.update({
        'black or african american': 'Black',
        'american indian or alaska native': 'Native American',
        'native hawaiian or other pacific islander': 'Pacific Islander',
    })
    missing = raw.isna() | raw.eq('').fillna(False)
    canonical = raw.str.casefold().map(lookup).mask(missing, 'Missing')
    if canonical.isna().any():
        unexpected = sorted(raw[canonical.isna()].unique().tolist())
        raise ValueError(f'Unrecognized race categories: {unexpected}')
    result = frame.copy()
    for level in RACE_LEVELS:
        result[f'race_{level}'] = canonical.eq(level).astype('int8')
    return result


def select_concept_confounders(links, target, outcome, cohort, metric,
                               correlation, feature_index, threshold=.35, n_select=10):
    """Production largest-OR selection, shared by isolated parallel reruns."""
    if not isinstance(n_select, int) or n_select < 0:
        raise ValueError('n_select must be a nonnegative integer.')
    if cohort == 'mayo' and target.startswith('labs_'):
        raise ValueError('Lab targets are not eligible at Mayo.')
    if n_select == 0:
        return []
    candidates = links.loc[
        links[f'{cohort}_promising_association'].fillna(False)
        & links['concept_id_string'].ne(target)
        & links['outcome'].eq(outcome)
    ]
    modality = target.split('_', 1)[0]
    if cohort == 'mayo':
        candidates = candidates.loc[~candidates['concept_id_string'].str.startswith('labs_')]
    if modality == 'image':
        candidates = candidates.loc[candidates['inputs'].ne('findings')]
    elif modality == 'findings':
        candidates = candidates.loc[candidates['inputs'].ne('image')]
    keep = candidates['concept_id_string'].map(
        lambda c: abs(correlation[feature_index[target], feature_index[c]]) < threshold
        if c in feature_index else True
    )
    return candidates.loc[keep.astype(bool)].nlargest(n_select, f'{cohort}_{metric}')['concept_id_string'].tolist()
