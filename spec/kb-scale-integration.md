# Integration note: the macro ceiling, and a KB-scale path for integrators

**Status**: Recorded, 2026-08-17
**Resolves**: #73 ("Document the macro ceiling (512×8) and a recommended
KB-scale tiling / DFFRAM path for integrators")
**Kind**: informational integration guidance, not a change to this repo's
ratified target. Nothing in `spec/sram.md` (organization, ports,
deliverables, characterization) is amended by this record — see "What this
record does not change."

## Gap

gf180mcu's open PDK ships exactly **four** SRAM macros, all in the
foundry-hardened `gf180mcu_fd_ip_sram` IP library documented in
[`bitcell-decision.md`](bitcell-decision.md): `64×8`, `128×8`, `256×8`,
`512×8`. An integrator who wants KB-scale RAM for an MCU-class design (8–32
KB is a typical want) does not learn the ceiling, or what to do above it,
from anything this repo previously published. This record fixes that.

## The macro ceiling, stated up front

The largest single foundry macro is **`gf180mcu_fd_ip_sram__sram512x8m8wm1`
— 512 words × 8 bits = 4,096 bits = 512 bytes = 0.5 KB.** That is the ceiling
of a *single instance* of the PDK's own hardened SRAM IP. Measured directly
from the shipped LEF (`SIZE` field, all four depths, `open_pdks` commit
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, the same PDK snapshot
`bitcell-decision.md` verifies against):

| Macro | Bits | Bytes | LEF size (µm) | Area | Area / bit |
|---|---|---|---|---|---|
| `sram64x8m8wm1` | 512 | 64 B | 431.86 × 232.88 | 0.1006 mm² | 196.4 µm² |
| `sram128x8m8wm1` | 1,024 | 128 B | 431.86 × 268.88 | 0.1161 mm² | 113.4 µm² |
| `sram256x8m8wm1` | 2,048 | 256 B | 431.86 × 340.88 | 0.1472 mm² | 71.9 µm² |
| `sram512x8m8wm1` | 4,096 | 512 B | 431.86 × 484.88 | 0.2094 mm² | 51.1 µm² |

(All four share the same 431.86 µm width; only the height, which scales with
word count, changes. Area/bit falls with depth because the fixed periphery
— decoder, sense amps, I/O — amortizes over more rows, which is also why
Option A below tiles the deepest macro rather than a shallower one.)

**Evidence tier: measured.** These numbers are read directly from the PDK's
own `LEF` `SIZE` statement, not estimated — reproduce with:

```bash
grep SIZE ~/.volare/gf180mcuC/libs.ref/gf180mcu_fd_ip_sram/lef/gf180mcu_fd_ip_sram__sram512x8m8wm1.lef
```

### What this block does about it

**This repo is neither a wrapper/tiler over the four PDK macros above, nor a
KB-scale replacement for them.** Per `bitcell-decision.md`, this repo draws
a **new, custom 6T bitcell and array** (`018SRAM_cell1`-topology-inspired
but independently implemented and laid out), and per `sram.md` its ratified
target is a single fixed **256 × 32 (1 KB) instance** — a different
organization (32-bit-wide word, not 8-bit) at a comparable total bit count
to the foundry macros' upper end, built to exercise array generation,
macro-level LVS, and abstract/Liberty *generation* tooling (`CLAUDE.md`),
not to serve as a KB-scale IP product. A parameterized generator, which
could in principle grow past 1 KB, is only a **stretch goal** (`sram.md`,
"Organization"), not built yet. So today: **an integrator who needs more
than ~1 KB from this repo's own macro has no path from this repo at all** —
the sections below are about the wider gf180mcu ecosystem, not this block's
own roadmap.

## KB-scale users: recommended path

Two real options exist today for tiling gf180mcu SRAM above the 512×8
ceiling. A third (OpenRAM) does not.

### Option A — tile the foundry `gf180mcu_fd_ip_sram` macros

