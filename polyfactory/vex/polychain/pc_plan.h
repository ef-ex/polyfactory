#ifndef PC_PLAN_H
#define PC_PLAN_H

// polyChain 4.2 - THE FITTING SOLVE, in VEX.  13.9 N2.
//
// `polychain/plan.py` ported function for function: `fit`, `evenly`,
// `candidates`, `choose`, `pick`, `_unit`, `_unit_metrics`, `_fill`,
// `_anchor_placement` and `plan_section`.  The Python stays as the reference
// and the parity oracle (13.6); `plan_solve_parity` in
// `tests/polychain/run_native_checks.py` asks BOTH on the same input, which
// is 13.8's rule 1.
//
// ⚠️ EVERY FUNCTION HERE READS ITS TABLES OFF INPUT 1 WITH `detail()`, and
// that is a decision, not laziness.  A VEX user function inside a snippet
// sees ONLY its own parameters - snippet-level locals are invisible to it -
// so the alternatives were a thirty-array parameter list on every function or
// one dict copied down the call chain.  `detail(1, ...)` is a hash lookup
// plus an array copy of the KIT (4 entries on the starter fence) or the RULE
// TABLE (single digits), and D157 already fixes input 1 as the CONFIG stream
// on every stage wrangle, so the index is a convention and not a magic
// number.
//
// ⚠️ AND IT REQUIRES `vex_precision = 64`.  4.2's arithmetic is float64 in
// Python and 13.8 asks the plan for EXACT parity, no absolute slack: the
// accumulation `cur += (s + padL + padR) * scale` has to round the same way
// or the exact-fill property becomes a tolerance.

#include "pc_rand.h"

#define PC_PEPS   1e-9          // `polychain.EPS`
#define PC_MAXU   100000        // `polychain.MAX_UNITS`

#define PC_W_KITGAP   "pc_warn_kit_gap"
#define PC_W_OVERFLOW "pc_warn_overflow"
#define PC_W_TILEFB   "pc_warn_tile_fallback"
#define PC_W_VEXPR    "pc_warn_vexpr_ignored"
#define PC_W_PAD      "pc_warn_degenerate_pad"

// `_cond_columns`' kinds, and they must match `hda.COND_*`.
#define PC_C_NONE 0
#define PC_C_NUM  1
#define PC_C_STR  2
#define PC_C_LIST 3
#define PC_C_BAD  4

// D202 - THE SUBJECT'S OWN THIRD ANSWER.  `pc_cond_subject` used to have two:
// absent (kind 0, which `evaluate_cond` reads as `value is None` -> False) and
// readable (a number or a string).  Python has a third, and it was answering
// differently: a subject whose value is a TUPLE (a multi-component or array
// prim attribute, through `place._prim_attrs`) or a DICT (`ctx_base`'s own
// `attrs` and `marker_data` keys) is NOT None, so `evaluate_cond` reaches the
// operator - where every ordered compare raises TypeError and is caught as
// False, `eq` is False and `ne` is TRUE.  Kind 3 is that answer exactly.
// A key is published under the sentinel prefix below rather than in `cf`/`cs`,
// so no function signature has to grow a third dict.
#define PC_S_UNREADABLE 3
#define PC_UNREADABLE "!unreadable:"

// --- CONFIG accessors -------------------------------------------------------

float pc_cfg_f(const string key; const float fallback) {
    dict cfg = detail(1, "pc_cfg");
    if (!isvalidindex(cfg, key)) return fallback;
    float v = cfg[key];
    return v;
}

string pc_cfg_s(const string key; const string fallback) {
    dict cfg = detail(1, "pc_cfg");
    if (!isvalidindex(cfg, key)) return fallback;
    string v = cfg[key];
    return v;
}

// --- the kit ----------------------------------------------------------------
//
// A CANDIDATE is an int: the module's row in the kit table, or -1 for
// `polychain.stand_in` - 3.4's blank box, which is a real answer and not a
// failure.  Its NAME travels beside it, because a stand-in is named after the
// thing that was missing and that name reaches `pc_module` downstream.

// ⚠️ THE FLOAT COLUMNS ARRIVE AS DECIMAL STRINGS AND `atof` IS WHAT MAKES
// THEM EXACT.  A float ARRAY attribute is float32 storage even when a 64-bit
// wrangle reads it (measured: 0.35 comes back 0.34999999403953552), so a kit
// module 0.35 m long reached this solve at 32 bits and the plan was 2.7e-9
// out.  `hda._exact` writes `repr(v)` and `atof` reads it back bit for bit.
float pc_m_len(const int m) {
    if (m < 0) return 1.0;
    string a[] = detail(1, "pc_k_len");
    return atof(a[m]);
}

float pc_m_pad(const int m; const int side) {
    if (m < 0) return 0.0;
    string a[] = detail(1, side ? "pc_k_pad1" : "pc_k_pad0");
    return atof(a[m]);
}

