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
# hython does not load the polyfactory package (dev-loop trap list), and this
# script needs exactly one thing from it: the storability guard that owns the
# format decision, so the rule lives with the format and not with each caller.
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts", "python"))

# ⚠️ TWO NUMBERS WERE REJECTED RATHER THAN COMMITTED, and they are recorded
# here so nobody re-adds them: a "Wirtschaftsteil = 1.5-1.6x Wohnteil" ratio
# for the Einhof, and a "typical Viennese block of 55 m x 140 m". Both came
# back from search with confident attributions; both were chased into the
# pages they were attributed to and appear in NEITHER. An unsourced field
# below says UNSOURCED. It does not say a plausible number.

ZSABETICH = ("Zsabetich, Streckhoefe des Nordburgenlandes, TU Wien 2019 - "
             "https://repositum.tuwien.at/bitstream/20.500.12708/10488/2/"
             "Zsabetich%20Julia%20-%202019%20-%20Streckhoefe%20des%20"
             "Nordburgenlandes%20eine%20gefaehrdete...pdf")
BAUNETZ = ("BauNetz Wissen, Wohnhaus Streckhof in Weingraben - "
           "https://www.baunetzwissen.de/geneigtes-dach/objekte/wohnen/"
           "wohnhaus-streckhof-in-weingraben-6461652")
OOE = ("Forum OOe Geschichte, Die Vierkanter - "
       "https://www.ooegeschichte.at/archiv/themen/wir-oberoesterreicher/"
       "die-vierkanter")
VK_WIKI = "Wikipedia Vierkanthof - https://de.wikipedia.org/wiki/Vierkanthof"
VK_FORUM = ("Austria-Forum, Vierkanthof - "
            "https://austria-forum.org/af/AustriaWiki/Vierkanthof")
VK_GARSTEN = ("Vierkanter 'Mayr auf der Wim', Garsten OOe, measured - "
              "https://www.nextroom.at/article.php?id=42271")
VK_MUSEUM = ("Volkskundemuseum Wien, Vierkanthof model OEMV/41080 - "
             "https://www.volkskundemuseum.at/onlinesammlungen/oemv41080")
BRAUN = ("Braun, Souterrain Hochparterre - Die Halbgeschosse der Wiener "
         "Gruenderzeit, TU Wien 2024 (quotes Bauordnung fuer Wien 1883 "
         "§42 and 1829 §23) - https://repositum.tuwien.at/bitstream/"
         "20.500.12708/196379/1/Braun%20Andrea%20-%202024%20-%20Souterrain"
         "%20Hochparterre%20-%20Die%20Halbgeschosse%20der...pdf")
OEAW = ("OEAW, Gruenderzeitliche Wohnhaustypen Wiens - "
        "https://epub.oeaw.ac.at/0xc1aa5576_0x003df00e.pdf")
FIERRO = ("Fierro, Ganzheitliche Modernisierung von Gruenderzeitbauten, "
          "TU Wien 2023 (Wiener Dachstuhl span and pitch) - "
          "https://repositum.tuwien.at/bitstream/20.500.12708/176593/1/"
          "Fierro%20Alan%20Andres%20-%202023%20-%20Ganzheitliche%20"
          "Modernisierung%20von%20Gruenderzeitbauten...pdf")

