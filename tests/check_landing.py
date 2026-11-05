"""Browser and data-contract verification for the published static site.

Run with playwright installed and its Chromium browser available.
No private cohort files or external services are needed.
"""
import csv
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
ARTIFACTS=ROOT/'test-artifacts'


def check():
    ARTIFACTS.mkdir(exist_ok=True)
    payload=json.loads((DOCS/'assets/atlas-data.json').read_text())
    layout=json.loads((DOCS/'assets/paper-layout.json').read_text())
    provenance=json.loads((DOCS/'assets/atlas-provenance.json').read_text())
    assert len(payload['nodes'])==347 and len(payload['outcomes'])==141 and len(payload['edges'])==659
    assert len({n['concept_id'] for n in payload['nodes']})==347
    assert sum(n['modality']=='Clinical variables' for n in payload['nodes'])==5
    by_id={n['concept_id']:n for n in payload['nodes']}
    for node in layout['nodes']:
        assert by_id[node['id']]['x']==node['x'] and by_id[node['id']]['y']==node['y']
    for concept in provenance['revised_interpretations']['concepts']:
        node=next(n for n in payload['nodes'] if n['name']==concept)
        assert node['interpretation_source']=='Revised interpretation' and node['accuracy'] is None
    for forbidden in ('anon_accession','patient_id','sample_id','nifti_path','/dataNAS/','/home/'):
        assert forbidden not in json.dumps(payload),forbidden
    handler=partial(SimpleHTTPRequestHandler,directory=str(DOCS))
    class QuietHandler(handler.func):
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(DOCS)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/'
    errors=[];external=[];checks=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            context=browser.new_context(viewport={'width':1512,'height':1080},device_scale_factor=1,accept_downloads=True)
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda req:external.append(req.url) if not req.url.startswith((url,'data:','blob:')) else None)
            page.goto(url);page.locator('#atlas-loading').wait_for(state='hidden')
            frame=page.locator('#concept-atlas').element_handle().content_frame()
            assert frame.locator('.hit').count()==347
            assert frame.evaluate("DATA.nodes.find(n=>n.name==='I87').interpretation")=="Hepatobiliary pattern correlated with a surgically absent gallbladder."
            assert frame.evaluate("DATA.nodes.find(n=>n.name==='I87').accuracy") is None
            frame.wait_for_function('!DATA.progressive_associations || DATA.associations_ready')
            frame.wait_for_function("selected.size===1 && selected.has('Sepsis (994.2)') && DATA.guided_mode")
            assert page.evaluate('scrollY')==0
            assert frame.locator('#mapMeta').inner_text()==''
            # Exercise the broad opening, single-disease transition and each zoom.
            assert page.locator('#active-disease').inner_text()=='Sepsis'
            page.locator('.story-step[aria-label="Heart failure (HFpEF)"]').scroll_into_view_if_needed()
            frame.wait_for_function("selected.size===1 && selected.has('Heart Failure With Preserved Ef [Diastolic Heart Failure] (428.4)') && !selectedNode && DATA.guided_mode")
            page.locator('.story-step[data-outcome="Cancer Liver Primary"]:not([data-concept])').scroll_into_view_if_needed()
            frame.wait_for_function("selected.size===1 && selected.has('Cancer Liver Primary') && !selectedNode && DATA.guided_mode")
            page.locator('.story-step[data-concept="L108"]').scroll_into_view_if_needed()
            frame.wait_for_function("selectedNode?.name==='L108' && DATA.guided_mode")
            assert frame.locator('#storyContextMarkers [data-related-concept]').count()==2
            assert page.locator('.story-step[data-concept="L108"] .story-prompt-text').inner_text()=='What are risk markers of primary liver cancer?'
            assert page.locator('.story-step[data-concept="L108"] .story-marker').count()==3
            page.locator('.story-step[aria-label="Heart failure"]:not([data-concept])').evaluate("el=>window.scrollTo({top:scrollY+el.getBoundingClientRect().top+el.offsetHeight/2-innerHeight/2,behavior:'instant'})")
            frame.wait_for_function("!selectedNode && selected.has('Heart Failure With Preserved Ef [Diastolic Heart Failure] (428.4)') && DATA.guided_mode")
            frame.wait_for_function("Math.abs(scale-1)<.001 && scrollCameraFrame===null")
            page.locator('.story-step[data-concept="L84"]').scroll_into_view_if_needed()
            frame.wait_for_function("selectedNode?.name==='L84' && selected.has('Heart Failure With Preserved Ef [Diastolic Heart Failure] (428.4)') && DATA.guided_mode")
            assert frame.locator('#storyContextMarkers [data-related-concept="L62"]').count()==1
            assert frame.locator('#storyContextMarkers [data-related-concept="L87"]').count()==1
            assert page.locator('.story-step[data-concept="L84"] .story-marker').count()==3
            page.locator('.story-step[data-concept="I26"]').scroll_into_view_if_needed()
            frame.wait_for_function("selectedNode?.name==='I26' && selected.has('Heart Failure With Preserved Ef [Diastolic Heart Failure] (428.4)') && DATA.guided_mode")
            assert page.locator('.story-step[data-concept="I26"] .story-prompt-text').inner_text()=='What are risk markers of heart failure?'
            assert page.locator('.story-step[data-concept="I26"] .story-marker').count()==4
            assert frame.locator('#storyContextMarkers [data-related-concept]').count()==3
            assert ' '.join(page.locator('.scroll-cue').inner_text().split())=='Scroll to explore ↓'
            assert frame.locator('.assoc tbody tr:visible').count()==3
            expected_rows=frame.locator('.assoc tbody tr').count()
            frame.get_by_role('button',name='I26',exact=True).click()
            page.wait_for_function('!guidedEnabled')
            frame.locator('#association-more').click()
            assert frame.locator('.assoc tbody tr:visible').count()==expected_rows
            frame.locator('#association-more').click()
            assert frame.locator('.assoc tbody tr:visible').count()==3
            page.reload();page.locator('#atlas-loading').wait_for(state='hidden')
            frame=page.locator('#concept-atlas').element_handle().content_frame()
            frame.wait_for_function("selected.size===1 && selected.has('Sepsis (994.2)') && DATA.guided_mode")
            assert page.evaluate('scrollY')==0
            page.locator('#show-liver-cancer').click()
            frame.wait_for_function("selected.has('Cancer Liver Primary') && !DATA.guided_mode")
            assert page.locator('#manual-disease').inner_text()=='Primary liver cancer'
            page.locator('#show-all-outcomes').click()
            frame.locator('#outcomePicker[open]>.outcomes').wait_for()
            page.locator('#choose-diseases').click()
            for selector,outcome in [('#show-cardiac','Heart Failure With Preserved Ef [Diastolic Heart Failure] (428.4)'),('#show-renal','Chronic Kidney Disease, Stage Iii (585.33)')]:
                scroll_before=page.evaluate('scrollY')
                page.locator(selector).click()
                frame.wait_for_function('(outcome)=>selected.size===1 && selected.has(outcome)',arg=outcome)
                assert abs(page.evaluate('scrollY')-scroll_before)<2
            checks.append('Top liver/cardiac/renal shortcuts and adjacent all-outcomes picker')
            page.locator('#atlas-reset').click()
            frame.wait_for_function('!selectedNode && scale===1 && tx===0 && ty===0 && selected.size===0')
            checks.append('Broad heart-failure/sepsis opening, single liver-cancer focus, guided L108 neighborhood, pullback to HFpEF overview, renal/L84, cardiovascular/I26, manual takeover and reload-to-top')
            assert frame.locator('#mapStatus').inner_text()==''
            assert frame.locator('#outcomeChoices input').count()==141
            assert len(frame.locator('#outcomeChoices input:checked').all())==0
            before=frame.evaluate('() => DATA.nodes.map(n=>[n.concept_id,n.x,n.y])')
            checks.append('347 nodes, 141 outcomes, original positions')
            assert frame.locator('.concept-region').count()==14
            assert frame.locator('.concept-region-label').count()==14
            assert frame.locator('#patientAgeAnnotation .clinical-node-annotation').text_content()=='Patient age'
            assert frame.locator('#smokingAnnotation .clinical-node-annotation').text_content()=='Smoking'
            assert frame.locator('.concept-region-label').evaluate_all("els=>els.every(el=>getComputedStyle(el).stroke==='none')")
            assert frame.locator('#conceptRegions').is_visible()
            if page.locator('#explore-tools').get_attribute('open') is None:
                page.locator('#explore-tools>summary').click()
            page.locator('#toggle-regions').click()
            frame.locator('#conceptRegions').wait_for(state='hidden')
            if page.locator('#explore-tools').get_attribute('open') is None:
                page.locator('#explore-tools>summary').click()
            page.locator('#toggle-regions').click()
            frame.locator('#conceptRegions').wait_for(state='visible')
            assert frame.evaluate('() => DATA.nodes.map(n=>[n.concept_id,n.x,n.y])')==before
            assert page.locator('.research-word').count()==0
            assert page.locator('.hero-description').count()==0
            assert page.locator('.hero-tagline').inner_text()=='Exploring clinical concepts in multimodal data.'
            checks.append('Fourteen rounded neighborhoods toggle without moving nodes; permanent Patient age annotation')
            page.locator('#atlas-search').fill('azotemia')
            azotemia=page.locator('#atlas-search-results button').filter(has_text='L84')
            azotemia.wait_for(state='visible')
            azotemia.click()
            frame.locator('#detail').filter(has_text='Azotemia').wait_for()
            frame.locator('#clearSelection').click()
            assert frame.locator('#side').is_visible()
            frame.wait_for_function("DATA.nodes.every(n=>getComputedStyle(n.el).opacity==='1')")
            checks.append('Azotemia search has a visible L84 result; disease selections start empty')
            for query,name in [('age','Age'),('sex','Sex'),('smoker','Current smoking'),('alcohol','Heavy alcohol use'),('bmi','Body mass index')]:
                page.locator('#atlas-search').fill(query)
                page.wait_for_function("name=>document.querySelector('#atlas-search-results button')?.textContent.startsWith(name+' · ')",arg=name)
                page.locator('#atlas-search-results button').first.click()
                frame.wait_for_function('(name)=>selectedNode?.name===name',arg=name)
                assert frame.locator('.wheel').count()==1
            page.locator('#atlas-reset').click()
            frame.wait_for_function('!selectedNode && selected.size===0')
            checks.append('Clinical variable names and aliases rank first and open their association wheels')
            assert payload['clinical_associations']['estimated']==705
            for key in ('patient_age','patient_sex','current_smoker','heavy_alcohol_use','recent_bmi'):
                frame.evaluate('(key)=>show(DATA.nodes.find(n=>n.concept_id===key))',key)
                assert frame.locator('.wheel-spoke').count()==frame.evaluate('(A[selectedNode.i]||[]).filter(a=>a.odds_ratio>1).length')
                assert frame.locator('.wheel').get_attribute('data-scale')=='sqrt-or-minus-one'
            frame.locator('#clearSelection').click()
            frame.wait_for_function("DATA.nodes.every(n=>getComputedStyle(n.el).opacity==='1')")
            checks.append('All five clinical variables show higher-risk wheels; all 141 estimates retained')
            assert frame.evaluate("() => DATA.nodes.every(n => Math.abs(+n.el.firstElementChild.getAttribute('r')-n.paper_style.radius)<1e-8 && Math.abs(+n.el.firstElementChild.getAttribute('fill-opacity')-n.paper_style.fill_opacity)<1e-8 && getComputedStyle(n.el).opacity==='1')")
            assert frame.evaluate("() => [...edgeLayer.children].every(el => Math.abs(+el.getAttribute('stroke-opacity')-.38)<1e-8 && +el.getAttribute('stroke-width')>=.65 && getComputedStyle(el).vectorEffect==='non-scaling-stroke')")
            checks.append('Paper SVG node styling and screen-readable weighted edges')
            assert page.locator('.study-numbers').count()==0
            assert page.locator('.atlas-card').evaluate("el => getComputedStyle(el).borderTopWidth")=='0px'
            frame.evaluate("() => showTip({clientX:200,clientY:200}, DATA.nodes[0])")
            expected=frame.evaluate("() => DATA.nodes[0].interpretation || 'No interpretation available'")
            assert frame.locator('#tip').inner_text()==expected
            frame.evaluate("() => tip.style.opacity=0")
            checks.append('No hero counters or graph frame; concept hover shows interpretation only')
            page.screenshot(path=str(ARTIFACTS/'desktop-first.png'))
            page.locator('#atlas').scroll_into_view_if_needed()
            page.screenshot(path=str(ARTIFACTS/'desktop-atlas.png'))
            if page.locator('#explore-tools').get_attribute('open') is None:
                page.locator('#explore-tools>summary').click()
            page.locator('#mode-outcome').click()
            frame.wait_for_function("colorMode==='outcome' && selected.size===0")
            page.locator('#choose-diseases').click()
            frame.locator('#outcomePicker[open]>.outcomes').wait_for()
            assert frame.locator('#outcomePicker').get_attribute('open') is not None
            assert frame.locator('.outcome-group').count()==11
            assert frame.locator('.outcome-group[open]').count()==0
            first_group=frame.locator('.outcome-group').first
            first_group.locator('summary').click()
            assert first_group.get_attribute('open') is not None
            first_group.locator('summary').press('Enter')
            assert first_group.get_attribute('open') is None
            frame.locator('#clearOutcomes').click()
            target=frame.evaluate('() => DATA.outcomes.find(x=>x.toLowerCase().includes("septicemia")) || DATA.outcomes[0]')
            frame.locator('#outcomeSearch').fill(target.split('(')[0].strip())
            assert frame.locator('.outcome-group[open]').count()>0
            frame.get_by_label(target,exact=True).check()
            assert frame.locator('#outcomeChoices input:checked').count()==1
            frame.wait_for_function('selected.size===1')
            page.locator('#choose-diseases').click()
            checks.append('Collapsible outcome groups, keyboard toggling, group counts and automatic search expansion')
            checks.append('Parent color toggle, searchable disease picker, individual outcome selection')
            shade_check=frame.evaluate("""() => {
              const outcome=[...selected][0];
              const maximum=associationStrengthLimit(outcome);
              const values=[0,1/3,2/3,1].map(t=>associationStrengthColor({outcome,odds_ratio:Math.exp(maximum*t)}));
              const luminance=c=>[1,3,5].map(i=>parseInt(c.slice(i,i+2),16)).reduce((a,b)=>a+b,0);
              return values[0]==='#ffffff' && values.every((c,i)=>!i || luminance(c)<luminance(values[i-1]))
                && associationStrengthColor({outcome,odds_ratio:Math.exp(-maximum*2/3)})===values[2]
                && DATA.nodes.every(n=>{const hits=selectedHits(n);return hits.length!==1 || hits[0].odds_ratio<1 || n.el.firstElementChild.getAttribute('fill')===associationStrengthColor(hits[0]);});
            }""")
            assert shade_check
            assert frame.evaluate("""() => DATA.outcomes.every(outcome => {
              const eligible=DATA.nodes.flatMap(n => (A[n.i]||[]).filter(a=>a.outcome===outcome && associationPasses(a,n)));
              const expected=eligible.reduce((m,a)=>Math.max(m,Math.abs(Math.log(a.odds_ratio))),0);
              return Math.abs(associationStrengthLimit(outcome)-expected)<1e-10;
            })""")
            assert frame.locator('.strength-key').is_visible()
            page.screenshot(path=str(ARTIFACTS/'disease-strength.png'))
            checks.append('Per-outcome |log OR| scales match all 141 outcome maxima; visible numeric key')
            page.locator('#atlas-search').fill('I109')
            frame.get_by_role('button',name='I109',exact=True).focus()
            frame.get_by_role('button',name='I109',exact=True).press('Enter')
            frame.locator('#detail').filter(has_text='Abdominal aortic calcification').wait_for()
            assert frame.locator('.interpretation-note').inner_text()=='Revised interpretation'
            assert frame.locator('.concept-heading .concept-code').inner_text()=='I109'
            assert frame.locator('.concept-heading .concept-interpretation').inner_text()=='Abdominal aortic calcification'
            assert frame.locator('.concept-code').evaluate('el=>getComputedStyle(el).color')=='rgb(70, 130, 180)'
            checks.append('Concept interpretation sits beside its modality-colored code')
            page.wait_for_url('**/*concept=I109*')
            spokes=frame.locator('.wheel-spoke').count()
            expected=frame.evaluate('() => DATA.associations[String(DATA.nodes.find(n=>n.name==="I109").i)].length')
            assert spokes==frame.evaluate('(A[selectedNode.i]||[]).filter(a=>a.odds_ratio>1).length')
            assert frame.locator('.wheel').get_attribute('data-scale')=='sqrt-or-minus-one'
            assert frame.locator('.wheel-window').inner_text().startswith('First recorded onset 1–4 years after the CT scan. ')
            assert frame.locator('.wheel-count,.concept-modality').count()==0
            assert frame.locator('table.assoc').evaluate("el=>el.previousElementSibling.textContent")=='Top outcomes by odds ratio, with Bonferroni-adjusted p-values.'
            assert frame.get_by_role('heading',name='Association wheel',exact=True).count()==1
            assert frame.locator('.wheel-family-label').count()==11
            assert frame.evaluate("""() => {
              const effects=[...document.querySelectorAll('.wheel-effect')];
              return effects.length>0 && effects.every(el=>{
                const or=+el.dataset.or, start=+el.dataset.startRadius, end=+el.dataset.endRadius;
                const top=Math.max(...A[selectedNode.i].map(a=>a.odds_ratio));
                return or>1 && Math.abs((end-start)/Math.sqrt(or-1)-162/(1.34*Math.sqrt(top-1)))<1e-6;
              });
            }""")
            assert not frame.locator('input[name=associationDirection][value=protective]').is_visible()
            assert frame.evaluate("[...document.querySelectorAll('.wheel-spoke')].every(el=>A[selectedNode.i][+el.dataset.association].odds_ratio>1)")
            assert not frame.locator('#search').is_visible()
            assert page.locator('#atlas-search').is_visible()
            frame.locator('.wheel').screenshot(path=str(ARTIFACTS/'I109-paper-wheel.png'))
            spoke=frame.locator('.wheel-spoke').first
            spoke.focus()
            assert frame.locator('#tip').inner_text().find('Odds ratio')>=0
            spoke.press('Enter')
            assert frame.locator('#outcomeChoices input:checked').count()==1
            checks.append('Paper-style family wheel: square-root risk geometry, concept center, interactive spokes')
            with page.expect_download() as download:
                frame.locator('#exportConcept').click()
            path=ARTIFACTS/'I109.csv';download.value.save_as(path)
            with path.open() as f:rows=list(csv.DictReader(f))
            assert len(rows)==expected
            checks.append('Revised I109 text, full outcome wheel, precise CSV export, shareable concept URL')
            camera=frame.locator('#camera').get_attribute('transform')
            frame.locator('#zoomIn').click()
            assert frame.locator('#camera').get_attribute('transform')!=camera
            assert frame.evaluate('() => DATA.nodes.map(n=>[n.concept_id,n.x,n.y])')==before

            page.locator('#atlas-reset').click()
            frame.wait_for_function('!selectedNode && scale===1 && tx===0 && ty===0 && selected.size===0')
            page.wait_for_function("document.querySelector('#mode-modality').getAttribute('aria-pressed')==='true' && document.querySelector('.count-chip').textContent==='0/141' && !location.search.includes('concept=')")
            assert frame.locator('#outcomeChoices input:checked').count()==0
            assert frame.locator('#search').input_value()==''
            assert frame.locator('#detail').inner_text()==''
            assert frame.evaluate("() => scale===1 && tx===0 && ty===0 && associationDirection==='risk' && !onlySignificant && !extremeOnly && regionsVisible")
            assert frame.locator('#camera').get_attribute('transform')!=camera or frame.evaluate('scale===1')
            assert frame.evaluate('() => DATA.nodes.map(n=>[n.concept_id,n.x,n.y])')==before
            checks.append('Reset view clears diseases, selected concept and search; restores initial colors, zoom and filters')
            page.evaluate('finishStory()')
            frame.wait_for_function('!DATA.story_wheel_locked && !DATA.guided_mode')
            assert frame.evaluate("""async () => {
              let renders=0;const observer=new MutationObserver(records=>renders+=records.length);
              observer.observe(camera,{attributes:true,attributeFilter:['transform']});
              const r=svg.getBoundingClientRect();
              for(let i=0;i<50;i++)svg.dispatchEvent(new WheelEvent('wheel',{clientX:r.left+r.width/2,clientY:r.top+r.height/2,deltaY:-.2,bubbles:true,cancelable:true}));
              await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
              observer.disconnect();return renders===1 && Math.abs(scale-Math.exp(.02))<1e-8;
            }""")
            page.locator('#atlas-reset').click()
            frame.wait_for_function('!selectedNode && scale===1 && tx===0 && ty===0 && selected.size===0')
            checks.append('Trackpad deltas are proportional and a burst of wheel events produces one camera update per frame')
            if page.locator('#explore-tools').get_attribute('open') is None:
                page.locator('#explore-tools>summary').click()
            page.locator('#mode-modality').click()
            assert page.locator('#mode-modality').get_attribute('aria-pressed')=='true'
            page.locator('#atlas-search').fill('No concept has this exact name')
            frame.locator('#emptyState').wait_for(state='visible')
            page.locator('#atlas-search').fill('')
            page.keyboard.press('Escape')
            page.wait_for_function('!location.search.includes("concept=")')
            checks.append('Zoom without coordinate changes, empty-state search, keyboard reset')

            assert page.locator('.study-section').count()==0
            assert page.locator('.timeline-example').count()==2
            assert page.locator('.timeline-hit').count()==67
            assert page.locator('.timeline-references a').count()==24
            first=page.locator('#timeline-hfpef .timeline-hit').first
            first.hover()
            assert page.locator('#timeline-tooltip').is_visible()
            assert 'Adjusted OR' in page.locator('#timeline-tooltip').inner_text()
            first.click()
            assert page.locator('#timeline-detail').is_visible()
            assert page.locator('.timeline-paper-link').get_attribute('href')=='https://pubmed.ncbi.nlm.nih.gov/21670229/'
            assert page.locator('.timeline-paper-link svg[aria-hidden="true"]').count()==1
            assert 'Read paper' in page.locator('.timeline-paper-link').inner_text()
            assert 'Continuous inverse serum albumin' in page.locator('.timeline-rule-summary').inner_text()
            page.locator('.timeline-rule summary').click()
            assert 'albumin_lower = -c.albumin' in page.locator('.timeline-rule pre').inner_text()
            page.keyboard.press('Escape')
            reference=page.locator('#timeline-hfpef .timeline-reference').first
            reference.focus();reference.press('Enter')
            assert page.locator('#timeline-detail').is_visible()
            page.locator('#timeline-close').click()
            page.locator('#timeline-hfpef').screenshot(path=str(ARTIFACTS/'hfpef-timeline.png'))
            glyph_id=page.evaluate("Object.keys(timelinePoints).find(k=>k.startsWith('hfpef-') && timelinePoints[k].kind==='glyph')")
            glyph_target=page.locator(f'#timeline-hfpef .timeline-hit[data-timeline-point="{glyph_id}"]')
            glyph_target.click()
            concept=page.evaluate('(id)=>timelinePoints[id].marker',glyph_id)
            page.locator('.timeline-concept-link').click()
            frame.wait_for_function('(name)=>selectedNode?.name===name',arg=concept)
            assert frame.locator('#selectedConceptMarker').get_attribute('data-concept')==concept
            assert frame.evaluate('scale===2.2')
            assert frame.evaluate('Math.abs(selectedNode.x*S*scale+tx-S/2)<1e-8 && Math.abs(selectedNode.y*S*scale+ty-S/2)<1e-8')
            page.locator('#atlas-reset').click()
            frame.wait_for_function('!selectedNode && scale===1 && tx===0 && ty===0 && selected.size===0')
            assert not frame.locator('#selectedConceptMarker').is_visible()
            checks.append('Timeline jump centers and zooms to the concept, shows ID and selection ring; reset clears highlight')
            about=context.new_page();about.on('pageerror',lambda error:errors.append(str(error)))
            about.goto(url+'about.html')
            assert about.locator('.study-section').count()==1
            assert about.locator('h1').inner_text()=='About Glyph'
            about.close()
            checks.append('Two paper timelines, 67 interactive markers, 24 paper links, keyboard details and About page')
            assert page.locator('.timeline-adjustment-note').count()==2
            assert page.locator('.timeline-intro').evaluate('el=>parseFloat(getComputedStyle(el).fontSize)')>=17
            for axis in page.locator('.timeline-figure .ytitle').all():assert axis.text_content()=='Odds Ratio*'
            checks.append('Concise odds-ratio axes, accurate age/sex/race footnotes and readable timeline introduction')
            inspection=context.new_page();inspection.on('pageerror',lambda error:errors.append(str(error)))
            inspection.goto(url);inspection.locator('#atlas-loading').wait_for(state='hidden')
            inf=inspection.locator('#concept-atlas').element_handle().content_frame();inf.wait_for_function('DATA.associations_ready')
            inspection.evaluate("()=>{const s=storySteps[3],r=s.getBoundingClientRect();scrollTo({top:scrollY+r.top+r.height/2-innerHeight/2-200,behavior:'instant'})}")
            inspection.wait_for_function('activeStory===3');inf.wait_for_function("selectedNode?.name==='L108' && scrollCameraFrame===null")
            inf.get_by_role('button',name='I87',exact=True).click()
            inspection.wait_for_function('!guidedEnabled');inf.wait_for_function("selectedNode?.name==='I87' && DATA.story_wheel_locked")
            old_y=inspection.evaluate('scrollY');old_scale=inf.evaluate('scale');bounds=inf.locator('#graph').bounding_box()
            inspection.mouse.move(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2);inspection.mouse.wheel(0,100)
            inspection.wait_for_function('guidedEnabled');inspection.wait_for_function('y=>Math.abs(scrollY-y-100)<2',arg=old_y)
            inf.wait_for_function("DATA.guided_mode && selectedNode?.name==='L108'")
            assert inf.evaluate('scale')>=old_scale-.001
            # Closing details and changing zoom must not detach the unfinished tour.
            inf.locator('#clearSelection').click()
            inf.locator('#zoomIn').click()
            inspection.wait_for_function('!guidedEnabled')
            bounds=inf.locator('#graph').bounding_box()
            inspection.mouse.move(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
            inspection.mouse.wheel(0,-100)
            inspection.wait_for_function('guidedEnabled')
            inf.wait_for_function('DATA.guided_mode && DATA.story_wheel_locked')
            inf.locator('#zoomOut').click()
            inspection.wait_for_function('!guidedEnabled')
            inf.locator('#zoomOut').press('PageDown')
            inspection.wait_for_function('guidedEnabled')
            assert inspection.locator('#concept-atlas').evaluate('el=>el.nextElementSibling.classList.contains("network-controls")')
            assert inf.locator('.legend').evaluate('el=>el.getBoundingClientRect().top')<=5
            inspection.close()
            checks.append('Node inspection, closing details and zoom controls preserve story resumption by wheel and keyboard')

            revisit=context.new_page();revisit.on('pageerror',lambda error:errors.append(str(error)))
            revisit.goto(url);revisit.locator('#atlas-loading').wait_for(state='hidden')
            rf=revisit.locator('#concept-atlas').element_handle().content_frame()
            rf.wait_for_function('DATA.associations_ready')
            long_height=revisit.evaluate('document.documentElement.scrollHeight')
            hold_center=revisit.evaluate("() => {const s=storySteps[3],r=s.getBoundingClientRect();return scrollY+r.top+r.height/2-innerHeight/2}")
            revisit.evaluate("y=>scrollTo({top:y,behavior:'instant'})",hold_center-350)
            revisit.wait_for_function('activeStory===3')
            rf.wait_for_function("selectedNode?.name==='L108'")
            revisit.wait_for_timeout(150)
            held_copy=revisit.locator('.story-step[data-concept="L108"] .story-step-copy')
            first_box=held_copy.bounding_box();first_center=first_box['y']+first_box['height']/2
            revisit.evaluate("y=>scrollTo({top:y,behavior:'instant'})",hold_center+350)
            revisit.wait_for_timeout(150)
            last_box=held_copy.bounding_box()
            assert abs(last_box['y']+last_box['height']/2-first_center+210)<2
            assert abs(first_center-645)<2
            checks.append('700 pixels of scroll move centered story text by 210 pixels: a longer continuous slow passage')

            revisit.evaluate("() => {const s=storySteps[6];scrollTo({top:scrollY+s.getBoundingClientRect().top+s.offsetHeight/2-innerHeight/2,behavior:'instant'})}")
            revisit.wait_for_function('activeStory===6')
            revisit.evaluate('scrollWithGraphGate(20000)')
            revisit.wait_for_function('storyCompleted && !guidedEnabled && heldGraphScroll===null')
            assert long_height-revisit.evaluate('document.documentElement.scrollHeight')>3000
            assert revisit.locator('#guide-toggle').inner_text()=='Replay story'
            revisit.evaluate("scrollTo({top:0,behavior:'instant'})")
            revisit.wait_for_function('scrollY===0')
            assert revisit.locator('#story-progress-fill').evaluate('el=>getComputedStyle(el).transform')=='matrix(1, 0, 0, 1, 0, 0)'
            revisit.locator('#guide-toggle').click()
            revisit.wait_for_function('guidedEnabled && !storyCompleted && activeStory===0')
            assert revisit.locator('.story-steps').evaluate('el=>getComputedStyle(el).display')!='none'
            revisit.evaluate("() => {const s=storySteps[3],r=s.getBoundingClientRect();scrollTo({top:scrollY+r.top+r.height/2-innerHeight/2-250,behavior:'instant'})}")
            revisit.wait_for_function('activeStory===3')
            revisit.wait_for_timeout(150)
            before_wheel=revisit.evaluate('scrollY');before_box=held_copy.bounding_box()
            revisit.mouse.move(20,800);revisit.mouse.wheel(0,100)
            revisit.wait_for_function('y=>Math.abs(scrollY-y-100)<2',arg=before_wheel)
            revisit.wait_for_timeout(150)
            after_box=held_copy.bounding_box()
            assert abs(after_box['y']-before_box['y']+30)<2
            checks.append('Native wheel scrolling stays continuous while story text slows through its focus')

            revisit.close()
            checks.append('Finished story removes dead scroll space, allows direct return to top, and replays only when requested')

            page.screenshot(path=str(ARTIFACTS/'desktop-full.png'),full_page=True)
            mobile=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
            m=mobile.new_page();m.on('pageerror',lambda error:errors.append(str(error)))
            m.goto(url);m.locator('#atlas-loading').wait_for(state='hidden')
            assert m.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert m.locator('.timeline-scroll').first.evaluate('el=>el.scrollWidth>el.clientWidth')
            mf=m.locator('#concept-atlas').element_handle().content_frame()
            assert mf.locator('.hit').count()==347
            m.evaluate("() => {const step=document.querySelector('.story-step[data-concept=\"L108\"]');scrollTo({top:scrollY+step.getBoundingClientRect().top-innerHeight*.35,behavior:'instant'})}")
            m.wait_for_function('activeStory===3')
            mf.wait_for_function("selectedNode?.name==='L108' && DATA.guided_mode")
            caption=m.locator('#mobile-story-caption');assert caption.is_visible()
            assert m.locator('.story-steps').evaluate("el=>getComputedStyle(el).visibility")=="hidden"
            graph_box=m.locator('#concept-atlas').bounding_box();caption_box=caption.bounding_box()
            assert caption_box['y']>=graph_box['y']+graph_box['height']-1
            assert not mf.locator('#side').is_visible()
            assert not page.locator('#mobile-story-caption').is_visible()
            checks.append('Phone narration stays below the full-width network; desktop retains its left story column')

            m.locator('#atlas').scroll_into_view_if_needed();m.locator('#choose-diseases').click()
            mf.locator('#outcomePicker[open]>.outcomes').wait_for()
            assert mf.locator('#outcomePicker').get_attribute('open') is not None
            m.locator('#choose-diseases').click()
            m.screenshot(path=str(ARTIFACTS/'mobile-atlas.png'))
            m.screenshot(path=str(ARTIFACTS/'mobile-full.png'),full_page=True)
            checks.append('390px mobile layout, no horizontal overflow, working disease picker')
            standalone=context.new_page();standalone.goto((DOCS/'atlas.html').as_uri())
            assert standalone.locator('.hit').count()==347
            checks.append('Standalone atlas works directly from a file')
            delayed=context.new_page();held=[]
            release_associations=[False]
            def delay_association(route):
                if release_associations[0]:route.continue_()
                else:held.append(route)
            delayed.route('**/assets/associations/*.json',delay_association)
            delayed.goto(url);delayed.locator('#atlas-loading').wait_for(state='hidden')
            df=delayed.locator('#concept-atlas').element_handle().content_frame()
            assert df.locator('.hit').count()==347
            assert df.evaluate('DATA.progressive_associations && !DATA.associations_ready')
            assert delayed.locator('#choose-diseases').is_disabled()
            assert not df.locator('#side').is_visible()
            df.locator('#zoomIn').click()
            assert df.evaluate('scale>1')
            release_associations[0]=True
            for route in list(held):route.continue_()
            df.wait_for_function('DATA.associations_ready')
            delayed.wait_for_function('!document.querySelector("#choose-diseases").disabled')
            assert df.evaluate('Object.values(A).reduce((n,rows)=>n+rows.length,0)')==sum(len(v) for v in payload['associations'].values())
            delayed.close()
            checks.append('Graph paints and zooms before delayed association chunks; all estimates hydrate correctly')
            assert not errors,errors
            assert not external,external
            checks.append('No JavaScript errors or external runtime requests')
            browser.close()
    finally:server.shutdown();server.server_close()
    result=dict(checks=checks,nodes=347,outcomes=141,edges=659,errors=errors,external_runtime_requests=external,
        revised_interpretations_applied=provenance['revised_interpretations']['applied'])
    (ARTIFACTS/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':check()
