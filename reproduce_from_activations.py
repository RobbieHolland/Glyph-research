"""Run the minimal MHG refit pipeline from HF activations and outcome labels."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from reproduction.runner import Inputs,REVISION
from reproduction.covariates import CLINICAL_CONFOUNDERS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clinical-data',type=Path);p.add_argument('--normalization-file',type=Path);p.add_argument('--data-dir',type=Path);p.add_argument('--cache',type=Path,default=Path('.cache/hf'));p.add_argument('--revision',default=REVISION);p.add_argument('--output-dir',type=Path,default=Path('outputs/refit'))
    p.add_argument('--features',nargs='+');p.add_argument('--outcomes',nargs='+');p.add_argument('--sites',nargs='+',default=['train','test','tri_valley'])
    p.add_argument('--selection',choices=['recorded','recompute'],default='recompute');p.add_argument('--estimator',choices=['current','paper-run'],default='current');p.add_argument('--retry-failed',action=argparse.BooleanOptionalAction,default=True)
    args=p.parse_args()
    # Check required inputs before starting a long grid of unadjusted fits.
    args.output=args.output_dir
    inputs=Inputs(args)
    available=set(inputs.labels.columns)|(set(inputs.clinical.columns) if inputs.clinical is not None else set())
    missing=sorted(set(CLINICAL_CONFOUNDERS)-available)
    if missing:p.error('Full adjusted refitting needs --clinical-data containing these missing HF inputs: '+', '.join(missing)+'. No models were fitted.')
    del inputs
    script=Path(__file__).with_name('refit_associations.py')
    common=['--revision',args.revision,'--cache',str(args.cache),'--sites',*args.sites]
    for name in ['data_dir','clinical_data','normalization_file']:
        value=getattr(args,name)
        if value is not None:common+=['--'+name.replace('_','-'),str(value)]
    for name in ['features','outcomes']:
        value=getattr(args,name)
        if value:common+=['--'+name,*value]
    unadjusted=args.output_dir/'unadjusted';adjusted=args.output_dir/'adjusted'
    subprocess.run([sys.executable,str(script),'unadjusted','--output',str(unadjusted),*common],check=True)
    command=[sys.executable,str(script),'adjusted','--output',str(adjusted),*common,'--estimator',args.estimator,'--selection',args.selection]
    if args.retry_failed:command+=['--retry-failed']
    if not args.features and not args.outcomes:
        screened=unadjusted/'screened.parquet'
        if not screened.exists():p.error('Full refitting requires train results to derive a fresh Discovery screen')
        command+=['--screen-results',str(screened)]
    subprocess.run(command,check=True)
    print(json.dumps({'status':'complete','unadjusted':str(unadjusted),'adjusted':str(adjusted),'partial_probe':bool(args.features or args.outcomes),'mayo_laboratory_results_computed':False},indent=2))

if __name__=='__main__':main()
