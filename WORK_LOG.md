# Work Log

Chronological record of merged PRs and closed issues, maintained automatically
by the Guide role's document maintenance phase. Newest entries first.

## Archives

- [2026-09](work_log/WORK_LOG_2026-09.md)
- [2026-08](work_log/WORK_LOG_2026-08.md)

### 2026-11-17

- **PR #447**: fix: resolve minter unit streams from the report's declared paths
- **PR #445**: docs(pex): point write-margin status cell at deck-mode regeneration path
- **PR #443**: docs(sim): finish the run_corner_sweep.sh tense cleanup in deck_adapter and snm_extract
- **PR #442**: sim: port the pex write-margin legs to deck mode with a record minter
- **PR #440**: docs(sim): sweep the stale run_corner_sweep.sh prose left by the #230 cutover
- **PR #438**: Retire the local sim grid launchers at the deck-mode cutover
- **Issue #444** (closed): sim: mint_corner_records.py hardcodes <corner>/stdout.bin instead of the report's declared stream paths
- **Issue #441** (closed): Residual present-tense run_corner_sweep.sh prose in deck_adapter.py and snm_extract.py (outside #439's enumerated set)
- **Issue #439** (closed): Sweep the stale run_corner_sweep.sh prose left in live sim/lib files after the #230 cutover
- **Issue #230** (closed): Retire hand-rolled local ngspice corner/MC grid launchers in favour of klt sim
- **PR #435**: docs: record the pinned hs a environment ruling and annotate the unpinned 2026-09-21 MC sample-sets
- **PR #434**: chore(loom): resync installed Loom to v0.19.1306
- **PR #433**: refactor: remove dead solve_inverse helper and its test-only caller
- **PR #414**: docs(ci): name array-schematics in attestation and fix harness test locations
- **Issue #421** (closed): Remove dead solve_inverse from sim/lib/snm_extract.py (test-only caller)
- **Issue #389** (closed): Decide which ngspice environment future sim campaigns standardize on (deterministic 'hs a' vs unpinned MC)
- **Issue #379** (closed): ci.yml header and repo-hygiene attestation prose: two residual accuracy gaps (1 of 5 jobs unnamed; harness suites not all under sim/lib/)
- **PR #431**: docs: state corners[].result_lines as a required clause in the deck-parity tree listing
- **PR #430**: fix: mc-reduce fails closed on deck-bytes drift
- **PR #426**: docs: exempt the full-grid receipt from the corners[].result_lines clause only
- **Issue #429** (closed): deck-parity README's directory-tree listing still states corners[].result_lines as a property of committed deterministic receipts
- **Issue #400** (closed): Committed-bytes rule's corners[].result_lines clause is satisfied by zero committed deterministic receipts
- **Issue #373** (closed): deck_adapter mc-reduce: the MC path never checks composed_deck_sha256, so MC receipts have no deck-bytes-unchanged check at all
- **PR #425**: refactor: single-owner klt request skeleton and Q-word grading for the three macro-netlist benches
- **Issue #423** (closed): ungated_receipt_headings docstring asserts a false fence invariant (and hides a fenced-example hard error)
- **PR #424**: fix: correct fenced-row slot invariant in ungated_receipt_headings docstring
- **Issue #420** (closed): Evidence gate: ungated-receipt-table warning misreads a fenced `| File | What |` row as a second table
- **PR #422**: fix: skip fenced "| File | What |" rows in the ungated-receipt warning
- **Issue #415** (closed): Ungated-receipt-table warning text misdescribes the newly-surfaced second-table shape
- **PR #419**: fix: name the second-table cause in the ungated-receipt warning
- **Issue #392** (closed): Four committed sim/pex/*/testbench/tb_* benches are pinned by no signoff wrapper
- **PR #418**: fix: pin the four nested sim/pex testbenches, widen the item-9 gate to any depth
- **Issue #388** (closed): Consolidate duplicated klt request skeleton and Q-word grading across smoke, access-power, min-clock-pulse benches

### 2026-11-16