Use the deepest macro (`512×8`) as the tiling unit — it has the best area/bit
of the four (51.1 µm²/bit measured above), so it minimizes macro count for a
given capacity. Bank-select decode and a per-macro `CEN` gate (from the
address bits above each macro's own `A[8:0]`) pick the active bank; an
output mux (or a shared, `CEN`-gated tri-state/OR bus, depending on the
target flow's macro I/O style) combines the `Q[7:0]` buses.

**Evidence tier: derived** (macro footprint arithmetic from the measured
table above; excludes bank-select/decode/floorplan overhead — see "Mux /
bank-select cost" below, which is *not* included in these numbers):

| Capacity | `512×8` macros needed | Macro-footprint-only area |
|---|---|---|
| 8 KB | 16 | 3.35 mm² |
| 16 KB | 32 | 6.70 mm² |
| 32 KB | 64 | 13.40 mm² |

This is a **lower bound**: it sums only the macros' own `LEF SIZE` footprints
and does not include bank-select mux/decode logic or the floorplan routing
channels between macro instances, neither of which this repo has built or
measured (see "Mux / bank-select cost"). It is offered here specifically
because the issue that opened this record flagged the alternative — "an area
class the row does not state (~1.5–3 mm² by rough estimate — unverified
here)" — as an unverified guess; the measured-macro-sum figure above (6.70
mm² for 16 KB) is **roughly 2–4x that guess**, which is itself a useful
correction: the rough estimate undercounted before any glue logic is even
added.

**Timing class** (also measured, not estimated): the Liberty `CLK`→`Q` rise
delay at the `tt_025C_3v30` corner (one of each macro's 15 shipped PVT
corners — see `bitcell-decision.md`), across the full 7×7 input-transition ×
output-load table, is essentially **flat with depth**:

| Macro | `CLK`→`Q` rise delay range, `tt_025C_3v30` |
|---|---|
| `sram64x8m8wm1` | 6.17 – 7.36 ns |
| `sram128x8m8wm1` | 6.29 – 7.48 ns |
| `sram256x8m8wm1` | 6.50 – 7.71 ns |
| `sram512x8m8wm1` | 6.92 – 8.13 ns |

I.e. a single macro access is in the **6–8 ns class** regardless of which of
the four depths is used — the delay is dominated by fixed sense-amp/output
buffer stages, not by row/column count in this depth range. A tiled
multi-bank system adds the bank-select mux's own delay on top of this
per-macro number (not measured here — see below).

### Option B — DFFRAM (standard-cell, flip-flop/latch based)

[DFFRAM](https://github.com/AUCOHL/DFFRAM) (`AUCOHL/DFFRAM`, Apache-2.0) is
a standard-cell-library-based memory compiler that builds RAM out of
DFF/latch cells and a custom placer/router rather than a dedicated bitcell —
no full-custom bitcell layout is needed, so it can, in principle, target any
platform with a digital standard-cell library and a place-and-route flow.

**Checked live against the upstream repo (2026-08-17) rather than assumed**:
DFFRAM's own platform-support table lists `gf180mcuD (Latches/DFF)` as
**configured but not signoff-clean** — "No\* (Hold violations in the
Netlist)" — and not silicon-proven, in contrast to `sky130A` (Latches),
which is both signoff-clean and silicon-proven. So DFFRAM is not, as of this
check, a drop-in KB-scale solution for gf180mcu; it is a starting point that
needs the gf180mcu hold-violation issue resolved (or worked around) before
it is signoff-clean on this PDK.

DFFRAM's own published area/bit-density comparison table is for its
signoff-clean platform (`sky130A`), not gf180mcu, so it is cited here only
as an **order-of-magnitude, cross-PDK reference**, not a gf180mcu number:
roughly 26,000–27,000 bits/mm² for the DFFRAM compiler's own placer, fairly
flat from 512 B to 8 KB. Do not read this as a gf180mcu area estimate —
gf180mcu's standard-cell geometry (larger feature size, different cell
heights) will not reproduce a sky130 density figure directly, and no one has
run DFFRAM's gf180mcuD target through to a clean, measured result to know
what it would actually produce here.

**Evidence tier: unverified for gf180mcu** (verified only that the platform
target exists and its own stated status; no gf180mcu DFFRAM build has been
run inside this repo).

### Option C — OpenRAM

**Not currently viable.** Already established in `bitcell-decision.md`
(verified against OpenRAM's own docs, 2026-08-05): OpenRAM does not support
gf180mcu SRAM generation at all; its gf180mcu support is experimental ROM
generation only. Re-check `VLSIDA/OpenRAM`'s `docs/source/basic_setup.md`
before relying on this if evaluating OpenRAM again later — this record does
not re-verify it, only cites the prior finding.

### Recommendation

For an integrator today: **Option A (tile the foundry `512×8` macros)** is
the only path with a signoff-clean, silicon-track-record building block on
gf180mcu right now. It costs the most macro-footprint area of the two real
options per the measured/derived numbers above (once DFFRAM's gf180mcu path
is made signoff-clean, its higher effective bit density, per the sky130
reference figures, would likely make it more area-efficient — but that is
speculative until someone actually clears DFFRAM's gf180mcuD hold
violations and measures the result). Option B (DFFRAM on gf180mcu) is the
one to watch, not yet the one to ship.

## Mux / bank-select cost

Not modeled or measured here — flagged explicitly rather than estimated,
per this repo's evidence-tier discipline. Building an N-macro bank (N = 16 /
32 / 64 for 8 / 16 / 32 KB via Option A) needs, at minimum:

- **Bank-select decode**: `⌈log2 N⌉` extra high-order address bits decoded
  to one active-low `CEN` per macro (N=64 → 6 bits).
- **Output combine**: an N:1 mux (or `CEN`-gated shared bus, if the flow's
  macro output style tolerates it) on the 8-bit `Q` bus, replicated per
  active byte lane if multiple macros are used side-by-side for word width.
- **Floorplan routing channels** between macro instances, which the
  macro-footprint-only sums above do not include.

None of this has been synthesized, placed, or timed in this repo, so no
area or delay number is given for it — a real KB-scale integration should
budget for it explicitly rather than treat the macro-sum table above as the
whole answer.

## No dense NVM in the open kit

Separately: the open gf180mcu kit ships no dense non-volatile memory macro
at all — only a bare `efuse_cell` primitive device (`libs.ref/gf180mcu_fd_pr/`
GDS/Magic plus a DRC/LVS rule-deck entry, not a packaged multi-bit ROM/OTP
macro) — so code storage for any MCU-class chip built on this kit is an
architecture decision (external QSPI flash vs. an on-die boot-ROM/OTP block
someone would have to design) rather than a part the PDK provides; a
boot-ROM/OTP macro is a plausible sibling catalog entry to this repo, to be
filed as its own issue if the program agrees it is in scope, not built here.

## What this record does not change

- **`spec/sram.md`**'s ratified organization (256 × 32, 1 kB, single fixed
  instance), ports, deliverables, or characterization/signoff definition —
  untouched.
