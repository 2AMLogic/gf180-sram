# Work Log

Chronological record of merged PRs and closed issues, maintained automatically
by the Guide role's document maintenance phase. Newest entries first.

### 2026-11-01

- **PR #273**: chore(pdk): default remaining scripts to ~/.ciel and add dated re-pin entries
- **Issue #173** (closed): Re-pin open_pdks to f6eeac7 (ciel) — fleet retires volare c6d73a3

### 2026-10-31

- **PR #296**: Bump Repo Skills 0.24.7 -> 0.25.1

### 2026-10-29

- **PR #289**: fix(sim): find repo root by .git marker instead of parents[2]
- **Issue #287** (closed): Signoff scripts default repo root to parents[2], wrong if relocated deeper than sim/lib/
- **PR #283**: ci: add drift check for tracked generated array schematics
- **Issue #274** (closed): Stop tracking generated array schematics (sram_256x32_array.sch, sram_64x128_array.sch): ~180k lines of regenerable output

### 2026-10-28

- **PR #286**: feat(signoff): bind array GDS to T1 item 2 via generic layout envelope
- **Issue #284** (closed): T1 item 2 (layout): replace the DRC-report placeholder with an artifact-anchored envelope binding sram_256x32_array.gds
- **PR #280**: signoff: cite artifact-anchored generic wrappers for T1 items 1, 9, 10
- **Issue #277** (closed): Signoff items 1, 9, 10 unmet (wrong_kind) under klt 0.8.0
- **Issue #278** (closed): Publish full-macro LEF/GDS (and Liberty) for the 1RW 256x32 pin list

### 2026-10-27

- **PR #276**: chore: bump pinned klayout-tools to 0.8.0 and re-grade signoff
- **Issue #275** (closed): Bump klayout-tools pin 0.6.0, 0.7.0 → 0.8.0
- **PR #174**: feat(sim): pin open_pdks f6eeac7 and reject mismatched PDK trees

### 2026-10-26

- **PR #270**: docs(sim): cite the tool-side tracker for the deck-mode executor blocker

### 2026-10-23

- **Issue #266** (closed): snm_extract.py over-reads SNM: vertical gap, not inscribed square
- **PR #259**: ci: pin Node to 22.23.4 (Node 20 is end-of-life)
- **Issue #258** (closed): security: pin CI Node to 22.23.4 (node-version 20 is end-of-life)

### 2026-10-21

- **PR #251**: Bump Repo Skills 0.24.3 -> 0.24.7
- **PR #249**: layout: draw sram_ctrl and col_decode, DRC clean and LVS-matched at block level
- **Issue #246** (closed): Layout the sram_ctrl and col_decode blocks (block-level DRC and LVS)
- **PR #244**: layout: draw the row decoder and wordline-driver strip
- **Issue #204** (closed): Draw row decoder and wordline driver layout, pitch-matched to the array
- **PR #228**: sim: wordline RC gate fails for the left-fed 4:1 row; propose superseding decision

### 2026-10-20

- **PR #241**: ci: pin setup-python to 3.12 so klayout installs from wheels
- **Issue #239** (closed): CI: signoff job fails installing klayout-tools==0.7.0 when setup-python '3.x' resolves to 3.15 (no klayout wheel)
- **PR #238**: feat(sim): add offline Monte Carlo deck-mode adapter
- **PR #233**: feat(sim): offline klt deck-mode adapter for the 27-corner grid
- **PR #236**: refactor(sim): inline PDK identity dict and remove env_provenance shim
- **Issue #235** (closed): Remove sim/lib/env_provenance.py: single-use shim for a klt subcommand that now exists

### 2026-10-18

- **PR #226**: refactor: drop local-only macro smoke flavor in favor of klt sim
- **Issue #224** (closed): Retire local-only macro-smoke testbench flavor; the klt twin supersedes it
- **PR #221**: feat: draw the column path (precharge and I/O slices) from the netlists
- **Issue #205** (closed): Draw column periphery layout (precharge, mux, sense amp, write driver)
- **PR #220**: feat: sweep control pulse and macro smoke over all 27 corners
- **Issue #217** (closed): Sweep macro-smoke and control-pulse testbenches across the 27-corner PVT set via klt sim
- **PR #219**: feat: add 64x128 bitcell array layout for the 4:1 organization
- **PR #216**: feat: add periphery netlists, 4:1 array and macro top with write/read smoke sim
- **Issue #203** (closed): Periphery schematics, netlists and macro top netlist for the 1RW macro
- **PR #214**: fix: measure SNM as inscribed-square side, not vertical curve gap
- **Issue #213** (closed): snm_extract.py reports the largest vertical gap, not the inscribed square (over-reads SNM)
- **PR #210**: docs(spec): add periphery architecture, floorplan, and pin placement record
- **Issue #202** (closed): Periphery architecture and floorplan record for the 1RW macro
- **PR #208**: docs(spec): fix macro interface details and Liberty corner names
- **Issue #198** (closed): Ratify 1RW macro interface details and Liberty corner naming (spec decision record)