- **PR #384**: chore(loom): resync installed Loom to v0.19.1302
- **PR #349**: config: widen Guide doc-maintenance debounce windows to 6h/12h
- **PR #413**: fix: decide ungated-table warning from the receipt parser's own walk
- **Issue #408** (closed): Evidence gate: ungated-receipt-table warning's nearest-heading scan diverges from parse_files_tables in two measured shapes
- **PR #336**: ci: run the evidence-format check once, in its own job only
- **Issue #332** (closed): Remove the duplicated evidence-format CI run and the stale 'nothing has landed yet' scaffolding framing
- **PR #411**: docs(sim): state the min-clock-pulse OPS table is imported, not copied
- **Issue #406** (closed): Stale docstring: test_min_clock_pulse.py OPSVerbatimTest still says 'copied verbatim'
- **PR #409**: fix(sim): name both reports and omit empty halves in grade-set corner-set error
- **Issue #403** (closed): grade-set: cross-report corner-set error names the wrong report when the short one is first, and prints empty halves
- **PR #407**: ci: report receipt files-table gate coverage, warn on ungated receipt tables
- **Issue #372** (closed): Evidence gate: receipt "Files in" coverage is invisible — a receipt with no matching table heading is silently ungated
- **PR #405**: refactor(sim): import smoke.py stimulus into pulse.py instead of copying
- **Issue #394** (closed): Dedupe pulse.py's copied smoke.py stimulus/testbench code (~50-110 LOC)
- **PR #402**: reports: guard --print templates like --set-format, naming the committed report
- **Issue #393** (closed): commit_report.py: --print templates are unguarded, so a malformed one tracebacks AFTER out.json is already committed
- **PR #401**: fix: grade-set completeness becomes a set test; validate before printing
- **PR #398**: docs: scope deck-parity committed-bytes rule to reduce output, relabel byte figure as raw text
- **Issue #382** (closed): sim: grade-set completeness is a distinct count, not a set — an off-grid variant can substitute for an omitted grid point
- **Issue #381** (closed): Amended committed-bytes rule: MC receipts carry no preserved RESULT: lines, and the stated byte cost measures raw line text rather than committed growth
- **PR #395**: ci: gate the item-9 testbench attestation on what sim/ ships
- **PR #391**: reports: catch TypeError and AttributeError in --set-format template failures
- **PR #387**: fix: label MC |delta| distribution stats from summary["unit"]
- **PR #367**: ci: add repo-hygiene gate bounding tracked blob size, binary type, venv paths
- **PR #366**: ci: resolve receipt "Files in" table entries against committed bytes
- **PR #386**: feat(sim): full 9-corner MC deck-mode parity receipt, 13,680 units, with pin-attributed negative-control finding
- **PR #383**: reports: template _note counts via --set-format; lint failures name the raw input
- **PR #380**: docs: index the spiceinit-pin receipt in deck-parity README and link the now-landed unpinned receipt
- **PR #377**: fix: label metric deltas with each family's unit from RECORD_CLAIMS
- **PR #375**: fix: grade-set counts distinct variant tags and rejects a repeated report
- **PR #374**: feat: preserve matched RESULT: lines per corner in deck_adapter reduce
- **Issue #385** (closed): commit_report.py: --set-format does not catch TypeError, so a list-subscript template tracebacks instead of naming the field
- **Issue #378** (closed): render_mc_markdown still hardcodes "V" on the per-sample |delta| distribution lines
- **Issue #361** (closed): No CI guard against an accidentally committed venv / vendored binary tree
- **Issue #357** (closed): Signoff T1 item 9 attests a named testbench set that now omits sim/access-power/testbench/tb_access_power.klt.spice
- **Issue #356** (closed): check-evidence-format.sh does not verify that a receipt's cited artifact files exist
- **Issue #371** (closed): commit_report.py: three small follow-ups from the #340 review (templated --set, lint-failure diagnostic, README scoping)
- **Issue #370** (closed): sim/deck-parity: index the spiceinit-pin receipt and drop its now-stale "not on main yet" note
- **Issue #365** (closed): sim: grade-set's variant-completeness guard counts occurrences, not distinct grid points
- **Issue #360** (closed): Full-grid deck-parity receipts commit no raw RESULT: lines, so the RESULT:-family exact-match claim is not re-derivable from committed bytes
- **Issue #359** (closed): parity_compare.py hardcodes "V" as the unit for every metric delta, mislabelling the access-time families

### 2026-11-15