int pc_m_deform(const int m) {
    if (m < 0) return 0;
    int a[] = detail(1, "pc_k_deform");
    return a[m];
}

int pc_m_missing(const int m) {
    if (m < 0) return 1;                       // a stand-in IS the kit gap
    int a[] = detail(1, "pc_k_missing");
    return a[m];
}

float pc_m_weight(const int m) {
    if (m < 0) return 1.0;
    string a[] = detail(1, "pc_k_weight");
    return atof(a[m]);
}

string pc_m_zmode(const int m) {
    if (m < 0) return "adaptive";
    string a[] = detail(1, "pc_k_zmode");
    return a[m];
}

string pc_m_variant(const int m) {
    if (m < 0) return "";
    string a[] = detail(1, "pc_k_variant");
    return a[m];
}

// `Kit._by_name` is a dict comprehension over the module list, so a REPEATED
// name is won by the LAST module carrying it, not the first.
int pc_kit_by_name(const string want) {
    if (want == "") return -1;
    string names[] = detail(1, "pc_k_name");
    for (int i = len(names) - 1; i >= 0; i--)
        if (names[i] == want) return i;
    return -1;
}

// `Kit.by_role` - payload order preserved, never set iteration.
void pc_kit_by_role(const string role; export int out[]) {
    resize(out, 0);
    if (role == "") return;
    string roles[] = detail(1, "pc_k_roles");
    for (int i = 0; i < len(roles); i++) {
        string mine[] = split(roles[i]);
        foreach (string r; mine)
            if (r == role) { push(out, i); break; }
    }
}

// `Kit.resolve` - name first, then role, then a stand-in.  Never empty.
void pc_kit_resolve(const string name; export int mi[]; export string mn[]) {
    resize(mi, 0); resize(mn, 0);
    int one = pc_kit_by_name(name);
    if (one >= 0) { push(mi, one); push(mn, name); return; }
    int byrole[];
    pc_kit_by_role(name, byrole);
    if (len(byrole)) {
        string names[] = detail(1, "pc_k_name");
        foreach (int i; byrole) { push(mi, i); push(mn, names[i]); }
        return;
    }
    push(mi, -1); push(mn, name);              // 3.4's stand-in box
}

// --- 7.2's cell role, which is the identity in 1D ---------------------------

string pc_role_2d(const string x_slot; const string y_slot) {
    if (y_slot == "" || y_slot == "default") return x_slot;
    return sprintf("%s_%s", x_slot, y_slot);
}

// --- 3.3's conditions -------------------------------------------------------

int pc_str_contains(const string hay; const string needle) {
    int n = strlen(needle), h = strlen(hay);
    if (n == 0) return 1;
    for (int i = 0; i + n <= h; i++)
        if (hay[i:i + n] == needle) return 1;
    return 0;
}

// The SUBJECT, as (kind, number, string).  kind 0 = the subject is absent,
// which `evaluate_cond` reads as None and answers False to.
void pc_cond_subject(const string subject; const dict cf; const dict cs;
                     export int kind; export float num; export string text) {
    kind = 0; num = 0.0; text = "";
    if (isvalidindex(cf, subject)) { float v = cf[subject]; num = v; kind = 1; return; }
    if (isvalidindex(cs, subject)) { string v = cs[subject]; text = v; kind = 2; return; }
    if (isvalidindex(cs, concat(PC_UNREADABLE, subject))) {
        kind = PC_S_UNREADABLE; return;        // present, but not a scalar
    }
}

