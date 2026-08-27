"""Author the CityGen style templates AND the construction-system library.

    hython devScripts/create_pf_building_styles.py

Writes `polyfactory/library/citygen/styles/<styleId>.geo` and
`polyfactory/library/citygen/systems/<systemId>.geo`, each one a Houdini
geometry file carrying the whole block as a single detail DICTIONARY
attribute `pf_style_template` - the storage format §12.12 left to "the first
template authored decides", decided in `citygen/buildings.py`.

⭐ TWO LIBRARIES, NOT ONE, AND THAT IS §9e's TWO-LAYER MODEL MADE LITERAL.
A *construction system* is layer 1 - what a material and its jointing permit
(span, storeys, wall thickness) - and it is SHARED between styles: both
Gruenderzeit styles read `at_ziegel_gruenderzeit`, and the Babel fixture reads
the SAME `at_lehm_massiv` block the Einhof does.  A *style* is layer 2 - which
point inside that space a culture picks.  §12.5 already spelled
`constructionSystem` "ref -> data block"; this is that word taken literally,
and it is the only arrangement in which "change a system's `maxSpanM` and see
what moves" is a question about the SYSTEM rather than about one style.

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
SYSOUT = os.path.join(REPO, "polyfactory", "library", "citygen",
                      "systems").replace("\\", "/")
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

LEHMREG = ("Lehmbau-Regeln (1990s), as quoted by two independent 2023 "
           "reports on their replacement DIN 18940 - 'Tragende Lehmmauern "
           "waren nach den Lehmbau-Regeln aus den 1990er Jahren nur bei "
           "Gebaeuden bis maximal zwei Stockwerken gestattet' / 'Zuvor "
           "mussten tragende Lehmsteine eine Wandstaerke von 36,5 Zentimeter "
           "aufweisen' - https://www.gebaeudeforum.de/service/newsletter/"
           "ausgabe-05/2023/neue-lehm-norm/ and 'So duerfen etwa Lehmsteine "
           "nur bei Gebaeuden mit maximal zwei Geschossen verwendet werden. "
           "Vorgeschrieben ist dann zusaetzlich eine Wandstaerke von "
           "mindestens 36,5 Zentimetern' - "
           "https://www.bba-online.de/news/neue-din-norm-lehmsteine/")
PAKIMMO = ("pak-immo, Gruenderzeithaeuser: Konstruktion und Sanierung - "
           "brick format '14/29/6,5 cm' (1883), 'Das Mauerwerk eines "
           "Stiegenhauses musste eine Mindestdicke von 60 cm aufweisen', "
           "'Kellerwaende konnten bis zu einem Meter dick werden' - "
           "https://www.pak-immo.at/gruenderzeithauser-konstruktion-"
           "sanierung/")

# ⚠️ 0.0 / 0 MEANS "THIS SYSTEM STATES NO LIMIT", NEVER "ZERO METRES".  It is
# the shape §12.5 asks for ("a template may be sparse") and it is used here
# rather than a plausible placeholder, because a placeholder is exactly the
# unsourced number that later reads as authoritative.  Where a field is 0 the
# `sources` line says NOT STATED and why.
SYSTEMS = [
    {
        "systemId": "at_lehm_massiv",
        "version": 1,
        "sources": [
            "TYPE: massive earth construction (Stampflehm / Lehmziegel) on a "
            "stone or brick footing - the traditional Nordburgenland "
            "Streckhof material. SOURCED: 'Die traditionellen Streckhoefe "
            "wurden haeufig in Lehmbauweise errichtet' - "
            "https://de.wikipedia.org/wiki/Streckhof",
            "maxSpanM 5.0: DERIVED, not measured as a limit. Zsabetich "
            "sources the house WIDTH at 5 m ('Die Haeuser sind 20 Meter lang "
            "und 5 Meter breit'), and the ceiling and roof timbers cross the "
            "house, so 5 m is the span these buildings actually spanned. "
            "⚠️ That is the span USED, not the maximum the material permits; "
            "no vernacular span table was found (§9c's own flag). " + ZSABETICH,
            "maxStoreys 2: SOURCED, and MODERN. " + LEHMREG + " ⚠️ It is a "
            "1990s code number, not a backdated vernacular measurement - the "
            "same objection this library raises against backdating the 2.50 m "
            "Raumhoehe minimum. It is used because it is a codification of "
            "the MATERIAL's limit rather than of a room, and because §9g's "
            "Babel case needs a real limit to exceed. Flagged, not hidden.",
            "wallThicknessM 0.365: SOURCED, and MODERN, same source and same "
            "caveat as maxStoreys.",
            "bayMaxM 0.0: NOT STATED. No source for a Streckhof opening "
            "rhythm was found, so the span alone decides the bay here - "
            "which is §9c's chain with nothing else in the way.",
        ],
        "maxSpanM": 5.0,
        "bayMaxM": 0.0,
        "maxStoreys": 2,
        "wallThicknessM": 0.365,
        "wallThicknessesM": [],
        "storeyHeightsM": [],
    },
    {
        "systemId": "at_ziegel_gruenderzeit",
        "version": 1,
        "sources": [
            "TYPE: unreinforced single-shell brick masonry with timber "
            "Tramdecken, Vienna, under the Bauordnung fuer Wien 1883. Read "
            "by BOTH Gruenderzeit styles - it is the shared layer-1 block "
            "§9e's two-layer model predicts.",
            "maxSpanM 6.0: DERIVED. The Wiener Dachstuhl spans ~12 m "
            "(SOURCED, caption 10-14 m), and that 12 m is read as two ~6 m "
            "timber-spanned bays either side of a load-bearing Mittelmauer - "
            "the same reading `at_vienna_perimeter` already records for its "
            "courtyardDepthM. So 6 m is the FLOOR structure's span, which is "
            "what sets a bay; the roof truss crosses the full 12 m because a "
            "truss is a different jointing system, and this block carries "
            "ONE span. " + FIERRO,
            "maxStoreys 5: SOURCED - Bauordnung fuer Wien 1883 §42. " + BRAUN,
            "wallThicknessM 0.45 and the per-storey table 0.60 / 0.60: "
            "DERIVED, and the derivation is thinner than it looks. What IS "
            "sourced: the 1883 brick format 14/29/6,5 cm, which makes wall "
            "thicknesses a 15 cm ladder; a 60 cm minimum for Stiegenhaus "
            "masonry; and cellar walls up to 1 m. " + PAKIMMO + " ⚠️ What is "
            "NOT sourced here is the STEPPING RULE itself - search returned a "
            "'reduced by half a stone every one to two storeys' rule and a "
            "37-74 cm ground/cellar band, and neither was verified in a "
            "document I read, so neither is cited. 0.60 at the two lowest "
            "storeys (2 Stein) stepping to 0.45 (1.5 Stein) above is the "
            "ladder applied once, conservatively.",
            "storeyHeightsM: the GROUND STOREY at 4.2 m: DERIVED, and this "
            "is the field §12.12 was open on. SOURCED is the band and the "
            "direction - Raumhoehe 3.2-4.0 m, 'in der Erdgeschosszone oft "
            "auch darueber'. " + OEAW + " 4.2 m is one step above the band's "
            "top, so the ground floor is taller by 0.7 m than the 3.5 m the "
            "styles carry. ⚠️ AND AN IMPRECISION INHERITED RATHER THAN "
            "INTRODUCED: 3.5 m is sourced as a ROOM height (Raumhoehe) and "
            "used as a STOREY height, which is short by the floor build-up. "
            "Recorded here rather than silently corrected - moving it is a "
            "change to a G1 fixture value and is not B3's to take.",
            "bayMaxM 0.0: NOT STATED. No source for a Gruenderzeit "
            "Fensterachse spacing was found. ⚠️ Consequence, stated because "
            "it bounds what this build proves: the culture-side arm of §9c's "
            "chain is unsourced on EVERY real system here, so the span alone "
            "decides every bay in the shipped data.",
        ],
        "maxSpanM": 6.0,
        "bayMaxM": 0.0,
        "maxStoreys": 5,
        "wallThicknessM": 0.45,
        "wallThicknessesM": [{"n": 1, "tM": 0.60}, {"n": 2, "tM": 0.60}],
        "storeyHeightsM": [{"n": 1, "hM": 4.2}],
    },
    {
        "systemId": "at_mauerwerk_land",
        "version": 1,
        "sources": [
            "TYPE: rural mass masonry, Traun-/Mostviertel farm. ⚠️ USED BY "
            "ONE STYLE, which is the shape G1's `rule_reuse` calls a style's "
            "data wearing a shared name. Kept anyway, and said out loud: a "
            "Vierkanthof is neither Lehm nor Gruenderzeit brick, and folding "
            "it into either would be a worse lie than a lonely block.",
            "maxStoreys 2: SOURCED - 'meist 2 Stockwerke, seltener 1'. "
            + VK_WIKI,
            "wallThicknessM 0.45: UNSOURCED. No wall thickness was found for "
            "this type; 0.45 is 1.5 Stein in the Austrian brick ladder and "
            "is a placeholder the cascade overrides.",
            "maxSpanM 0.0 and bayMaxM 0.0: NOT STATED. No tract span and no "
            "opening rhythm was found for a Vierkanthof. ⚠️ The visible "
            "consequence is in the output rather than hidden: with no cap "
            "from either side, every face of the Vierkanthof gets ONE bay. "
            "That is what 'we have no number' looks like in the geometry, "
            "and it is preferred to a plausible invention.",
        ],
        "maxSpanM": 0.0,
        "bayMaxM": 0.0,
        "maxStoreys": 2,
        "wallThicknessM": 0.45,
        "wallThicknessesM": [],
        "storeyHeightsM": [],
    },
    {
        # ⭐ §9g's CORUSCANT CASE: "the layer stops being derived and becomes
        # AUTHORED - and that is where it earns most."  Every number is
        # invented, and the point of the fixture is that the chain follows
        # from the invention CONSISTENTLY rather than that the numbers are
        # right.  It is also the only block in the library that exercises
        # `bayMaxM`, because every real system above states no bay cap.
        "systemId": "fic_coruscant_mega",
        "version": 1,
        "sources": [
            "TYPE: none. AUTHORED FICTION, §9g's Coruscant stress test. No "
            "number below is sourced or derived from anything - that is the "
            "case being tested: 'invent a material with a 400 m span limit "
            "and the entire downstream chain follows consistently from that "
            "one invention'.",
            "maxSpanM 400.0 / bayMaxM 60.0: the invention. The bay cap is "
            "BELOW the span on purpose, so this block is the one place in "
            "the library where the culture-side arm of the chain is the "
            "binding one and can be seen to bind.",
            "maxStoreys 500 / wallThicknessM 2.5 / ground storey 24 m and "
            "4.0 m thick: authored to be internally coherent with a 400 m "
            "span, nothing more.",
        ],
        "maxSpanM": 400.0,
        "bayMaxM": 60.0,
        "maxStoreys": 500,
        "wallThicknessM": 2.5,
        "wallThicknessesM": [{"n": 1, "tM": 4.0}],
        "storeyHeightsM": [{"n": 1, "hM": 24.0}],
    },
]

STYLES = [
    {
        "styleId": "at_einhof",
        "version": 1,
        "constructionSystem": "at_lehm_massiv",
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
        "constructionSystem": "at_ziegel_gruenderzeit",
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
        "constructionSystem": "at_mauerwerk_land",
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
        "constructionSystem": "at_ziegel_gruenderzeit",
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
    {
        # ⭐ GATE G2's SUBJECT, and it is NOT a vernacular style.  The four
        # above are sourced buildings; this one is a FIXTURE, authored to put
        # a reflex corner and an eave/gable seam in front of B4/B5/B6, and it
        # says so in its own provenance rather than borrowing a country code
        # for a shape.  §12.10 G2 asks for `shapeL`; `shapeL` is a B1 op and
        # B1 has only `setback`, so the L arrives as a LOT (which is what S8
        # produces anyway) and `setback` insets it - which is the harder of
        # the two, because it is the reflex corner that `pf_inset.vfl` has
        # never been asked to solve.
        "styleId": "g2_lshape",
        "version": 1,
        "sources": [
            "TYPE: none. This is gate G2's acceptance fixture (§12.10), not a "
            "surveyed building, and every number below is chosen to exercise "
            "a SEAM rather than to describe a place. It is listed here rather "
            "than hidden in the test harness because a style is data and the "
            "cascade must be able to reach it (§12.5).",
            "setbackM per role, all four different: UNSOURCED BY DESIGN. The "
            "reflex corner of the L is where the `rear` edge meets the "
            "`interiorSide` edge, and two edges meeting at a reflex corner "
            "with DIFFERENT insets is the case `pf_inset.vfl` solves "
            "corner-by-corner and nothing has ever checked.",
            "rails `solid`: the rule G2 added. One volume over the whole "
            "footprint, whatever its corner count - see `pf_mass.vfl`. "
            "Without it a non-convex footprint could only become one mass "
            "through the DEGRADED fallback, which carries "
            "`pf_warn_topology_arity` and would build the gate on a path that "
            "declares itself broken.",
            "storeys 3, storeyHeightM 3.2: UNSOURCED. Enough storeys that the "
            "facade has more than one row to misalign, low enough that the "
            "gate images frame.",
            "capFamily pitchDeg 38, eaveDepthM 0.7: UNSOURCED. The pitch is "
            "any value that makes hips and the valley visible; the eave is "
            "non-zero ON PURPOSE, because a zero overhang makes the roof's "
            "boundary identical to the wall top and the eave seam then closes "
            "by construction rather than by B6 doing anything.",
            "junctions cornerMode `miter`: this is the treatment §12.6 B6 "
            "names as its PRIMARY strategy (a corner module from the kit), "
            "and §0.0d records that it is also the one polyChain's native "
            "chain refuses per-BUILD. G2 measures both; the template asks for "
            "the one the spec prefers.",
        ],
        "storeyHeightM": 3.2,
        "lotToFootprint": {
            "op": "setback",
            "defaultSetbackM": 2.0,
            "setbackM": {"front": 3.0, "sideStreet": 2.0, "rear": 4.0,
                         "interiorSide": 1.5, "alley": 2.5},
        },
        "volumeTopology": {
            "rails": "solid",
            "cutsAt": [],
            "courtyardDepthM": 0.0,
            "volumes": [{"role": "dwelling", "storeys": 3, "capGroup": 0}],
            "plinth": {"mode": "none", "minM": 0.0},
        },
        "capFamily": {"family": "skeletonRoof", "pitchDeg": 38.0,
                      "eaveDepthM": 0.7},
        "junctions": {"cornerMode": "miter"},
    },
    {
        # ⭐ §9g's BABEL CASE, and the whole point is the SHARED block: this
        # style reads the SAME `at_lehm_massiv` the Einhof reads - a real
        # material with a real, sourced limit of two storeys - and asks for
        # eight.  §9g: "the tool knows the building is impossible, says so,
        # and builds it."  `pf_warn_storeys_exceeded` fires on every face and
        # the eight-storey building is built anyway (`citygen.md` §2.0/§2.2:
        # advisory, never a refusal).
        "styleId": "babel_lehm_tower",
        "version": 1,
        "constructionSystem": "at_lehm_massiv",
        "sources": [
            "TYPE: none. §9g's Babel stress test - a REAL material at an "
            "impossible scale. Every number here is a fixture value; the "
            "only thing that matters is that the construction system is not "
            "a fixture, it is the Einhof's own sourced block.",
            "storeys 8 against the system's sourced maxStoreys 2: UNSOURCED "
            "BY DESIGN, and it is the case under test rather than a claim "
            "about a building.",
            "storeyHeightM 4.0 / rails `solid` / cap `flat`: UNSOURCED. One "
            "volume over the whole footprint so the storey count has nowhere "
            "to hide, and a flat cap so nothing but the warning is at issue.",
        ],
        "storeyHeightM": 4.0,
        "lotToFootprint": {"op": "setback", "defaultSetbackM": 0.0,
                           "setbackM": {}},
        "volumeTopology": {
            "rails": "solid",
            "cutsAt": [],
            "courtyardDepthM": 0.0,
            "volumes": [{"role": "tower", "storeys": 8, "capGroup": 0}],
            "plinth": {"mode": "none", "minM": 0.0},
        },
        "capFamily": {"family": "flat", "pitchDeg": 0.0, "eaveDepthM": 0.0},
    },
    {
        # ⭐ §9g's CORUSCANT CASE: an invented construction system is just
        # another authored block, and the chain follows from it consistently.
        # Nothing here is claimed to be right; what is claimed is that a
        # 400 m span, a 60 m bay cap and a 24 m ground storey produce a
        # coherent bay grid, coherent splits and NO warnings - because an
        # invented system's limits are whatever it says they are.
        "styleId": "coruscant_spire",
        "version": 1,
        "constructionSystem": "fic_coruscant_mega",
        "sources": [
            "TYPE: none. §9g's Coruscant stress test. AUTHORED FICTION "
            "throughout, and the fiction is the subject: 'for a real style "
            "you could skip the structure layer and just imitate "
            "photographs; for a fictional one you cannot'.",
            "12 storeys at 20 m, `solid` rails, flat cap: UNSOURCED BY "
            "DESIGN. 12 x 20 m sits far inside the invented 500-storey "
            "limit, so this fixture's output must carry NO warning - which "
            "is the half of §9g that the Babel fixture cannot show.",
        ],
        "storeyHeightM": 20.0,
        "lotToFootprint": {"op": "setback", "defaultSetbackM": 0.0,
                           "setbackM": {}},
        "volumeTopology": {
            "rails": "solid",
            "cutsAt": [],
            "courtyardDepthM": 0.0,
            "volumes": [{"role": "spire", "storeys": 12, "capGroup": 0}],
            "plinth": {"mode": "none", "minM": 0.0},
        },
        "capFamily": {"family": "flat", "pitchDeg": 0.0, "eaveDepthM": 0.0},
    },
]


def main():
    import hou
    from polyfactory.citygen import buildings
    # ⭐ `storeyHeightsM` / `wallThicknessesM` ARE THE SHAPE §12.12 WAS OPEN
    # ON, and they go through the same guard as everything else: a list of
    # DICTS is exactly what G3 measured as surviving the `.geo` detail-dict
    # round trip, and `assert_storable` is what would have caught it had it
    # not.  It is called on the SYSTEMS too - a construction system is a
    # template file by the same mechanism, so it inherits the same trap.
    for out, blocks, key in ((SYSOUT, SYSTEMS, "systemId"),
                             (OUT, STYLES, "styleId")):
        if not os.path.isdir(out):
            os.makedirs(out)
        for block in blocks:
            # ⚠️ BEFORE THE WRITE, because after it the loss is undetectable:
            # a nested list, or a list mixing strings with numbers, leaves the
            # key simply ABSENT from the loaded template with no exception at
            # either end, and `resolve()` then substitutes a DEFAULTS value
            # nobody asked for.  Measured on 22.0.398; the rule and the
            # measurements live in `buildings.assert_storable`.
            buildings.assert_storable(block)
            geo = hou.Geometry()
            geo.addAttrib(hou.attribType.Global, "pf_style_template", {},
                          create_local_variable=False)
            geo.setGlobalAttribValue("pf_style_template", block)
            path = os.path.join(out, block[key] + ".geo").replace("\\", "/")
            geo.saveToFile(path)
            print("wrote %-46s %5d bytes" % (path, os.path.getsize(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
