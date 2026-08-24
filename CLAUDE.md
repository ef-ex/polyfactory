# polyfactory — project instructions

polyfactory is a suite of **standalone artist-facing Houdini tools** (polyChain, polyKnit,
citygen, …). Tools may consume each other — citygen will consume polyChain — but each is its
own product by design. Do not treat a tool as a subsystem of another.

## Non-negotiable working rules

1. **Houdini work starts with the dev-loop skill**: `houdini_get_skill("houdini-dev-loop")`
   before creating or editing ANY node network, VEX, HDA or geometry code. Rule 0 applies:
   nothing is "done" without an independent audit on the current build.
2. **Language hierarchy for geometry work**: native nodes → VEX → OpenCL. Python only for
   UI/parameter marshalling or data genuinely inexpressible otherwise — and every surviving
   Python case must be named and justified in the owning doc's decision log.
   Never choose a language for test convenience.
3. **Data conventions are law**: [`ideas/conventions.md`](ideas/conventions.md) —
   `pf_` prefix on everything that leaves a node; `_*` internals deleted before output,
   enforced by test. An attribute's STORAGE (int/float/string) is part of its contract.
4. **Batch over language**: one wrangle/verb execution over ALL data, never per piece or per
   curve (measured 55×). Bench many-short-curves fixtures, not one long one.
5. **Checks must be able to fail**: a check is not written until its mutation has been seen
   to go red. State what each check cannot see. Assert truth, not presence; never compare
   after rounding unless the rounding is the contract (state the real tolerance at the real
   magnitude). Runners exit non-zero on any movement they print. Parity runs against the
   shipped asset, never a rig. Verify an image contains its subject before judging it.
6. **Read the incident history before running autonomous cycles**:
   [`ideas/build_retrospective.md`](ideas/build_retrospective.md) §3–§4.

## Multi-agent / shared-branch rules

- **Never rewrite history on a shared branch** — no `commit --amend`, `rebase`, `reset`, or
  `checkout` of files you did not edit. Stage and revert **named paths only**, never `-A`.
- **Commit incrementally, per item.** Interruptions (usage limits, 529s) are routine; only
  committed work survives them.
- Long autonomous builds keep a **resume pointer** in the owning `ideas/*.md` (§0.0 pattern:
  branch, gates, next item, recovery procedure). Verify any brief against `git log` first —
  briefs go stale.
- Namespace scratchpad files per agent. Workflow scripts: LF endings only, no backticks in
  template-literal text.

## Testing

- `tests/README.md` first. Numbers before renders; baselines record values, not pass/fail.
- Fast pure-logic tests run under plain `python`; scene checks run headless under hython
  (`"C:/Program Files/Side Effects Software/Houdini 22.0.398/bin/hython.exe"`), throwaway
  sessions, never saving a .hip.
- The live MCP bridge is Hannes' GUI session: serial access, leave no trace, never save.

## Docs

One owner per topic; extend, never duplicate ([`ideas/`](ideas/) holds the design docs and
build logs). `ideas/citygen.md` is the citygen hub; `ideas/polychain.md` owns polyChain;
`ideas/conventions.md` owns data conventions.
