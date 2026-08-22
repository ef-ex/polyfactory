"""The VEX sources for polyChain's node network, loaded and inlined.

The wrangles live in `polyfactory/vex/polychain/*.vfl` as real files - version
controlled, diffable, syntax-highlighted, and readable by an artist who dives
into the HDA and middle-clicks a wrangle.  They are INLINED into the snippet
parms at build time rather than `#include`d at cook time, so the shipped asset
carries no dependency on `HOUDINI_VEX_PATH` being set (hython does not set it -
dev-loop trap list).

This module is TOOLING, not a cook path: it reads text files and returns
strings.  Nothing here touches geometry.
"""

import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
# polyfactory/scripts/python/polyfactory/polychain -> polyfactory/vex/polychain
VEX_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "..", "..", "vex", "polychain")).replace("\\", "/")

_INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"\s*$', re.M)


def _read(name):
    path = os.path.join(VEX_DIR, name).replace("\\", "/")
    with io.open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def source(name, _seen=None):
    """The snippet for `name` (with or without `.vfl`), includes expanded once.

    An include seen twice is dropped rather than repeated - VEX has no include
    guards inside a snippet, and two copies of `pc_bisect_right` is a redefine
    error, not a warning.
    """
    seen = set() if _seen is None else _seen
    if not name.endswith((".vfl", ".h")):
        name += ".vfl"
    text = _read(name)

    def swap(match):
        inc = match.group(1)
        if inc in seen:
            return "// (%s already inlined above)" % inc
        seen.add(inc)
        return source(inc, seen)

    return _INCLUDE.sub(swap, text)
