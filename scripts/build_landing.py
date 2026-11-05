"""Export an aggregate-only atlas using the verified paper layout, without refitting.

Maintainer tool: provide private aggregate model-results paths explicitly.
The generated site has no Python/backend dependencies or patient-level payloads.
"""
from paper_appearance import apply_paper_appearance
from build_regions import build_regions
from merge_clinical_associations import merge_clinical
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs/assets'
MODALITIES={'image':'CT imaging','findings':'Radiology reports','labs':'Laboratory values'}
COLORS={'CT imaging':'#0066CC','Radiology reports':'#FE9638','Laboratory values':'#4A9748','Clinical variables':'#999999'}
CLINICAL={'patient_age':'Age','patient_sex':'Sex','current_smoker':'Current smoking','heavy_alcohol_use':'Heavy alcohol use','recent_bmi':'Body mass index'}
GROUP_COLORS={'Cardiovascular':'#e34948','Neuro/cognitive':'#2a78d6','Renal/urinary':'#eb6834','Metabolic/nutritional':'#1baf7a','Hepatic/biliary':'#b5178e','Respiratory':'#00b3c8','Infection/sepsis':'#008300','Oncologic':'#4a3aa7','Haematologic':'#e87ba4','Musculoskeletal/trauma':'#eda100','Other':'#8a8a85'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def optional(value):
    if value is None or pd.isna(value):return None
    value=float(value)
    return value if math.isfinite(value) else None


def export(args):
    ASSETS.mkdir(parents=True,exist_ok=True)
    coords=pd.read_csv(args.coords,sep='\t',comment='#')
    graph=json.loads(args.graph.read_text())
    links=pd.read_pickle(args.links)
    # `feature` is the complete canonical key; `feature_id` is nullable AutoInterp join metadata.
    links['feature_id']=links['feature']
    groups=pd.read_csv(args.groups,dtype={'outcome':str})
    revisions=pd.read_csv(args.interpretations,dtype={'concept':str})
    if revisions.concept.duplicated().any():raise ValueError('Ambiguous revised interpretation mapping')
    revised=revisions.dropna(subset=['revised']).set_index('concept').revised.to_dict()
    if len(coords)!=347 or len(graph['nodes'])!=347:raise ValueError('Expected verified 347-node paper layout')
    if coords.node.duplicated().any():raise ValueError('Duplicate layout nodes')
    if groups.outcome.nunique()!=141 or len(groups)!=141:raise ValueError('Expected all 141 paper outcomes')
    if links[['feature_id','outcome']].duplicated().any():raise ValueError('Ambiguous aggregate association rows')
    if len(links)!=604185 or int(links.train_promising_association.sum())!=4463:
        raise ValueError('Association snapshot does not match paper v34 (604185 tests, 4463 Discovery hits)')
    source_features=links.loc[links.train_promising_association,'concept_short_id'].nunique()
    if source_features!=397:raise ValueError('Expected paper v34 high-risk concept count')
    if set(coords.node)!={n['id'] for n in graph['nodes']}:raise ValueError('Graph and coordinate membership differ')
    if not set(groups.outcome)==set(links.outcome.astype(str)):raise ValueError('Outcome list differs from the source snapshot')
    by_feature=links.drop_duplicates('feature_id').set_index('feature_id')
    by_node={n['id']:n for n in graph['nodes']}
    explained=set(pd.read_csv(args.coords.parent/'coords_n=283_umap_all.tsv',sep='\t',comment='#').node)
    outcomes=groups.outcome_display.tolist()
    outcome_index={o:i for i,o in enumerate(groups.outcome)}
    outcome_groups={g:s.outcome_display.tolist() for g,s in groups.groupby('disease_group',sort=False)}
    nodes=[];all_features=[];revised_used=[]
    smallest=min(n['size'] for n in graph['nodes']);largest=max(n['size'] for n in graph['nodes'])
    for index,row in enumerate(coords.itertuples(index=False)):
        key=row.node;source=by_node[key]
        clinical=key in CLINICAL
        match=by_feature.loc[key] if key in by_feature.index else None
        modality='Clinical variables' if clinical else MODALITIES[key.split('_')[0]]
        if clinical:
            name=CLINICAL[key];interpretation='Clinical context variable included in the original paper layout. Association estimates for this anchor are not included in this atlas.';accuracy=None
        else:
            if match is None:raise ValueError('Layout concept is missing from current aggregate results: '+key)
            name=str(match.concept_short_id).replace('/','')
            interpretation='' if pd.isna(match.extracted_interpretation) else re.sub(r'^This cohort is characterized by\s*','',str(match.extracted_interpretation),flags=re.I)
            if name in revised:
                interpretation=str(revised[name]);revised_used.append(name)
            if str(interpretation).strip().casefold() in {'nan','none','null','<na>'}:interpretation=''
            accuracy=optional(match.get('test_interpretation_discrimination_accuracy'))
            if accuracy is not None:accuracy*=100
            if name in revised or not interpretation:accuracy=None  # Scores do not validate revised or absent wording.
        area=150+1000*(source['size']-smallest)/(largest-smallest)
        nodes.append(dict(i=index,concept_id=key,feature_idx=int(key.split('_')[-1]) if not clinical else index,
            name=name,x=float(row.x_frac),y=float(row.y_frac),modality=modality,embedding_family='default',
            active=int(source['size']),rate=float(source['rate']),interpretation=interpretation,accuracy=accuracy,
            contexts={},undocumented=not clinical and key not in explained,
            interpretation_source='Revised interpretation' if name in revised else ('Clinical context' if clinical else 'AutoInterp candidate'),
            paper_radius=math.sqrt(area/math.pi)*1000/1296))
        if not clinical:all_features.append(key)
    node_index={n['concept_id']:n['i'] for n in nodes}
    edges=[[node_index[a],node_index[b],float(w)] for a,b,w in graph['edges']]
    associations={str(i):[] for i in range(len(nodes))}
    selected=links[links.feature_id.isin(all_features)]
    for r in selected.itertuples(index=False):
        odds=optional(r.train_isolated_odds_ratio)
        if odds is None or odds<=0:continue
        p=optional(r.train_isolated_odds_ratio_p_value)
        ci0=optional(r.train_isolated_odds_ratio_ci_lower);ci1=optional(r.train_isolated_odds_ratio_ci_upper)
        associations[str(node_index[r.feature_id])].append([outcome_index[str(r.outcome)],odds,p,ci0,ci1,
            min(1.,p*len(links)) if p is not None else None,
            bool(p is not None and p<=.05/len(links)),optional(r.train_c_f)])
    payload=dict(title='Stanford abdominal CT concept atlas',view='simple',wheel_label_limit=20,
        modality='multiple modalities',top_k='40',split='Discovery',initial_outcome=None,
        outcomes=outcomes,modalities=list(COLORS),embedding_families=['default'],bonferroni_alpha=.05,
        bonferroni_threshold=.05/len(links),selection_note='Original seed-1283 paper layout',
        nodes=nodes,edges=edges,associations=associations,technical_details=None,agentic_analysis=None,
        analysis_report_url=None,contexts=[],context_min_activations=20,
        node_sizing=dict(full_prevalence_area=math.pi*14**2,minimum_area=math.pi*.35**2),
        outcome_groups=outcome_groups,outcome_colors={row.outcome_display:GROUP_COLORS.get(row.disease_group,'#8a8a85') for row in groups.itertuples()},
        modality_colors=COLORS,image_bank={},concept_images={},image_example_info={},
        association_columns=['outcome_index','odds_ratio','p_value','ci_lower','ci_upper','corrected_p_value','significant','count'])
    paper_svg=args.paper_svg or args.coords.parent/"network_no_labels_n=347_umap_all_with_clinical_vars.svg"
    apply_paper_appearance(payload,paper_svg)
    payload["regions"]=build_regions(payload["nodes"])
    (ASSETS/"concept-regions.json").write_text(json.dumps(dict(method="Rounded convex envelopes of curated semantic anchors; approximate visual neighborhoods, not a partition.",regions=payload["regions"]),indent=2))
    if args.clinical_associations:
        merge_clinical(payload,args.clinical_associations)
    packed=json.dumps(payload,separators=(',',':'),ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    template=(ROOT/'vendor/glyph-explorer.html').read_text()
    expression='''const DATA=__GLYPH_DATA__,NS='http://www.w3.org/2000/svg',S=1000,BASE_NODE_OPACITY=.7;'''
    expanded='''const DATA=__GLYPH_DATA__;
Object.keys(DATA.associations).forEach(k=>DATA.associations[k]=DATA.associations[k].map(a=>({outcome:DATA.outcomes[a[0]],odds_ratio:a[1],p_value:a[2],ci_lower:a[3],ci_upper:a[4],corrected_p_value:a[5],significant:a[6],count:a[7],modality_corrected_p_value:null})));
const NS='http://www.w3.org/2000/svg',S=1000,BASE_NODE_OPACITY=1;'''
    if expression not in template:raise ValueError('Glyph template changed; review the adapter')
    template=template.replace(expression,expanded)
    template=template.replace("let colorMode='outcome';","let colorMode='modality';")
    template=template.replace("const modalityColor=m=>MODALITY_PALETTE[(DATA.modalities||[]).indexOf(m)%MODALITY_PALETTE.length];", "const modalityColor=m=>DATA.modality_colors[m]||'#999999';")
    template=template.replace('const radius=n=>Math.sqrt(', 'const radius=n=>n.paper_radius??Math.sqrt(')
    template=template.replace("let associationDirection='both',extremeOnly=!isSimple,extremeThresholds={};", "let associationDirection='risk',extremeOnly=false,extremeThresholds={};")
    template=template.replace('const items=A[n.i]||[];\n if(DATA.progressive', 'const items=(A[n.i]||[]).filter(a=>a.odds_ratio>1);\n if(DATA.progressive')
    template=template.replace('data-association="${i}" data-outcome=', 'data-association="${(A[n.i]||[]).indexOf(a)}" data-outcome=')
    template=template.replace('Hover for values; lower-odds estimates are available on hover and in the table.', 'Hover for values. Only higher-risk estimates (OR > 1) are shown.')

    template=template.replace("n.interpretation||'No interpretation available.'", "n.interpretation||''")
    template=template.replace("function showTip(e,n){tip.textContent=n.interpretation||'No interpretation available';moveTip(e)}", "function showTip(e,n){tip.textContent=n.interpretation||'';if(!tip.textContent){tip.style.opacity=0;return}moveTip(e)}")
    template=template.replace('selected.clear();selected.add(DATA.initial_outcome);','selected.clear();')
    template=template.replace('${DATA.nodes.length.toLocaleString()} concepts · ${hits.toLocaleString()}', '${DATA.nodes.length.toLocaleString()} nodes · ${hits.toLocaleString()}')
    template=template.replace("if(isSimple)return;activeRankSort=sortOutcome;", "if(isSimple)return;activeRankSort=sortOutcome;")
    style=(ROOT/'scripts/atlas-theme.css').read_text()
    adapter=(ROOT/'scripts/atlas-adapter.js').read_text()
    html=template.replace('__GLYPH_DATA__',packed)
    html=html.replace('</head>','<style>'+style+'</style></head>')
    html=html.replace('</body>','<script>'+adapter+'</script></body>')
    html='<!-- Interactive renderer adapted from Glyph. MIT license: assets/glyph-renderer-license.txt -->\n'+html
    (ROOT/'docs/atlas.html').write_text(html)
    (ASSETS/'glyph-renderer-license.txt').write_text((ROOT/'vendor/GLYPH_LICENSE').read_text())
    (ASSETS/'atlas-data.json').write_text(json.dumps(payload,separators=(',',':'),ensure_ascii=False,allow_nan=False))
    layout=dict(seed=1283,nodes=[dict(id=n['concept_id'],x=n['x'],y=n['y']) for n in nodes],edges=graph['edges'])
    (ASSETS/'paper-layout.json').write_text(json.dumps(layout,separators=(',',':')))
    provenance=dict(paper_version=34,study=dict(tested_associations=len(links),discovery_associations=4463,
        high_risk_concepts=397,outcomes=141),atlas=dict(nodes=len(nodes),concepts=len(all_features),clinical_anchors=5,
        edges=len(edges),association_estimates=sum(map(len,associations.values())),seed=1283,
        coordinates='Unmodified x_frac/y_frac from the verified paper coordinate export; no fitting, jitter or force layout.',
        node_sizes='Exact radii, colors, opacity, outlines and edge widths extracted from the verified 1296-point paper SVG.',
        site='Discovery',model='Unadjusted per-standard-deviation odds ratios',multiple_testing_denominator=len(links)),
        source_sha256={name:sha(path) for name,path in [('layout_coordinates',args.coords),('layout_graph',args.graph),
            ('association_snapshot',args.links),('outcome_groups',args.groups),('revised_interpretations',args.interpretations),('glyph_renderer',ROOT/'vendor/glyph-explorer.html')]},
        revised_interpretations=dict(applied=len(revised_used),concepts=revised_used,precedence='Curated revised text overrides the original AutoInterp description; concept IDs/statistics/positions are unchanged.'),
        payload='Aggregate concept positions, coactivation display edges, interpretations and association estimates only; no patient records or images.',
        exclusions='Clinical anchor associations are unavailable. No Mayo laboratory or diagnostic-phecode estimates are displayed.')
    provenance['source_sha256']['paper_svg']=sha(paper_svg)
    if args.paper:provenance['source_sha256']['paper_v34']=sha(args.paper)
    (ASSETS/'atlas-provenance.json').write_text(json.dumps(provenance,indent=2))
    print(json.dumps(provenance['atlas'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('coords','graph','links','groups','interpretations'):p.add_argument('--'+key,required=True,type=Path)
    p.add_argument('--clinical-associations',type=Path);p.add_argument('--paper-svg',type=Path);p.add_argument('--paper',type=Path);export(p.parse_args())