### 2026-10-17

- **PR #195**: chore(signoff): re-grade T1 verdict on klayout-tools 0.7.0
- **Issue #194** (closed): Re-grade the T1 verdict of record on klayout-tools 0.7.0 (grader pin is still 0.6.0)
- **PR #192**: refactor: table-drive derived-file freshness checks in check_evidence_format
- **Issue #191** (closed): Simplify check_evidence_format.py: collapse three copy-pasted freshness checks into one
- **PR #186**: chore(layout): remove no-op LVS reference rewrite script
- **Issue #185** (closed): Remove layout/lvs_reference.py: documented no-op bulk-net rewrite
- **PR #183**: chore(views): drop LEF-abstract wrapper, regenerate with released klt 0.6.0
- **Issue #182** (closed): Remove views/run_lef_abstract.py: upstream klayout-tools#1613 is closed

### 2026-10-16

- **PR #176**: Bump Repo Skills 0.24.1 -> 0.24.3

### 2026-10-15

- **PR #170**: Bump Repo Skills 0.19.5 -> 0.24.1
- **PR #168**: loom: unpin curator.md and guard-loom-workflow.sh (2am#4345 Q7)

### 2026-10-13

- **PR #166**: chore(loom): drop onIdle [auditor] — follow the fleet idle-role setting
- **Issue #140** (closed): README: embed the fleet burndown chart (one line)

### 2026-10-09

- **PR #163**: T1 item 11: ties[] in the array supply spec, ERC re-mint, compound ERC + LVS citation
- **Issue #159** (closed): T1 item 11: declare ties[] in the array supply spec, re-run klt erc, and cite the ERC and LVS reports together

### 2026-10-08

- **Issue #158** (closed): T1 item 11: move the signoff grader pin from klt 0.5.0 to the released 0.6.0 so the power-delivery row is graded
- **PR #161**: chore(signoff): grade with released klt 0.6.0 and retire the vendored checklist
- **Issue #150** (closed): Guard-decision review: rm-scope-unresolved-var never got its own #3898 review, propose keep-flagged

### 2026-10-03

- **Issue #144** (closed): Guard telemetry review 2026-09-28: all four logged patterns confirmed correct denials (keep flagged)
- **Issue #126** (closed): OPERATOR: bronze (T1) grant decision — 10/10 read since 2026-08-22, all holes closed, item 11 now outstanding
- **PR #155**: Record bronze (T1) grant; re-cite items 1, 2, 9, 10 (#126)

### 2026-09-30

- **Issue #141** (closed): loom:curating claim label stuck on PR #139 for 2+ days — Curator dispatch mismatched a PR number for an issue
- **PR #142**: Guard against issue-only claim labels landing on PRs

### 2026-09-29

- **Issue #153** (closed): Consolidate duplicated PVT corner-matrix constants: compare_records.py should reuse render_signoff_table's CORNER_ORDER
- **PR #154**: refactor: reuse render_signoff_table's CORNER_ORDER in compare_records.py
- **Issue #149** (closed): Remove duplicated latest_mc_record_for_claim: reuse signoff.latest_record_for_claim
- **PR #151**: refactor(measurements): remove duplicated latest_mc_record_for_claim

- **Issue #145** (closed): Remove unused repo_relative_path() in sim/lib/env_provenance.py
- **PR #147**: refactor: drop unused repo_relative_path() from env_provenance
- **Issue #143** (closed): merge-pr.sh hardcodes squash merge method; fails 405 when repo has allow_squash_merge:false

### 2026-09-21

