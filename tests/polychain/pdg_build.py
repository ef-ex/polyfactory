"""THE PARALLEL CACHED RUNNER - a TOP net, built in code, cooked headless.

    hython tests/polychain/pdg_build.py --cycle    # per-change gate
    hython tests/polychain/pdg_build.py --full     # milestone sweep
    hython tests/polychain/pdg_build.py --changed HEAD~1   # changed-code only

v2 principle 4: *use the platform's own machinery before writing a runner*.
Every work item is a separate PROCESS - which test isolation forces anyway -
so PDG's local scheduler gets to run them concurrently and to skip the ones
whose inputs did not change, and the test graph is an inspectable Houdini
artifact instead of a bespoke pool.

PROBED LIVE ON 22.0.398 BEFORE ANY OF THIS WAS DESIGNED (skill rule 1), and
three of the four answers were not what the docs imply:

  * `topnet.parm("topscheduler")` must be set to the scheduler's FULL PATH.
    Its default value is the bare name `localscheduler`, and cooking with that
    default raises `RuntimeError: No default scheduler set`.
  * `node.cookWorkItems(block=True)` cooks headless; `GraphContext.cook()` is
    the API that raises the error above.
  * A FAILED WORK ITEM DOES NOT RAISE.  12 items that exit 3 leave
    `cookWorkItems` returning normally with `workItemState.CookedFail` on each.
    A runner that trusted the absence of an exception would exit 0 on a red
    sweep - D210 exactly.  So the states are inspected and this file exits
    non-zero itself.
  * `@pdg_index` is NOT expanded in a command; `` `@pdg_index` `` is.
    Measured by writing one file per item and listing the directory.

Caching was measured too: a re-cook of 12 unchanged items takes 0.11 s.

WHAT IT CANNOT SEE: whether the underlying runners are any good.  It schedules
them and reports their exit codes; every assertion lives in the runner.
"""

