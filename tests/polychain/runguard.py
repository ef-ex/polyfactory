"""TWO STRUCTURAL PROTECTIONS FOR THE PARALLEL RUNNERS - `begin`, `safe_slots`.

Both incidents belong to `ideas/build_retrospective.md` 2c #11 and are not
retold here: fifteen concurrent hythons HARD-FROZE this machine twice, and five
days of headless sessions left 19.9 GB of orphaned temp on a 6 GB-free drive.

(1) `safe_slots` - lowering the default to 4 was a NUMBER, not a protection;
    the count is decided against the headroom the OS will actually grant.
(2) `begin` - HOUDINI_TEMP_DIR, and TEMP/TMP where `tempfile.mkdtemp` puts
    the export trees, point inside `.tmp/` on the repo's own roomy drive, and
    every hython inherits it.  Deleted at exit; because A CRASHED RUN CANNOT
    CLEAN ITSELF, a run first sweeps what a dead one left.

WHAT THIS CANNOT SEE.  Whether 8 GB a slot is right - one Houdini runtime's
committed peak rounded up.  Nor a process ignoring the environment it was
handed, nor a run alive past 24 h, whose directory `sweep` takes for an orphan.
"""

import atexit
import os
import shutil
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TMP = os.path.join(REPO, ".tmp").replace("\\", "/")
GB = 1 << 30
PER_SLOT = 8 * GB
ORPHAN_AGE_S = 24 * 3600


def commit_headroom():
    """Bytes the OS will still COMMIT, or None where it cannot be asked.
    Commit, not free RAM: Windows charges every reservation against physical +
    pagefile touched or not, and the COMMIT LIMIT is what ran out with ~100 GB
    of RAM nominally free.  `ctypes`: nothing new installed."""
    if os.name != "nt":
        return None
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in
            ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
             "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual",
             "ullAvailExtendedVirtual")]

    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    return int(m.ullAvailPageFile)


def safe_slots(requested, headroom=None, per_slot=PER_SLOT):
    """-> (slots, one line naming the numbers it was decided on).
    ⚠️ `headroom` IS INJECTABLE BECAUSE THE FAILURE CANNOT BE REPRODUCED ON
    PURPOSE: freezing the machine to prove the guard bites is not a test, and
    without the parameter this file is unfalsifiable on every machine healthy
    enough to run the suite - which is every machine that does.
    """
    if headroom is None:
        headroom = commit_headroom()
    if headroom is None:
        return requested, ("commit headroom cannot be read on %r - %d slot(s) "
                           "unchanged" % (os.name, requested))
    fits = int(headroom // per_slot)
    where = "%.1f GB commit headroom / %.1f GB per slot = %d" % (
        headroom / float(GB), per_slot / float(GB), fits)
    if fits < 1:
        raise SystemExit(
            "REFUSED: %s. Fifteen hythons froze this machine twice; four on a "
            "machine with no commit headroom would do it again. Close "
            "something, or grow the pagefile." % where)
    return (min(fits, requested),
            "%s - %d requested, %s" % (where, requested,
                                       "SHRUNK" if fits < requested
                                       else "granted"))


def sweep(root=TMP, now=None, max_age_s=ORPHAN_AGE_S):
    """Delete run dirs an earlier run did not live to delete.  -> names.
    Age is the dir's own mtime, which Windows moves on every entry added or
    removed - so a live run keeps refreshing its own."""
    now = time.time() if now is None else now
    gone = []
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        path = os.path.join(root, name)
        if not name.startswith("run_") or not os.path.isdir(path):
            continue
        if now - os.path.getmtime(path) <= max_age_s:
            continue
        shutil.rmtree(path, ignore_errors=True)
        gone.append(name)
    return gone


def begin(root=TMP, now=None, max_age_s=ORPHAN_AGE_S):
    """Sweep orphans, claim a per-run directory, export it.  -> (dir, swept).
    ⚠️ IDEMPOTENT ACROSS A PROCESS TREE: the work items inherit this
    environment, so a child calling `begin` again would claim a second dir AND
    register an `atexit` deleting the one its siblings are writing into."""
    have = os.environ.get("HOUDINI_TEMP_DIR", "").replace("\\", "/")
    if have.startswith(root + "/"):
        return have, []
    swept = sweep(root, now, max_age_s)
    run = os.path.join(root, "run_%d_%d" % (time.time(), os.getpid())) \
        .replace("\\", "/")
    os.makedirs(run)
    for var in ("HOUDINI_TEMP_DIR", "TEMP", "TMP"):
        os.environ[var] = run
    atexit.register(shutil.rmtree, run, True)
    return run, swept