- **Issue #135** (closed): layout/README.md Known-tool-gaps #2 caveat is stale: current lvs-array.json does echo options.flatten_reference
- **PR #138**: docs(layout): reword the stale klt options-echo caveat as historical context
- **Issue #128** (closed): Machine-gradeable T1 rows: re-mint LVS input provenance, a klt sim envelope, and repo-relative MC yield records so signoff items 4-6 can verify
- **PR #137**: verify: re-mint LVS/corner/MC evidence so T1 items 4-6 grade met
- **Issue #130** (closed): Guard follow-up to #127: same-command var resolver does not substitute quoted "$VAR" write targets, so the deny message's own remedy fails (06:59 shape)
- **PR #136**: fix(guard): resolve quoted write targets through same-command var assignments
- **Issue #133** (closed): layout/reports/README.md's array-level LVS section is stale: documents mismatch, lvs-array.json now reads match
- **PR #134**: docs(layout): update array-level LVS reporting to current match status
- **Issue #124** (closed): T1 item 11 (power delivery, structural): no klt erc supply spec or report in this repo
- **PR #132**: layout: add the klt erc supply spec and array supply report (T1 item 11)
- **Issue #127** (closed): Guard-decision review: scratch-var exemption misses the klt/KLayout layout cold-start idiom (inline ./layout/verify.sh reproduction denied), propose extending the #65 exemption
- **PR #131**: fix(guard): exempt the klt layout cold-start idiom from unresolved-var denies (#127)
- **Issue #125** (closed): Commit a klt signoff block manifest so this block's T1 state is graded, not hand-read
- **PR #129**: feat: grade this block's T1 checklist state via a klt signoff manifest

### 2026-09-10

- **Issue #121** (closed): layout: add Metal1 landing pads for the 256 wordlines so klt lef-abstract can emit real WL* pin geometry
- **PR #123**: layout: add Metal1 landing pads for the 256 wordlines

### 2026-09-09

- **Issue #120** (closed): Generate the LEF abstract for the 256x32 array with `klt lef-abstract` — first `views/` deliverable (spec/sram.md "Deliverables")
- **PR #122**: views: generate the LEF abstract for the 256x32 array (klt lef-abstract)

### 2026-08-27

- **PR #119**: ratification: install the two-key reviewer variant (EE key + market key)

### 2026-08-26

- **Issue #115** (closed): Champion: Merge-Risk Hold Digest

### 2026-08-25

- **Issue #109** (closed): MC/yield evidence-minting scripts leak absolute /Users/ paths — adopt klt env-provenance going forward
- **PR #117**: fix: stop leaking absolute host paths from evidence-minting scripts (#109)

### 2026-08-24

- **Issue #116** (closed): Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

### 2026-08-22

- **Issue #106** (closed): Re-run sim/pex parasitics and 27-corner PEX deltas against the issue #103 bitcell revision
- **PR #114**: verify: re-run sim/pex parasitics and 27-corner PEX deltas against the issue #103 bitcell
- **Issue #110** (closed): README.md's Status/maturity-ladder text is stale relative to landed signoff and layout evidence
- **PR #113**: docs: correct README.md's stale Status/maturity-ladder text
- **Issue #108** (closed): Array-level LVS now matches with klt lvs's flatten_reference option — refresh layout/reports/lvs-array.json and layout/README.md
- **PR #112**: fix: enable array-level LVS via klt lvs's flatten_reference option
- **Issue #100** (closed): T1/bronze checklist re-read against current evidence (first since #13, and the first under klayout-tools 0.3.0)
- **PR #111**: spec: T1/bronze checklist re-read against current evidence (2026-08-22)
- **Issue #103** (closed): Native gf180mcu DRC deck finds 21 violations on the custom bitcell the curated deck cannot see
- **PR #107**: fix(layout): re-derive bitcell implant, contact-M1 and Nwell margins from the rules that actually govern them
- **Issue #101** (closed): design/README.md still prescribes replacing the placeholder bitcell, which layout/README.md records as already done
- **PR #105**: docs: correct design/README.md's stale placeholder-bitcell prescription
- **Issue #8** (closed): Survey gf180mcu's design rules for SRAM-specific allowances, and run the open DRC deck against the foundry's own bitcell
- **PR #104**: docs(layout): survey gf180mcu SramCore DRC allowances, DRC the foundry bitcell
- **Issue #7** (closed): Spec gap: the write-margin criterion cites a timing target that does not exist, and signoff as ratified cannot reach T1
- **PR #102**: spec: ratify no independent write timing target, fixed 2ns pulse width
- **Issue #10** (closed): Lay out the 6T bitcell as a tileable cell, DRC- and LVS-clean standalone and tiled
- **Issue #6** (closed): Bootstrap the sim harness, PDK environment, and evidence CI from gf180-bandgap

### 2026-08-21