STYLES = [
    {
        "styleId": "at_einhof",
        "version": 1,
        "sources": [
            "TYPE: Streckhof, Nordburgenland. Wohnhaus -> Stall -> Scheune "
            "in one line, gable to the street. " + BAUNETZ,
            "footprint width 5.0 m: SOURCED, stated twice independently - "
            "'Die Haeuser sind 20 Meter lang und 5 Meter breit, das ist "
            "sozusagen der Standard'. " + ZSABETICH,
            "dwelling length 20 m of a 45 m bar (cut 0.444): SOURCED for the "
            "20 m; the same sentence continues '...und dann reihen sich "
            "aussen die Neben- und Wirtschaftsraeume hinten an', so 20 m is "
            "the WOHNTEIL, not the whole hof. " + ZSABETICH,
            "second cut 0.722 (stable vs barn): UNSOURCED. No ratio between "
            "Stall and Scheune was found in any source; a claimed 1.5-1.6x "
            "was traced to the pages it was attributed to and is not there. "
            "Split evenly, pending evidence.",
            "storeys 1 (ebenerdig): SOURCED as the original form - upper "
            "floors are documented post-war additions. " + ZSABETICH,
            "storeyHeightM 3.0: UNSOURCED. No Burgenland vernacular room "
            "height was found; modern Austrian code minima (2.50 m) must "
            "not be backdated.",
            "roof Satteldach, gable to the street, pitch 45 deg: TYPE "
            "sourced ('Satteldach mit zur Strasse orientiertem Giebel'); "
            "the ANGLE is not sourced for this type. 45 deg is the "
            "Regeldachneigung for thatch, which constrains the straw-roofed "
            "originals, and is used here as a flagged proxy. " + ZSABETICH,
            "plinth minM 0.4: UNSOURCED. Nothing dimensional about Sockel "
            "or building on slopes was found; the RULE is kept because "
            "slope adaptation is a §12.6 B2 requirement, the NUMBER is a "
            "placeholder the cascade overrides.",
        ],
        "storeyHeightM": 3.0,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 2.5,
            "setbackM": {"front": 2.0, "interiorSide": 2.5, "rear": 43.0},
        },
        "volumeTopology": {
            "rails": "bar",
            "cutsAt": [0.444, 0.722],
            "courtyardDepthM": 0.0,
            "volumes": [
                {"role": "dwelling", "storeys": 1, "capGroup": 0},
                {"role": "stable", "storeys": 1, "capGroup": 0},
                {"role": "barn", "storeys": 1, "capGroup": 0},
            ],
            "plinth": {"mode": "levelToHighest", "minM": 0.4},
        },
        "capFamily": {"family": "skeletonRoof", "pitchDeg": 45.0,
                      "eaveDepthM": 0.8},
    },
    {
        "styleId": "at_vienna_perimeter",
        "version": 1,
        "sources": [
            "TYPE: Gruenderzeit Blockrandbebauung inside the Guertel.",
            "storeys 5 including the ground floor: SOURCED, and the counting "
            "convention with it - Bauordnung fuer Wien 1883 §42, 'Wohnhaeuser "
            "duerfen nicht mehr als fuenf Geschosse erhalten, wobei "
            "Erdgeschoss und allfaelliges Mezzanin einzurechnen sind'. "
            + BRAUN,
            "storeyHeightM 3.5: SOURCED as a band, not a value - Raumhoehe "
            "3.2-4.0 m, 'in der Erdgeschosszone oft auch darueber'. The "
            "ground floor being TALLER is documented and is NOT expressible "
            "here: B2 gives a volume one height, and per-storey splits are "
            "B3's. " + OEAW,
            "courtyardDepthM 12.0 (tract depth): SOURCED - the span of the "
            "'Wiener Dachstuhl', ~12 m, caption 10-14 m, which is the same "
            "12 m read as two ~6 m timber-spanned bays either side of a "
            "load-bearing Mittelmauer. " + FIERRO,
            "the courtyard wings at the SAME depth and height as the street "
            "wing: DERIVED, not sourced. Seitentrakt/Hoftrakt depth was not "
            "found. The residential Hoftrakt is documented as a full-height "
            "part of the same Wohnhaus; it is the ANCILLARY and COMMERCIAL "
            "courtyard buildings that are 'meist niedriger'. So no storey "
            "differential is committed here. " + OEAW,
            "setback 0 on every street edge: SOURCED and strong - 'standen "
            "die Gebaeude direkt an der Grundstuecksgrenze'; permitted "
            "projections past the Baulinie were 10-23 cm. Vorgarten "
            "exceptions (Cottageviertel, 1873 servitude) are a different "
            "template. " + BRAUN,
            "roof pitch 30 deg behind a Kranzgesims: SOURCED as a band - "
            "Wiener Dachstuhl 25-45 deg over a ~12 m span, facade "
            "terminating in a Kranzgesims with the roof rising behind it. "
            "⚠️ The 45 deg envelope often quoted is CURRENT Bauordnung §81, "
            "not Gruenderzeit law. " + FIERRO,
        ],
        "storeyHeightM": 3.5,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 0.0,
            "setbackM": {"front": 0.0, "sideStreet": 0.0, "rear": 0.0},
        },
        "volumeTopology": {
            "rails": "ring",
            "cutsAt": [],
            "courtyardDepthM": 12.0,
            "volumes": [
                {"role": "vorderhaus", "storeys": 5, "capGroup": 0},
                {"role": "seitentrakt", "storeys": 5, "capGroup": 0},
                {"role": "hoftrakt", "storeys": 5, "capGroup": 0},
                {"role": "seitentrakt", "storeys": 5, "capGroup": 0},
            ],
            "plinth": {"mode": "none", "minM": 0.0},
        },
        "capFamily": {"family": "skeletonRoof", "pitchDeg": 30.0,
                      "corniceM": 0.9},
    },
    {
        "styleId": "at_vierkanthof",
        "version": 1,
        "sources": [
            "TYPE: Vierkanthof, Traun-/Mostviertel OOe. Built ring around a "
            "closed courtyard. " + VK_WIKI,
            "outer 54 x 30 m and Innenhof 450 m2: SOURCED from a measured "
            "example, Vierkanter 'Mayr auf der Wim', Garsten. " + VK_GARSTEN,
            "courtyardDepthM 9.0: DERIVED, NOT MEASURED, and the sources "
            "conflict. A uniform 9 m ring on 54 x 30 leaves 36 x 12 = 432 "
            "m2, close to the stated 450; but the same articles also call "
            "the atrium '30 x 15 m', which needs a NON-uniform ring. The "
            "uniform reading is preferred because the ridge height is equal "
            "on all four sides, and unequal tract depths under one ridge "
            "force a different pitch per side. " + VK_GARSTEN,
            "fronts 30-60 m, mittlere Hoefe ~40 m: SOURCED. " + OOE,
            "2 storeys: SOURCED - 'meist 2 Stockwerke, seltener 1'. "
            + VK_WIKI,
            "ONE cap group over all four wings: SOURCED, and it is the fact "
            "this whole cap-group mechanism exists for - 'Dachfirst auf "
            "allen vier Seiten gleich hoch'. " + VK_FORUM,
            "the farm wings single-storey at 5.2 m so the ridge stays level: "
            "DERIVED from that equal-ridge fact plus the 2-storey dwelling. "
            "The 2.6 m dwelling storey height itself is UNSOURCED.",
            "wing order - Wohntrakt at the front, Stall to one side, "
            "Scheune opposite the Wohntrakt with a central Tenne, "
            "Wagenschuppen beside: SOURCED. " + VK_MUSEUM,
            "plinth minM 0.4: UNSOURCED, same as the Einhof.",
        ],
        "storeyHeightM": 2.6,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 4.0,
            "setbackM": {"front": 4.0, "interiorSide": 4.0, "rear": 4.0},
        },
        "volumeTopology": {
            "rails": "ring",
            "cutsAt": [],
            "courtyardDepthM": 9.0,
            "volumes": [
                {"role": "dwelling", "storeys": 2, "capGroup": 0},
                {"role": "stable", "storeys": 1, "storeyHeightM": 5.2,
                 "capGroup": 0},
                {"role": "barn", "storeys": 1, "storeyHeightM": 5.2,
                 "capGroup": 0},
                {"role": "cartShed", "storeys": 1, "storeyHeightM": 5.2,
                 "capGroup": 0},
            ],
            "plinth": {"mode": "levelToHighest", "minM": 0.4},
        },
        "capFamily": {"family": "skeletonRoof", "pitchDeg": 38.0,
                      "eaveDepthM": 0.6},
    },
    {
        "styleId": "at_zinshaus_row",
        "version": 1,
        "sources": [
            "TYPE: Gruenderzeit Zinshaus on a mid-block plot, street tract "
            "plus a lower commercial rear tract, no courtyard.",
            "Parzellenbreite 15-20 m: SOURCED, so the 17 m fixture lot sits "
            "inside it. " + OEAW,
            "Vorderhaus depth 12 m (cut 0.462 of a 26 m plot): SOURCED, the "
            "Wiener Dachstuhl span again. " + FIERRO,
            "5 storeys, 3.5 m: SOURCED as above (1883 §42; Raumhoehe band). "
            + BRAUN,
            "rear tract LOWER: SOURCED only qualitatively - 'meist "
            "niedrigere Hofbebauungen, in der Regel fuer die gewerbliche "
            "Nutzung'. The 3 storeys is UNSOURCED; no storey differential "
            "was found in metres or counts. " + OEAW,
            "setback 0 on the street and on both party edges: SOURCED. "
            + BRAUN,
            "⚠️ The side walls are the party walls to the NEIGHBOURING "
            "BUILDINGS (Feuermauern). B2 emits them as exterior walls "
            "carrying the site role `abuts`; building-to-building junctions "
            "are deferred to v2 by §12.1 and are B6's to resolve.",
        ],
        "storeyHeightM": 3.5,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 0.0,
            "setbackM": {"front": 0.0, "abuts": 0.0, "rear": 0.0},
        },
        "volumeTopology": {
            "rails": "bar",
            "cutsAt": [0.462],
            "courtyardDepthM": 0.0,
            "volumes": [
                {"role": "vorderhaus", "storeys": 5, "capGroup": 0},
                {"role": "gewerbeHoftrakt", "storeys": 3, "capGroup": 1},
            ],
            "plinth": {"mode": "none", "minM": 0.0},
        },
        "capFamily": {"family": "skeletonRoof", "pitchDeg": 30.0,
                      "corniceM": 0.9},
    },
]


def main():
    import hou
    from polyfactory.citygen import buildings
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for style in STYLES:
        # ⚠️ BEFORE THE WRITE, because after it the loss is undetectable: a
        # nested list, or a list mixing strings with numbers, leaves the key
        # simply ABSENT from the loaded template with no exception at either
        # end, and `resolve()` then substitutes a DEFAULTS value nobody asked
        # for.  Measured on 22.0.398; the rule and the measurements live in
        # `buildings.assert_storable`.
        buildings.assert_storable(style)
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
