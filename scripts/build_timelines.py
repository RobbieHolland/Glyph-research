"""Publish frozen paper timelines as SVG with local hover/click metadata.

Reads only aggregate published figure exports. Does not refit or load cohorts.
"""
import argparse
from copy import deepcopy
import hashlib
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)
ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
AXES=[('hfpef','04_abdominal_hfpef','Heart failure with preserved ejection fraction'),('sepsis','01_abdominal_sepsis','Sepsis')]
FIELDS=('kind','marker','label','or_sd','lo','hi','p','q','url','title','novelty','note')


def build(source_root,site_root):
    assets=site_root/'docs/assets/timelines';assets.mkdir(parents=True,exist_ok=True)
    sections=[];metadata={};sources={};counts={}
    rules_path=assets/'marker-rules.json'
    rules=json.loads(rules_path.read_text()) if rules_path.exists() else {}
    atlas=json.loads((site_root/'docs/assets/atlas-data.json').read_text())
    descriptions={node['name']:node for node in atlas['nodes']}
    for key,folder,outcome_title in AXES:
        title='Abdominal CT and laboratory risk markers for the onset of '+outcome_title[0].lower()+outcome_title[1:]
        source=source_root/folder
        figure=json.loads((source/'timeline.plotly.json').read_text())
        tree=ET.parse(source/'timeline.svg');svg=tree.getroot()
        groups=svg.findall(f'.//{{{NS}}}g[@class="scatterlayer mlayer"]/{{{NS}}}g')
        assert len(groups)==len(figure['data'])
        svg.set('class','timeline-figure');svg.set('role','group');svg.set('aria-label',title+' literature and Glyph timeline')
        svg.set('viewBox','0 70 2700 920');svg.attrib.pop('width',None);svg.attrib.pop('height',None)
        # The page provides a concise heading instead of the figure's long title.
        for parent in svg.iter():
            for child in list(parent):
                if child.get('class')=='g-gtitle':parent.remove(child)
        point_by_x=[];references={};npoints=0
        for i,(trace,group) in enumerate(zip(figure['data'],groups)):
            raw=trace.get('customdata',[])
            points=[p for p in group.iter(f'{{{NS}}}path') if 'point' in p.get('class','').split()]
            if not raw:continue
            assert len(points)==len(raw)
            for j,(point,serialized) in enumerate(zip(points,raw)):
                record=json.loads(serialized) if isinstance(serialized,str) else serialized
                data={k:record[k] for k in FIELDS if k in record}
                if data.get('kind')=='literature':
                    rule=rules.get(key,{}).get(data['marker'])
                    if not rule:raise ValueError(f"No verified rule for {key}/{data['marker']}; update marker-rules.json before publishing")
                    if rule['source_note']!=record.get('note'):raise ValueError(f"Rule provenance differs for {key}/{data['marker']}")
                    data['rule']=rule
                if data.get('kind')=='glyph':
                    node=descriptions.get(data.get('marker'))
                    if node and node.get('interpretation_source')=='Revised interpretation':
                        data['interpretation']=node['interpretation']
                        data['interpretation_source']=node['interpretation_source']
                if data.get('url'):assert re.match(r'^https://(?:pubmed\.ncbi\.nlm\.nih\.gov/\d+/?|doi\.org/)',data['url'])
                identity=f'{key}-{i}-{j}';metadata[identity]=data;npoints+=1
                # Transparent hit area shares the original marker transform.
                hit=ET.SubElement(group,f'{{{NS}}}circle',{'class':'timeline-hit','transform':point.get('transform'),'r':'22','fill':'transparent','data-timeline-point':identity,'tabindex':'0','role':'button','aria-label':data['label']})
                point_by_x.append((float(trace['x'][j]),identity,data))
                if data.get('url'):references[data['url']]=data['title']
        annotations=figure['layout'].get('annotations',[])
        for group in svg.findall(f'.//{{{NS}}}g[@class="annotation"]'):
            annotation=annotations[int(group.get('data-index'))]
            if not str(annotation.get('name','')).startswith('paper_'):continue
            candidates=[p for p in point_by_x if p[2].get('kind')=='literature']
            if not candidates:continue
            x,identity,data=min(candidates,key=lambda p:abs(p[0]-float(annotation['x'])))
            if abs(x-float(annotation['x']))>1e-5:continue
            group.set('data-timeline-point',identity);group.set('role','button');group.set('tabindex','0');group.set('aria-label',data['title'])
            group.set('class','annotation timeline-reference')
        # Namespacing IDs allows both unmodified figure layouts on one page.
        ids={el.get('id'):f'{key}-{el.get("id")}' for el in svg.iter() if el.get('id')}
        for el in svg.iter():
            for attr,value in list(el.attrib.items()):
                if attr=='id':el.set(attr,ids[value]);continue
                for old,new in ids.items():
                    value=value.replace('url(#'+old+')','url(#'+new+')')
                    if value=='#'+old:value='#'+new
                el.set(attr,value)
        rendered=ET.tostring(svg,encoding='unicode')
        for forbidden in ('/dataNAS/','/home/','patient_id','anon_accession'):assert forbidden not in rendered+json.dumps(metadata)
        (assets/(key+'.svg')).write_text(rendered)
        refs=''.join('<li><a href="'+html.escape(url,quote=True)+'" target="_blank" rel="noopener noreferrer">'+html.escape(name)+' <span aria-hidden="true">↗</span></a></li>' for url,name in references.items())
        heading=f'<span class="timeline-marker-scope">Abdominal CT and laboratory risk markers</span><span class="timeline-outcome">Onset of {html.escape(outcome_title[0].lower()+outcome_title[1:])}</span>'
        sections.append(f'<article class="timeline-example" id="timeline-{key}"><div class="timeline-example-heading"><h3>{heading}</h3><a href="assets/timelines/{key}.svg" target="_blank" rel="noopener">Open figure ↗</a></div><div class="timeline-scroll" tabindex="0" aria-label="Scrollable {html.escape(title)} timeline">{rendered}</div><details class="timeline-references"><summary>References ({len(references)})</summary><ol>{refs}</ol></details></article>')
        sources[key]={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('timeline.svg','timeline.plotly.json')}
        counts[key]=dict(points=npoints,references=len(references))
    (assets/'points.json').write_text(json.dumps(metadata,separators=(',',':'),ensure_ascii=False,allow_nan=False))
    (assets/'provenance.json').write_text(json.dumps(dict(method='Frozen paper SVGs; plotted estimates and annotation placement unchanged. Page headings replace figure titles. Hover metadata is restricted to aggregate estimates and bibliographic fields.',source_sha256=sources,counts=counts),indent=2))
    section='<!-- TIMELINES START -->\n<section id="timelines" class="timelines-section page-shell" aria-labelledby="timelines-title"><h2 id="timelines-title">Concepts complement clinical literature</h2><p class="timeline-intro">Clinically adjusted associations alongside prior studies. Hover for values; click a marker or reference for details.</p>'+''.join(sections)+'</section>\n<dialog id="timeline-detail" aria-labelledby="timeline-detail-title"><button id="timeline-close" type="button" aria-label="Close details">×</button><div id="timeline-detail-body"></div></dialog><div id="timeline-tooltip" role="tooltip" hidden></div><script type="application/json" id="timeline-points">'+json.dumps(metadata,separators=(',',':'),ensure_ascii=False).replace('</','<\\/')+'</script>\n<!-- TIMELINES END -->'
    page=site_root/'docs/index.html';content=page.read_text()
    if '<!-- TIMELINES START -->' in content:content=re.sub(r'<!-- TIMELINES START -->.*?<!-- TIMELINES END -->',lambda _:section,content,flags=re.S)
    else:
        start=content.index('    <section class="study-section');end=content.index('  </main>',start)
        content=content[:start]+section+'\n'+content[end:]
    if 'assets/timelines.js' not in content:content=content.replace('</head>','  <script src="assets/timelines.js" defer></script>\n</head>')
    page.write_text(content)
    print(json.dumps(counts))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-root',type=Path,required=True);parser.add_argument('--site-root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args();build(args.source_root,args.site_root)