import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hou                                                        # noqa: E402
import mutations as REG                                           # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE)).replace("\\", "/")
HYTHON = sys.executable.replace("\\", "/")
def _system_python():
    """A python that can actually import the test tooling.

    ⚠️ TWO TRAPS, BOTH MEASURED HERE RATHER THAN GUESSED.
    (1) `shutil.which("python")` INSIDE HYTHON FINDS HOUDINI'S OWN, because
        Houdini puts its python313 on PATH ahead of everything - the first fix
        picked `.../HOUDIN~1.398/python313/python.EXE` and failed identically.
    (2) hython EXPORTS `PYTHONHOME`/`PYTHONPATH`, so a real system python
        launched from it imports Houdini's standard library and dies on
        `import hypothesis`. `-E` makes the interpreter ignore every PYTHON*
        variable, and it is carried into the work-item commands too - the
        scheduler inherits hython's environment.
    So candidates are TESTED, not guessed. `PC_PYTHON` overrides.
    """
    seen, cands = set(), []
    if os.environ.get("PC_PYTHON"):
        cands.append(os.environ["PC_PYTHON"])
    for name in ("python", "python3"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            exe = os.path.join(d, name + (".exe" if os.name == "nt" else ""))
            if os.path.isfile(exe) and exe.lower() not in seen:
                seen.add(exe.lower())
                cands.append(exe)
    for exe in cands:
        try:
            if subprocess.call([exe, "-E", "-c", "import hypothesis, pytest"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0:
                return exe.replace("\\", "/")
        except OSError:
            continue
    raise SystemExit(
        "no python on PATH can import hypothesis and pytest - "
        "`pip install hypothesis mutmut`, or set PC_PYTHON. Tried: %s"
        % ", ".join(cands[:6]))


PYTHON = _system_python()
OUT = os.path.join(hou.text.expandString("$TEMP") or os.environ.get(
    "TEMP", "."), "pc_v2").replace("\\", "/")

# One generated-scene work item covers this many seeds.  A whole hython
# startup is ~10 s and 400 seeds cost 41 s in ONE process, so a work item per
# seed would be 95 % startup - the chunk is what makes the parallelism real.
CHUNK = 50
SEEDS = 400


def _q(path):
    return '"%s"' % path


# The two interpreter strings the commands are built from.  `-E` on the system
# one is not optional - see `_system_python`.
PY = _q(PYTHON) + " -E"
HY = _q(HYTHON)


def _cmd(exe, script, *args):
    return " ".join([exe, _q(os.path.join(REPO, script).replace("\\", "/"))]
                    + list(args))


def changed_mutations(base):
    """Mutations whose edits touch a file that changed since `base`.

    Google's policy, and the reason the per-cycle gate is minutes rather than
    an hour: mutants on changed code only, per change.  A mutation whose
    target file is untouched proved its check last cycle and will prove it
    again at the milestone sweep.
    """
    out = subprocess.check_output(["git", "diff", "--name-only", base],
                                 cwd=REPO).decode("utf-8", "replace")
    touched = set(l.strip().replace("\\", "/") for l in out.splitlines() if l)
    picked = []
    for i, mut in enumerate(REG.MUTATIONS):
        if any(rel.replace("\\", "/") in touched for rel, _o, _n in mut.edits):
            picked.append(i)
    return picked, sorted(touched)


def build(mode, mut_indices, seeds=SEEDS, slots=None):
    """The whole graph, in code.  Returns (topnet, {node: what it is})."""
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    # Stale per-item JSON from a previous run would be collated as if it were
    # this run's - the same shape as a cached verdict for an edited entry.
    for name in os.listdir(OUT):
        if name.startswith(("mut_", "gen_")) and name.endswith(".json"):
            os.remove(os.path.join(OUT, name))
    top = hou.node("/tasks").createNode("topnet", "pc_v2")
    sch = top.node("localscheduler")
    top.parm("topscheduler").set(sch.path())     # the FULL PATH - see above
    # ⚠️ SLOTS ARE A TRADE, NOT A FREE SPEEDUP.  `run_native_checks.py` holds
    # WALL-CLOCK ceilings (`bench_deform_20km`, the `*_wall_clock` rows), and
    # the registry's own control already had to grow a 3-attempt retry because
    # a second hython on this machine reddened them.  CPU-1 is the default;
    # `--slots N` is how an operator buys stability back.
    if slots:
        sch.parm("maxprocsmenu").set("1")
        sch.parm("maxprocs").set(int(slots))
    else:
        sch.parm("maxprocsmenu").set("-1")       # CPU count less one
    sch.parm("pdg_workingdir").set(REPO)
    made = {}

    # 1. the pure-Python kernel: pytest, one item, seconds.
    unit = top.createNode("genericgenerator", "unit")
    unit.parm("itemcount").set(1)
    unit.parm("pdg_command").set(
        '%s -m pytest %s %s -q -p no:cacheprovider'
        % (PY, _q(REPO + "/tests/unit/test_polychain_properties.py"),
           _q(REPO + "/tests/unit/test_polychain.py")))
    made[unit] = "the pure-Python kernel (pytest + Hypothesis)"

    # 1b. THE BUDGET, as its own node so its red is never confused with the
    #     kernel's.  It is red until the v1 deletions land, and that is what a
    #     budget is for - see the file's own docstring.
    budget = top.createNode("genericgenerator", "budget")
    budget.parm("itemcount").set(1)
    budget.parm("pdg_command").set(
        '%s -m pytest %s -q -p no:cacheprovider'
        % (PY, _q(REPO + "/tests/unit/test_polychain_budget.py")))
    made[budget] = "the size budget (test lines <= tool lines)"

    # 2. the comparator's own mutation battery - the oracle everything else
    #    is judged by, so it is judged first.
    selftest = top.createNode("genericgenerator", "diff_selftest")
    selftest.parm("itemcount").set(1)
    selftest.parm("pdg_command").set(
        _cmd(HY, "tests/polychain/run_diff_selftest.py"))
    made[selftest] = "the differential comparator's 19 mutations"

    # 3. generated scenes through the differential oracle, in chunks.
    nchunk = max(1, (seeds + CHUNK - 1) // CHUNK)
    gen = top.createNode("genericgenerator", "generated")
    gen.parm("itemcount").set(nchunk)
    gen.parm("pdg_command").set(_cmd(
        HY, "tests/polychain/run_generated.py",
        "--start", "`@pdg_index * %d`" % CHUNK, "--seeds", str(CHUNK),
        "--quiet", "--json", _q("%s/gen_`@pdg_index`.json" % OUT)))
    made[gen] = "%d generated scenes, %d items" % (seeds, nchunk)

    if not mut_indices:
        return top, made

    # 4. the control build, ONCE - then every mutation reads it.  Without the
    #    shared file each of the 32 items pays a pristine export, an HDA
    #    rebuild and a full runner for the same answer; measured, the control
    #    alone is 8 min 24 s because `run_native_checks.py` is 430 s.
    # ⚠️ THE SUBJECT COMMIT IS RESOLVED ONCE AND PASSED TO EVERY ITEM.  Two
    # commits landed on the branch during this cycle's first full sweep; each
    # later item would have read a different HEAD, called the shared control
    # stale and recomputed it - 32 x 8.5 minutes for an answer already on
    # disk.  Freezing it also means the sweep reports on ONE tree, which is
    # the only thing that makes its verdicts comparable to each other.
    head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                   cwd=REPO).decode().strip()
    ctl = "%s/control.json" % OUT
    if os.path.exists(ctl):
        os.remove(ctl)
    control = top.createNode("genericgenerator", "control")
    control.parm("itemcount").set(1)
    # ⚠️ HYTHON, not the system python, and deliberately: the registry is
    # stdlib-only and spawns hython per suite anyway, so running the parent
    # under hython removes the PYTHONHOME/PYTHONPATH trap from the one item
    # that has to survive an 8-minute cook.
    control.parm("pdg_command").set(_cmd(
        HY, "tests/polychain/run_mutation_registry.py",
        "--control-only", "--head", head, "--control", _q(ctl)))
    made[control] = "the pristine control at %s, shared by every mutation" % head[:8]

    # 5. one work item per selected mutation, downstream of the control so
    #    PDG serialises that dependency for us.
    muts = top.createNode("genericgenerator", "mutations")
    muts.setInput(0, control)
    muts.parm("itemcount").set(len(mut_indices))
    # A partial selection is written out and `--selection` narrows the
    # registry to it, so the item needs nothing but its own index.  The
    # alternative - a python expression inside the command template - would
    # put a second declaration of the registry in a place nothing type-checks.
    sel = "%s/selection.json" % OUT
    with open(sel, "w") as fh:
        json.dump(mut_indices, fh)
    muts.parm("pdg_command").set(_cmd(
        HY, "tests/polychain/run_mutation_registry.py",
        "--selection", _q(sel), "--index", "`@pdg_index`",
        "--head", head, "--control", _q(ctl),
        "--json", _q("%s/mut_`@pdg_index`.json" % OUT)))
    made[muts] = "%d of %d registered mutations" % (len(mut_indices),
                                                    len(REG.MUTATIONS))
    return top, made


def cook(top, made):
    """Cook the WHOLE GRAPH once, then READ THE STATES - a failure does not
    raise (see the module docstring).

    ⚠️ COOKING NODE BY NODE SERIALISES THE NODES.  The first version looped
    over the leaves calling `cookWorkItems` on each, and the per-cycle gate
    took 1.9 + 7.7 + 3.8 s in sequence for work that has no dependency between
    it at all.  One `waitforall` sink downstream of every leaf makes the whole
    graph one cook, and the scheduler overlaps it.
    """
    sink = top.createNode("waitforall", "all")
    for i, node in enumerate(sorted(made, key=lambda n: n.name())):
        sink.setInput(i, node)
    sink.setDisplayFlag(True)
    t0 = time.time()
    sink.cookWorkItems(block=True)
    wall = time.time() - t0

    rows, red = [], []
    for node in sorted(made, key=lambda n: n.name()):
        items = node.getPDGNode().workItems
        took = sum(w.cookDuration for w in items)
        bad = [w for w in items if str(w.state) != "workItemState.CookedSuccess"]
        rows.append((node.name(), made[node], len(items), len(bad), took))
        print("  [%s] %-14s %2d item(s), %2d failed, %7.1f s cpu  - %s"
              % ("FAIL" if bad else "PASS", node.name(), len(items), len(bad),
                 took, made[node]))
        for w in bad[:4]:
            red.append("%s item %d: %s" % (node.name(), w.index, w.state))
            for line in _log(w)[-16:]:
                print("        | %s" % line[:200])
    print("  ---- %.1f s WALL, %.1f s summed across items ----"
          % (wall, sum(r[4] for r in rows)))
    return rows, red


def _log(item):
    """The item's own stdout.  `logMessages` is empty for an out-of-process
    item - the scheduler writes a file and `logURI` names it, which is the
    only place a failing runner's output exists."""
    out = [str(m) for m in item.logMessages]
    uri = str(item.logURI or "")
    path = uri[8:] if uri.startswith("file:///") else uri
    if path.startswith("file:"):          # the scheduler writes `file:C:/...`
        path = path[5:]
    try:
        with open(path, errors="replace") as fh:
            out += [l.rstrip() for l in fh if l.strip()]
    except (IOError, OSError):
        out.append("(no log at %r)" % uri)
    return out


def main():
    argv = sys.argv[1:]
    mode = "cycle"
    if "--full" in argv:
        mode = "full"
    base = argv[argv.index("--changed") + 1] if "--changed" in argv else None
    seeds = int(argv[argv.index("--seeds") + 1]) if "--seeds" in argv \
        else SEEDS
    slots = int(argv[argv.index("--slots") + 1]) if "--slots" in argv else None

    if mode == "full":
        picked, touched = list(range(len(REG.MUTATIONS))), None
    elif base:
        picked, touched = changed_mutations(base)
    else:
        picked, touched = [], []

    print("polyChain v2 runner - %s" % ("FULL SWEEP" if mode == "full"
                                        else "per-cycle gate"))
    if touched is not None:
        print("  changed files: %d%s" % (len(touched),
                                         (" - " + ", ".join(touched[:6]))
                                         if touched else ""))
    print("  mutations selected: %d of %d%s"
          % (len(picked), len(REG.MUTATIONS),
             (" - " + ", ".join(REG.MUTATIONS[i].id for i in picked[:6]))
             if picked else ""))
    print("  python: %s" % PYTHON)
    print("  slots: %s" % (slots or "CPU count less one"))
    print("  scratch: %s" % OUT)

    t0 = time.time()
    top, made = build(mode, picked, seeds, slots)
    rows, red = cook(top, made)

    # The mutation items' own verdicts, collated: a mutation that SURVIVED its
    # paired check exits non-zero, so it is already a failed work item - but
    # the id is what an operator needs, and it lives in the JSON.
    verdicts = []
    for name in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
        if name.startswith("mut_") and name.endswith(".json"):
            with open(os.path.join(OUT, name)) as fh:
                verdicts += json.load(fh)
    if verdicts:
        print("\n  mutation verdicts (%d):" % len(verdicts))
        for v in sorted(verdicts, key=lambda v: (v["ok"], v["id"])):
            print("    [%s] %-32s %-8s %s"
                  % ("ok" if v["ok"] else "!!", v["id"], v["verdict"],
                     v["detail"][:110]))

    print("\n%s: %d node(s), %d failure(s), %.1f s total"
          % ("FULL SWEEP" if mode == "full" else "per-cycle gate",
             len(rows), len(red), time.time() - t0))
    for r in red:
        print("  !! %s" % r)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
