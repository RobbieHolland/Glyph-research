"""Fit MHG associations from released inputs; saved estimates are comparisons only."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download
from threadpoolctl import threadpool_limits

from .isolated import IsolatedModel
from .covariates import CLINICAL_CONFOUNDERS,add_race_covariates,select_concept_confounders
from . import fmr_current,fmr_paper_run
from .correction import screen_unadjusted

REVISION='fc3f8ad26f8928bede2c495ae68fa5bdf6f2d1a0'  # Clean non-Mayo HF release.
SITES={'train':'Discovery Site','test':'Internal Test','tri_valley':'External Site #1','mayo':'External Site #2'}
ISOLATED=['isolated_odds_ratio','isolated_odds_ratio_p_value','isolated_odds_ratio_ci_lower','isolated_odds_ratio_ci_upper']
DML=['dml_odds_ratio','dml_odds_ratio_p_value','dml_odds_ratio_ci_lower','dml_odds_ratio_ci_upper']


def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bh_q(values):
    p=values.fillna(1).to_numpy(float);order=np.argsort(p);q=np.empty(len(p))
    q[order]=np.minimum(1,np.minimum.accumulate((p[order]*len(p)/np.arange(1,len(p)+1))[::-1])[::-1]);return q


class Inputs:
    def __init__(self,args):
        self.args=args
        self.input_hashes={}
        old=args.output/'run.json'
        self.expected_hashes=json.loads(old.read_text()).get('input_files',{}) if old.exists() else {}
        self.labels=pd.read_parquet(self.file('outcomes/outcomes.parquet'))
        if not self.labels.study_id.is_unique:raise ValueError('Duplicate outcome study IDs')
        self.reference=pd.read_parquet(self.file('associations/unadjusted.parquet'))
        self.meta=self.reference[['modality','feature','concept_short_id','concept_id_string']].drop_duplicates()
        self.keys=self.meta.set_index('concept_id_string').to_dict('index')
        self.clinical=None
        if args.clinical_data:
            c=pd.read_parquet(args.clinical_data)
            if 'study_id' not in c or not c.study_id.is_unique:raise ValueError('Clinical data require unique public study_id keys')
            if 'Race' in c or 'race' in c:c=add_race_covariates(c)
            self.clinical=c

    def file(self,name):
        if self.args.data_dir:
            path=self.args.data_dir/name
            if not path.exists():raise FileNotFoundError(path)
        else:
            path=Path(hf_hub_download('RobbieHolland/Glyph-research',name,repo_type='dataset',revision=self.args.revision,cache_dir=str(self.args.cache)))
        if name not in self.input_hashes:
            value=file_hash(path)
            if name in self.expected_hashes and self.expected_hashes[name]!=value:raise ValueError(f'Resume input changed: {name}')
            self.input_hashes[name]=value
        return path

    def chosen(self):
        chosen=self.meta
        if self.args.features:
            unknown=set(self.args.features)-set(chosen.concept_short_id)-set(chosen.concept_id_string)
            if unknown:raise ValueError(f'Unknown features: {sorted(unknown)}')
            chosen=chosen[chosen.concept_short_id.isin(self.args.features)|chosen.concept_id_string.isin(self.args.features)]
        outcomes=list(self.reference.outcome.astype(str).drop_duplicates())
        if self.args.outcomes:
            unknown=set(self.args.outcomes)-set(outcomes)
            if unknown:raise ValueError(f'Unknown outcomes: {sorted(unknown)}')
            outcomes=[o for o in outcomes if o in self.args.outcomes]
        return chosen,outcomes

    def activation(self,modality,all_columns=True,keys=None):
        columns=None
        if not all_columns:
            columns=['study_id','Site',*[self.keys[k]['feature'] for k in keys if self.keys[k]['modality']==modality]]
        # Do not read Mayo lab activation rows or produce Mayo lab results.
        filters=[('Site','!=',SITES['mayo'])] if modality=='labs' else None
        return pd.read_parquet(self.file(f'activations/{modality}.parquet'),columns=columns,filters=filters)

    def adjusted_frames(self,features):
        available=set(self.labels.columns)|(set(self.clinical.columns) if self.clinical is not None else set())
        missing=sorted(set(CLINICAL_CONFOUNDERS)-available)
        if missing:raise ValueError('HF lacks required clinical covariates: '+', '.join(missing)+'. Supply --clinical-data with public study_id keys; missing variables are never replaced by zero.')
        frame=self.labels.copy()
        if self.clinical is not None:
            # Supplement columns, preserving HF outcomes/age/sex and their missingness.
            columns=['study_id',*[c for c in self.clinical if c not in frame and c!='Site']]
            frame=frame.merge(self.clinical[columns],on='study_id',how='left',validate='one_to_one')
            if 'Site' in self.clinical:
                site=self.clinical.set_index('study_id').Site.reindex(frame.study_id)
                known=site.notna().to_numpy()
                if not np.array_equal(site.to_numpy()[known],frame.Site.to_numpy()[known]):raise ValueError('Clinical and outcome sites differ')
        if 'analysis_order' in frame:
            for _,g in frame.groupby('Site'):
                if g.analysis_order.isna().any() or g.analysis_order.duplicated().any():raise ValueError('analysis_order must be unique and complete within each site')
            frame=frame.sort_values(['Site','analysis_order'],kind='stable')
        for modality in ['image','labs','findings']:
            names=[k for k in features if self.keys[k]['modality']==modality]
            if not names:continue
            data=self.activation(modality,False,names)
            data=data.rename(columns={self.keys[k]['feature']:k for k in names}).drop(columns='Site')
            frame=frame.merge(data,on='study_id',how='left',validate='one_to_one',sort=False)
        # MHG adjusted inputs use Discovery pandas std(ddof=1)+1e-8,
        # separately from the cohort std(ddof=0) unadjusted pipeline.
        train=frame.Site.eq(SITES['train'])
        if not train.any():raise ValueError('Discovery data are required for normalization')
        normalization={}
        frozen=json.loads(self.args.normalization_file.read_text()) if self.args.normalization_file else None
        if frozen and 'normalization' in frozen:frozen=frozen['normalization']
        for col in [*features,*CLINICAL_CONFOUNDERS]:
            if frozen is not None:
                stored=frozen[col];mean,sd=(stored['mean'],stored['std']) if isinstance(stored,dict) else stored
            else:
                values=frame.loc[train,col];mean=float(values.mean());sd=float(values.std()+1e-8)
            if not np.isfinite([mean,sd]).all():raise ValueError(f'No Discovery normalization data for {col}')
            normalization[col]={'mean':mean,'std':sd}
            frame[col]=(frame[col]-mean)/sd
        result={s:frame[frame.Site.eq(label)].copy() for s,label in SITES.items()}
        if 'mayo' in result:result['mayo']=result['mayo'].drop(columns=[k for k in features if self.keys[k]['modality']=='labs'])
        return result,normalization


def fit_adjusted_frame(frame,feature,outcome,columns,*,engine='paper-run',outer=5,inner=5,retry=False):
    if feature.startswith('labs_') and frame.attrs.get('site')=='mayo':raise ValueError('Mayo lab targets are prohibited')
    sample=frame[[feature,*columns,outcome]].dropna()
    sample=sample[sample[outcome].isin([0,1])]
    kept=[c for c in columns if sample[c].std(ddof=0)>1e-8]
    module=fmr_paper_run if engine=='paper-run' else fmr_current
    with warnings.catch_warnings(record=True) as caught,threadpool_limits(limits=1):
        warnings.simplefilter('always')
        args=(sample[feature].to_numpy(float),sample[outcome].to_numpy(int),sample[kept].to_numpy(float))
        result=module.fmr_orthogonal(*args,n_splits=outer,inner_splits=inner,device='cpu',random_state=42)
        retried=False
        if retry and not np.isfinite(result['dml_odds_ratio_p_value']):
            result=module.fmr_orthogonal(*args,n_splits=2,inner_splits=2,device='cpu',random_state=42);retried=True
    return dict(n=len(sample),events=int(sample[outcome].sum()),columns=json.dumps(kept),engine=engine,requested_outer=outer,requested_inner=inner,retried_2x2=retried,warnings=' | '.join(str(w.message) for w in caught),**result)


def unadjusted(inputs,args,chosen,outcomes):
    fitter=IsolatedModel(seed=42);files=[]
    for modality,selection in chosen.groupby('modality',sort=False):
        data=inputs.activation(modality)
        all_features=[c for c in data if c.startswith('Concept_')]
        data=data.merge(inputs.labels.drop(columns='Site'),on='study_id',how='left',validate='one_to_one',sort=False)
        arrays={};labels={}
        for site,label in SITES.items():
            if modality=='labs' and site=='mayo':continue
            g=data[data.Site.eq(label)].copy()
            if g.empty:continue
            values=g[all_features].to_numpy()
            complete=np.isfinite(values).all(axis=1);g=g.loc[complete];values=values[complete]
            mu=values.mean(axis=0);sd=values.std(axis=0)
            normalized=(values-mu)/np.where(sd>1e-8,sd,1)
            arrays[site]=(values,normalized);labels[site]=g
        indices={name:i for i,name in enumerate(all_features)}
        for outcome in outcomes:
            path=args.output/'unadjusted'/modality/(hashlib.sha256(outcome.encode()).hexdigest()[:12]+'.parquet');path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():files.append(path);continue
            rows=[]
            for record in selection.itertuples(index=False):
                i=indices[record.feature]
                train_y=labels['train'][outcome].to_numpy();valid_train=np.isin(train_y,[0,1])
                train_support=int((arrays['train'][0][valid_train,i]>0).sum())
                for site in args.sites:
                    row=dict(modality=modality,feature=record.feature,concept_id_string=record.concept_id_string,concept=record.concept_short_id,outcome=outcome,cohort=site,train_support=train_support,**dict.fromkeys(ISOLATED,np.nan))
                    if site not in arrays:row['status']='ineligible_mayo_laboratory';rows.append(row);continue
                    raw,normed=arrays[site];y=labels[site][outcome].to_numpy();valid=np.isin(y,[0,1]);row['n']=int(valid.sum())
                    if train_support<25:row['status']='insufficient_discovery_activation_support'
                    elif np.unique(y[valid]).size<2:row['status']='insufficient_outcome_classes'
                    else:
                        with threadpool_limits(limits=1):result=fitter.fit_isolated_model(normed[valid,i],y[valid])
                        row.update(result);row['status']='estimated'
                    rows.append(row)
            pd.DataFrame(rows).to_parquet(path,index=False);files.append(path)
    return files,ISOLATED


def adjusted(inputs,args,chosen,outcomes):
    base=pd.read_parquet(args.screen_results) if args.screen_results else inputs.reference
    if base.duplicated(['modality','feature','outcome']).any():raise ValueError('Duplicate input screening keys')
    discovery=base.train_isolated_odds_ratio.gt(1)&base.train_isolated_odds_ratio_p_value.lt(.05/len(base))
    family=base.loc[discovery].copy()
    family['inputs']=family.modality
    family['train_promising_association']=True
    for site in args.sites:
        if site!='train':family[f'{site}_promising_association']=family[f'{site}_reproducible_association'].fillna(False).to_numpy(bool)
    features=list(family.concept_id_string.drop_duplicates())
    frames,normalization=inputs.adjusted_frames(features)
    specs=pd.read_parquet(inputs.file('associations/adjustment_specifications.parquet'))
    lookup=specs.set_index(['cohort','concept_id_string','outcome'])
    tasks=family[family.concept_id_string.isin(chosen.concept_id_string)&family.outcome.isin(outcomes)]
    correlations={}
    if args.selection=='recompute':
        for site in args.sites:
            keys=[k for k in features if site!='mayo' or not k.startswith('labs_')]
            matrix=frames[site][keys].dropna().to_numpy(float)
            if len(matrix)<2:raise ValueError('Insufficient correlation population')
            correlations[site]=(np.corrcoef(matrix,rowvar=False),{k:i for i,k in enumerate(keys)})
    files=[]
    for task in tasks.itertuples(index=False):
        for site in args.sites:
            if site=='mayo' and task.modality=='labs':continue
            key=(site,task.concept_id_string,task.outcome)
            recorded=lookup.loc[key] if key in lookup.index else None
            if args.selection=='recorded' and recorded is None:raise ValueError('Newly discovered pair has no frozen covariate specification; use --selection recompute')
            columns=json.loads(recorded.confounders) if recorded is not None else []
            if args.selection=='recompute':
                candidates=family
                if task.concept_short_id=='I26':candidates=candidates[~candidates.concept_short_id.isin(['I15','I106','I109','L121'])]
                corr,index=correlations[site]
                columns=select_concept_confounders(candidates,task.concept_id_string,task.outcome,site,'isolated_odds_ratio',corr,index,threshold=.35,n_select=10)
                if task.concept_short_id=='I26':columns=[c for c in columns if inputs.keys[c]['concept_short_id']!='I102']
                columns+=list(CLINICAL_CONFOUNDERS)
            if site=='mayo' and any(c.startswith('labs_') for c in columns):raise ValueError('Mayo lab covariates are prohibited')
            path=args.output/'adjusted'/site/(hashlib.sha256((task.concept_id_string+'|'+task.outcome).encode()).hexdigest()[:16]+'.parquet');path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists():
                # The Mayo no-lab run used the later rare-class-capable routine.
                engine='current' if args.estimator=='current' or site=='mayo' else 'paper-run'
                fit=fit_adjusted_frame(frames[site],task.concept_id_string,task.outcome,columns,engine=engine,outer=int(recorded.outer_splits) if recorded is not None else 5,inner=int(recorded.inner_splits) if recorded is not None else 5,retry=args.retry_failed)
                pd.DataFrame([dict(modality=task.modality,feature=task.feature,concept_id_string=task.concept_id_string,concept=task.concept_short_id,outcome=task.outcome,cohort=site,**fit)]).to_parquet(path,index=False)
            files.append(path)
    (args.output/'normalization.json').write_text(json.dumps(normalization,indent=2,allow_nan=False)+'\n')
    return files,DML


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['unadjusted','adjusted'])
    parser.add_argument('--data-dir',type=Path);parser.add_argument('--clinical-data',type=Path);parser.add_argument('--normalization-file',type=Path);parser.add_argument('--screen-results',type=Path);parser.add_argument('--revision',default=REVISION);parser.add_argument('--cache',type=Path,default=Path('.cache/hf'))
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--features',nargs='+');parser.add_argument('--outcomes',nargs='+');parser.add_argument('--sites',nargs='+',choices=list(SITES),default=['train','test','tri_valley'])
    parser.add_argument('--selection',choices=['recorded','recompute'],default='recorded');parser.add_argument('--estimator',choices=['paper-run','current'],default='paper-run');parser.add_argument('--retry-failed',action='store_true')
    args=parser.parse_args(argv)
    inputs=Inputs(args);chosen,outcomes=inputs.chosen()
    missing_sites=[site for site in args.sites if SITES[site] not in set(inputs.labels.Site)]
    if missing_sites:raise ValueError('No released study-level inputs for '+', '.join(missing_sites)+'. Mayo is aggregate-only in the cleaned release.')
    settings={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(args).items()}
    settings['runner_sha256']=file_hash(Path(__file__))
    settings['input_sha256']={name:file_hash(getattr(args,name)) for name in ['clinical_data','normalization_file','screen_results'] if getattr(args,name) is not None}
    settings['seed']=42;settings['source_provenance_sha256']=file_hash(Path(__file__).with_name('source_provenance.json'))
    args.output.mkdir(parents=True,exist_ok=True);manifest_path=args.output/'run.json'
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        if old['settings']!=settings:raise ValueError('Resume settings differ from existing run')
    manifest={'status':'running','settings':settings,'versions':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','scikit-learn','xgboost']},'row_order':'HF outcomes order unless clinical-data includes explicit analysis_order; original FMR fold equivalence needs the original order','refits_from_activations':True,'mayo_laboratory_results_computed':False}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    try:
        files,fields=(unadjusted if args.stage=='unadjusted' else adjusted)(inputs,args,chosen,outcomes)
        if not files:raise ValueError('No selected hypotheses')
        result=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
        if result.duplicated(['cohort','concept_id_string','outcome']).any():raise ValueError('Duplicate result keys')
        reference=inputs.reference if args.stage=='unadjusted' else pd.read_parquet(inputs.file('associations/adjusted.parquet'))
        comparisons=[]
        for site,g in result.groupby('cohort'):
            cols=['modality','feature','outcome',*[site+'_'+f for f in fields]]
            joined=g.merge(reference[cols],on=['modality','feature','outcome'],validate='one_to_one')
            for f in fields:joined['reference_'+f]=joined[site+'_'+f];joined=joined.drop(columns=site+'_'+f)
            comparisons.append(joined)
        comparison=pd.concat(comparisons,ignore_index=True)
        result.to_parquet(args.output/'refitted.parquet',index=False);comparison.to_csv(args.output/'comparison.csv',index=False)
        manifest.update(status='complete',rows=len(result),finite_estimates=int(result[fields[1]].notna().sum()),checkpoint_files=len(files),full_family=not args.features and not args.outcomes)
        # Correction must never be computed on a requested demonstration subset.
        if manifest['full_family']:
            if args.stage=='unadjusted':
                if 'train' in args.sites:
                    screened,screening=screen_unadjusted(result,inputs.reference)
                    screened.to_parquet(args.output/'screened.parquet',index=False)
                    manifest['screening']=screening
                else:manifest['correction_status']='Requires complete Discovery refits before held-out screening'
            else:
                flags=[]
                for site,g in result.groupby('cohort'):
                    g=g.copy();g['q']=bh_q(g[fields[1]]);g['significant']=g.q.lt(.05)&g[fields[0]].gt(1);flags.append(g)
                if flags:pd.concat(flags).to_parquet(args.output/'corrected.parquet',index=False)
    except Exception as exc:
        manifest.update(status='failed',error=str(exc));raise
    finally:
        manifest['input_files']=inputs.input_hashes
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
