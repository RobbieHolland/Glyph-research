"""Fit aggregate clinical associations with the original isolated-model method.

Read-only inputs; write aggregates only. Verify canonical Discovery membership
and outcome-specific production sample counts before calling the estimator.
"""
import argparse
import ast
import hashlib
import json
import warnings
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.exceptions import ConvergenceWarning

FEATURES=['patient_age','patient_sex','current_smoker','heavy_alcohol_use','recent_bmi']


def digest(path):
    checksum=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def compute(args):
    args.output.mkdir(parents=True,exist_ok=True)
    outcomes=pd.read_csv(args.groups,dtype={'outcome':str}).outcome.tolist()
    assert len(outcomes)==141
    labels=pd.read_pickle(args.labels)
    assert len(labels)==15331 and not labels.anon_accession.duplicated().any()
    # Source get_stanford_datalist explicitly defines 0/1/2 as train, 3 as val, 4 as test.
    assert set(labels['split'].dropna().unique())=={0,1,2}
    metadata=pd.read_csv(args.metadata,usecols=['anon_accession','split'])
    assert not metadata.anon_accession.duplicated().any()
    canonical=metadata.set_index('anon_accession')['split'].reindex(labels.anon_accession)
    assert canonical.notna().all() and canonical.isin([0,1,2]).all()
    assert (canonical.to_numpy()==labels['split'].to_numpy()).all()
    assert not set(labels.anon_accession)&set(metadata.loc[metadata.split.isin([3,4]),'anon_accession'])
    assert labels[FEATURES].notna().all().all()
    print('Canonical Discovery membership verified; zero held-out overlap.',flush=True)
    links=pd.read_pickle(args.links)
    reference=links[['outcome','train_n_samples']].dropna().copy()
    reference['outcome']=reference.outcome.astype(str)
    # Model populations can differ by modality availability. Clinical fields are
    # complete, so their eligible count matches the maximal production population.
    counts=reference.groupby('outcome').train_n_samples.max()
    del links,reference
    validations=[]
    for outcome in outcomes:
        y=labels[outcome];valid=y.isin([0,1]);n=int(valid.sum())
        assert n==int(counts.loc[outcome]),(outcome,'population mismatch')
        validations.append(dict(outcome=outcome,n=n,production_n=int(counts.loc[outcome]),events=int((y[valid]==1).sum())))
    print('Eligible sample counts verified for all 141 outcomes.',flush=True)
    tree=ast.parse(args.estimator.read_text())
    function=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='fit_isolated_model')
    namespace=dict(np=np,norm=norm,LogisticRegression=LogisticRegression,roc_auc_score=roc_auc_score)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(args.estimator),'exec'),namespace)
    estimator=namespace['fit_isolated_model'];owner=SimpleNamespace(config=SimpleNamespace(seed=42))
    denominator=604185+len(FEATURES)*len(outcomes)
    results=[];normalization={};sex_mapping={}
    raw_sex=next((c for c in ('Sex','sex','Gender','gender') if c in labels.columns),None)
    if raw_sex:
        table=pd.crosstab(labels.patient_sex,labels[raw_sex])
        if len(table.columns)<=5:
            sex_mapping={str(i):{str(j):int(v) for j,v in row.items()} for i,row in table.to_dict(orient='index').items()}
    for feature in FEATURES:
        values=labels[feature].to_numpy(dtype=float)
        mean=float(values.mean());sd=float(values.std(ddof=0));assert sd>0
        normalized=(values-mean)/sd
        normalization[feature]=dict(mean=mean,sd=sd,coding_values=sorted(labels[feature].unique().tolist()) if feature not in ('patient_age','recent_bmi') else None)
        for outcome in outcomes:
            valid=labels[outcome].isin([0,1]).to_numpy();event=labels[outcome].to_numpy()[valid].astype(int)
            basic=dict(feature=feature,outcome=outcome,n_samples=int(valid.sum()),events=int(event.sum()))
            if len(np.unique(normalized[valid]))<2 or len(np.unique(event))<2:
                results.append(dict(**basic,status='Not identifiable: no predictor or outcome variation',significant=False));continue
            with warnings.catch_warnings():
                warnings.simplefilter('error',ConvergenceWarning)
                fit=estimator(owner,normalized[valid],event)
            odds=float(fit['isolated_odds_ratio']);p=float(fit['isolated_odds_ratio_p_value'])
            lower=float(fit['isolated_odds_ratio_ci_lower']);upper=float(fit['isolated_odds_ratio_ci_upper'])
            assert all(np.isfinite([odds,p,lower,upper])) and 0<lower<=odds<=upper and 0<=p<=1
            results.append(dict(**basic,status='Estimated',odds_ratio=odds,p_value=p,ci_lower=lower,ci_upper=upper,corrected_p_value=min(1,p*denominator),significant=p<=.05/denominator,count=int((values[valid]>0).sum()),normalization_mean=mean,normalization_sd=sd))
        pd.DataFrame(results).to_csv(args.output/'associations.csv',index=False)
        print(feature,'complete;',sum(row['significant'] for row in results if row['feature']==feature),'significant',flush=True)
    pd.DataFrame(validations).to_csv(args.output/'population_validation.csv',index=False)
    record=dict(cohort='Canonical Discovery training cohort',base_studies=len(labels),features=FEATURES,outcomes=len(outcomes),tests=len(results),estimated=sum(r['status']=='Estimated' for r in results),population_validation='Canonical metadata verifies all studies in train folds 0/1/2 with no validation/test overlap. All 141 outcome-specific sample counts match maximal production counts; lab-model populations can be smaller.',estimator='Unchanged original fit_isolated_model method: unpenalized logistic regression, Fisher-information Wald confidence intervals and p-values.',normalization='Full Discovery mean and population SD (ddof=0), before outcome masking; OR per SD.',multiple_testing_denominator=denominator,multiple_testing_note='Clinical tests corrected over the 604185 original tests plus 705 new tests. Frozen concept estimates retain their original correction.',normalization_stats=normalization,sex_coding_crosscheck=sex_mapping,source_sha256={key:digest(getattr(args,key)) for key in ('labels','metadata','links','estimator','groups')},payload='Aggregate effects, counts and normalization parameters; no patient records, identifiers or activations.')
    (args.output/'provenance.json').write_text(json.dumps(record,indent=2,allow_nan=False))
    print('Clinical association analysis complete.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('labels','metadata','links','groups','estimator','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    compute(parser.parse_args())
