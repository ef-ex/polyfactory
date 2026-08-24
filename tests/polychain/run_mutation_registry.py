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
     rule 1, mechanised.

Exit code is 0 only if all three hold.
"""

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

LINE = re.compile(r"^\s*\[(PASS|FAIL|SKIP)\]\s+([A-Za-z_0-9]+)")
MOVED = re.compile(r"(\d+) moved baseline values")


# --- the throwaway copy ------------------------------------------------------

def export(dest):
    """`git archive HEAD` into `dest`.  Read-only against the real repo."""
    assert os.path.abspath(dest) != os.path.abspath(REPO)
    os.makedirs(dest)
    tar = subprocess.Popen(["tar", "-x", "-C", dest], stdin=subprocess.PIPE)
    arc = subprocess.Popen(["git", "archive", "HEAD"], cwd=REPO,
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
    states, moved = {}, 0
    for line in out.splitlines():
        m = LINE.match(line)
        if m:
            state, name = m.group(1), m.group(2)
            # A name that fails ANYWHERE is red: the scene runners print the
            # same check once per case.
            if states.get(name) != "FAIL":
                states[name] = state
        m = MOVED.search(line)
        if m:
            moved = int(m.group(1))
    return p.returncode, states, moved, out


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


def execute(mut, control):
    """One mutation, in its own export.  -> (verdict, detail, reddened set)"""
    root = tempfile.mkdtemp(prefix="pcmut_")
    root = os.path.join(root, "tree")
    try:
        export(root)
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
        return ("RED", "%d red, %d unreached, exit %d"
                % (len(red), len(missing), code), red)
    finally:
        shutil.rmtree(os.path.dirname(root), ignore_errors=True)


# --- the run -----------------------------------------------------------------

def main():
    argv = sys.argv[1:]
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
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

    runners = sorted(set(m.runner for m in picked))
    t0 = time.time()

    print("=== 0. the control build: a pristine export, all four runners ===")
    control, bad = {}, []
    root = os.path.join(tempfile.mkdtemp(prefix="pcmut_ctl_"), "tree")
    try:
        export(root)
        rebuild(root)
        for r in runners:
            code, states, moved, _out = run(root, r)
            red = sorted(n for n, s in states.items() if s == "FAIL")
            # ⚠️ THE CONTROL IS RE-RUN ONCE BEFORE IT IS DECLARED BROKEN, and
            # its failing names are PRINTED. Measured: a pristine HEAD export
            # reported `hda 33 checks, 1 red` and aborted the whole sweep
            # without naming the row, then ran green on the next invocation
            # and green again when the export was reproduced by hand. This
            # machine carries another agent's hython and a live GUI session,
            # and several rows in these suites are timings. A sweep that a
            # timing flake can silently invalidate is worse than one that
            # costs a second control build - and an operator who cannot see
            # WHICH check went red cannot tell a flake from a real defect.
            if red or moved or code:
                print("  %-7s retrying the control: %d red %s, %d moved, "
                      "exit %d" % (r, len(red), red[:6], moved, code))
                code, states, moved, _out = run(root, r)
                red = sorted(n for n, s in states.items() if s == "FAIL")
            control[r] = states
            print("  %-7s %4d checks, %d red, %d moved, exit %d %s"
                  % (r, len(states), len(red), moved, code, red[:6] or ""))
            if red or moved or code:
                bad.append("%s: %d red %s, %d moved, exit %d"
                           % (r, len(red), red[:6], moved, code))
    finally:
        shutil.rmtree(os.path.dirname(root), ignore_errors=True)
    if bad:
        print("\n⚠️ THE CONTROL BUILD IS NOT GREEN - every verdict below is "
              "worthless until it is: %s" % "; ".join(bad))
        return 1

    print("\n=== 1. the registered mutations ===")
    rows, proven = [], {}
    for mut in picked:
        t = time.time()
        try:
            verdict, detail, red = execute(mut, control)
        except Exception as exc:                                # noqa: BLE001
            verdict, detail, red = "STALE", "%s: %s" % (
                type(exc).__name__, str(exc)[:300]), set()
        if verdict == "ABORT" and mut.expect == "abort":
            verdict = "RED(abort, declared)"
        ok = verdict.startswith("RED")
        for name in red:
            proven.setdefault(name, []).append(mut.id)
        rows.append((mut, verdict, detail, ok))
        print("  [%s] %-32s %-8s %5.0fs  %s"
              % ("ok" if ok else "!!", mut.id, verdict, time.time() - t,
                 detail))

    print("\n=== 2. coverage - every check name, PROVEN / EXEMPT / UNPROVEN ===")
    gaps = []
    for r in runners:
        names = sorted(control[r])
        p = [n for n in names if n in proven]
        e = [n for n in names if n not in proven and n in REG.EXEMPT]
        u = [n for n in names if n not in proven and n not in REG.EXEMPT
             and n in REG.UNPROVEN]
        g = [n for n in names if n not in proven and n not in REG.EXEMPT
             and n not in REG.UNPROVEN]
        gaps += ["%s/%s" % (r, n) for n in g]
        print("  %-7s %4d checks: %3d proven, %3d exempt, %3d unproven, "
              "%3d UNDECLARED" % (r, len(names), len(p), len(e), len(u),
                                  len(g)))
    if REG.UNPROVEN:
        print("\n  --- declared debt (%d) ---" % len(REG.UNPROVEN))
        for n in sorted(REG.UNPROVEN):
            print("    %-44s %s" % (n, REG.UNPROVEN[n]))
    if gaps:
        print("\n  --- UNDECLARED: no mutation, no exemption, no debt entry "
              "(%d) ---" % len(gaps))
        for n in gaps:
            print("    " + n)
        if "--emit-unproven" in argv:
            # Paste into `mutations.UNPROVEN`. The names are the debt; the
            # reason is shared and dated, because a hand-written sentence
            # repeated 200 times is noise, not justification. An EXEMPTION is
            # the thing that needs its own line.
            print("\nUNPROVEN.update(dict.fromkeys((")
            for n in gaps:
                print('    "%s",' % n.split("/", 1)[1])
            print('), "no mutation yet"))')

    failed = [m.id for m, _v, _d, ok in rows if not ok]
    print("\n%d mutations: %d reddened their paired check, %d did not (%s). "
          "%d undeclared check names. %.0f s"
          % (len(rows), len(rows) - len(failed), len(failed),
             ", ".join(failed) or "none", len(gaps), time.time() - t0))
    return 1 if (failed or gaps) else 0


if __name__ == "__main__":
    sys.exit(main())
