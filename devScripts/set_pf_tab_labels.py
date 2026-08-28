"""Every polyfactory tool carries the `PF ` prefix in the TAB menu.

    hython devScripts/set_pf_tab_labels.py            # CHECK: report, exit 1 if wrong
    hython devScripts/set_pf_tab_labels.py --apply    # FIX: rewrite the labels

The TAB entry shows an HDA's DESCRIPTION (`Tools.shelf` substitutes it as
`$HDA_LABEL`), and the suite had drifted: 39 of 57 definitions read `PF <Name>`
while the rest read `Ring`, `polyChain Facade`, `CityGen Solver`,
`Connectivity Plus`, `Asset Placement` - and one `Pf Save Asset` with the
prefix miscased. Typing "pf" in the TAB menu therefore did not find the suite.

Run with no argument it is a CHECK and exits non-zero on anything that would
move, so it can go in the gate; `--apply` is the only thing that writes.
Idempotent either way - `PF Box` maps to itself.

⚠️ `hou.HDADefinition.setDescription()` WRITES THROUGH TO THE .hda FILE
IMMEDIATELY - verified here by setting a probe value and reading it back in a
separate process. There is no separate save step and no undo, so the check
mode is the default and `--apply` has to be asked for.

NOT ours to rename: definitions in a foreign namespace. `efex::normalizemesh`
and `efex::scale_to_one` live in `otls/` but belong to another package, and
prefixing another vendor's tool with ours would be a lie about where it came
from. They are listed as skipped rather than silently passed over.
"""

import glob
import os
import sys

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
OTLS = os.path.join(_POLYFACTORY, "otls").replace("\\", "/")

PREFIX = "PF "
FOREIGN = ("efex::",)


def wanted(description):
    """The label this tool should carry. Idempotent, and it repairs a prefix
    that is present but miscased (`Pf Save Asset`)."""
    d = description.strip()
    if d[:3].lower() == PREFIX.lower():
        return PREFIX + d[3:].lstrip()
    return PREFIX + d


def main():
    apply_it = "--apply" in sys.argv
    moves, skipped, kept = [], [], 0

    for path in sorted(glob.glob(OTLS + "/*.hda")):
        for defn in hou.hda.definitionsInFile(path.replace("\\", "/")):
            name = defn.nodeTypeName()
            if any(name.startswith(f) for f in FOREIGN):
                skipped.append((name, defn.description()))
                continue
            cur = defn.description()
            new = wanted(cur)
            if new == cur:
                kept += 1
                continue
            moves.append((name, cur, new, defn))

    for name, cur, new, defn in moves:
        print("  %-34s %-28s -> %s" % (name, repr(cur), repr(new)))
        if apply_it:
            defn.setDescription(new)

    for name, desc in skipped:
        print("  SKIPPED (foreign namespace) %-24s %r" % (name, desc))

    print("\n%d already correct, %d %s, %d skipped"
          % (kept, len(moves), "relabelled" if apply_it else "WRONG", len(skipped)))

    if apply_it:
        # Read every definition back off disk - the build script's rule, and
        # the only thing that proves setDescription reached the file.
        bad = []
        for path in sorted(glob.glob(OTLS + "/*.hda")):
            for defn in hou.hda.definitionsInFile(path.replace("\\", "/")):
                if any(defn.nodeTypeName().startswith(f) for f in FOREIGN):
                    continue
                if not defn.description().startswith(PREFIX):
                    bad.append((defn.nodeTypeName(), defn.description()))
        if bad:
            print("\nSTILL WRONG AFTER WRITING:")
            for name, desc in bad:
                print("  %-34s %r" % (name, desc))
            return 1
        print("verified on disk: every polyfactory label starts with %r" % PREFIX)
        return 0

    return 1 if moves else 0


if __name__ == "__main__":
    sys.exit(main())
