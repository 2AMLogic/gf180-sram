# Roadmap

gf180-sram builds a 1 kB (256 x 32) 1RW SRAM macro on the gf180mcu open PDK to
find out what breaks when `klt` is pointed at a memory array, and to get it fixed
upstream.

**Status as of 2026-11-13, `main` @ `caedcec`**, tracker as read that day.
[`WORK_PLAN.md`](WORK_PLAN.md) is the machine-generated label view of the same.

## Where it stands

Against the README's maturity ladder (bitcell question answered → spec ratified →
bitcell characterized → array assembled → DRC/LVS-clean → abstract and Liberty
views → shuttle seat → measured silicon):

| Step | State | Evidence |
|---|---|---|
| Bitcell question, spec | Done | `spec/bitcell-decision.md`, `spec/sram.md` |
| Bitcell characterized, 27 corners | Done, overall PASS | `sim/signoff-summary.md` |
| Array assembled, DRC/LVS-clean | Done for the 256 x 32 core | `layout/reports/drc-array.json`, `lvs-array.json` (`status: match`) |
| T1 checklist | 11/11 met, graded by `klt signoff` under klt 0.8.0 | `signoff/signoff-report.json`; grant record `spec/t1-grant-2026-10-02.md` |
| Macro interface and periphery architecture | Ratified | `spec/macro-interface-decision.md` (#198), `spec/periphery-architecture.md` (#202) |
| Periphery schematics and macro top netlist | Done | `design/netlist/sram_256x32.spice` (#203) |
| Periphery block layouts | Done, each DRC-clean and LVS `match` | row path (#204), column path (#205), `sram_ctrl` and `col_decode` (#246); reports under `layout/reports/` |
| Macro functional smoke | Done, 27 corners, reduced array | `sim/macro-smoke/` (#203, #217) |
| LEF abstract | Array core only | `views/sram_256x32_array.lef`, 322 pins all `drawn` |
| Macro GDS, macro LEF, Liberty | Not on `main` | #247, #199, #200 |
| Shuttle seat, measured silicon | Not started | n/a |

Known soft spots in the T1 evidence, all disclosed in the repo:

- Item 4 (LVS) is graded `met` with `input_verified: null`: the array LVS input
  was a temporary extracted netlist, so no committed file is re-hashed (#285).
- Item 7 has no post-layout path for read SNM and hold SNM (`sim/pex/README.md`).
- Reference sim records ran under the previous open_pdks pin; the pin moved to
  `f6eeac7` (#173) and the records have not been re-run under it (#272).

Most recent merged work: the standby-leakage bench (#310), report-relative
samples paths in yield reports (#160), `check_macro_pins.py` in CI (#304).

## Now

No open issue carries `loom:issue` today; every tracked item is blocked or held
(see "Blocked and waiting"). The four items below are startable and have no
issue yet.

1. **Land the macro GDS, pin check and macro DRC, split from #247's LVS.**
   Branch `feature/issue-247` already holds `layout/macro/generate.py`,
   `layout/macro/check_pins.py` and `layout/macro/sram_256x32.gds`. Done when
   those are on `main`, `check_pins.py` passes on the 107 signal pins plus
   `VDD`/`VSS`, and `layout/reports/drc-macro.json` is committed. The macro LVS
   criterion stays on #247.
2. **Commit DRC and LVS reports for the 64 x 128 array.** `layout/verify.sh`
   steps 8 and 9 run them, but `layout/reports/` holds no report for the array
   the macro is actually built on. Done when `drc-array-64x128.json` and
   `lvs-array-64x128.json` exist with provenance and `layout/reports/README.md`
   lists them.
3. **Minimum clock pulse bench.** `spec/area-clock-pulse-power-decision.md`
   records this row as "not yet measured". Done when a `klt sim` request sweeps
   `CLK` high/low width on the macro-smoke netlist over the 27 corners and a
   record under `sim/` states the shortest passing width per corner.
4. **Dynamic power per access.** Same decision record, same status. Done when a
   27-corner `klt sim` record states supply charge per read and per write cycle
   on the macro-smoke netlist, with the reduced-array limit stated.

## Next

- **Macro LVS verdict** (#247, parent #206, tracker #201). Done when
  `layout/reports/lvs-macro.json` is a real verdict against
  `design/netlist/sram_256x32.spice`, and `layout/README.md` drops the
  "periphery not drawn" scope text. Blocked on
  [klayout-tools#5322](https://github.com/2AMLogic/klayout-tools/issues/5322)
  (open): the flat compare of about 53k devices gave no verdict in about 100
  minutes, and the hierarchical route has no working GDS-to-verdict form.
- **Array LVS bound to a committed input** (#285). Done when `lvs-array.json` is
  `match` under klt 0.8.0 with an input hash equal to a committed file, and
  signoff items 4 and 11 cite it. Blocked on run time: inline extraction over
  the 49,152-device array ran past 60 minutes on one core with no result.
- **Macro LEF abstract** (#199). Done when `klt lef-abstract` emits a LEF with
  the ratified 109 pins and `klt socket-check` is clean. Needs the macro GDS
  (Now item 1); whether it should also wait for the macro LVS verdict is open.
- **Launcher retirement** (#230). `sim/lib/deck_adapter.py` and its offline
  tests are done. Done when one corner per family through `klt sim` deck mode
  matches the committed record, then `run_corner_sweep.sh` and the Monte Carlo
  pool are removed. The tool-side prerequisite klayout-tools#4109 is closed;
  the parity run itself is held for an operator decision.
- **Re-qualify reference records under `f6eeac7`** (#272). Done when each of the
  five claims and three Monte Carlo families has a new record with a
  **Supersedes** line and `sim/signoff-summary.md` is regenerated. After #230.
- **Shared layout-generator helpers** (#252). Parked behind #247.

## Later

- **Liberty timing views** (#200, consumer request #197). First question: what
  simulated sense path supplies clock-to-`Q`, setup and hold?
  `spec/macro-interface-decision.md` forbids backfilling them from the bitcell
  proxy, and the full 8,192-cell transient did not finish in 10 minutes.
- **Macro and LEF name.** #197 records a consumer instantiating a prefixed
  name that appears nowhere in this tree. Which name ships needs a decision
  record in `spec/` before #199.
- **Retire the 256 x 32 array files?** `layout/README.md` leaves them until
  macro assembly; `layout/layout.signoff.json` (T1 item 2) binds the 256 x 32
  GDS, so what does the manifest bind once the macro is the layout of record?
- **Post-re-pin evidence re-read.** #285 records that all evidence is re-read
  once after #272 lands. Question: does that re-read grade the macro or the core?
- **Stretch goals in `spec/sram.md`:** parameterized generator, 1RW1R port.
  Not before the fixed 1RW macro has LVS-clean GDS, LEF and Liberty. Shuttle
  seat and measured silicon follow those; no plan is recorded in this repo.

## Blocked and waiting

| Item | Waiting on |
|---|---|
| #247, #206, #201 macro assembly and LVS | klayout-tools#5322 (open) |
| #285 array LVS freshness | an execution window longer than 60 minutes, or a cheaper extraction route in `klt` |
| #230 launcher retirement | operator authorization for one bounded parity run (`loom:operator`) |
| #272 record re-qualification | #230 |
| #262 / PR #264 artifact store for new evidence | PR is conflicting with `main` and held (`loom:operator`); no Judge verdict because CI did not execute on its head |
| #199, #200, #197 macro views | #201 |
| #252 helper consolidation | #247 |

## Not planned

- Competing with or reimplementing OpenRAM or the foundry `gf180mcu_fd_ip_sram`
  macros (README, "Why this block, stated honestly").
- A KB-scale path beyond the single 1 kB instance; options elsewhere are
  recorded in `spec/kb-scale-integration.md`.
- A post-layout read/hold SNM measurement through `klt pex`: recorded as
  structural in `sim/pex/README.md`, not as a tool gap.
- Relaxing the ratified spec to make a result pass (`CLAUDE.md`).