- **PR #369**: fix: fail closed when a request lacks composed_deck_sha256
- **PR #364**: feat(sim): first live Monte Carlo deck-mode parity receipt, 3 families x 2 corners
- **PR #346**: feat(sim): pin the ngspice environment via a staged run-directory .spiceinit
- **PR #344**: refactor(reports): one guarded scrub path for every committed klt report
- **Issue #362** (closed): deck_adapter: expected_from_request silently returns no composed_deck_sha256, re-opening the fail-open one level up
- **Issue #340** (closed): Collapse layout/reports/generate.sh's ten inline python3 -c scrub blocks into one helper, guarded by klt env-provenance scan
- **Issue #338** (closed): Pin ngspice compatibility mode in deck-mode requests instead of inheriting the executing host's .spiceinit
- **PR #363**: feat(layout): mint the 64 x 128 array DRC/extract/LVS report trio under the pinned klt
- **PR #358**: fix: fail closed on unreported deck_sha256 in reduce_report
- **PR #355**: sim: full-grid deck-mode parity receipt, 27 corners x 5 families, via mechanical parity_compare
- **PR #354**: refactor: derive the repo root via find_repo_root() at the last five fixed-depth sites
- **PR #352**: fix: drop dead spacing_of() stub from the macro generator
- **PR #351**: data: measure minimum clock pulse width per corner on the macro bench (#328)
- **PR #350**: sim: dynamic access energy per read/write cycle on the macro netlist, 27 corners
- **PR #348**: build: remove dead worktree:return npm script entry
- **Issue #347** (closed): deck_adapter reduce: a unit that omits deck_sha256 silently passes the deck-bytes-unchanged check
- **Issue #345** (closed): deck_adapter.reduce_report() inlines the RESULT:/RESULT-ERROR: grammar its own module already re-exports
- **Issue #342** (closed): Remove the dead spacing_of() stub in layout/macro/generate.py: no callers, and wrong for M1 and vias
- **Issue #337** (closed): Adopt sim/lib/repo_root.py at the 5 sites still hand-rolling a fixed-depth repo root
- **Issue #335** (closed): Remove dead npm script worktree:return — its target was deleted by a Loom resync
- **Issue #329** (closed): sim: dynamic power per read and write access on the macro-smoke netlist, 27 corners
- **Issue #328** (closed): sim: minimum clock pulse bench on the macro-smoke netlist over the 27 corners
- **Issue #327** (closed): Commit DRC and LVS reports for the 64 x 128 array the macro is built on
- **PR #339**: sim: record the fleet deck-mode parity receipt at tt_25c_3.30v and bound build/reduce to a corner subset

### 2026-11-14

- **PR #334**: feat(layout): land the sram_256x32 macro GDS, pin check and macro DRC report
- **PR #333**: refactor(sim): give the ratified corner matrix a single owner in sim/lib
- **PR #325**: docs: roadmap as of 2026-11-13
- **Issue #331** (closed): Give the ratified 27-corner matrix a single owner: 4 copies, 3 unguarded
- **Issue #326** (closed): Land the macro GDS, pin check and macro DRC report (split from #247; LVS stays there)

### 2026-11-13

- **Issue #118** (closed): Champion: Merge-Risk Hold Digest

### 2026-11-12

- **PR #321**: Bump Repo Skills 0.25.10 -> 0.26.1

### 2026-11-08

- **PR #317**: fix(sim): record report-relative samples path in klt yield reports
- **Issue #160** (closed): T1 item 6: make the klt yield report's samples path resolve from any working directory

### 2026-11-07

- **PR #313**: Bump Repo Skills 0.25.1 -> 0.25.10

### 2026-11-06

- **PR #311**: sim: add bitcell standby-leakage bench with 27-corner klt sim record
- **Issue #310** (closed): sim: add a klt sim bitcell standby-leakage bench over the 27 corners (recorded Power row)

### 2026-11-04

- **PR #294**: docs(spec): record area, min clock pulse and power as no-threshold rows
- **Issue #293** (closed): spec: no area, min-clock-pulse or power rows in spec/sram.md

### 2026-11-03

- **PR #306**: ci: run check_macro_pins.py from the array-schematics drift gate
- **Issue #304** (closed): check_macro_pins.py is documented as a guard but never runs: wire it into CI or delete it

### 2026-11-01

- **PR #300**: refactor: share router A* search, override only the heuristic in FastRouter
- **Issue #299** (closed): Dedupe FastRouter._search: ~50-line copy of the column A* router differing only in heuristic
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