- **Issue #9** (closed): Draw and size the 6T bitcell, and measure read SNM, hold SNM, write margin and access time across the ratified nine corners
- **Issue #23** (closed): Run DRC, LVS, and post-layout PEX verification on the SRAM macro (T1 items 3, 4, 7)
- **Issue #95** (closed): Adapt SRAM PVT testbenches so klt pex can close T1 item 7 (post-layout PEX)
- **PR #99**: feat: add klt-pex-native and by-hand PEX evidence for SRAM access time and write margin
- **Issue #97** (closed): guard: rm_scope_mktemp_same_command_safe() (#6520) has no TMPDIR gate, conflicting with local pdk_env.sh scratch-var test intent
- **Issue #94** (closed): main's harness (npm run check:ci) red again: test:guards symlinked-ancestor cases fail since the f1fa04c resync
- **PR #98**: fix(guard): restore symlink-ancestor and for-loop-loopvar fixes after resync
- **PR #96**: verify: run DRC, LVS, and post-layout parasitic extraction on the SRAM macro
- **Issue #90** (closed): Ratify a numeric target_yield (or explicit 'no target') for read SNM, hold SNM, and write margin
- **PR #93**: spec: ratify no numeric target_yield for read/hold SNM and write margin

### 2026-08-19

- **Issue #88** (closed): Loom resync (f1fa04c) wiped guard-hook fixes again — restore test:guards pattern (like #80/#83/#84/#85)
- **PR #92**: fix(guard): restore guard-destructive-generic.sh fixes wiped by the f1fa04c Loom resync
- **Issue #86** (closed): Pin gf180mcuD (not gf180mcuC) — spec, design/, layout/, and sim/ evidence all cite the wrong shuttle variant
- **PR #87**: fix(spec): pin gf180mcuD PDK variant, not gf180mcuC
- **Issue #20** (closed): Operator decision: ratify whether read/hold SNM and write margin are statistical (Monte-Carlo-requiring) spec rows
- **PR #91**: spec: ratify read/hold SNM and write margin as statistical rows
- **Issue #19** (closed): Operator decision: ratify this block's T1 evidence-tier kind (analog/digital/mixed-signal) in spec/sram.md
- **PR #89**: docs(spec): ratify this block's T1 evidence-tier kind as analog
- **Issue #17** (closed): Guard-decision review: rm-scope-outside-repo fired on own memory-store cleanup, propose scoped allowlist
- **Issue #11** (closed): Guard-decision review: worktree-write-confinement-unresolved-var fired correctly, propose keep-flagged
- **Issue #44** (closed): Guard-decision review: git clean -fd ask fired on scoped worktree cleanup, propose keep-flagged
- **Issue #42** (closed): Guard-decision review: worktree-write-confinement false-DENY on '>=' inside a python3 heredoc body
- **Issue #41** (closed): Guard-decision review: gh-api-rawfield-body-literal-at fired correctly, propose keep-flagged
- **Issue #56** (closed): Guard-decision review: stash-scope:create-redirect denied raw 'git stash push' in a linked worktree, propose keep-flagged
- **Issue #39** (closed): Guard-decision review: worktree-write-confinement fired on scratch ngspice run in /tmp, propose keep-flagged
- **Issue #82** (closed): rm-scope-unresolved-var (guards.rmScope=repo) also blocks the pdk_env.sh mktemp-scratch cleanup, masking the #65 restoration
- **PR #85**: fix(guard): exempt the pdk_env.sh mktemp-scratch cleanup from rm-scope-unresolved-var
- **Issue #81** (closed): The Loom resync (2f8fdd8) also reverted the #65 pdk_env guard fix; several hook test suites are ungated and red
- **PR #84**: fix(guard): restore write-confinement keyword-strip and redir/cd fixes wiped by the Loom resync

### 2026-08-18

- **PR #83**: fix(guard): restore pdk_env.sh scratch-var exemption (#65) wiped by the Loom resync
- **Issue #49** (closed): Guard-decision review: sed -i with a quoted script containing space+'../' falsely denies a safe in-worktree write
- **Issue #78** (closed): main's harness (npm run check:ci) is red: test:guards fails on Linux CI after the Loom resync (2f8fdd8)
- **PR #80**: fix(guard): restore for-loop binding (#66) and symlinked-root resolution (#70) wiped by the Loom resync
- **Issue #77** (closed): guard-destructive-generic.sh: main's BSD sed -i fix (#66) fail-opens on crafted out-of-worktree targets
- **PR #79**: fix(guard): disambiguate BSD sed -i script arg from a real file operand
- **Issue #75** (closed): layout/verify.sh: bitcell LVS reports mismatch, not the README's documented match
- **PR #76**: fix(layout): derive LVS reference bulk-net rewrite from actual extraction, not hardcoded names
- **Issue #33** (closed): Operator: #21's implementation is complete on local branch feature/issue-21 but cannot be pushed (403 Contents write) — same credential gap as #29
- **Issue #29** (closed): Operator: this session's forge credential cannot push/comment/edit on this repo — blocks #18's PR and closing comment