// `plan.evaluate_cond`, including its two quiet rules: an unknown op is
// False, and a TYPE MISMATCH is False rather than an exception - except
// under `eq`/`ne`, where Python compares across types without raising, so
// `3 != "3"` is TRUE and must stay true here.
int pc_evaluate_cond(const int r; const dict cf; const dict cs) {
    int ckind[] = detail(1, "pc_r_ckind");
    if (ckind[r] == PC_C_NONE) return 1;       // no condition is always true

    string cops[] = detail(1, "pc_r_cop");
    string op = cops[r];
    if (op != "lt" && op != "le" && op != "gt" && op != "ge"
        && op != "eq" && op != "ne" && op != "in") return 0;

    string csubj[] = detail(1, "pc_r_csubj");
    int skind; float snum; string stext;
    pc_cond_subject(csubj[r], cf, cs, skind, snum, stext);
    if (skind == 0) return 0;                  // `value is None` -> False
    // D202 - present but unreadable.  Python compares a tuple or a dict
    // against the condition value without raising under `eq`/`ne` (never
    // equal, so `ne` is True) and raises TypeError under every other
    // operator, which `evaluate_cond` catches as False.  MEASURED on the
    // shipped asset: `attr:vecattr gt 5.0` against the prim vector
    // (7.5, 1.0, 2.0) built 12 `gate` prims natively and 10 `panel` prims in
    // the reference, because `prim(0, name, pr)` read COMPONENT 0.
    if (skind == PC_S_UNREADABLE) return (op == "ne");

    int kind = ckind[r];
    string cnums[] = detail(1, "pc_r_cnum");
    string cstrs[] = detail(1, "pc_r_cstr");

    if (op == "in") {
        if (kind == PC_C_LIST) {
            int cl0[] = detail(1, "pc_r_cl0"), cln[] = detail(1, "pc_r_cln");
            string items[] = detail(1, "pc_r_clist");
            string inums[] = detail(1, "pc_r_clnum");
            int ikind[] = detail(1, "pc_r_clkind");
            for (int j = 0; j < cln[r]; j++) {
                int k = cl0[r] + j;
                if (skind == 1 && ikind[k] == PC_C_NUM && snum == atof(inums[k])) return 1;
                if (skind == 2 && ikind[k] == PC_C_STR && stext == items[k]) return 1;
            }
            return 0;
        }
        if (kind == PC_C_STR && skind == 2) return pc_str_contains(cstrs[r], stext);
        return 0;                              // `3 in 4` raises -> False
    }

    int same_num = (skind == 1 && kind == PC_C_NUM);
    int same_str = (skind == 2 && kind == PC_C_STR);
    if (op == "eq" || op == "ne") {
        int equal = 0;
        if (same_num)      equal = (snum == atof(cnums[r]));
        else if (same_str) equal = (stext == cstrs[r]);
        // anything else compares UNEQUAL in Python and does not raise
        return (op == "eq") ? equal : !equal;
    }
    if (same_num) {
        float b = atof(cnums[r]);
        if (op == "lt") return snum <  b;
        if (op == "le") return snum <= b;
        if (op == "gt") return snum >  b;
        return snum >= b;
    }
    if (same_str) {
        string b = cstrs[r];
        if (op == "lt") return stext <  b;
        if (op == "le") return stext <= b;
        if (op == "gt") return stext >  b;
        return stext >= b;
    }
    return 0;                                  // TypeError -> warn-never-block
}

// --- selection (3.3) --------------------------------------------------------

// `candidates` - the rule's module list as real modules: name, then role,
// then stand-in.  `role` is the CELL role when the caller knows it.
void pc_candidates(const int r; const string role;
                   export int mi[]; export string mn[]) {
    resize(mi, 0); resize(mn, 0);
    int mod0[] = detail(1, "pc_r_mod0"), modn[] = detail(1, "pc_r_modn");
    string mods[] = detail(1, "pc_r_mods");
    for (int j = 0; j < modn[r]; j++) {
        int one[]; string oname[];
        pc_kit_resolve(mods[mod0[r] + j], one, oname);
        for (int k = 0; k < len(one); k++) { push(mi, one[k]); push(mn, oname[k]); }
    }
    if (len(mi)) return;
    string slots[] = detail(1, "pc_r_slot");
    int one[]; string oname[];
    pc_kit_resolve(role != "" ? role : slots[r], one, oname);
    for (int k = 0; k < len(one); k++) { push(mi, one[k]); push(mn, oname[k]); }
}

// `__init__.scope_key` + `seed_for`, as the exact text Python hashes.
string pc_scope_text(const string scope; const string curve_id;
                     const int sec_index; const string slot; const int index) {
    string key;
    if (scope == "generator")    key = "";
    else if (scope == "spline")  key = curve_id;
    else if (scope == "section") key = sprintf("%s|%d", curve_id, sec_index);
    else key = sprintf("%s|%d|%s|%d", curve_id, sec_index, slot, index);
    float seed = pc_cfg_f("seed", 0.0);
    return sprintf("%d\x1f%s\x1f%s\x1f%s", (int)seed,
                   pc_cfg_s("style_id", ""), scope, key);
}

