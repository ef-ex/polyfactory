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
// ⚠️ ASCII ONLY.  `ord` answers about a CHARACTER; a non-ASCII one would need
// its UTF-8 bytes.  Every string that reaches here is a curve id, a slot
// name, a scope name or a style id; `pc_is_ascii` below is how a caller finds
// out when that stops being true instead of shipping a wrong key.
int pc_crc32(const string text) {
    int crc = 0xFFFFFFFF;
    int n = strlen(text);
    for (int c = 0; c < n; c++) {
        crc = (crc ^ (ord(text[c]) & 0xFF)) & 0xFFFFFFFF;
        for (int k = 0; k < 8; k++) {
            int lsb = crc & 1;
            crc = shrz(crc, 1) & 0x7FFFFFFF;
            if (lsb) crc = crc ^ 0xEDB88320;
        }
    }
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF;
}

// 3.4's `pc_elem_key` - a 31-bit int for grouping and sorting only.
int pc_elem_key(const string elem_id) {
    return pc_crc32(elem_id) & 0x7FFFFFFF;
}

// 1 when every character of `text` is ASCII, so `pc_crc32` is answerable for
// it.  Warn-never-block: the caller warns, it does not stop.
int pc_is_ascii(const string text) {
    int n = strlen(text);
    for (int c = 0; c < n; c++)
        if (ord(text[c]) > 127) return 0;
    return 1;
}

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

void pc_mt_init(export int mt[]; const int s) {
    resize(mt, PC_MT_N);
    mt[0] = s & PC_MT_M32;
    for (int i = 1; i < PC_MT_N; i++)
        mt[i] = (1812433253 * (mt[i - 1] ^ shrz(mt[i - 1], 30)) + i) & PC_MT_M32;
}

// CPython `random_seed` + `init_by_array`.  `keyused` is 1 below 2^32 and 2
// above it, which is what `_PyLong_AsByteArray` into 32-bit little-endian
// words comes to for the 64-bit seed `seed_for` produces.
void pc_mt_seed64(export int mt[]; const int seed64) {
    int lo = seed64 & PC_MT_M32;
    int hi = shrz(seed64, 32) & PC_MT_M32;
    int key[] = array(lo);
    if (hi != 0) push(key, hi);
    int klen = len(key);
    pc_mt_init(mt, 19650218);
    int i = 1, j = 0;
    for (int k = max(PC_MT_N, klen); k > 0; k--) {
        mt[i] = ((mt[i] ^ ((mt[i - 1] ^ shrz(mt[i - 1], 30)) * 1664525))
                 + key[j] + j) & PC_MT_M32;
        i++; j++;
        if (i >= PC_MT_N) { mt[0] = mt[PC_MT_N - 1]; i = 1; }
        if (j >= klen) j = 0;
    }
    for (int k = PC_MT_N - 1; k > 0; k--) {
        mt[i] = ((mt[i] ^ ((mt[i - 1] ^ shrz(mt[i - 1], 30)) * 1566083941))
                 - i) & PC_MT_M32;
        i++;
        if (i >= PC_MT_N) { mt[0] = mt[PC_MT_N - 1]; i = 1; }
    }
    mt[0] = 0x80000000;
}

int pc_mt_next(export int mt[]; export int mti) {
    if (mti >= PC_MT_N) {
        for (int kk = 0; kk < PC_MT_N; kk++) {
            int y = (mt[kk] & 0x80000000) | (mt[(kk + 1) % PC_MT_N] & 0x7FFFFFFF);
            int nx = mt[(kk + 397) % PC_MT_N] ^ shrz(y, 1);
            if (y & 1) nx = nx ^ 0x9908B0DF;
            mt[kk] = nx & PC_MT_M32;
        }
        mti = 0;
    }
    int y = mt[mti];
    mti++;
    y = y ^ shrz(y, 11);
    y = (y ^ (shl(y, 7) & 0x9D2C5680)) & PC_MT_M32;
    y = (y ^ (shl(y, 15) & 0xEFC60000)) & PC_MT_M32;
    return (y ^ shrz(y, 18)) & PC_MT_M32;
}

// `random.random()` = `genrand_res53`.  `float` is float64 under
// `vex_precision = 64`, which is what makes the 53-bit assembly exact.
float pc_random01(const int seed64) {
    int mt[]; int mti = PC_MT_N;
    pc_mt_seed64(mt, seed64);
    int ua = shrz(pc_mt_next(mt, mti), 5);
    int ub = shrz(pc_mt_next(mt, mti), 6);
    return ((float)ua * 67108864.0 + (float)ub) * (1.0 / 9007199254740992.0);
}

// The whole of `__init__.seed_for`, given the text it assembles.
int pc_seed_for(const string text) {
    return pc_splitmix(pc_crc32(text));
}

#endif
