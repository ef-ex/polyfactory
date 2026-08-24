#ifndef PC_RAND_H
#define PC_RAND_H

// polyChain - 3.3's SEEDING CHAIN and 3.4's `pc_elem_key`, in VEX.
//
// ⚠️ THIS FILE EXISTS BECAUSE 13.2's RISK R1 WAS WRONG, AND THE CORRECTION IS
// WORTH MORE THAN THE CODE.  13.2 probed `long x = 5;` (invalid), `>>>` (a
// parse error) and concluded "VEX has no int64 and no unsigned shift", which
// made `_splitmix` the one algorithm with no VEX expression, put a four-limb
// re-implementation at the head of 13.9's build order and reserved a Python
// fallback for it.  Measured on 22.0.398 this cycle:
//
//   * VEX has no `>>` or `<<` OPERATORS AT ALL - `1 << 4` is a syntax error.
//     The shifts are FUNCTIONS: `shl`, `shr` (arithmetic) and `shrz` (zero
//     fill).  `shrz` IS the unsigned shift.
//   * under `vex_precision = 64` VEX's `int` IS 64-BIT: `shl(1, 62)` gives
//     4611686018427387904, `shrz(-1, 8)` gives 2^56-1, and
//     `1812433253 * 1812433253` gives the exact 64-bit product.  Under
//     `vex_precision = 32` all three collapse to 32 bits.
//
// So splitmix64 is six lines, and the ONLY trap left is the literal:
//
//   ⚠️ A HEX LITERAL WIDER THAN INT64_MAX IS CLAMPED, NOT WRAPPED.
//   `0x9E3779B97F4A7C15` reads back as 9223372036854775807 (INT64_MAX), and
//   splitmix built on it is silently wrong on every input.  The three
//   constants are therefore written as their SIGNED DECIMAL equivalents,
//   with the hex beside them.
//
// EVERY FUNCTION HERE REQUIRES `vex_precision = 64`.  At 32 bits they all
// compile and all answer wrongly, which is exactly the failure mode the
// existing `native_intermediates_are_64bit` check was written for.

// --- splitmix64 - `polychain.__init__._splitmix`, bit for bit ---------------

int pc_splitmix(const int x0) {
    int x = x0 + -7046029254386353131;      // 0x9E3779B97F4A7C15
    int z = x;
    z = (z ^ shrz(z, 30)) * -4658895280553007687;   // 0xBF58476D1CE4E5B9
    z = (z ^ shrz(z, 27)) * -7723592293110705685;   // 0x94D049BB133111EB
    return z ^ shrz(z, 31);
}

// --- crc32 - zlib's, i.e. the reflected IEEE polynomial ---------------------
//
// `elem_key` and `seed_for` both go through `zlib.crc32`.  Table-free: eight
// shifts a byte is nothing at this N, and a 256-entry table inside a snippet
// is 256 lines an artist has to scroll past.  Masked back to 32 bits at every
// step because `int` is 64 bits here.
//
// ⚠️ THE CHARACTER WALK IS `text[c]`, NOT `split(text, "")`.  13.2 recorded
// `split` as the way to reach a string's characters; measured this cycle,
// `split(s, "")` returns the WHOLE STRING AS ONE TOKEN (`split("ab c|d", "")`
// -> `('ab c|d',)`), so a crc built on it hashes `ord(first character)` once
// and agrees with zlib on 1-character strings only - which is exactly how it
// first shipped here: 333 of 358 test strings wrong, 25 right.  String
// INDEXING is the answer (`"abcd"[2]` -> `"c"`), with `strlen` for the count.
//
// ⚠️ IT HASHES UTF-8 BYTES, BECAUSE `zlib.crc32` DOES.  This used to fold
// `ord(text[c]) & 0xFF` - the CODE POINT masked to 8 bits - and a non-ASCII
// id then hashed something zlib never sees: measured on 22.0.398,
// `pc_crc32("é")` was 3815224791 against `zlib.crc32`'s 235179326, and
// because `pc_seed_for` runs through the same function a German styleId moved
// 28 of 40 `random` picks.  It was not only `pc_elem_key`, which is what the
// old comment here claimed.
//
// The walk is over BYTES and the decode is free, because VEX already works
// that way (probed): `strlen("éx")` is 3, and indexing gives
// `"é"` / `""` / `"x"` with `ord` 233 / -1 / 120 - i.e. `s[i]` decodes
// the code point that STARTS at byte i and answers -1 on a continuation byte.
// So skipping the -1 slots and re-encoding each code point reproduces
// Python's `str.encode("utf-8")` exactly.
//
// ⚠️ AND THE BYTES ARE FOUR SCALARS, NOT AN ARRAY.  `array(...)` is
// ambiguous inside a loop in VEX (recorded trap), and a four-element array
// allocated per character would be the batching mistake this cycle spent its
// time removing.
int pc_crc32(const string text) {
    int crc = 0xFFFFFFFF;
    int n = strlen(text);
    for (int c = 0; c < n; c++) {
        int cp = ord(text[c]);
        if (cp < 0) continue;                  // a UTF-8 continuation byte
        int b0 = cp, b1 = 0, b2 = 0, b3 = 0, nb = 1;
        if (cp >= 0x80 && cp < 0x800) {
            b0 = 0xC0 | shrz(cp, 6); b1 = 0x80 | (cp & 0x3F); nb = 2;
        } else if (cp >= 0x800 && cp < 0x10000) {
            b0 = 0xE0 | shrz(cp, 12);
            b1 = 0x80 | (shrz(cp, 6) & 0x3F);
            b2 = 0x80 | (cp & 0x3F); nb = 3;
        } else if (cp >= 0x10000) {
            b0 = 0xF0 | shrz(cp, 18);
            b1 = 0x80 | (shrz(cp, 12) & 0x3F);
            b2 = 0x80 | (shrz(cp, 6) & 0x3F);
            b3 = 0x80 | (cp & 0x3F); nb = 4;
        }
        for (int i = 0; i < nb; i++) {
            int by = (i == 0) ? b0 : ((i == 1) ? b1 : ((i == 2) ? b2 : b3));
            crc = (crc ^ (by & 0xFF)) & 0xFFFFFFFF;
            for (int k = 0; k < 8; k++) {
                int lsb = crc & 1;
                crc = shrz(crc, 1) & 0x7FFFFFFF;
                if (lsb) crc = crc ^ 0xEDB88320;
            }
        }
    }
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF;
}

