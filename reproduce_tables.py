"""Reproduce Glyph association tables from the versioned HF aggregate release.

This replays saved estimates, validates their correction families and checksums,
and checks activation schemas. It does not refit patient-level models.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DATASET='RobbieHolland/Glyph-research'
REVISION='fc3f8ad26f8928bede2c495ae68fa5bdf6f2d1a0'  # Clean non-Mayo HF release.
SITES=('train','test','tri_valley','mayo')
MODALITIES=('findings','image','labs')
KEY=['modality','feature','outcome']
ALPHA=.05


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def input_file(name,data_dir,revision=REVISION):
    if data_dir is not None:
        path=data_dir/name
        if not path.exists():raise FileNotFoundError(path)
        return path
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(repo_id=DATASET,filename=name,repo_type='dataset',revision=revision))


def bh_q(pvalues):
    # Keep every eligible hypothesis, including failed fits, in the family.
    p=pvalues.fillna(1).to_numpy(float)
    if not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid p-values')
    order=np.argsort(p);q=np.empty(len(p))
    q[order]=np.minimum(1,np.minimum.accumulate((p[order]*len(p)/np.arange(1,len(p)+1))[::-1])[::-1])
    return q


def bh_cutoff(pvalues,alpha=ALPHA):
    values=np.sort(pvalues.dropna().to_numpy(float))
    passing=values<=alpha*np.arange(1,len(values)+1)/len(pvalues)
    return float(values[passing].max()) if passing.any() else float('nan')


def summarize(data,manifest):
    discovery=(data.train_isolated_odds_ratio_p_value<ALPHA/len(data))&data.train_isolated_odds_ratio.gt(1)
    gates={'discovery':discovery};thresholds={'discovery_bonferroni':ALPHA/len(data)}
    available={};fit_rows=[]
    for site in SITES:
        if site!='train':
            original=data[f'{site}_reproducible_association'].fillna(False).astype(bool)
            if site!='mayo':
                p=data.loc[discovery,f'{site}_isolated_odds_ratio_p_value']
                cutoff=bh_cutoff(p)
                recomputed=discovery&data[f'{site}_isolated_odds_ratio_p_value'].lt(cutoff)&data[f'{site}_isolated_odds_ratio'].gt(1)
                np.testing.assert_array_equal(original,recomputed)
                np.testing.assert_allclose(data.loc[discovery,f'{site}_association_q_value'],bh_q(p))
                thresholds[f'{site}_association_bh_raw_p']=cutoff
            # Mayo: retain original non-lab screening flags. Its historical
            # full-family q-values cannot be reconstructed from excluded labs.
            gates[f'{site}_association']=discovery&original
        eligible=discovery&data[f'{site}_adjustment_eligible'].fillna(False).astype(bool)
        expected_eligible=discovery&(data.modality.ne('labs') if site=='mayo' else True)
        np.testing.assert_array_equal(eligible,expected_eligible)
        if int(eligible.sum())!=manifest['methods']['adjusted_families'][site]:raise ValueError('Wrong adjustment family')
        p=data.loc[eligible,f'{site}_dml_odds_ratio_p_value'];q=bh_q(p)
        np.testing.assert_allclose(q,data.loc[eligible,f'{site}_dml_q_value'],rtol=1e-10,atol=1e-12)
        passed=pd.Series(False,index=data.index)
        passed.loc[eligible]=(q<ALPHA)&data.loc[eligible,f'{site}_dml_odds_ratio'].gt(1).to_numpy()
        np.testing.assert_array_equal(passed,data[f'{site}_adjusted_significant'].fillna(False).to_numpy(bool))
        gates[f'{site}_adjusted']=passed;available[site]=eligible
        thresholds[f'{site}_adjusted_bh_raw_p']=bh_cutoff(p)
        for modality in MODALITIES:
            mask=eligible&data.modality.eq(modality)
            valid=mask&data[f'{site}_dml_odds_ratio_p_value'].notna()
            fit_rows.append(dict(cohort=site,modality=modality,tested=int(mask.sum()),valid=int(valid.sum()),failed=int((mask&~valid).sum()),significant=int((passed&mask).sum())))
    frame=data[['modality']].copy()
    for name,mask in gates.items():frame[name]=mask
    frame['tested']=1
    def totals(columns):
        table=frame.groupby('modality')[columns].sum().reindex(MODALITIES,fill_value=0)
        table.loc['Total']=table.sum();table.index.name='modality';return table
    association=totals(['tested','discovery',*[f'{s}_association' for s in SITES[1:]]])
    adjusted=totals(['discovery',*[f'{s}_adjusted' for s in SITES]])
    for site in SITES[1:]:frame[f'train_adjusted_then_{site}']=frame.train_adjusted&frame[f'{site}_adjusted']
    reproduction=totals(['train_adjusted',*[f'train_adjusted_then_{s}' for s in SITES[1:]]])
    def given_association(require_train=False):
        table=pd.DataFrame(index=MODALITIES);base=frame.train_adjusted if require_train else frame.discovery
        def group(mask):return mask.groupby(frame.modality).sum().reindex(MODALITIES,fill_value=0)
        table['train_adjusted']=group(base&frame.train_adjusted);table['train_discovery']=group(base)
        for site in SITES[1:]:
            denominator=base&frame[f'{site}_association']
            table[f'{site}_adjusted_given_association']=group(denominator&frame[f'{site}_adjusted'])
            table[f'{site}_association']=group(denominator)
        table.loc['Total']=table.sum();table.index.name='modality';return table
    denominators=pd.DataFrame({s:available[s].groupby(frame.modality).sum().reindex(MODALITIES,fill_value=0) for s in SITES})
    denominators.loc['Total']=denominators.sum();denominators.index.name='modality'
    tables={'association_summary':association,'adjusted_summary':adjusted,'adjusted_reproduction':reproduction,
        'adjusted_given_association':given_association(),'adjusted_given_association_and_train_adjusted':given_association(True),
        'adjusted_denominators':denominators,'adjusted_fit_availability':pd.DataFrame(fit_rows).set_index(['cohort','modality'])}
    counts={'tested':len(data),**{name:int(mask.sum()) for name,mask in gates.items()}}
    expected={'tested':manifest['unadjusted_associations']['rows'],'discovery':manifest['adjusted_associations']['rows']}
    for site in SITES:
        expected[f'{site}_adjusted']=manifest['adjusted_summary'][site]['significant']
        if site!='train':expected[f'{site}_association']=manifest['unadjusted_screening'][site]['significant']
    failures={key:(counts.get(key),value) for key,value in expected.items() if counts.get(key)!=value}
    if failures:raise ValueError(f'Counts differ from release manifest: {failures}')
    return tables,dict(counts=counts,thresholds=thresholds,notes=[
        'Adjusted BH includes failed fits as p=1 and retains the full eligible family.',
        'Mayo laboratory statistical fields are all null and excluded from adjusted families.',
        'Original non-lab Mayo unadjusted screening flags are replayed; historical q-values are not reconstructed using excluded lab results.',
        'Paper-v34 release excludes the later experimental failed-fit retry cache.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path);parser.add_argument('--output-dir',type=Path,default=Path('outputs'))
    parser.add_argument('--revision',default=REVISION);parser.add_argument('--skip-activation-check',action='store_true')
    args=parser.parse_args()
    path=lambda name:input_file(name,args.data_dir,args.revision)
    manifest_path=path('associations/manifest.json');manifest=json.loads(manifest_path.read_text())
    if manifest.get('schema_version')!=2 or manifest.get('estimator')!='fmr_orthogonal':raise ValueError('Expected corrected orthogonal release schema v2')
    loaded={}
    for name in ['associations/unadjusted.parquet','associations/adjusted.parquet']:
        file=path(name)
        if digest(file)!=manifest['files'][name]['sha256']:raise ValueError(f'Checksum mismatch: {name}')
        loaded[name]=pd.read_parquet(file)
    data=loaded['associations/unadjusted.parquet'];adjusted=loaded['associations/adjusted.parquet']
    if data.duplicated(KEY).any() or adjusted.duplicated(KEY).any():raise ValueError('Duplicate concept/outcome rows')
    discovery=(data.train_isolated_odds_ratio_p_value<ALPHA/len(data))&data.train_isolated_odds_ratio.gt(1)
    expected_keys=pd.MultiIndex.from_frame(data.loc[discovery,KEY]);actual_keys=pd.MultiIndex.from_frame(adjusted[KEY])
    if len(adjusted)!=int(discovery.sum()) or set(expected_keys)!=set(actual_keys):raise ValueError('Adjusted keys differ from Discovery selection')
    # Every Mayo statistical field is null for laboratory targets.
    for source in [data,adjusted]:
        stats=[c for c in source if c.startswith('mayo_') and any(t in c for t in ['odds_ratio','q_value'])]
        if source.loc[source.modality.eq('labs'),stats].notna().any().any():raise ValueError('Mayo laboratory statistics must be null')
    if not args.skip_activation_check:
        for modality in MODALITIES:
            name=f'activations/{modality}.parquet';file=path(name)
            if digest(file)!=manifest['activation_sha256'][name]:raise ValueError(f'Activation checksum mismatch: {modality}')
            names=set(pq.read_schema(file).names);used=set(data.loc[data.modality.eq(modality),'feature'])
            if used!={n for n in names if n.startswith('Concept_')}:raise ValueError(f'Activation schema mismatch: {modality}')
            print(f'{modality}: {len(used)} concepts match released activation file')
    columns=[*KEY,*[c for c in adjusted if c.startswith(tuple(s+'_' for s in SITES))]]
    data=data.merge(adjusted[columns],on=KEY,how='left',validate='one_to_one')
    tables,audit=summarize(data,manifest)
    # Make differences from the frozen manuscript explicit, never force counts.
    paper={'tested':604185,'discovery':4463,'test_association':3095,'tri_valley_association':3314,'mayo_association':1701,'train_adjusted':1198,'test_adjusted':489,'tri_valley_adjusted':645,'mayo_adjusted':643}
    comparison=pd.DataFrame([dict(metric=k,manuscript_v34=v,current_release=audit['counts'][k],difference=audit['counts'][k]-v) for k,v in paper.items()]).set_index('metric')
    if manifest.get('analysis_version')=='paper_v34' and comparison.difference.ne(0).any():raise ValueError('Release does not match manuscript v34 totals')
    if manifest.get('analysis_version')=='paper_v34':
        for site,counts in manifest['manuscript']['adjusted_counts_by_modality'].items():
            actual=tables['adjusted_summary'][f'{site}_adjusted'].drop('Total').astype(int).to_dict()
            if actual!=counts:raise ValueError(f'Manuscript v34 modality mismatch: {site}')
    tables['manuscript_v34_comparison']=comparison
    audit.update(dataset=DATASET,revision=args.revision if args.data_dir is None else 'local',release=manifest['release'],association_manifest_sha256=digest(manifest_path),activation_checks=not args.skip_activation_check)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name,table in tables.items():table.to_csv(args.output_dir/f'{name}.csv')
    (args.output_dir/'audit.json').write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n')
    print(json.dumps(audit,indent=2,allow_nan=False));print(f'Saved {len(tables)} tables to {args.output_dir}')

if __name__=='__main__':main()