- **`spec/bitcell-decision.md`**'s scope decision (custom bitcell/array,
  Option 2) — untouched; this record's Option A/B/C survey is about the
  wider gf180mcu ecosystem an *integrator* might reach for above 1 KB, not
  a re-litigation of what this repo itself builds.
- Nothing here commits this repo to building a tiler, a generator, or a
  boot-ROM/OTP block. `sram.md`'s stretch goal (parameterized generator) and
  the "possible sibling catalog row" above are both explicitly out of this
  record's scope — noted, not started.

## References

- `spec/bitcell-decision.md` — the foundry `gf180mcu_fd_ip_sram` macro
  family (pin list, 15-corner Liberty characterization, `018SRAM_cell1`
  bitcell) and the prior, still-current finding that OpenRAM has no gf180mcu
  SRAM generation support.
- `spec/sram.md` — this repo's own ratified 256 × 32 (1 kB) target and its
  parameterized-generator stretch goal.
- `~/.volare/gf180mcu{A,B,C,D}/libs.ref/gf180mcu_fd_ip_sram/lef/*.lef` — `SIZE`
  fields, the source for the measured macro-area table.
- `~/.volare/gf180mcu{A,B,C,D}/libs.ref/gf180mcu_fd_ip_sram/lib/*__tt_025C_3v30.lib`
  — `cell_rise(q_delay_template)` tables, the source for the measured
  `CLK`→`Q` timing-class table.
- `~/.volare/gf180mcu{A,B,C,D}/libs.ref/gf180mcu_fd_pr/{gds,mag}/efuse*` and
  `libs.tech/klayout/{drc,lvs}/rule_decks/efuse*` — the eFuse primitive that
  is the sole NVM-adjacent device in the open kit.
- [`AUCOHL/DFFRAM`](https://github.com/AUCOHL/DFFRAM), `Readme.md`
  (`main` branch, fetched live 2026-08-17) — platform support table
  (`gf180mcuD` listed, not signoff-clean) and area/bit-density comparison
  table (`sky130A`, cited as cross-PDK reference only).
- Issue #73 — "Document the macro ceiling (512×8) and a recommended KB-scale
  tiling / DFFRAM path for integrators," which this record resolves.
