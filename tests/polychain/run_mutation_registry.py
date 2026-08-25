"""THE META-RUNNER: break the thing each check guards, and watch it go red.

    python tests/polychain/run_mutation_registry.py
    python tests/polychain/run_mutation_registry.py --only pc_local_scaled
    python tests/polychain/run_mutation_registry.py --runner scene
    python tests/polychain/run_mutation_registry.py --list

⚠️ THIS RUNNER IS SLOW ON PURPOSE - it is a weekly / audit tool, not a
per-commit one.  It exports the repo once per mutation and re-runs a whole
suite inside the export, and `run_native_checks` alone is ~6 minutes.  What it
buys is the one thing 15 build cycles proved the fast suites cannot buy:
evidence that a green check is a check that CAN go red.

⚠️ IT NEVER TOUCHES THE WORKING TREE.  Every mutation is applied inside its own
`git archive HEAD` export under the system temp directory, and the export is
deleted afterwards.  There is nothing to restore, which is the point: 21.4
recorded a tree-wide `git checkout` from one agent silently reverting
another's uncommitted work, and a mutation sweep that edits real files is that
accident waiting for a crash to happen in the middle of it.

WHAT IT ASSERTS, and each one is a recorded incident:

  1. **Every registered edit still matches its source exactly once.**  A
     mutation whose target line has moved reports a green forever (D208).
  2. **Every registered mutation reddens the check it is paired with.**  Not
     "reddens something" - 21.4 M10 was killed by an `AssertionError` raised
     inside a check while the check credited with the catch printed PASS, so a
     run that ABORTS counts as a failure unless the entry says `expect="abort"`.
  3. **Every check name a runner prints is PROVEN, EXEMPT or UNPROVEN.**  A
     name in none of the three fails the run, so a check cannot be added to
     this project without a decision about how it can fail.  Retrospective 4a
     rule 1, mechanised.  PROVEN means *a mutation registered against that
     name reddened it* - the rest of a mutation's blast radius is printed and
     credits nothing, because only the declared pairing was examined.
  4. **The inventory is pinned both ways.**  A new name is UNDECLARED and
     fails; a name that stops being printed trips `EXPECT_CHECKS`.  A check
     that quietly stops being emitted used to be deleted from the meta-check
     in silence, with its debt entry left describing nothing.
  5. **Every EXEMPT / UNPROVEN key names a live check**, and no debt entry
     also has a mutation.  Declarations rot as fast as checks do.

Exit code is 0 only if all five hold.  `--only` / `--runner` make it a PARTIAL
run: the mutations still have to redden their paired checks, but the coverage
table is labelled and cannot fail the run, since names proven by unselected
mutations necessarily read as undeclared.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import mutations as REG                                          # noqa: E402

HYTHON = os.environ.get(
    "HYTHON",
    "C:/Program Files/Side Effects Software/Houdini 22.0.398/bin/hython.exe")
BUILD_SCRIPT = "devScripts/create_pf_polychain_hda.py"

# ⚠️ THE NAME IS CAPTURED WHOLE, and an unparseable one is reported rather
# than trimmed.  `([A-Za-z_0-9]+)` stopped at the first character outside the
# class, so a check named `clip_stamp.v2` was silently folded into the already
# PROVEN `clip_stamp` row: the inventory did not grow, the new check vanished
# from the meta-check, and the sweep stayed green.  Nothing in this project
# forces snake_case check names, so the parser may not assume it.
LINE = re.compile(r"^\s*\[(PASS|FAIL|SKIP)\]\s+(\S+)")
NAME_OK = re.compile(r"^[A-Za-z_0-9]+$")
MOVED = re.compile(r"(\d+) moved baseline values")
# FAIL beats PASS beats SKIP.  The scene runners print the same name once per
# case, and a name that is SKIPPED on every case is not the same thing as a
# name that passed - retrospective P2 is "the check is well written; nothing
# ever runs it", and conflating the two hides exactly that.
RANK = {"SKIP": 0, "PASS": 1, "FAIL": 2}


# --- the throwaway copy ------------------------------------------------------

def export(dest, rev="HEAD"):
    """`git archive <rev>` into `dest`.  Read-only against the real repo.

    ⚠️ `rev` IS NOT DECORATION.  The parallel sweep shares ONE control build
    across 32 work items and keys it to a commit; if a commit lands on the
    branch while the sweep runs, every later item reads a different `HEAD`,
    decides the control is stale, and recomputes it - 32 x 8.5 minutes for an
    answer that was already on disk.  Observed live during this cycle, with
    two commits landing mid-sweep.  `pdg_build.py` therefore resolves the
    commit ONCE and passes `--head <sha>` to every item.
    """
    assert os.path.abspath(dest) != os.path.abspath(REPO)
    os.makedirs(dest)
    tar = subprocess.Popen(["tar", "-x", "-C", dest], stdin=subprocess.PIPE)
    arc = subprocess.Popen(["git", "archive", rev], cwd=REPO,
                           stdout=tar.stdin)
    arc.wait()
    tar.stdin.close()
    tar.wait()
    assert arc.returncode == 0 and tar.returncode == 0, "export failed"
    assert os.path.exists(os.path.join(dest, BUILD_SCRIPT)), "empty export"


def rebuild(root):
    """Rebuild the .hda FROM THIS COPY.

    ⚠️ `POLYFACTORY` is not optional: 21.7 recorded that the build script
    defaults it to a HARDCODED `F:/projects/polyfactory`, so a rebuild launched
    from a copy overwrites the REAL repo's asset.
    """
    env = dict(os.environ)
    env["POLYFACTORY"] = os.path.join(root, "polyfactory").replace("\\", "/")
    p = subprocess.Popen([HYTHON, BUILD_SCRIPT], cwd=root, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode("utf-8", "replace")
    if p.returncode != 0:
        raise RuntimeError("hda rebuild failed:\n" + out[-2000:])


def run(root, runner):
    """Run one suite inside the export.  -> (exit code, {name: state}, moved)"""
    p = subprocess.Popen([HYTHON, REG.RUNNERS[runner]], cwd=root,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode("utf-8", "replace")
    states, moved, odd = {}, 0, set()
    for line in out.splitlines():
        m = LINE.match(line)
        if m:
            state, name = m.group(1), m.group(2)
            if not NAME_OK.match(name):
                odd.add(name)
            if RANK[state] > RANK.get(states.get(name), -1):
                states[name] = state
        m = MOVED.search(line)
        if m:
            moved = int(m.group(1))
    if odd:
        print("  [!] %-7s printed %d check name(s) that are not [A-Za-z_0-9]+: "
              "%s - they are carried through verbatim, so they surface as "
              "UNDECLARED rather than being folded into another check's "
              "coverage" % (runner, len(odd), ", ".join(sorted(odd)[:6])))
    return p.returncode, states, moved, out


def digest(mut):
    """A fingerprint of everything about an entry that decides its verdict."""
    blob = json.dumps([mut.runner, mut.edits, sorted(mut.kills), mut.expect,
                       bool(mut.rebuild)], sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def cleanup(path):
    """Remove an export, and SAY SO when it cannot be removed.

    `ignore_errors=True` alone leaked: on Windows Houdini holds handles inside
    the export (the installed .hda, loaded modules), the rmtree partially
    fails, and an audit measured up to 54 MB of `pcmut_*` trees left in %TEMP%
    with the operator never told.
    """
    shutil.rmtree(path, ignore_errors=True)
    if os.path.exists(path):
        print("  [!] the export at %s could not be removed (Houdini still "
              "holds a handle inside it) - sweep it by hand" % path)


# --- applying an entry -------------------------------------------------------

def perturb_baseline(path):
    """Move exactly one recorded value, the smallest possible baseline move.

    Not a rewrite: D210's defect was that a runner PRINTED a moved value and
    exited 0, so the mutation has to be one value, not a corrupted file.
    """
    with open(path) as fh:
        base = json.load(fh)
    for case in sorted(base):
        for rec in base[case]:
            if isinstance(rec.get("value"), int) and not rec.get("skipped"):
                rec["value"] = rec["value"] + 1
                with open(path, "w") as fh:
                    json.dump(base, fh, indent=2, sort_keys=True)
                return "%s/%s -> %d" % (case, rec["name"], rec["value"])
    raise RuntimeError("no integer baseline value in " + path)


def apply(root, mut):
    """Apply every edit, asserting each matched EXACTLY ONCE."""
    notes = []
    for rel, old, new in mut.edits:
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(path):
            raise RuntimeError("%s: no such file in the export" % rel)
        if old is None:                       # the baseline perturbation
            notes.append(perturb_baseline(path))
            continue
        with open(path, "rb") as fh:
            src = fh.read().decode("utf-8")
        # ⚠️ `git archive` APPLIES THE REPO'S eol SETTING, so a .vfl that is LF
        # in the working tree arrives CRLF in the export - and a registered
        # multi-line edit written against the working tree then matches ZERO
        # times and reports STALE. Normalise, edit, restore the ending.
        crlf = "\r\n" in src
        if crlf:
            src = src.replace("\r\n", "\n")
        n = src.count(old)
        if n != 1:
            raise RuntimeError(
                "%s: the registered edit matches %d times, not once - the "
                "mutation no longer names a line that exists, so it would "
                "report a green forever (D208)" % (rel, n))
        out = src.replace(old, new)
        if crlf:
            out = out.replace("\n", "\r\n")
        with open(path, "wb") as fh:
            fh.write(out.encode("utf-8"))
        notes.append(rel)
    return "; ".join(notes)


def execute(mut, control, head="HEAD"):
    """One mutation, in its own export.  -> (verdict, detail, reddened set)"""
    root = tempfile.mkdtemp(prefix="pcmut_")
    root = os.path.join(root, "tree")
    try:
        export(root, head)
        detail = apply(root, mut)
        if mut.rebuild:
            rebuild(root)
        code, states, moved, out = run(root, mut.runner)
        red = set(n for n, s in states.items() if s == "FAIL")
        if moved:
            red.add(REG.BASELINE_MOVED)
        base = control[mut.runner]
        # A name the control printed and this run did not is a name the
        # mutation stopped from being reached.  It is NOT evidence the check
        # can fail (21.5) - so it is reported, and it never credits coverage.
        missing = sorted(set(base) - set(states) - set([REG.BASELINE_MOVED]))
        if not states:
            return ("ABORT", "the runner produced no verdicts (exit %d): %s"
                    % (code, out.strip().splitlines()[-1:] or ""), set())
        survived = [k for k in mut.kills if k not in red]
        if survived:
            unreached = [k for k in survived if k in missing]
            return ("SURVIVED",
                    "still green: %s%s; what it DID redden (%d): %s"
                    % (", ".join(survived),
                       (" (never reached: %s)" % ", ".join(unreached))
                       if unreached else "", len(red),
                       ", ".join(sorted(red)[:8]) or "nothing at all"),
                    red)
        # ⚠️ THE BLAST RADIUS IS PRINTED AND CREDITS NOTHING.  It used to be
        # credited: every name the mutation happened to redden was marked
        # PROVEN, so permuting the conform axis credited `stepped_riser_is_m`
        # - a step-height check nobody had examined - and removed it from the
        # debt list for good.  Only `kills` was examined, so only `kills`
        # counts (D277, one level up).
        extra = sorted(red - set(mut.kills))
        return ("RED", "%d red, %d unreached, exit %d; also reddened "
                "(credits nothing, %d): %s"
                % (len(red), len(missing), code, len(extra),
                   ", ".join(extra[:6]) or "nothing else"), red)
    finally:
        cleanup(os.path.dirname(root))


# --- the run -----------------------------------------------------------------

def main():
    argv = sys.argv[1:]
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    # `--index N` is `--only` by POSITION, and it exists for the PDG runner:
    # a work item knows its own index and nothing else, and embedding thirty
    # ids in a command template is a second place for the registry to be
    # declared. `pdg_build.py` asserts the count it saw matches len(MUTATIONS).
    # `--selection FILE` narrows the registry to a list of indices first, so
    # `--index` counts within THAT list. It exists so a PDG work item needs
    # nothing but its own index: no expression language in the command
    # template, and the registry is still the one declaration.
    pool = REG.MUTATIONS
    if "--selection" in argv:
        with open(argv[argv.index("--selection") + 1]) as fh:
            pool = [REG.MUTATIONS[i] for i in json.load(fh)]
    if "--index" in argv:
        only = pool[int(argv[argv.index("--index") + 1])].id
    want = argv[argv.index("--runner") + 1] if "--runner" in argv else None
    picked = [m for m in REG.MUTATIONS
              if (only is None or m.id == only)
              and (want is None or m.runner == want)]
    if "--list" in argv:
        for m in REG.MUTATIONS:
            print("%-32s %-7s -> %s" % (m.id, m.runner, ", ".join(m.kills)))
        print("\n%d mutations, %d exempt, %d unproven"
              % (len(REG.MUTATIONS), len(REG.EXEMPT), len(REG.UNPROVEN)))
        return 0
    if not picked:
        print("no mutation matches --only %r / --runner %r" % (only, want))
        return 1

    # ⚠️ A FULL SWEEP INVENTORIES EVERY RUNNER, not just the runners that
    # happen to own a mutation.  `images` has ONE registered mutation, and
    # deriving the inventory from the selection meant deleting that one entry
    # would drop all 43 image checks out of the meta-check in silence.  A
    # PARTIAL run (`--only` / `--runner`) inventories only what it selected
    # and its coverage table is not comparable to a full sweep's - it is
    # labelled and it cannot fail on coverage, because names proven by the
    # mutations it did NOT select necessarily read as undeclared.
    full = only is None and want is None
    runners = sorted(REG.RUNNERS) if full else sorted(
        set(m.runner for m in picked))
    t0 = time.time()

    # ⚠️ THE SWEEP HAS TO BE RESUMABLE, and this is not a convenience.  A full
    # pass is over an hour of hython, the two long-running agents on this
    # machine share it, and the first attempt was KILLED at mutation 7 of 27 -
    # losing 45 minutes of green verdicts that had already been earned.  The
    # state file is keyed to the COMMIT **and each entry to its own digest**,
    # and the second half is not optional: the subject comes from `git archive
    # HEAD` but the registry is imported from the WORKING TREE, so a cached
    # verdict keyed on HEAD alone replayed RED for an entry that had since
    # been edited into one that cannot fail.  Measured: neutering
    # `2d_clip_stamp_zeroed` in the working tree and re-running with `--state`
    # printed `RED (cached)`, `1 proven`, exit 0, while the same tree without
    # `--state` correctly printed `SURVIVED ... nothing at all`, exit 1.
    state_path = (argv[argv.index("--state") + 1]
                  if "--state" in argv else None)
    # `--head SHA` freezes the subject commit for the whole sweep - see
    # `export`.  Without it a commit landing mid-run invalidates the shared
    # control for every item that has not started yet.
    head = (argv[argv.index("--head") + 1] if "--head" in argv else
            subprocess.check_output(["git", "rev-parse", "HEAD"],
                                    cwd=REPO).decode().strip())
    state = {"head": head, "control": {}, "results": {}}
    if state_path and os.path.exists(state_path):
        with open(state_path) as fh:
            got = json.load(fh)
        if got.get("head") == head:
            state = got
            print("resuming %s: %d cached control runners, %d cached verdicts"
                  % (state_path, len(state["control"]), len(state["results"])))
        else:
            print("%s is for %s, not HEAD %s - starting clean"
                  % (state_path, got.get("head", "?")[:8], head[:8]))

    def save():
        if state_path:
            with open(state_path, "w") as fh:
                json.dump(state, fh, indent=1, sort_keys=True)

    # ⚠️ THE CONTROL IS COMPUTED ONCE AND SHARED, or 30 parallel work items
    # each pay a pristine export + HDA rebuild + full runner for the same
    # answer.  It is keyed to HEAD exactly as `--state` is, and a file for a
    # different HEAD is IGNORED with a printed line rather than trusted - a
    # stale control silently turns "this check went red" into a coin toss.
    # `--control-only` is the upstream work item that writes it.
    ctl_path = (argv[argv.index("--control") + 1]
                if "--control" in argv else None)
    ctl_loaded = False
    if ctl_path and os.path.exists(ctl_path):
        with open(ctl_path) as fh:
            got = json.load(fh)
        if got.get("head") == head:
            ctl_loaded = True
            state["control"] = got["control"]
            print("control from %s (%d runners, HEAD %s)"
                  % (ctl_path, len(got["control"]), head[:8]))
        else:
            print("%s is for %s, not HEAD %s - recomputing the control"
                  % (ctl_path, got.get("head", "?")[:8], head[:8]))

    print("=== 0. the control build: a pristine export, %d runner(s)%s ==="
          % (len(runners), "" if full else " - PARTIAL RUN"))
    control, bad = dict(state["control"]), []
    todo = [r for r in runners if r not in control]
    for r in control:
        print("  %-7s %4d checks (cached)" % (r, len(control[r])))
    root = os.path.join(tempfile.mkdtemp(prefix="pcmut_ctl_"), "tree")
    try:
        if todo:
            export(root, head)
            rebuild(root)
        for r in todo:
            # ⚠️ THE CONTROL IS RE-RUN BEFORE IT IS DECLARED BROKEN, and its
            # failing names are PRINTED. Measured: a pristine HEAD export
            # reported `hda 33 checks, 1 red` and aborted the whole sweep
            # without naming the row, then ran green on the next invocation
            # and green again when the export was reproduced by hand. This
            # machine carries another agent's hython and a live GUI session,
            # and several rows in these suites are WALL-CLOCK ceilings
            # (`bench_deform_20km`, `*_cost_is_flat_in_piece_count`) - a later
            # audit saw a pristine control go red on `bench_deform_20km`
            # TWICE in a row with a second hython on the machine, which a
            # single retry cannot ride out. Three attempts, and an operator
            # who cannot see WHICH check went red cannot tell a flake from a
            # real defect.
            for attempt in range(3):
                code, states, moved, _out = run(root, r)
                red = sorted(n for n, s in states.items() if s == "FAIL")
                if not (red or moved or code):
                    break
                print("  %-7s attempt %d: %d red %s, %d moved, exit %d"
                      % (r, attempt + 1, len(red), red[:6], moved, code))
            control[r] = states
            print("  %-7s %4d checks, %d red, %d moved, exit %d %s"
                  % (r, len(states), len(red), moved, code, red[:6] or ""))
            if red or moved or code:
                bad.append("%s: %d red %s, %d moved, exit %d"
                           % (r, len(red), red[:6], moved, code))
    finally:
        cleanup(os.path.dirname(root))
    if bad:
        # ⚠️ ASCII ONLY. This was the file's one printed non-ASCII string, and
        # `sys.stdout.encoding` is cp1252 on this machine whenever stdout is
        # redirected to a file or a pipe - so the one diagnostic the comment
        # block above calls essential died in a `UnicodeEncodeError` instead
        # of naming the check that went red. Observed live.
        print("\n!! THE CONTROL BUILD IS NOT GREEN - every verdict below is "
              "worthless until it is: %s" % "; ".join(bad))
        return 1

    state["control"] = control
    save()
    if ctl_path and not ctl_loaded:
        with open(ctl_path, "w") as fh:
            json.dump({"head": head, "control": control}, fh, indent=1)
    if "--control-only" in argv:
        print("control written to %s: %s"
              % (ctl_path, ", ".join("%s=%d" % (r, len(control[r]))
                                     for r in sorted(control))))
        return 0

    print("\n=== 1. the registered mutations ===")
    rows, proven = [], {}
    for mut in picked:
        t = time.time()
        cached = state["results"].get(mut.id) if only is None else None
        if cached and (len(cached) < 4 or cached[3] != digest(mut)):
            print("  ...  %-32s the registered entry changed since it was "
                  "cached - re-running it" % mut.id)
            cached = None
        if cached:
            verdict, detail, red = cached[0], cached[1] + " (cached)", set(
                cached[2])
        else:
            try:
                verdict, detail, red = execute(mut, control, head)
            except Exception as exc:                            # noqa: BLE001
                verdict, detail, red = "STALE", "%s: %s" % (
                    type(exc).__name__, str(exc)[:300]), set()
            state["results"][mut.id] = [verdict, detail, sorted(red),
                                        digest(mut)]
            save()
        if verdict == "ABORT" and mut.expect == "abort":
            verdict = "RED(abort, declared)"
        ok = verdict.startswith("RED")
        for name in mut.kills:
            # ⚠️ ONLY THE DECLARED PAIRING IS CREDITED, and keyed BY RUNNER.
            # `corner_abut_m` exists in `scene`, `2d` AND `images`, and a
            # mutation that reddens the scene copy says nothing about the
            # other two.  The same argument forbids crediting the rest of the
            # blast radius: a mutation is evidence about the check it was
            # PAIRED with and examined against, not about the forty names that
            # happened to go red downstream of it.
            if name in red:
                proven.setdefault("%s/%s" % (mut.runner, name),
                                  []).append(mut.id)
        rows.append((mut, verdict, detail, ok))
        print("  [%s] %-32s %-8s %5.0fs  %s"
              % ("ok" if ok else "!!", mut.id, verdict, time.time() - t,
                 detail))

    print("\n=== 2. coverage - every check name, PROVEN / EXEMPT / UNPROVEN "
          "%s===" % ("" if full else "(PARTIAL RUN) "))
    gaps, miscount, skipped_all = [], [], []
    for r in runners:
        names = ["%s/%s" % (r, n) for n in sorted(control[r])]
        p = [n for n in names if n in proven]
        e = [n for n in names if n not in proven and n in REG.EXEMPT]
        u = [n for n in names if n not in proven and n not in REG.EXEMPT
             and n in REG.UNPROVEN]
        g = [n for n in names if n not in proven and n not in REG.EXEMPT
             and n not in REG.UNPROVEN]
        # A name that is SKIPPED on every case it appears in is not a check
        # that passed - it is retrospective P2, "the check is well written;
        # nothing ever runs it", and it read as an ordinary inventory row.
        s = sorted(n for n in control[r] if control[r][n] == "SKIP")
        skipped_all += ["%s/%s" % (r, n) for n in s]
        gaps += g
        print("  %-7s %4d checks: %3d proven, %3d exempt, %3d unproven, "
              "%3d UNDECLARED, %3d always skipped"
              % (r, len(names), len(p), len(e), len(u), len(g), len(s)))
        # ⚠️ AND THE INVENTORY IS PINNED.  A check that stops being emitted
        # was silently DELETED from the meta-check: filtering `cell_grid` out
        # of every 2d case took the control from 40 names to 39, and the
        # sweep reported `0 UNDECLARED` and exited 0 while `2d/cell_grid` sat
        # in the debt list describing a check that no longer existed.  Growth
        # already failed the run (UNDECLARED); this is the other direction.
        expect = REG.EXPECT_CHECKS.get(r)
        if expect is not None and expect != len(names):
            miscount.append("%s: %d checks, %d declared in "
                            "mutations.EXPECT_CHECKS" % (r, len(names), expect))
    if skipped_all:
        print("\n  --- always skipped: printed, never executed (%d) ---"
              % len(skipped_all))
        for n in skipped_all:
            print("    " + n)
    if REG.UNPROVEN:
        print("\n  --- declared debt (%d) ---" % len(REG.UNPROVEN))
        for n in sorted(REG.UNPROVEN):
            print("    %-44s %s" % (n, REG.UNPROVEN[n]))
    # ⚠️ AND THE DECLARATIONS ARE RECONCILED AGAINST THE INVENTORY, both ways.
    # Nothing checked that an EXEMPT or UNPROVEN key still NAMES a live check,
    # so 11 entries described checks no runner prints any more - and
    # `scene/conform_parity` sat in the debt list as "no mutation yet" while
    # being the declared kill of `conform_drop_biased_py`. A debt list that
    # can rot is not a debt list. Only a full sweep can judge this: a partial
    # run has no inventory for the runners it skipped.
    dead, stale = [], []
    if full:
        live = set()
        for r in runners:
            live |= set("%s/%s" % (r, n) for n in control[r])
            live.add("%s/%s" % (r, REG.BASELINE_MOVED))
        dead = sorted(k for k in list(REG.EXEMPT) + list(REG.UNPROVEN)
                      if k not in live)
        stale = sorted(k for k in REG.UNPROVEN if k in proven)
        if dead:
            print("\n  --- DEAD DECLARATIONS: named in EXEMPT/UNPROVEN, "
                  "printed by no runner (%d) ---" % len(dead))
            for n in dead:
                print("    " + n)
        if stale:
            print("\n  --- STALE DEBT: has a registered mutation, still "
                  "listed as debt (%d) ---" % len(stale))
            for n in stale:
                print("    %-44s proven by %s" % (n, ", ".join(proven[n])))
    if miscount:
        print("\n  --- INVENTORY SHRANK (%d) ---" % len(miscount))
        for m in miscount:
            print("    " + m)
    if gaps:
        print("\n  --- UNDECLARED: no mutation, no exemption, no debt entry "
              "(%d)%s ---"
              % (len(gaps), "" if full else " - PARTIAL RUN, so these are "
                 "names proven by mutations this run did not select; they do "
                 "NOT fail it"))
        for n in gaps:
            print("    " + n)
        if "--emit-unproven" in argv:
            # Paste into `mutations.UNPROVEN`. The names are the debt; the
            # reason is shared and dated, because a hand-written sentence
            # repeated 200 times is noise, not justification. An EXEMPTION is
            # the thing that needs its own line.
            print("\nUNPROVEN.update(dict.fromkeys((")
            for n in gaps:
                print('    "%s",' % n)
            print('), "no mutation yet"))')

    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as fh:
            json.dump([{"id": m.id, "runner": m.runner, "verdict": v,
                        "detail": d, "ok": bool(ok), "kills": list(m.kills)}
                       for m, v, d, ok in rows], fh, indent=1)

    failed = [m.id for m, _v, _d, ok in rows if not ok]
    print("\n%d mutations: %d reddened their paired check, %d did not (%s). "
          "%d undeclared check names, %d dead declarations, %d stale debt "
          "entries, %d shrunken inventories. %s. %.0f s"
          % (len(rows), len(rows) - len(failed), len(failed),
             ", ".join(failed) or "none", len(gaps), len(dead), len(stale),
             len(miscount),
             "FULL SWEEP" if full else "PARTIAL RUN - coverage is not "
             "comparable to a full sweep and cannot fail this run",
             time.time() - t0))
    return 1 if (failed or dead or stale or miscount
                 or (gaps and full)) else 0


if __name__ == "__main__":
    sys.exit(main())