// 3.4's `pc_elem_key` - a 31-bit int for grouping and sorting only.
int pc_elem_key(const string elem_id) {
    return pc_crc32(elem_id) & 0x7FFFFFFF;
}

// ⚠️ `pc_is_ascii` IS GONE, AND ITS DELETION IS THE POINT.  It existed to
// warn that `pc_crc32` could not answer for a non-ASCII `elem_id`; the crc
// answers for every string now, so the guard would only ever have fired on
// keys that are correct.  A warning that says "this may be wrong" about a
// value that is right is worse than no warning: it trains the reader to
// ignore it.  `seed_crc32_parity` carries non-ASCII texts instead, which is
// a check rather than a caveat.

// --- MT19937 - because `plan.choose` weighs with `random.Random(s).random()`--
//
// Reproducing the SELECTION means reproducing that number, so CPython's
// generator ports too: `random.Random(int)` splits the seed into 32-bit words,
// little-endian, and runs `init_by_array`.  Roughly 2 500 int operations a
// call, and only a `random` rule ever pays them.
//
// Every value is masked to 32 bits by hand - `int` is 64-bit here, so the
// wrap MT19937 is defined on has to be written out.

#define PC_MT_N 624
#define PC_MT_M32 0xFFFFFFFF

// ⚠️ D245 - MT19937 IS INLINED INTO ONE FUNCTION, AND THAT IS A COST FIX,
// NOT A STYLE ONE.  It used to be three functions - `pc_mt_init`,
// `pc_mt_seed64`, `pc_mt_next` - each taking the 624-word state as
// `export int mt[]`, which VEX copies IN and OUT on every call.  Measured on
// the shipped asset, a 2 km straight at `Piece Order = Random` (a MAIN-page
// parm the guard ADMITS), `hou.perfMon` Cook-ms, min of 3 dirtied cooks:
// `pc_plan_solve` 21.7 ms under `first` against 251.7 ms under `random` on
// the same 1 002 pieces, and the whole native cook 42.3 -> 273.2 ms against
// the reference's 68.3 ms - 4.00x SLOWER than the Python it ported, where
// `first` on the identical input is 0.69x.  That is ~230 us of VEX for one
// `random.Random(s).random()` CPython answers in 1-2 us.
//
// ⚠️ AND THE FIRST TWIST IS TRUNCATED TO THE TWO WORDS THE TWO DRAWS READ.
// `genrand_res53` consumes `genrand_int32` twice, which with `mti = N` is
// mt[0]' and mt[1]' of the first twist.  mt[0]' depends on mt[0], mt[1] and
// mt[397]; mt[1]' on mt[1], mt[2] and mt[398] - and at kk = 1 the real loop
// has written only mt[0], so mt[1], mt[2], mt[397] and mt[398] are all still
// the seeded values.  The two words are therefore PROVABLY the same numbers
// the full 624-word twist would produce, and `plan_random_matches_cpython`
// compares the result against `random.Random(s).random()` itself.
//
// `random.Random(int)` splits the seed into 32-bit words, little-endian, and
// runs `init_by_array`.  Every value is masked to 32 bits by hand - `int` is
// 64-bit here, so the wrap MT19937 is defined on has to be written out.

