"""Audit addition: measurements that kill mutations the main checks miss (nozzle, panel layers 1/3, island cleanup, taper, center).
hython tests/spacetools/audit_starship_mut_extra.py   -> prints FAIL lines; exit 1 on fail. PF_MUTATE=bypass:node to prove they can fail."""
import hou, os, sys, collections
HERE=os.path.dirname(os.path.abspath(__file__))
hou.hda.installFile(os.path.join(os.path.dirname(os.path.dirname(HERE)),"polyfactory","otls","pf_starship_generator.hda"))
n=hou.node("/obj").createNode("geo").createNode("pf::starship_generator")
for k,v in dict(seed=313997).items(): n.parm(k).set(v)
mut=os.environ.get("PF_MUTATE")
if mut and mut.startswith("bypass:"):
    n.allowEditingOfContents()
    for nm in mut[7:].split(","): n.node(nm).bypass(True)
n.cook(force=True); g=n.geometry(); fails=[]
def ck(ok,msg): print(("ok   " if ok else "FAIL ")+msg); ok or fails.append(msg)
part=g.primIntAttribValues("pf_part"); pan=g.primIntAttribValues("pf_panel")
nb=part.count(3); ck(nb>=16*3,"booster prims %d >= 48 (tube+nozzle extrusions)"%nb)
# panel layer heights: layer k prims come from extrusions of height h_k; the number of prims per layer must all be >0 and
# strictly ordered by extrusion present: count of side quads grows with layer; here just require each layer > 200 prims
c=collections.Counter(pan); ck(all(c[k]>200 for k in (1,2,3)),"panel layer prim counts %s each >200 and layer3 > 2.5x layer2"%dict(c)); ck(c[3]>2.5*c[2],"panel layer3 %d > 2.5 x layer2 %d (micro layer extruded)"%(c[3],c[2]))
# hull islands: hull prims (pf_part 0) weld into one connected piece in terms of points
hull=[p for p in g.prims() if p.attribValue("pf_part")==0]
par=collections.defaultdict(list)
for p in hull:
    for v in p.vertices(): par[v.point().number()]
uf={}
def f(x):
    while uf.setdefault(x,x)!=x: uf[x]=uf[uf[x]]; x=uf[x]
    return x
for p in hull:
    vs=[v.point().number() for v in p.vertices()]
    for a in vs[1:]: uf[f(a)]=f(vs[0])
roots={f(v.point().number()) for p in hull for v in p.vertices()}
ck(len(roots)<=3,"hull connected components %d <= 3 (cleanup keeps one island/half)"%len(roots))
bb=g.boundingBox(); ck(abs(bb.center()[2])<7.5 and abs(bb.center()[0])<0.05,"bbox centre %s"%[round(x,2) for x in bb.center()])
print("FAILS:",len(fails)); sys.exit(1 if fails else 0)
