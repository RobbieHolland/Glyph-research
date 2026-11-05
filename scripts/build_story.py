"""Build the guided scientific narrative from frozen, aggregate atlas results."""
from pathlib import Path
import json
import re


def build(root):
    page=root/'docs/index.html';text=page.read_text();payload=json.loads((root/'docs/assets/atlas-data.json').read_text())
    def evidence(concept,outcome):
        node=next(n for n in payload['nodes'] if n['name']==concept)
        row=next(a for a in payload['associations'][str(node['i'])] if payload['outcomes'][a[0]]==outcome)
        assert row[6]
        return f'<p class="story-evidence" title="95% CI {row[3]:.2f}–{row[4]:.2f}"><strong>{row[1]:.2f}</strong><span>Unadjusted odds ratio<br>per SD of {concept} activation</span></p>'
    def marker_list(items,outcome):
        rows=[]
        for concept,label in items:
            node=next(n for n in payload['nodes'] if n['name']==concept)
            row=next(a for a in payload['associations'][str(node['i'])] if payload['outcomes'][a[0]]==outcome)
            if not row[6] or row[1]<=1:raise ValueError(f'{concept} is not a significant higher-odds marker for {outcome}')
            rows.append(f'<div class="story-marker"><dt><code>{concept}</code><span>{label}</span></dt><dd title="95% CI {row[3]:.2f}–{row[4]:.2f}">{row[1]:.2f}</dd></div>')
        return '<div class="story-marker-results"><div class="story-marker-heading"><span>Associated concepts</span><span>OR</span></div><dl>'+''.join(rows)+'</dl><p class="story-marker-note">Unadjusted OR per SD · Discovery Site</p></div>'

    liver='Cancer Liver Primary';kidney='Chronic Kidney Disease, Stage Iii (585.33)';cardio='Heart Failure With Preserved Ef [Diastolic Heart Failure] (428.4)'
    for concept in ('L108','R85','I87'):evidence(concept,liver)
    sections=[
        ('','Sepsis','Widespread risk markers for sepsis 1–4 years after CT.','','Sepsis (994.2)','Sepsis',None,None,''),
        ('','Heart failure (HFpEF)','More clustered, yet distributed, risk markers 1–4 years after CT.','',cardio,'Heart failure (HFpEF)',None,None,''),
        ('','Primary liver cancer','More tightly clustered risk markers 1–4 years after CT.','',liver,'Primary liver cancer',None,None,''),
        ('Labs · reports · CT','Liver disease','Cholestasis in labs, cirrhotic morphology in reports, and liver/biliary findings on CT.','',liver,'Primary liver cancer','L108','R85,I87',marker_list([('L108','Cholestasis'),('R85','Cirrhotic liver morphology'),('I87','Hepatobiliary pattern')],liver)),
        ('','Heart failure','Renal and cardiovascular signs associated with later HFpEF.','',cardio,'Heart failure (HFpEF)',None,None,''),
        ('Laboratory findings','Renal function','Renal dysfunction sits alongside metabolic and coagulation abnormalities.','',cardio,'Heart failure (HFpEF)','L84','L62,L87',marker_list([('L84','Azotemia'),('L62','Renal dysfunction and acidosis'),('L87','Coagulopathy with renal impairment')],cardio)),
        ('CT · reports','Cardiovascular markers','Aortic disease, cardiac calcification and cardiomegaly cluster nearby.','',cardio,'Heart failure (HFpEF)','I26','I109,R21,R204',marker_list([('I26','Aortic atherosclerosis'),('I109','Abdominal aortic calcification'),('R21','Coronary / valve calcification'),('R204','Cardiomegaly')],cardio)),
        ('','Explore another outcome','Choose a disease, or continue to the literature examples.','','428.4','Heart failure (HFpEF)',None,None,''),
    ]
    questions={'L108':'What are risk markers of primary liver cancer?',
               'L84':'What are renal risk markers of heart failure?',
               'I26':'What are risk markers of heart failure?'}
    html='<div class="story-steps">\n'
    for i,(label,title,body,hint,outcome,disease,concept,related,stats) in enumerate(sections):
        selection=(f'data-outcomes="{"|".join(outcome)}"' if isinstance(outcome,(list,tuple)) else f'data-outcome="{outcome}"')
        accent=payload['outcome_colors'].get(outcome if isinstance(outcome,str) else outcome[0],'#525252')
        attributes=f'{selection} data-disease="{disease}" style="--story-accent:{accent}"'
        if concept:attributes+=f' data-concept="{concept}"'
        if related:attributes+=f' data-related="{related}"'
        label_html=f'<p class="step-label">{label}</p>' if label else ''
        question=questions.get(concept,'')
        for phrase in ('primary liver cancer','heart failure'):
            question=question.replace(phrase,f'<span class="story-disease-accent">{phrase}</span>')
        prompt_html=('<div class="story-prompt"><span class="story-prompt-label">You ask Glyph</span><p class="story-prompt-text">'+question+'</p></div>') if concept in questions else ''
        hint_html=f'<p class="step-hint">{hint}</p>' if hint else ''
        if i<len(sections)-1:
            prefix='Renal risk markers for ' if concept=='L84' else 'Cardiovascular risk markers for ' if concept=='I26' else 'Risk markers for '
            heading_html=prefix+f'<span class="story-disease-accent">{disease}</span>'
        else:heading_html=title

        html+=f'<section class="story-step{" is-active" if i==0 else ""}" {attributes} aria-label="{title}"><div class="story-step-copy">{prompt_html}{label_html}<h3 class="story-accent-heading">{heading_html}</h3><p>{body}</p>{stats}{hint_html}</div></section>\n'
    html+='</div>'
    start=text.index('<div class="story-steps">');end=text.index('</div></div>\n    </section>',start)+len('</div>')
    text=text[:start]+html+text[end:]
    text=re.sub(r'(<span id="active-disease">).*?(</span>)',r'\g<1>Sepsis\2',text,count=1)
    text=re.sub(r'(<h3 id="manual-disease">).*?(</h3>)',r'\g<1>Sepsis\2',text,count=1)
    page.write_text(text)
    print('Story: sepsis overview -> heart-failure overview -> liver cancer overview -> L108 with R85/I87 -> HFpEF overview -> renal/L84 -> cardiovascular/I26 -> overview.')


if __name__=='__main__':build(Path(__file__).resolve().parents[1])
