"""Author the CityGen style templates.

    hython devScripts/create_pf_building_styles.py

Writes `polyfactory/library/citygen/styles/<styleId>.geo`, each one a Houdini
geometry file carrying the whole template as a single detail DICTIONARY
attribute `pf_style_template` - the storage format §12.12 left to "the first
template authored decides", decided in `citygen/buildings.py`.

⚠️ A TEMPLATE IS DATA.  Nothing here is imported at cook time and nothing in
the generator may import it.  This script is the authoring surface until an
artist-facing one exists (`artist_ui.md`), which is why the declarations below
are a plain dict per style and read top to bottom.

⚠️ EVERY NUMBER CARRIES ITS SOURCE (§12.5: `sources` is a provenance list, and
this file's evidence-ledger discipline applies to style data too).  "Start
realistic, end artistic" (`citygen.md` §2.0): these are DEFAULTS taken from
measured vernacular, never limits - the cascade overrides every one of them.

THE FOUR STYLES ARE CHOSEN TO CROSS THE ROWS, not to cover a catalogue.
`at_einhof` and `at_vienna_perimeter` are gate G1's two required subjects and
differ in every row under test.  `at_vierkanthof` and `at_zinshaus_row` exist
to falsify the gate: a farm built on the perimeter block's `ring` rule and a
Viennese apartment house built on the farmhouse's `bar` rule.  If either had
needed a code change, `volumeTopology` would not be data.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "polyfactory", "library", "citygen",
                   "styles").replace("\\", "/")

VERNACULAR_AT = ("https://de.wikipedia.org/wiki/Einhof",
                 "https://de.wikipedia.org/wiki/Streckhof")
VIERKANT = ("https://de.wikipedia.org/wiki/Vierkanthof",)
GRUENDERZEIT = ("https://de.wikipedia.org/wiki/Wiener_Zinshaus",
                "https://de.wikipedia.org/wiki/Gr%C3%BCnderzeit")

STYLES = [
    {
        "styleId": "at_einhof",
        "version": 1,
        "sources": list(VERNACULAR_AT),
        "storeyHeightM": 2.5,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 3.0,
            "setbackM": {"front": 8.0, "sideStreet": 3.0,
                         "interiorSide": 3.0, "rear": 12.0},
        },
        "volumeTopology": {
            "rails": "bar",
            "cutsAt": [0.42, 0.66],
            "courtyardDepthM": 0.0,
            "volumes": [
                {"role": "dwelling", "storeys": 2, "capGroup": 0},
                {"role": "stable", "storeys": 1, "storeyHeightM": 5.0,
                 "capGroup": 0},
                {"role": "barn", "storeys": 1, "storeyHeightM": 5.0,
                 "capGroup": 0},
            ],
            "plinth": {"mode": "levelToHighest", "minM": 0.4},
        },
        "capFamily": {"family": "skeletonRoof", "pitchDeg": 45.0,
                      "eaveDepthM": 0.8},
    },
    {
        "styleId": "at_vienna_perimeter",
        "version": 1,
        "sources": list(GRUENDERZEIT),
        "storeyHeightM": 3.3,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 0.0,
            "setbackM": {"front": 0.0, "sideStreet": 0.0, "rear": 0.0},
        },
        "volumeTopology": {
            "rails": "ring",
            "cutsAt": [],
            "courtyardDepthM": 14.0,
            "volumes": [
                {"role": "vorderhaus", "storeys": 5, "storeyHeightM": 3.6,
                 "capGroup": 0},
                {"role": "seitentrakt", "storeys": 4, "capGroup": 1},
                {"role": "hoftrakt", "storeys": 4, "capGroup": 1},
                {"role": "seitentrakt", "storeys": 4, "capGroup": 1},
            ],
            "plinth": {"mode": "none", "minM": 0.0},
        },
        "capFamily": {"family": "parapet", "parapetM": 0.9},
    },
    {
        "styleId": "at_vierkanthof",
        "version": 1,
        "sources": list(VIERKANT),
        "storeyHeightM": 2.6,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 4.0,
            "setbackM": {"front": 6.0, "interiorSide": 4.0, "rear": 6.0},
        },
        "volumeTopology": {
            "rails": "ring",
            "cutsAt": [],
            "courtyardDepthM": 12.0,
            "volumes": [
                {"role": "dwelling", "storeys": 2, "capGroup": 0},
                {"role": "stable", "storeys": 1, "storeyHeightM": 5.2,
                 "capGroup": 0},
                {"role": "barn", "storeys": 1, "storeyHeightM": 5.2,
                 "capGroup": 0},
                {"role": "granary", "storeys": 2, "capGroup": 0},
            ],
            "plinth": {"mode": "levelToHighest", "minM": 0.4},
        },
        "capFamily": {"family": "skeletonRoof", "pitchDeg": 38.0,
                      "eaveDepthM": 0.6},
    },
    {
        "styleId": "at_zinshaus_row",
        "version": 1,
        "sources": list(GRUENDERZEIT),
        "storeyHeightM": 3.3,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 0.0,
            "setbackM": {"front": 0.0, "abuts": 0.0, "rear": 0.0},
        },
        "volumeTopology": {
            "rails": "bar",
            "cutsAt": [0.55],
            "courtyardDepthM": 0.0,
            "volumes": [
                {"role": "vorderhaus", "storeys": 5, "storeyHeightM": 3.6,
                 "capGroup": 0},
                {"role": "hoftrakt", "storeys": 4, "capGroup": 1},
            ],
            "plinth": {"mode": "none", "minM": 0.0},
        },
        "capFamily": {"family": "parapet", "parapetM": 0.9},
    },
]


def main():
    import hou
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for style in STYLES:
        geo = hou.Geometry()
        geo.addAttrib(hou.attribType.Global, "pf_style_template", {},
                      create_local_variable=False)
        geo.setGlobalAttribValue("pf_style_template", style)
        path = os.path.join(OUT, style["styleId"] + ".geo").replace("\\", "/")
        geo.saveToFile(path)
        print("wrote %-44s %5d bytes" % (path, os.path.getsize(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