// `random.random()` = `genrand_res53`.  `float` is float64 under
// `vex_precision = 64`, which is what makes the 53-bit assembly exact.
float pc_random01(const int seed64) {
    // `init_genrand(19650218)`
    int mt[];
    resize(mt, PC_MT_N);
    int seedprev = 19650218 & PC_MT_M32;
    mt[0] = seedprev;
    for (int i = 1; i < PC_MT_N; i++) {
        seedprev = (1812433253 * (seedprev ^ shrz(seedprev, 30)) + i)
                   & PC_MT_M32;
        mt[i] = seedprev;
    }

    // CPython `random_seed` + `init_by_array`.  `keyused` is 1 below 2^32 and
    // 2 above it, which is what `_PyLong_AsByteArray` into 32-bit
    // little-endian words comes to for the 64-bit seed `seed_for` produces.
    int lo = seed64 & PC_MT_M32;
    int hi = shrz(seed64, 32) & PC_MT_M32;
    int klen = (hi != 0) ? 2 : 1;
    // ⚠️ `prev` CARRIES mt[i-1] IN A REGISTER, and the key is two scalars.
    // Every read of `mt[i - 1]` is the value the previous iteration WROTE
    // (and at the wrap, `mt[0] = mt[N-1]` writes exactly that value again),
    // so the array read is redundant - and a VEX array read is not free:
    // measured single-threaded, the 624-word init loop alone goes 23.6 us to
    // 18.6 us a call (-21 %) on this one change.  `key[]` becomes `lo`/`hi`
    // for the same reason: `array(...)` inside a loop is this project's
    // recorded ambiguity trap AND an allocation nobody asked for.
    int prev = mt[0];
    int i = 1, j = 0;
    for (int k = PC_MT_N; k > 0; k--) {
        int kv = (j == 0) ? lo : hi;
        prev = ((mt[i] ^ ((prev ^ shrz(prev, 30)) * 1664525))
                + kv + j) & PC_MT_M32;
        mt[i] = prev;
        i++; j++;
        if (i >= PC_MT_N) { mt[0] = mt[PC_MT_N - 1]; i = 1; }
        if (j >= klen) j = 0;
    }
    for (int k = PC_MT_N - 1; k > 0; k--) {
        prev = ((mt[i] ^ ((prev ^ shrz(prev, 30)) * 1566083941))
                - i) & PC_MT_M32;
        mt[i] = prev;
        i++;
        if (i >= PC_MT_N) { mt[0] = mt[PC_MT_N - 1]; i = 1; }
    }
    mt[0] = 0x80000000;

    // the first twist, words 0 and 1 - see the note above for why the other
    // 622 cannot change either of them
    int y0 = (mt[0] & 0x80000000) | (mt[1] & 0x7FFFFFFF);
    int w0 = mt[397] ^ shrz(y0, 1);
    if (y0 & 1) w0 = w0 ^ 0x9908B0DF;
    w0 = w0 & PC_MT_M32;
    int y1 = (mt[1] & 0x80000000) | (mt[2] & 0x7FFFFFFF);
    int w1 = mt[398] ^ shrz(y1, 1);
    if (y1 & 1) w1 = w1 ^ 0x9908B0DF;
    w1 = w1 & PC_MT_M32;

    // `genrand_int32`'s tempering, twice
    int t0 = w0 ^ shrz(w0, 11);
    t0 = (t0 ^ (shl(t0, 7) & 0x9D2C5680)) & PC_MT_M32;
    t0 = (t0 ^ (shl(t0, 15) & 0xEFC60000)) & PC_MT_M32;
    t0 = (t0 ^ shrz(t0, 18)) & PC_MT_M32;
    int t1 = w1 ^ shrz(w1, 11);
    t1 = (t1 ^ (shl(t1, 7) & 0x9D2C5680)) & PC_MT_M32;
    t1 = (t1 ^ (shl(t1, 15) & 0xEFC60000)) & PC_MT_M32;
    t1 = (t1 ^ shrz(t1, 18)) & PC_MT_M32;

    int ua = shrz(t0, 5);
    int ub = shrz(t1, 6);
    return ((float)ua * 67108864.0 + (float)ub) * (1.0 / 9007199254740992.0);
}

// The whole of `__init__.seed_for`, given the text it assembles.
int pc_seed_for(const string text) {
    return pc_splitmix(pc_crc32(text));
}

#endif
