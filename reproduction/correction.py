"""Whole-family screening for newly fitted estimates; never subsets."""
import numpy as np
import pandas as pd

FIELDS=['isolated_odds_ratio','isolated_odds_ratio_p_value','isolated_odds_ratio_ci_lower','isolated_odds_ratio_ci_upper']
KEY=['modality','feature','outcome']

def bh_q(values):
    p=values.fillna(1).to_numpy(float)
    if not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid p-values')
    order=np.argsort(p);q=np.empty(len(p))
    q[order]=np.minimum(1,np.minimum.accumulate((p[order]*len(p)/np.arange(1,len(p)+1))[::-1])[::-1]);return q

def screen_unadjusted(result,metadata):
    """Require the full grid; fresh Mayo BH uses non-lab hypotheses only.

    Historical Mayo flags cannot be reconstructed from the current release
    because the original full-family laboratory results are excluded. This
    fresh non-lab-only screen is explicitly distinguished in its metadata.
    """
    meta=metadata[[*KEY,'concept_short_id','concept_id_string','outcome_display']].copy()
    full_keys=pd.MultiIndex.from_frame(meta[KEY]);n=len(meta)
    if full_keys.has_duplicates or result.duplicated(['cohort',*KEY]).any():raise ValueError('Duplicate association keys')
    if 'train' not in set(result.cohort):raise ValueError('A fresh Discovery screen requires the full train results')
    wide=meta
    for site,g in result.groupby('cohort'):
        keys=pd.MultiIndex.from_frame(g[KEY])
        if set(keys)!=set(full_keys):raise ValueError(f'{site}: correction requires the entire test grid')
        g=g[[*KEY,*FIELDS]].rename(columns={f:site+'_'+f for f in FIELDS})
        wide=wide.merge(g,on=KEY,validate='one_to_one',sort=False)
    wide['train_promising_association']=wide.train_isolated_odds_ratio_p_value.lt(.05/n)&wide.train_isolated_odds_ratio.gt(1)
    families={}
    for site in result.cohort.drop_duplicates():
        if site=='train':continue
        eligible=wide.train_promising_association & (wide.modality.ne('labs') if site=='mayo' else True)
        p=wide.loc[eligible,site+'_isolated_odds_ratio_p_value']
        q=bh_q(p)
        values=p.dropna().sort_values().to_numpy(float)
        passing=values<=.05*np.arange(1,len(values)+1)/len(p) if len(p) else np.array([],dtype=bool)
        cutoff=float(values[passing].max()) if passing.any() else np.nan
        wide[site+'_association_q_value']=np.nan;wide.loc[eligible,site+'_association_q_value']=q
        wide[site+'_reproducible_association']=eligible&wide[site+'_isolated_odds_ratio_p_value'].lt(cutoff)&wide[site+'_isolated_odds_ratio'].gt(1)
        families[site]={'hypotheses':int(eligible.sum()),'strict_raw_p_cutoff':cutoff if np.isfinite(cutoff) else None,'significant':int(wide[site+'_reproducible_association'].sum())}
    return wide,{'tested':n,'discovery':int(wide.train_promising_association.sum()),'heldout':families,'mayo_screen':'Fresh non-laboratory-only BH; may differ from historical frozen Mayo screening flags. No Mayo lab results used.'}