// --- THE POOL, AND WHY IT IS ITS OWN FUNCTION ------------------------------
//
// ⚠️ NOTHING IN THE POOL DEPENDS ON THE PIECE.  The candidate list, its
// (name, variant) sort order and its weight vector are a pure function of
// (rule, role) - and `pc_choose` rebuilt all three on EVERY piece, with each
// insertion-sort comparison calling `pc_m_variant`, which copies the entire
// `pc_k_variant` detail array.  So the solve grew super-linearly in KIT SIZE,
// which the whole suite could not see because every fixture uses a
// five-module kit.  Measured here, plan chain only, 2 km fence, 1 000 pieces
// held constant, ONE `default` rule that names no modules so the kit resolves
// by ROLE (which is 7.2's own idiom and what makes the pool the whole kit):
//
//     modules       1        51       151
//     `first`     0.051 s  0.051 s   0.053 s      (flat - D175's hoist)
//     `random`    0.283 s  2.632 s  66.493 s      <- this
//     after       0.267 s  0.295 s   0.309 s
//
// 3x the modules cost 25x the time, and the `first` row isolates the whole
// delta to the selection path.  7.2's 25 cell roles imply a facade kit in the
// hundreds, so this is a shape an artist reaches, not a stress toy.
//
// It is D175's fix applied one level up: D175 hoisted the UNIT's numbers out
// of the piece loop, and the pool is the other thing in there that cannot
// change inside a run.
void pc_pool(const int r; const string role;
             export int ci[]; export string cn[]; export int ord[];
             export float weights[]; export float total) {
    resize(ord, 0); resize(weights, 0); total = 0.0;
    pc_candidates(r, role, ci, cn);
    int n = len(ci);
    if (!n) return;
    string selects[] = detail(1, "pc_r_select");
    if (selects[r] != "random") return;          // only `random` needs either

    // ⚠️ THE COLUMNS ARE READ ONCE, NOT PER COMPARISON.  `pc_m_variant` and
    // `pc_m_weight` each copy a whole detail array, and the insertion sort
    // below asks O(n^2) times.
    string kvar[] = detail(1, "pc_k_variant");
    string kwgt[] = detail(1, "pc_k_weight");
    string cv[];
    for (int i = 0; i < n; i++)
        push(cv, (ci[i] < 0) ? "" : kvar[ci[i]]);

    // sorted by (name, variant), so the pick cannot depend on the order the
    // payload happens to list the modules in.
    for (int i = 0; i < n; i++) {
        push(ord, i);
        int j = i;
        while (j > 0) {
            int a = ord[j - 1], b = ord[j];
            if (cn[a] < cn[b] || (cn[a] == cn[b] && cv[a] <= cv[b])) break;
            ord[j - 1] = b; ord[j] = a;
            j--;
        }
    }
    int w0[] = detail(1, "pc_r_w0"), wn[] = detail(1, "pc_r_wn");
    string wkey[] = detail(1, "pc_r_wkey");
    string wval[] = detail(1, "pc_r_wval");
    foreach (int o; ord) {
        float w = (ci[o] < 0) ? 1.0 : atof(kwgt[ci[o]]);
        for (int j = 0; j < wn[r]; j++)
            if (wkey[w0[r] + j] == cn[o]) { w = atof(wval[w0[r] + j]); break; }
        push(weights, w);
        total += w;
    }
}

// `plan.choose`'s TAIL: the part that does depend on the piece.  `cs` must
// already carry the `slot` key (see `pc_choose`), because `slot` is a
// readable conditional subject and the caller is the one that knows it.
void pc_pick_from_pool(const int r; const dict cf; const dict cs;
                       const string use_slot; const int index;
                       const string curve_id; const int sec_index;
                       const int ci[]; const string cn[]; const int ord[];
                       const float weights[]; const float total;
                       export int mi; export string mn; export int ok) {
    mi = -1; mn = ""; ok = 0;
    int n = len(ci);
    if (!n) return;
    string selects[] = detail(1, "pc_r_select");
    string sel = selects[r];

    if (sel == "sequence") {
        int k = index % n;
        if (k < 0) k += n;
        mi = ci[k]; mn = cn[k]; ok = 1;
        return;
    }
    if (sel == "random") {
        string scopes[] = detail(1, "pc_r_scope");
        float roll = pc_random01(pc_seed_for(
            pc_scope_text(scopes[r], curve_id, sec_index, use_slot, index)))
            * total;
        int pick = ord[n - 1];
        if (total <= 0.0) pick = ord[0];
        else {
            float acc = 0.0;
            for (int i = 0; i < n; i++) {
                acc += weights[i];
                if (roll < acc) { pick = ord[i]; break; }
            }
        }
        mi = ci[pick]; mn = cn[pick]; ok = 1;
        return;
    }
    if (sel == "conditional") {
        if (pc_evaluate_cond(r, cf, cs)) { mi = ci[0]; mn = cn[0]; ok = 1; return; }
        if (n > 1) { mi = ci[1]; mn = cn[1]; ok = 1; }
        return;                                 // a rule that declines
    }
    mi = ci[0]; mn = cn[0]; ok = 1;              // first
}

