"""Build a light, graph-first embed while keeping the full standalone HTML export."""
from pathlib import Path
import argparse,json


def build(root):
    docs=root/'docs';assets=docs/'assets';data=json.loads((assets/'atlas-data.json').read_text())
    full=(docs/'atlas.html').read_text();manifest=[];out=assets/'associations';out.mkdir(exist_ok=True)
    associations=data['associations']
    for first in range(0,len(data['nodes']),44):
        indices=list(range(first,min(first+44,len(data['nodes']))));name=f'chunk-{first//44}.json'
        records={str(i):associations[str(i)] for i in indices}
        (out/name).write_text(json.dumps(records,separators=(',',':'),ensure_ascii=False,allow_nan=False))
        manifest.append(dict(url='assets/associations/'+name,nodes=indices))
    data['associations']={str(n['i']):[] for n in data['nodes']};data['progressive_associations']=True;data['associations_ready']=False;data['association_chunks']=manifest
    for n in data['nodes']:n['associations_ready']=False
    packed=json.dumps(data,separators=(',',':'),ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    start=full.index('const DATA=')+len('const DATA=');end=full.index(';\nObject.keys(DATA.associations)',start)
    embed=full[:start]+packed+full[end:]
    embed=embed.replace('</body>','<script defer src="assets/progressive-associations.js"></script></body>')
    (docs/'atlas-embed.html').write_text(embed)
    (assets/'association-manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(dict(standalone_bytes=len(full.encode()),initial_embed_bytes=len(embed.encode()),chunks=len(manifest))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);build(p.parse_args().root)
