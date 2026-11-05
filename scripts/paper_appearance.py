"""Read exact marker and edge appearance from the verified seed-1283 SVG."""
import math
import re
import xml.etree.ElementTree as ET


def apply_paper_appearance(payload, svg_path):
    root = ET.parse(svg_path).getroot()
    _, _, width, height = map(float, root.get('viewBox').split())
    assert width == height == 1296
    ns = '{http://www.w3.org/2000/svg}'
    def style(el):
        return dict(item.strip().split(':', 1) for item in el.get('style', '').split(';') if ':' in item)
    def nearest(x, y):
        node = min(payload['nodes'], key=lambda n: math.hypot(n['x']*width-x, n['y']*height-y))
        assert math.hypot(node['x']*width-x, node['y']*height-y) < .03
        return node
    styles = {}; edges = []; order = []
    for group in root.iter(ns+'g'):
        name = group.get('id', '')
        if name.startswith('PathCollection_'):
            for el in group.findall(ns+'path'):
                numbers = list(map(float, re.findall(r'-?\d+(?:\.\d+)?(?:e[-+]?\d+)?', el.get('d'), re.I)))
                xs, ys = numbers[::2], numbers[1::2]
                node = nearest((min(xs)+max(xs))/2, (min(ys)+max(ys))/2)
                index = node['i']; parsed = {k.strip():v.strip() for k,v in style(el).items()}
                marker = styles.setdefault(index, {})
                if parsed.get('fill', 'none') != 'none':
                    marker.update(fill=parsed['fill'], fill_opacity=float(parsed.get('fill-opacity', 1)),
                                  radius=(max(xs)-min(xs))/2*1000/width)
                    order.append(index)
                if 'stroke' in parsed:
                    marker.update(stroke=parsed['stroke'], stroke_opacity=float(parsed.get('stroke-opacity', 1)),
                                  stroke_width=float(parsed.get('stroke-width', 1))*1000/width,
                                  dasharray=' '.join(str(float(v)*1000/width) for v in re.split(r'[, ]+', parsed.get('stroke-dasharray','').strip()) if v))
        elif name.startswith('LineCollection_'):
            for el in group.findall(ns+'path'):
                xy=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',el.get('d'))))
                a=nearest(*xy[:2])['i']; b=nearest(*xy[2:4])['i']
                parsed={k.strip():v.strip() for k,v in style(el).items()}
                edges.append(dict(a=a,b=b,stroke=parsed['stroke'],opacity=float(parsed.get('stroke-opacity',1)),
                                  width=float(parsed.get('stroke-width',1))*1000/width))
    assert len(styles)==len(payload['nodes'])==347
    assert len(edges)==len(payload['edges'])==659
    assert {tuple(sorted((e['a'],e['b']))) for e in edges}=={tuple(sorted(e[:2])) for e in payload['edges']}
    for node in payload['nodes']:
        marker=styles[node['i']]
        marker.setdefault('stroke', 'none');marker.setdefault('stroke_width', 0);marker.setdefault('stroke_opacity', 1);marker.setdefault('dasharray','')
        node['paper_radius']=marker['radius'];node['paper_style']=marker
    payload['paper_node_order']=order
    payload['paper_edges']=edges
    payload['modality_colors']={n['modality']:n['paper_style']['fill'] for n in payload['nodes']}
