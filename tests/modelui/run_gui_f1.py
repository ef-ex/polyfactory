"""Run the modelUI F1 GUI checks (gui_f1.py) in a throwaway Houdini and judge them.

    python tests/modelui/run_gui_f1.py

Isolation: its own HOUDINI_USER_PREF_DIR (a copy of the top-level *.pref files of Hannes' prefs, read only) and a
packages folder with only the polyfactory package (not the MCP bridge), both in F:/cache/modelui/f1/gui. The window
goes off screen; on a timeout only the launched process tree is killed.
Exit 0 = both baselines (first and last run) all green, every mutation red on its paired check, every check paired
or listed in EXEMPT with its reason.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
SCR = os.environ.get("PF_F1_SCRATCH", "F:/cache/modelui/f1/gui")   # auditors: set your own folder
HOUDINI = "C:/Program Files/Side Effects Software/Houdini 22.0.442/bin/houdini.exe"
EXEMPT = {"toggle_key_registered": "registered by uiready.py at startup; a mutation needs a second launch"}


def main():
    shutil.rmtree(SCR, ignore_errors=True)
    # the C++ mutation: the filter without its window-receiver test, built beside the scratch folder
    mut = os.path.normpath(SCR + "_mut")   # beside the run's own folder: parallel runs never share it
    os.makedirs(mut, exist_ok=True)
    afdir = os.path.join(REPO, "polyfactory", "scripts", "python", "polyfactory", "modelui", "appfilter")
    with open(os.path.join(afdir, "appfilter.cpp")) as f:
        src = f.read()
    snip = "        if (!receiver->isWindowType())\n            return false;\n"
    if src.count(snip) != 1:
        print("C++ mutation snippet not found once")
        return 1
    with open(os.path.join(mut, "appfilter_nowindow.cpp"), "w") as f:
        f.write(src.replace(snip, ""))
    r = subprocess.run(["cmd", "/c", os.path.join(afdir, "build.bat"), os.path.join(mut, "appfilter_nowindow.cpp"),
                        os.path.join(mut, "pf_appfilter_nowindow.dll")], capture_output=True, text=True)
    if r.returncode:
        print("mutated DLL build failed:", r.stdout[-2000:], r.stderr[-2000:])
        return 1
    prefs = SCR + "/prefs/houdini__HVER__"
    pv = prefs.replace("__HVER__", "22.0")
    os.makedirs(pv + "/packages")
    real = os.path.join(os.path.expanduser("~"), "Documents", "houdini22.0")
    for f in os.listdir(real):
        if f.endswith(".pref") and os.path.isfile(os.path.join(real, f)):
            shutil.copy2(os.path.join(real, f), pv)
    with open(pv + "/packages/polyfactory.json", "w") as f:
        json.dump({"env": [{"POLYFACTORY": REPO.replace("\\", "/") + "/polyfactory"}], "path": "$POLYFACTORY"}, f)
    env = dict(os.environ)
    env.pop("HOUDINI_PATH", None)
    if os.environ.get("PF_GUI_SCRIPT", "gui_f1.py") == "gui_f1.py":
        env["PF_MODELUI_DEMO"] = "1"   # the F1 checks use the demo gesture; it is not installed otherwise
    env.update(PF_F1_MUT_DLL=os.path.join(mut, "pf_appfilter_nowindow.dll").replace("\\", "/"),
               HOUDINI_USER_PREF_DIR=prefs, HOUDINI_PACKAGE_DIR=pv + "/packages", PF_F1_OUT=SCR + "/result.json")
    console = open(SCR + "/console.txt", "w")
    p = subprocess.Popen([HOUDINI, "-foreground", os.path.join(HERE, os.environ.get("PF_GUI_SCRIPT", "gui_f1.py"))], env=env, stdout=console,
                         stderr=subprocess.STDOUT)
    try:
        p.wait(timeout=1500)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)])
        print("TIMEOUT: killed the test Houdini (pid %d); log: %s" % (p.pid, SCR + "/result.json.log"))
        return 1
    if not os.path.exists(SCR + "/result.json"):
        print("no result; log:", SCR + "/result.json.log")
        return 1
    with open(SCR + "/result.json") as f:
        res = json.load(f)
    bad, names, paired = [], set(), set()
    base = [r for r in res if r["mutation"] is None]
    for i, r in enumerate(base):
        for k, v in r["out"].items():
            names.add(k)
            print("baseline%d %-28s %s" % (i, k, "ok" if v is True else "RED %s" % str(v)[-300:]))
            if v is not True:
                bad.append("baseline%d %s" % (i, k))
    for r in res:
        if r["mutation"] is None:
            continue
        paired.add(r["check"])
        v = r["out"].get(r["check"])
        how = "red" if v is False else ("red by exception" if "_exception" in r["out"] else "red (%s)" % v)
        print("mutation %-26s -> %-28s %s" % (r["mutation"], r["check"], "STILL GREEN" if v is True else how))
        if v is not False:   # credited only when the paired check itself evaluated False (not an earlier exception)
            bad.append("mutation " + r["mutation"])   # a mutation that could not be applied proves nothing
        if "_exception" in r["out"]:
            print("    " + r["out"]["_exception"].strip().splitlines()[-1])
    unpaired = names - paired - set(EXEMPT)
    if len(base) != 2 or unpaired:
        bad.append("baselines %d, unpaired %s" % (len(base), sorted(unpaired)))
    for k, why in EXEMPT.items():
        print("exempt %s: %s" % (k, why))
    print("FAIL" if bad else "PASS", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