### 2026-08-17

- **Issue #73** (closed): Document the macro ceiling (512×8) and a recommended KB-scale tiling / DFFRAM path for integrators
- **PR #74**: docs: record the gf180mcu macro ceiling and a KB-scale integration path
- **Issue #68** (closed): Two more worktree-write-confinement false positives: cp/mv '2>/dev/null' destination, and unresolved $VAR in the tracked cd argument
- **PR #72**: fix: exclude >/>> redirection tokens and resolve cd's tracked var in write-confinement scan
- **Issue #67** (closed): Guard bypass: Bash write-confinement extracts no targets from a one-line 'do'/'then' compound statement
- **PR #71**: fix(guard): strip leading do/then/else/elif/{ before write-idiom scan
- **Issue #69** (closed): guard write-confinement: symlinked TMPDIR (macOS) causes main-root path mismatch, denies silently become allows
- **PR #70**: fix(guard): resolve write targets to physical form for symlinked-TMPDIR write-confinement
- **Issue #64** (closed): Guard-decision review: worktree-write-confinement-unresolved-var blocks well-formed scratch-dir ngspice pattern
- **PR #65**: fix: exempt pdk_env.sh-sourced mktemp -d scratch vars from unresolved-var write-confinement deny
- **Issue #63** (closed): Guard-decision review: worktree-write-confinement false-positives on in-worktree relative-path writes
- **PR #66**: fix(guard): resolve for-loop vars and BSD sed -i '' suffix in Bash write-confinement scan
- **Issue #27** (closed): Publish an aggregated characterization report across all spec rows and corners (T1 item 8)
- **PR #62**: feat: add aggregated per-corner + MC/yield characterization report
- **Issue #59** (closed): Write margin is derived two different ways in sim/ (WTV vs VDD - WTV), and one of them scores an unwritable cell as best-in-class
- **PR #61**: fix: report write margin as WTV directly instead of VDD - WTV
- **Issue #53** (closed): spec/sram.md "Corner set" arithmetic error: 3x3x3 labeled "9 corners" but the actual matrix (and every committed sim/ record) has 27 points
- **PR #60**: spec: correct the ratified corner count to 27 and compute it in the sweep harness
- **Issue #26** (closed): Produce Monte Carlo / yield evidence for the SRAM stability margins (T1 item 6)
- **PR #58**: sim: add Monte Carlo mismatch campaigns and klt yield reports for the three stability margins
- **Issue #25** (closed): Run the ratified 9-corner PVT verification and record SNM/write-margin/access-time (T1 item 5)
- **PR #57**: sim: add explicit per-corner PVT PASS/FAIL signoff rollup with CI freshness enforcement
- **Issue #52** (closed): spec/sram.md says "3 x 3 x 3 = 9 corners" for a 27-point corner set; the harness and every record enumerate 27
- **Issue #22** (closed): Produce the SRAM macro layout / GDS (T1 item 2)
- **PR #55**: layout: draw the device-level 6T bitcell and tile it into the 256x32 array
- **Issue #47** (closed): write-margin testbench: WTV reported as first-fail point, not last-success point (~2.5% VDD quantization)
- **PR #54**: fix: record last-succeeding write trial in write-margin WTV sweep
- **Issue #50** (closed): [test] permission probe - please ignore/delete
- **Issue #24** (closed): Ship the ratified 9-corner spec testbenches (T1 item 9)
- **PR #46**: sim: add 9-corner PVT testbenches for read SNM, hold SNM, write margin, and access time

### 2026-08-16

- **PR #36**: layout: add 256x32 array-tiling generator infra with placeholder bitcell
- **Issue #21** (closed): Commit the SRAM bitcell/array schematic sources and derived netlist (T1 item 1)
- **PR #37**: design: add 6T bitcell + 256x32 array schematics and derived netlists
- **Issue #28** (closed): Add CI that validates the harness and evidence-record formats (T1 item 10)
- **PR #31**: ci: add CI workflow validating harness and evidence-record format
- **Issue #18** (closed): Decompose the T1 re-read's failing items (#13) into dispatchable issues

### 2026-08-15

- **Issue #13** (closed): T1/bronze checklist re-read against current evidence (2026-08-15)

### 2026-08-05

- **Issue #2** (closed): Ratify the target spec
- **PR #5**: docs: ratify target spec into spec/sram.md, replace README DRAFT table
- **Issue #3** (closed): permission probe - please ignore
- **Issue #1** (closed): Answer the bitcell question before ratifying anything
- **PR #4**: docs: record the bitcell decision — draw a custom array, don't integrate the hardened macro
