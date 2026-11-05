"""Standalone parity and scientific filtering checks; no private data required."""
import json
from pathlib import Path
import unittest
import tempfile
import contextlib
import io
from unittest.mock import patch
import warnings
import numpy as np
import pandas as pd
from scipy.special import expit
from reproduction import fmr_current,fmr_paper_run
from reproduction.covariates import add_race_covariates,select_concept_confounders
from reproduction.correction import screen_unadjusted,bh_q,FIELDS
from reproduction.runner import fit_adjusted_frame

class MHGReproductionTests(unittest.TestCase):
    def test_original_mhg_fmr_numerical_reference(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/mhg_fmr_reference.json').read_text())
        rng=np.random.default_rng(fixture['seed']);w=rng.normal(size=(fixture['n'],3));t=.4*w[:,0]+rng.normal(size=fixture['n']);y=rng.binomial(1,expit(.65*t+.4*w[:,0]-.3*w[:,1]))
        for label,module in [('paper-run',fmr_paper_run),('current',fmr_current)]:
            result=module.fmr_orthogonal(t,y,w,**fixture['settings'])
            for field,expected in fixture['original_mhg'][label].items():self.assertAlmostEqual(result[field],expected,places=12)

    def test_rare_class_policy_is_explicit(self):
        y=np.array([1]*4+[0]*20)
        self.assertEqual(fmr_current.fmr_crossfit_splits(y,5,5,42),(2,2))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');result=fmr_paper_run.fmr_orthogonal(np.arange(len(y),dtype=float),y,np.ones((len(y),1)))
        self.assertTrue(all(np.isnan(v) for v in result.values()))

    def test_complete_cases_precede_constant_covariate_removal(self):
        frame=pd.DataFrame({'f':[0.,1.,2.,3.,4.],'y':[0,1,-1,1,0],'w':[1.,2.,3.,np.nan,4.],'constant':[1.]*5})
        def fit(t,y,w,**kwargs):
            np.testing.assert_array_equal(t,[0.,1.,4.]);np.testing.assert_array_equal(y,[0,1,0]);np.testing.assert_array_equal(w[:,0],[1.,2.,4.]);self.assertEqual(w.shape,(3,1));self.assertEqual(kwargs['random_state'],42)
            return {'dml_odds_ratio':1.,'dml_odds_ratio_p_value':.5,'dml_odds_ratio_ci_lower':.8,'dml_odds_ratio_ci_upper':1.2}
        with patch('reproduction.runner.fmr_paper_run.fmr_orthogonal',side_effect=fit):result=fit_adjusted_frame(frame,'f','y',['w','constant'])
        self.assertEqual(result['n'],3);self.assertEqual(result['events'],1);self.assertEqual(json.loads(result['columns']),['w'])

    def test_mayo_laboratory_target_guard(self):
        frame=pd.DataFrame();frame.attrs['site']='mayo'
        with self.assertRaisesRegex(ValueError,'prohibited'):fit_adjusted_frame(frame,'labs_Concept_84','y',[])

    def test_covariate_selection_respects_modality_correlation_and_mayo(self):
        names=['image_Concept_26','image_Concept_87','findings_Concept_85','labs_Concept_108']
        links=pd.DataFrame({'concept_id_string':names,'inputs':['image','image','findings','labs'],'outcome':['y']*4,'train_promising_association':[True]*4,'mayo_promising_association':[True]*4,'train_isolated_odds_ratio':[5.,3.,10.,4.],'mayo_isolated_odds_ratio':[5.,3.,10.,4.]})
        corr=np.eye(4);corr[0,1]=corr[1,0]=.3;corr[0,3]=corr[3,0]=.35
        index={v:i for i,v in enumerate(names)}
        actual=select_concept_confounders(links,names[0],'y','train','isolated_odds_ratio',corr,index)
        self.assertEqual(actual,[names[1]])
        self.assertEqual(select_concept_confounders(links,names[0],'y','mayo','isolated_odds_ratio',corr,index),[names[1]])

    def test_race_encoding_preserves_missing_and_reference(self):
        result=add_race_covariates(pd.DataFrame({'Race':['White','Black or African American',None]}))
        self.assertEqual(result.race_Black.tolist(),[0,1,0]);self.assertEqual(result.race_Missing.tolist(),[0,0,1])
        with self.assertRaises(ValueError):add_race_covariates(pd.DataFrame({'Race':['unexpected']}))

    def test_failed_fits_remain_in_bh_family(self):
        np.testing.assert_allclose(bh_q(pd.Series([.01,.03,np.nan])),[.03,.045,1.])

    def test_fresh_screen_requires_full_grid_and_never_mayo_labs(self):
        meta=pd.DataFrame({'modality':['image','findings','labs'],'feature':['Concept_26','Concept_85','Concept_108'],'outcome':['y']*3,'concept_short_id':['I26','R85','L108'],'concept_id_string':['image_Concept_26','findings_Concept_85','labs_Concept_108'],'outcome_display':['Y']*3})
        rows=[]
        for site,pvalues in [('train',[.0001]*3),('mayo',[.001,.015,np.nan])]:
            for row,pvalue in zip(meta.to_dict('records'),pvalues):rows.append(dict(**row,cohort=site,isolated_odds_ratio=2.,isolated_odds_ratio_p_value=pvalue,isolated_odds_ratio_ci_lower=1.5,isolated_odds_ratio_ci_upper=2.5))
        data=pd.DataFrame(rows);wide,audit=screen_unadjusted(data,meta)
        self.assertEqual(audit['heldout']['mayo']['hypotheses'],2);self.assertFalse(wide.loc[wide.modality.eq('labs'),'mayo_reproducible_association'].any())
        with self.assertRaisesRegex(ValueError,'entire test grid'):screen_unadjusted(data.iloc[:-1],meta)

    def test_adjusted_runner_accepts_hf_shaped_offline_inputs(self):
        from reproduction.runner import main
        from reproduction.covariates import CLINICAL_CONFOUNDERS
        rng=np.random.default_rng(91);n=320
        keys=['image_Concept_26/40/[128, 512, 2048, 8192]','labs_Concept_108/40/[128, 512, 2048, 8192]']
        features=rng.normal(size=(n,2)).astype('float32')
        age=rng.normal(60,10,n);bmi=rng.normal(27,3,n)
        y=rng.binomial(1,expit(.6*features[:,0]+.3*features[:,1]+.02*(age-60)))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=root/'data';(data/'outcomes').mkdir(parents=True);(data/'associations').mkdir();(data/'activations').mkdir()
            ids=[f'synthetic_{i}' for i in range(n)]
            labels=pd.DataFrame({'study_id':ids,'Site':['Discovery Site']*n,'patient_age':age,'patient_sex':rng.binomial(1,.5,n),'outcome':y})
            labels.to_parquet(data/'outcomes/outcomes.parquet',index=False)
            rows=[]
            for i,(modality,col,concept) in enumerate([('image','Concept_26','I26'),('labs','Concept_108','L108')]):
                row={'modality':modality,'feature':col,'outcome':'outcome','concept_short_id':concept,'concept_id_string':keys[i],'outcome_display':'Synthetic outcome','train_isolated_odds_ratio':2.,'train_isolated_odds_ratio_p_value':1e-12,'train_isolated_odds_ratio_ci_lower':1.5,'train_isolated_odds_ratio_ci_upper':2.5};rows.append(row)
                pd.DataFrame({'study_id':ids,'Site':['Discovery Site']*n,col:features[:,i]}).to_parquet(data/f'activations/{modality}.parquet',index=False)
            pd.DataFrame(rows).to_parquet(data/'associations/unadjusted.parquet',index=False)
            adjusted=pd.DataFrame(rows)
            for key in ['dml_odds_ratio','dml_odds_ratio_p_value','dml_odds_ratio_ci_lower','dml_odds_ratio_ci_upper']:adjusted['train_'+key]=np.nan
            adjusted.to_parquet(data/'associations/adjusted.parquet',index=False)
            columns=['patient_age','recent_bmi',keys[1]]
            pd.DataFrame([{'cohort':'train','concept_id_string':keys[0],'outcome':'outcome','confounders':json.dumps(columns),'outer_splits':5,'inner_splits':5}]).to_parquet(data/'associations/adjustment_specifications.parquet',index=False)
            clinical=pd.DataFrame({'study_id':ids,**{col:np.zeros(n) for col in CLINICAL_CONFOUNDERS if col not in labels},'recent_bmi':bmi})
            clinical.to_parquet(root/'clinical.parquet',index=False)
            with contextlib.redirect_stdout(io.StringIO()):
                main(['adjusted','--data-dir',str(data),'--clinical-data',str(root/'clinical.parquet'),'--features','I26','--outcomes','outcome','--sites','train','--output',str(root/'output')])
            run=json.loads((root/'output/run.json').read_text());self.assertEqual(run['status'],'complete');self.assertTrue(run['input_files'])
            result=pd.read_parquet(root/'output/refitted.parquet');self.assertEqual(len(result),1);self.assertEqual(int(result.iloc[0]['n']),n);self.assertTrue(np.isfinite(result.iloc[0].dml_odds_ratio))
            self.assertNotIn('study_id',result.columns)

if __name__=='__main__':unittest.main()