// `plan.choose` - one module for one piece, or -1/"" when a conditional rule
// declines.  `ok` is the `is not None` half of the answer, because a real
// module can legitimately be row -1 (the stand-in).  Pool plus pick, for the
// callers that ask ONCE; `pc_fill` splits them and hoists the pool.
void pc_choose(const int r; const dict cf; const dict cs; const string slot;
               const int index; const string curve_id; const int sec_index;
               const string yclass;
               export int mi; export string mn; export int ok) {
    string slots[] = detail(1, "pc_r_slot");
    string use_slot = (slot != "") ? slot : slots[r];
    // ⚠️ `plan.pick` DOES `dict(ctx, slot=slot)` AND `_fill`'s ctx0 sets
    // `slot="default"`, so `slot` is a readable conditional subject on EVERY
    // pick - `cond_subject` ends in `ctx.get(subject)`.  It was missing from
    // the VEX bag, and a `{subject: slot, op: eq, value: "start"}` rule
    // therefore declined natively where the reference accepted.  It is added
    // HERE rather than at the five call sites because here is where the
    // answer to "which slot" exists.
    dict cs_slot = cs;
    cs_slot["slot"] = use_slot;
    int ci[], ord[]; string cn[]; float weights[], total;
    pc_pool(r, pc_role_2d(use_slot, yclass), ci, cn, ord, weights, total);
    pc_pick_from_pool(r, cf, cs_slot, use_slot, index, curve_id, sec_index,
                      ci, cn, ord, weights, total, mi, mn, ok);
}

// `Style.rules_for` - payload order preserved, the scoped rules first (D119).
void pc_rules_for(const string slot; const string yclass; export int out[]) {
    resize(out, 0);
    string slots[] = detail(1, "pc_r_slot");
    string ycl[] = detail(1, "pc_r_yclass");
    if (yclass == "") {
        for (int i = 0; i < len(slots); i++) if (slots[i] == slot) push(out, i);
        return;
    }
    for (int i = 0; i < len(slots); i++)
        if (slots[i] == slot && ycl[i] == yclass) push(out, i);
    for (int i = 0; i < len(slots); i++)
        if (slots[i] == slot && ycl[i] == "") push(out, i);
}

// `plan.pick` - (rule, module) for `slot`; the first rule that yields wins.
void pc_pick(const string slot; const dict cf; const dict cs; const int index;
             const string curve_id; const int sec_index; const string yclass;
             export int rule; export int mi; export string mn) {
    rule = -1; mi = -1; mn = "";
    int rules[];
    pc_rules_for(slot, yclass, rules);
    foreach (int r; rules) {
        int gi, ok; string gn;
        pc_choose(r, cf, cs, slot, index, curve_id, sec_index, yclass, gi, gn, ok);
        if (ok) { rule = r; mi = gi; mn = gn; return; }
    }
}

// `plan._module_warns`, as the space-joined string every placement carries.
string pc_module_warns(const int m; const int r) {
    string out = "";
    if (pc_m_missing(m)) out = PC_W_KITGAP;
    if (r >= 0) {
        string vexprs[] = detail(1, "pc_r_vexpr");
        if (vexprs[r] != "")
            out = (out == "") ? PC_W_VEXPR : sprintf("%s %s", out, PC_W_VEXPR);
    }
    return out;
}

string pc_warn_join(const string a; const string b) {
    if (a == "") return b;
    if (b == "") return a;
    return sprintf("%s %s", a, b);
}

int pc_warn_has(const string list; const string one) {
    foreach (string w; split(list)) if (w == one) return 1;
    return 0;
}

// `plan._zmode` - D6's three-state: a non-empty style zmode overrides.
string pc_zmode(const int m) {
    string z = pc_cfg_s("zmode", "");
    return (z != "") ? z : pc_m_zmode(m);
}

// `Section.u_at` - 0-1 along the PARENT curve for `s_local` into the section.
float pc_u_at(const float sec_s0; const float curve_len; const float s_local) {
    if (curve_len <= PC_PEPS) return 0.0;
    float u = (sec_s0 + s_local) / curve_len;
    return (u > 1.0) ? (u % 1.0) : u;
}

// --- the pure fitting maths -------------------------------------------------

// `plan.fit`.  `count`/`scale`/`remainder`/`slice`/`warns`, and D17's
// degenerate-padding degradations rather than a division by zero.
void pc_fit(const float length; const float nominal; const string mode;
            const float gap; const float fixed;
            export int count; export float scale; export float remainder;
            export int doslice; export string warns) {
    float L = length, s = nominal;
    count = 0; scale = 1.0; remainder = 0.0; doslice = 0; warns = "";
    if (s <= PC_PEPS || L <= PC_PEPS) return;
    float step = s + fixed + gap;
    if (step <= PC_PEPS) {
        // D17: one more unit costs nothing, so "how many fit" has no answer.
        count = 1;
        scale = max((L - fixed) / s, 0.0);
        warns = PC_W_PAD;
        return;
    }
    // A `(int)floor(x)` CAST IS AMBIGUOUS IN VEX - `floor` has a float and
    // an int overload, so the cast has two candidates and the snippet does
    // not compile.  A float temporary picks the overload by assignment.
    float fwhole = floor((L + gap + PC_PEPS) / step);
    int whole = (int)fwhole;
    string dense = (step < s * 0.01) ? PC_W_PAD : "";

    if (mode == "tile") {
        int n = max(whole, 0);
        warns = (n <= PC_MAXU) ? dense : PC_W_PAD;
        n = min(n, PC_MAXU);
        float used = n * (s + fixed) + max(n - 1, 0) * gap;
        float rem = L - used - ((n > 0) ? gap : 0.0);
        count = n;
        scale = 1.0;
        remainder = max(rem, 0.0);
        doslice = (rem > PC_PEPS);
        return;
    }

    int n;
    if (mode == "scale") n = 1;                          // D12
    else if (mode == "count") { float c = pc_cfg_f("count", 1.0);
                                n = max((int)c, 0); }
    else {
        float exact = (L + gap) / step;
        float fn = floor(exact + PC_PEPS);
        n = (int)fn;
        if ((exact - n) * 100.0 >= pc_cfg_f("adaptive_pct", 50.0) - PC_PEPS) n += 1;
        n = max(n, 1);
    }
    if (n <= 0) return;
    warns = (n <= PC_MAXU) ? dense : PC_W_PAD;
    n = min(n, PC_MAXU);
    while (n > 1 && (L - n * fixed - (n - 1) * gap) <= PC_PEPS) n--;
    scale = (L - n * fixed - (n - 1) * gap) / (n * s);
    if (scale < 0.0) {
        // D17 again, the n == 1 case the drop loop cannot reach.
        scale = 0.0;
        warns = pc_warn_join(warns, PC_W_PAD);
    }
    count = n;
}

