"""Merge validated aggregate clinical fits without changing frozen concept results."""
import json,math
from pathlib import Path
import pandas as pd

DESCRIPTIONS={
 'patient_age':('Patient age at the CT examination.','Age'),
 'patient_sex':('Sex indicator (1 = male; 0 = female or unknown).','Sex'),
 'current_smoker':('Current smoking status (binary indicator).','Smoking'),
 'heavy_alcohol_use':('Heavy alcohol use (binary indicator).','Alcohol'),
 'recent_bmi':('Body mass index (BMI) at the CT examination.','BMI'),
}


def merge_clinical(payload,csv_path):
    rows=pd.read_csv(csv_path,dtype={'outcome':str})
    provenance=json.loads(csv_path.with_name('provenance.json').read_text())
    assert len(rows)==705 and not rows.duplicated(['feature','outcome']).any()
    assert provenance['base_studies']==15331 and provenance['outcomes']==141
    mapping={o:i for i,o in enumerate(payload['outcomes'])}
    # The outcome order is linked by the published disease-group CSV; callers
    # supply that mapping explicitly through this companion metadata export.
    groups=pd.read_csv(csv_path.with_name('outcome_mapping.csv'),dtype={'outcome':str})
    display=dict(zip(groups.outcome,groups.outcome_display))
    for node in payload['nodes']:
        key=node['concept_id']
        if key not in DESCRIPTIONS:continue
        description,label=DESCRIPTIONS[key]
        selected=rows[rows.feature.eq(key)];estimates=[]
        assert len(selected)==141
        for row in selected.itertuples():
            if row.status!='Estimated':continue
            assert all(math.isfinite(v) for v in (row.odds_ratio,row.p_value,row.ci_lower,row.ci_upper))
            estimates.append([mapping[display[row.outcome]],float(row.odds_ratio),float(row.p_value),float(row.ci_lower),float(row.ci_upper),float(row.corrected_p_value),bool(row.significant),int(row.n_samples)])
        payload['associations'][str(node['i'])]=estimates
        node.update(interpretation=description,interpretation_source='Clinical variable',wheel_label=label,association_model='Unadjusted logistic regression, per Discovery SD',clinical_population=15331,multiple_testing_denominator=int(provenance['multiple_testing_denominator']),normalization=provenance['normalization_stats'][key])
    payload['clinical_associations']=dict(features=5,tested=705,estimated=int(provenance['estimated']),multiple_testing_denominator=int(provenance['multiple_testing_denominator']),provenance_url='assets/clinical-associations-provenance.json')
    return provenance
