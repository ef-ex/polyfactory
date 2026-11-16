"""Audit additions for pf::starship_generator: odd parm values, timing, projections.
hython tests/spacetools/audit_starship_edges.py [outdir]"""
import hou, os, sys, math, time, json
HERE=os.path.dirname(os.path.abspath(__file__))
hou.hda.installFile(os.path.join(os.path.dirname(os.path.dirname(HERE)),"polyfactory","otls","pf_starship_generator.hda"))
OUT=sys.argv[1] if len(sys.argv)>1 else "F:/cache/spacetools/audit_starship"
os.makedirs(OUT,exist_ok=True)
geo=hou.node("/obj").createNode("geo")
def cook(**p):
    n=geo.createNode("pf::starship_generator")
    for k,v in p.items():
        t=n.parmTuple(k)
        if t is None: print("NOPARM",k); continue
        t.set(v if isinstance(v,(tuple,list)) else (v,))
    t=time.time(); n.cook(force=True); dt=time.time()-t
    bad=[]; st=[n]
    while st:
        c=st.pop(); st+=list(c.children())
        if c.errors() or c.warnings(): bad.append((c.path().split('/')[-1],(c.errors()+c.warnings())[0][:80]))
    return n,bad,dt
if "--parms" in sys.argv:
    n=geo.createNode("pf::starship_generator")
    for t in n.parmTuple and n.parms(): print(t.name(),t.eval(),t.parmTemplate().type().name())
    sys.exit()
base=dict(detail=3,subdiv_hull=1,subdiv_med=0,subdiv_small=0,panel_subdiv=0,variants=2)
cases=[("seed0",dict(seed=0)),("seedneg",dict(seed=-5)),("seedhuge",dict(seed=2**31-1)),
 ("len_tiny",dict(length=0.001)),("len_huge",dict(length=1e5)),("len0",dict(length=0)),("len_neg",dict(length=-3)),
 ("variants0",dict(variants=0)),("variants_big",dict(variants=20)),
 ("allzero",dict(jiggle=0,ext_amount=0,med_density=0,small_density=0,panels=0,boosters=0,mirror=0)),
 ("detail1",dict(detail=1)),("detail0",dict(detail=0)),("subdiv_neg",dict(subdiv_hull=-1)),
 ("paneltiny",dict(panel_size=0.0001)),("panelhuge",dict(panel_size=100)),]
for name,kw in (cases if "--skipcases" not in sys.argv else []):
    k=dict(base); k.update(kw)
    try:
        n,bad,dt=cook(**k); g=n.geometry(); p=g.pointFloatAttribValues("P")
        fin=all(math.isfinite(v) for v in p); bb=g.boundingBox()
        N=g.findVertexAttrib("N"); nn=[v for v in g.vertexFloatAttribValues("N")] if N else []
        nanN=not all(math.isfinite(v) for v in nn)
        print("%-12s %5.1fs prims=%6d finite=%s Nfinite=%s size=%s bad=%s"%(name,dt,len(g.prims()),fin,not nanN,[round(v,3) for v in bb.sizevec()],bad[:2]))
    except Exception as e: print(name,"EXC",str(e)[:150])
# timing default
n,bad,dt=cook(); print("default cook %.1fs prims=%d bad=%s"%(dt,len(n.geometry().prims()),bad))
# projections
from PIL import Image, ImageDraw
for s in (313997,5,777):
    n,_,_=cook(seed=s); g=n.geometry(); P=g.pointFloatAttribValues("P")
    xs,ys,zs=P[0::3],P[1::3],P[2::3]
    W=500; sc=W/ 20.0
    im=Image.new("RGB",(W*3,W),"black"); px=im.load()
    for ax,(a,b) in enumerate((((xs,zs)),(ys,zs),(xs,ys))):  # top, side, front
        for u,v in zip(a,b):
            i=int(ax*W+W/2+u*sc); j=int(W/2+v*sc)
            if 0<=i<W*(ax+1) and 0<=j<W and i>=ax*W: px[i,j]=(255,255,255)
    im.save("%s/proj_%d.png"%(OUT,s)); print("saved",s,len(xs))