// `plan.evenly` - anchor positions in metres along a span (4.2, D15).
void pc_evenly(const float length; export float out[]) {
    resize(out, 0);
    float L = length;
    if (L <= PC_PEPS) return;
    float fecount = pc_cfg_f("evenly_count", 0.0);
    int ecount = (int)fecount;
    if (ecount > 0) {
        float step = L / (ecount + 1);
        for (int i = 0; i < ecount; i++) push(out, step * (i + 1));
        return;
    }
    float d = pc_cfg_f("evenly_spacing", 0.0);
    if (d <= PC_PEPS) return;
    float fn = floor((L - PC_PEPS) / d);
    int n = (int)fn;
    if (n <= 0) return;
    float leftover = L - n * d;
    if (0.0 < leftover && leftover <= pc_cfg_f("adjust_to_end", 0.0) + PC_PEPS) {
        d = L / n;                                 // the last anchor on the end
        for (int i = 0; i < n; i++) push(out, d * (i + 1));
        return;
    }
    string justify = pc_cfg_s("justify", "center");
    float lead;
    if (justify == "start")     lead = d;
    else if (justify == "end")  lead = leftover;
    else                        lead = (L - (n - 1) * d) * 0.5;
    for (int i = 0; i < n; i++) push(out, lead + d * i);
}

