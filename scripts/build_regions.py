"""Fit rounded neighborhood outlines to curated concept anchors on the fixed graph.

Labels follow the main regions in manuscript v34 Figure 2. These are visual
neighborhood annotations, not a partition or additional statistical clustering.
"""
REGIONS = [
 ('liver','Liver',[.16,.847],['R85','R1765','R414','R309','R1015','L6965','I87','I65','I331','I202','I1230','R1815','R1884']),
 ('cancer','Cancer',[.125,.625],['R64','R98','R26','R390','R215','R826','I114','I345','I650','R1708']),
 ('musculoskeletal','Musculoskeletal|& orthopedic',[.77,.09],['R115','R139','R67','R1','R1710','R1931','I102','I338','I44','I284','I453']),
 ('cardiovascular','Cardiovascular',[.77,.558],['R21','R3','R420','R409','R901','R487','R1690','R415','R535','I106','I15','I276','I26','I109','I334','I307']),
 ('kidney','Kidney',[.82,.748],['R302','R221','L2358','L69','L974','L84','L1121','L62']),
 ('inflammatory','Inflammatory markers',[.50,.947],['L4','L21','L0','L68','L1590','L54','L110','L1460','L92','L1478','L5922','L74','L60']),
 ('cholesterol','Cholesterol',[.80,.873],['L496','L481','L184','L182','L852']),
]

# Smaller neighborhoods visible in the paper or supported by nearby interpretations.
DETAIL_REGIONS = [
 ('post_surgical_bowel','Post-surgical|bowel changes',[.17,.12],['R95','R368','R40','R285','R43','R498','R678','R1581','R701','I7','I119','I491','R1644','R284']),
 ('collections','Fluid collections|& abscesses',[.15,.25],['R52','R312','R4','R74','R359','R6710','R4895','R1617','I105','I3966','I12']),
 ('pancreatic_biliary','Pancreatic|& biliary',[.125,.425],['R42','R5','R73','R13','R473','R407','R990','R300','R892','R197','I70','I59','I347','I454','I154','I1416','I414','I8083','I1674']),
 ('tubes_drains','Tubes & drains',[.46,.38],['R96','R149','R380','R1481','I495','R71']),
 ('fluid_accumulation','Fluid accumulation',[.45,.66],['R101','R34','I21','I25','I83','I11','I5321','I262','I447']),
 ('cholestasis','Cholestasis',[.325,.685],['L108','L595','L33','L590','L173']),
 ('thrombosis','Venous|thrombosis',[.075,.735],['R24','R423','R333']),
]
REGIONS += DETAIL_REGIONS
DETAIL_IDS={row[0] for row in DETAIL_REGIONS}


def build_regions(nodes):
    from shapely.geometry import MultiPoint, Point
    by_name={n['name']:n for n in nodes}
    regions=[]
    for key,label,position,names in REGIONS:
        missing=set(names)-by_name.keys()
        if missing:raise ValueError(f'Missing region anchors: {missing}')
        points=[(by_name[name]['x'],by_name[name]['y']) for name in names]
        # A convex envelope avoids sharp inward spikes; rounded buffering gives
        # nodes a margin and softens every corner without moving any node.
        margin=.012 if key=='thrombosis' else .015 if key in DETAIL_IDS else .022
        shape=MultiPoint(points).convex_hull.buffer(margin,resolution=6)
        assert shape.is_valid and all(shape.covers(Point(p)) for p in points)
        polygon=[[round(x,7),round(y,7)] for x,y in list(shape.exterior.coords)[:-1]]
        regions.append(dict(id=key,label=label.split('|'),label_position=position,anchors=names,polygon=polygon,detail=key in DETAIL_IDS,basis='Interpretation-supported local neighborhood' if key in DETAIL_IDS else 'Main manuscript neighborhood'))
    return regions