// --- `plan._fill` - one RUN into [a, b] -------------------------------------
//
// `lead_pad` / `trail_pad` are the facing pads of the neighbouring pieces, and
// `has_lead` / `has_trail` are Python's `None`: at a SECTION END nothing is
// there to be pushed, so the run's own outer pad must not displace it -
// padding moves neighbours, never the padded piece.
//
// ⚠️ D11'S TILE FALLBACK IS A LOOP, NOT RECURSION.  The Python calls `_fill`
// again with `mode="adaptive"`; VEX has no recursion (probed - "Call to
// undefined function"), and it does not need it: the retry can only be
// triggered from the slice tail and `adaptive` never slices, so the fallback
// is exactly one re-run.  The output arrays are rewound to their entry length
// first, which is what discarding the failed attempt's `out` list amounts to.
int pc_fill(const float a; const float b; const int r;
            const dict cf; const dict cs;
            const string curve_id; const int sec_index; const float sec_s0;
            const float curve_len; const string yclass; const int index0;
            const float lead_pad; const int has_lead;
            const float trail_pad; const int has_trail;
            const string mode_in; const string extra_in; const int cyclic;
            // ⚠️ D244 - THE POOL AND THE SLOT CONTEXT ARE THE CALLER'S NOW.
            // They are a pure function of (rule, yclass), which do not change
            // between the gaps an `evenly` or `marker` rule leaves, and
            // rebuilding them here cost one `pc_candidates` plus one dict
            // copy PER GAP: measured on a 2 km straight at 2 m spacing (1 000
            // anchors), `pc_plan_solve` 177.2 ms with them inside against
            // 63 ms of fill for the same 3 001 pieces with no anchor in the
            // run.  Same shape as the pool hoist out of the PIECE loop above,
            // one level further out.
            const int p_ci[]; const string p_cn[]; const int p_ord[];
            const float p_w[]; const float p_total; const dict cs_slot;
            export string o_slot[]; export int o_index[];
            export string o_module[]; export string o_variant[];
            export float o_s0[]; export float o_s1[]; export float o_u[];
            export float o_scale[]; export float o_slice[];
            export int o_deform[]; export string o_zmode[];
            export string o_warns[]) {
    if (r < 0) return index0;
    int entry = len(o_slot);
    string selects[] = detail(1, "pc_r_select");
    string mode = mode_in, extra = extra_in;
    int idx = index0;

    for (int attempt = 0; attempt < 2; attempt++) {
        resize(o_slot, entry);   resize(o_index, entry);
        resize(o_module, entry); resize(o_variant, entry);
        resize(o_s0, entry);     resize(o_s1, entry);    resize(o_u, entry);
        resize(o_scale, entry);  resize(o_slice, entry);
        resize(o_deform, entry); resize(o_zmode, entry); resize(o_warns, entry);
        idx = index0;

        // ⚠️ THE POOL IS RESOLVED ONCE PER RUN, NOT ONCE PER PIECE, AND
        // SINCE D244 ONCE PER SECTION RATHER THAN ONCE PER GAP - the caller
        // hands it in (see the signature).  The slot is "default" for the
        // whole fill and the yclass is the row's, so the candidate list, its
        // (name, variant) order and its weights cannot change inside this
        // loop - and rebuilding them per piece cost 32 s on a 301-module kit
        // against 0.13 s under `first`.

        // `_unit` (D14): a whole SEQUENCE, or one module.
        dict cf0 = cf;
        cf0["index"] = (float)index0; cf0["segIndex"] = (float)index0;
        int umi[]; string umn[];
        if (selects[r] == "sequence") {
            // ⚠️ THE CELL ROLE, exactly as `choose` asks for it.  A `sequence`
            // rule naming no modules is the phase-2 idiom, and resolving the
            // bare X slot silently filled a ground floor with the default bay.
            umi = p_ci; umn = p_cn;
        } else {
            int mi, ok; string mn;
            pc_pick_from_pool(r, cf0, cs_slot, "default", index0, curve_id,
                              sec_index, p_ci, p_cn, p_ord, p_w, p_total,
                              mi, mn, ok);
            if (ok) { push(umi, mi); push(umn, mn); }
        }
        int nu = len(umi);
        if (!nu) return index0;

        float span_a = has_lead  ? (a + lead_pad + pc_m_pad(umi[0], 0)) : a;
        float span_b = has_trail ? (b - trail_pad - pc_m_pad(umi[nu - 1], 1)) : b;
        float L = span_b - span_a;
        if (L <= PC_PEPS) return index0;

        // ⚠️ THE UNIT'S OWN NUMBERS, ONCE.  Every `pc_m_*` accessor reads a
        // detail ARRAY, which copies it - a VEX function inside a snippet
        // cannot see a snippet local, so the read is inside the function.
        // Calling them per PIECE is what made a 10 000-piece section cost
        // 1.94 s in the solve alone; the unit is the same object for the
        // whole run, so its numbers are hoisted here.
        float u_len[], u_pad0[], u_pad1[];
        int u_deform[];
        string u_zmode[], u_variant[], u_warn[];
        for (int j = 0; j < nu; j++) {
            push(u_len, pc_m_len(umi[j]));
            push(u_pad0, pc_m_pad(umi[j], 0));
            push(u_pad1, pc_m_pad(umi[j], 1));
            push(u_deform, pc_m_deform(umi[j]));
            push(u_zmode, pc_zmode(umi[j]));
            push(u_variant, pc_m_variant(umi[j]));
            push(u_warn, pc_module_warns(umi[j], r));
        }

        // `_unit_metrics`
        float s = 0.0, fixed = 0.0;
        for (int j = 0; j < nu; j++) s += u_len[j];
        for (int j = 0; j < nu - 1; j++) fixed += u_pad1[j] + u_pad0[j + 1];
        float gap = u_pad1[nu - 1] + u_pad0[0];

        if (mode == "") mode = pc_cfg_s("fill", "adaptive");
        float lead = 0.0;
        if (cyclic && L - gap > PC_PEPS) {        // D19: fold the wrap gap in
            L -= gap;
            lead = gap * 0.5;
        }
        int count, doslice; float scale, remainder; string fwarns;
        pc_fit(L, s, mode, gap, fixed, count, scale, remainder, doslice, fwarns);
        string warns = pc_warn_join(extra, fwarns);
        int clipping = pc_warn_has(warns, PC_W_PAD);

        // ⚠️ AND ONLY `random` AND `conditional` RE-SELECT PER PIECE.  D14
        // says a run is fitted on its unit and a per-piece re-selection is
        // scaled into the slot the unit laid out; `plan.choose` under
        // `first` reads nothing from the ctx that changes inside a run (the
        // slot is "default" throughout, the yclass is the row's), so its
        // answer is the unit's own module and asking again 10 000 times is
        // 10 000 kit resolutions for one answer.
        int reselects = (selects[r] == "random" || selects[r] == "conditional");

        float cursor = span_a + lead;
        int redo = 0;
        for (int u = 0; u < count; u++) {
            if (u > 0) cursor += gap;
            for (int j = 0; j < nu; j++) {
                if (j > 0) cursor += u_pad1[j - 1] + u_pad0[j];
                float target = u_len[j] * scale;
                int mi = umi[j]; string mn = umn[j];
                float mlen = u_len[j];
                string mzmode = u_zmode[j], mvariant = u_variant[j];
                string mwarn = u_warn[j];
                int mdeform = u_deform[j];
                if (reselects) {
                    dict cfi = cf;
                    cfi["index"] = (float)idx; cfi["segIndex"] = (float)idx;
                    cfi["u"] = pc_u_at(sec_s0, curve_len, cursor);
                    int gi, ok; string gn;
                    pc_pick_from_pool(r, cfi, cs_slot, "default", idx,
                                      curve_id, sec_index, p_ci, p_cn, p_ord,
                                      p_w, p_total, gi, gn, ok);
                    if (ok) {
                        mi = gi; mn = gn;
                        mlen = pc_m_len(mi);
                        mzmode = pc_zmode(mi);
                        mvariant = pc_m_variant(mi);
                        mwarn = pc_module_warns(mi, r);
                        mdeform = pc_m_deform(mi);
                    }
                }
                float p0 = cursor, p1 = cursor + target;
                if (clipping) {
                    // degenerate padding walks the cursor out of the span, and
                    // nothing may be planned outside the section it belongs to
                    p0 = min(max(p0, span_a), span_b);
                    p1 = min(max(p1, span_a), span_b);
                }
                push(o_slot, "default"); push(o_index, idx);
                push(o_module, mn); push(o_variant, mvariant);
                push(o_s0, p0); push(o_s1, p1);
                push(o_u, pc_u_at(sec_s0, curve_len, cursor));
                push(o_scale, (mlen > PC_PEPS) ? (target / mlen) : 1.0);
                push(o_slice, -1.0);
                push(o_deform, mdeform); push(o_zmode, mzmode);
                push(o_warns, pc_warn_join(warns, mwarn));
                cursor += target;
                idx++;
            }
        }

        if (doslice && remainder > PC_PEPS) {
            // The tile remainder CONTINUES the unit rather than being one cut
            // copy of its first module: whole modules until one straddles the
            // boundary, and only that one is sliced.  A 3 m panel cannot
            // supply a 2 m tail just because the unit starts with a 1 m post.
            if (count > 0) cursor += gap;
            float stop = cursor + remainder;
            int prev = -2;
            for (int j = 0; j < nu; j++) {
                if (prev != -2) cursor += pc_m_pad(prev, 1) + u_pad0[j];
                float avail = stop - cursor;
                if (avail <= PC_PEPS) break;
                int mi = umi[j]; string mn = umn[j];
                if (reselects) {
                    dict cfi = cf;
                    cfi["index"] = (float)idx; cfi["segIndex"] = (float)idx;
                    cfi["u"] = pc_u_at(sec_s0, curve_len, cursor);
                    int gi, ok; string gn;
                    pc_pick_from_pool(r, cfi, cs_slot, "default", idx,
                                      curve_id, sec_index, p_ci, p_cn, p_ord,
                                      p_w, p_total, gi, gn, ok);
                    if (ok) { mi = gi; mn = gn; }
                }
                float mlen = pc_m_len(mi), plen = 0.0, slice_t = -1.0;
                if (mlen <= avail + PC_PEPS) plen = mlen;
                else if (pc_m_deform(mi) < 2) {
                    // the module that ACTUALLY lands on the boundary decides
                    // this, not the unit's first module: a re-selected rigid
                    // piece may never be cut, so the WHOLE run falls back
                    redo = 1;
                    break;
                } else {
                    plen = avail;
                    slice_t = (mlen > PC_PEPS) ? min(avail / mlen, 1.0) : 1.0;
                }
                float p0 = cursor, p1 = cursor + plen;
                if (clipping) {
                    p0 = min(max(p0, span_a), span_b);
                    p1 = min(max(p1, span_a), span_b);
                }
                push(o_slot, "default"); push(o_index, idx);
                push(o_module, mn); push(o_variant, pc_m_variant(mi));
                push(o_s0, p0); push(o_s1, p1);
                push(o_u, pc_u_at(sec_s0, curve_len, cursor));
                push(o_scale, 1.0); push(o_slice, slice_t);
                push(o_deform, pc_m_deform(mi)); push(o_zmode, pc_zmode(mi));
                push(o_warns, pc_warn_join(warns, pc_module_warns(mi, r)));
                cursor += plen;
                idx++;
                prev = mi;
                if (slice_t >= 0.0) break;
            }
        }
        if (!redo) return idx;
        mode = "adaptive";                        // D11 - the WHOLE run
        extra = pc_warn_join(warns, PC_W_TILEFB);
    }
    return idx;
}

#endif
