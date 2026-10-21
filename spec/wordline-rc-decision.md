# Decision record: the wordline RC gate fails for the left-fed 4:1 array — proposed superseding row organization

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act). Nothing here is
ratified, and nothing here is a physical PASS.
**Preferred candidate (operator direction, 2026-10-19 Pacific)**: **4:1 with a
centre-fed row** — two 64-column halves driven from the centre (option A below). The
operator preferred it in an attended fleet-decide. That is a preference for the
proposal, not approval of this PR, architectural ratification, or a validated
timing claim.
**Resolves**: the "Wordline RC gate" of `spec/periphery-architecture.md`, assigned
to #204 (child of #201)
**Would supersede (only if ratified)**: rows 1 and 4 of
`spec/periphery-architecture.md` — "Decisions" table, its "Floorplan" and
"Consequences of 4:1" sections, and the "Wordline RC gate" section's fallback list,
which asked for exactly this record. **Until ratified,
`spec/periphery-architecture.md` stands unedited and in force.** A later superseding
record must name exactly what it changes (see "What a superseding record would change").
**Amends**: nothing in `spec/sram.md` or `spec/macro-interface-decision.md`.
The 256 x 32 logical organization, the external interface and every ratified numeric
specification are unchanged by every option.

## Question

`spec/periphery-architecture.md` adopted a 4:1 column mux (physical array 64 rows
x 128 columns, row decoder and wordline drivers on the **left** edge) "conditionally":
#204 had to extract the far-end wordline delay at `ss_125c_2.97v` and compare it with
the 2 ns write pulse and the read path, and if it did not fit, file the superseding
record, centre decoder first, then 2:1. Does it fit?

## What the single-corner comparison shows

**The left-fed row does not meet the drafting agent's criteria at one corner.**
`sim/wordline-rc/` (record `sim/wordline-rc/records/20261018-124149-8d5a317.md`)
drives the extracted 128-cell wordline (571 µm of Poly2, 256 access gates) with the
real `rowdrv` from the landing-pad end:

| Left-fed 128-cell row, `ss_125c_2.97v` | Poly2 R as extracted | Poly2 R x1.5 |
|---|---|---|
| Driver output reaches 50 % (after the input edge) | 0.21 ns | 0.21 ns |
| **Far end** reaches 50 % | **1.57 ns** | 2.16 ns (on a long pulse; never on 2.0 ns) |
| Far end reaches 90 % (5.88 ns pulse) | 3.92 ns | 5.59 ns |
| Far-end peak on a 2.0 ns pulse | **1.92 V (65 % of VDD)** | 1.43 V (48 %) |
| Far end above 50 % of VDD, 2.0 ns pulse | 1.38 ns | never |

### This is a comparison, not a qualification

* **One corner, one bench.** All figures are `ss_125c_2.97v` only. The 27-corner set
  has not been run for any topology. A single-corner comparison between topologies
  ranks them on that bench; it does not qualify any of them.
* **The criteria are the drafting agent's.** G1 (the far cell sees a fully asserted
  wordline within the 2 ns floor) and G2 (far-end 50 % delay plus single-cell read
  access against the control block's `s_en` delay) are not ratified numbers; the repo
  ratifies no wordline number, and none is invented here to make a result pass.
* **G2 is a proxy, not an integrated read.** It adds numbers from three testbenches:
  the far cell's wordline passes 50 % at 1.57 ns, plus the single-cell read access time
  (0.32 ns), is 1.89 ns against a 1.96 ns `s_en` delay. That `s_en` delay is a
  schematic number with no wire RC. 0.07 ns of spare at R as extracted; 2.48 ns, past
  `s_en`, at 1.5x. No integrated read/control simulation was run.
* **The original left-fed arrangement was not shown to fail a write.** The macro's
  actual `wl_en` pulse at this corner is 5.88 ns, and on it the far end reaches 90 % at
  3.92 ns and holds it 2.38 ns. What the record shows is that the *2 ns write-pulse
  floor* (`spec/write-pulse-width-decision.md`) is not honoured at the far cell and that
  the read-path proxy has little spare margin. It does not show that a write fails.
* **1.5x Poly2 R is a sensitivity assumption.** It is not a PDK-characterized bound
  and not a corner. For reference (reviewer addition, 2026-10-20): the extractor's
  Poly2 sheet resistance is the PDK's nominal `resist (allpolynonres)/active 7300`
  (7.3 ohm/sq, `libs.tech/magic/gf180mcuD.tech` at `open_pdks` `c6d73a3`), and the
  same file's "high-end corner" table lists `15000` (15 ohm/sq, 2.05x nominal). The
  extracted 21.97 kohm is 1.37x a plain 571 x 0.26 µm stripe at 7.3 ohm/sq (the
  extractor's whole-fragment square count includes the gate stubs), so 1.5x of it
  (32.9 kohm) happens to equal that stripe at 15 ohm/sq. None of this was simulated as
  a corner; the extracted resistors carry no temperature coefficient.

For comparison, the same bench for the two fallbacks the architecture record named:

| Same bench, `ss_125c_2.97v` | Far end 50 % | Far end 90 % | Peak on 2.0 ns pulse | Above 90 %, 2.0 ns pulse |
|---|---|---|---|---|
| A. 4:1, centre-fed (two 64-cell halves, one `rowdrv` feeding both) | 0.69 ns | 1.46 ns | 2.90 V | 0.79 ns (**0.38 ns at R x1.5**) |
| B. 2:1 (128 rows x 64 cols, left-fed) | 0.57 ns | 1.23 ns | 2.94 V | 1.00 ns (0.59 ns at R x1.5) |

Not simulated: a **metal-strapped** left-fed 4:1 row (option C below). No strapped layout exists.

## Unresolved concern for the centre-fed candidate: write-waveform margin

This is open, and it is the main reason the preference above is not a timing claim.

* Under the 2 ns stimulus and 1.5x Poly2 resistance, the centre-fed far end is above
  90 % of VDD for only **0.38 ns** (0.79 ns at R as extracted).
* The cell flips in 85 ps with an **ideal** wordline
  (`sim/access-time/records/20260817-012005-4448966.md`). A crossing time or an
  ideal-wordline flip time is **not** proof of adequate write margin. Write trip
  voltage and write margin were **not** measured with this wordline waveform
  (`sim/write-margin/` was not re-run against it).
* 1.5x Poly2 R is a sensitivity assumption, not a PDK-characterized bound, so 0.38 ns
  is neither a worst-case nor a best-case number.
* The far-end waveform write-margin recheck is therefore required before any timing
  claim for this candidate (validation matrix, item 4).

## Options, best to worst for this block

**A. 4:1 with a centre-fed row (operator-preferred candidate).**
Keeps the 4:1 organization, the 17.84 µm column slice (#205, committed and DRC/LVS clean), the
64-row decoder netlist (`design/netlist/row_path.spice`, #203) and the one-`rowdrv`-per-row
sizing, which the bench shows still drives two halves at 0.69 ns.
*Array/band rearrangement proposed*: two 64-column halves with the decoder / driver strip
between them, so each wordline is fed from the centre and runs outward to two far ends; the 32
column slices are split 16 + 16 around the strip, one group under each half.
*Cost*: a **second wordline landing-pad strip** (the left-fed array has one) and the
**16 + 16 slice arrangement** (#206 places the slices; the committed 64 x 128 array GDS, #219,
is re-tiled or split). Array and band re-assembly work; the bitcell, slices and decoder cells
are reused as cells, but whether they fit the rearranged floorplan is not established.
Foundry macro precedent: `gf180mcu_fd_ip_sram` drives from the middle (`LWL`/`RWL`) per
`spec/periphery-architecture.md`.

**B. 2:1 (128 rows x 64 columns).**
Passes with the most margin on the wordline and keeps a left-edge strip. Costs the most
redone work: the slice pitch halves to 8.92 µm per I/O, so the committed 17.84 µm `io_slice`
and `precharge_slice` (#205) would have to be redrawn in half the width, the decoder becomes
7 -> 128 (new #203 netlist and layout), and bit lines double to 691 µm. Whether a sense amp,
write driver, mux and three flops fit 8.92 µm is unknown.

**C. Keep left-fed 4:1 and strap the wordline in metal.**
Standard SRAM practice, not on the architecture record's fallback list and not evaluated here.
It needs a strap tap (Poly2 contact, `Metal1` landing, via stack) every N cells, which does not
fit the current bitcell without an extra strap column, and `Metal1` carries the bit lines
vertically through the cell. It would reopen the array layout (#219). Listed so the operator can
ask for it to be evaluated; no number supports it yet.

**D. Keep the ratified organization and accept the gate failure.**
Not recommended. It would leave the 2 ns floor unmet at the far cell and the read path with
no spare margin at 1.5x Poly2 R, and "agents do not relax the ratified spec to make results
pass" applies equally to accepting a failed gate.

## What a superseding record would change

Nothing is changed by drafting this record. If A is ratified, a later superseding record
(B or C would need their own) must name exactly these, and no others:

* `spec/periphery-architecture.md` rows 1 and 4, its "Floorplan" and "Consequences of 4:1"
  sections: superseded by the centre-fed arrangement (they will carry a pointer to the
  superseding record);
* the physical array/band arrangement only: two 64-column halves, a second landing-pad
  strip, 16 + 16 column slices.

It does **not** change the logical organization, the pins, any ratified number in
`spec/sram.md`, the 2 ns write-pulse floor, or the leaf cells (`and3`, `and4`, `rowdrv`).
No spec value is relaxed to make a result pass.

## Later validation matrix (proposal only; none of it is run or authorized by this PR)

Executing any of this needs separate authorization. Existing records and their original
limitations are preserved; evidence is appended only when measured, never edited into
existing records.

1. **All 27 operating corners** for the chosen topology, on the batch fleet (this record covers one).
   Each corner's second pulse is that corner's own `wl_en` width from the `sim/macro-smoke`
   record (2.46 ns at `ff_-40c_3.63v` to 5.88 ns here), not 5.88 ns everywhere as `gen.py`
   hard-codes today; Poly2 R is run at the PDK's stated high-end sheet resistance (15 ohm/sq,
   above) as well as the 1.5x assumption, so the resistance case is a PDK figure, not a guess.
2. **Actual predecoder slew and row/driver loading**, not the bench's ideal stimulus and single `rowdrv`.
3. **Correct topology for each bench**: pad-end drive versus centre drive, with the driven
   node identified per bench (see "Extracted-node provenance").
4. **Far-end waveform write-margin recheck** with the extracted wordline waveform, including
   the centre-fed 1.5x R case where only 0.38 ns is above 90 % of VDD.
5. **Integrated read/control timing**, replacing the G2 sum with a simulated read that has
   wire RC in the `s_en` path.
6. **DRC, LVS, connectivity and abutment** on the actual rearranged layout.

## Extracted-node provenance

The first version of the bench read as a pass because `klt extract --distributed-rc` puts
the net's pin on a mid-ladder terminal (the 129th of 256 gates), so driving the pin fed the
line from its centre. Filed as 2AMLogic/klayout-tools#3937 (closed 2026-10-18), which
documents and reports the middle-pin convention.

* **Closing #3937 does not repin the frozen extracted ladder** in `sim/wordline-rc/dut/`,
  and does not validate this macro. Those netlists keep the mid-ladder pin as extracted.
* The figures above come from `.ported.spice` copies that **drive the pad-end node** (the
  end-node workaround), not the extracted pin. This is auditable by diffing each
  `dut/wl_row_*.extracted.spice` against its `.ported.spice` copy.
* The `centre` bench equals what a pin-driven run of the unmodified extracted netlist
  reports (`sim/wordline-rc/README.md`): its driven node is the extracted mid-chain pin,
  i.e. the shared centre end of two 64-cell halves, with the wordline running outward to
  each far end. Which node each bench drives, and which physical topology that node
  represents (left-fed landing-pad end for `row128`/`row64`; the shared centre end for
  `centre`), must stay explicit in every later record. A later re-extraction or tool fix
  does not retroactively change these figures.

## Reconciliation with #204 and #206

* **#204 remaining acceptance criteria** stay open: the row decoder generator and committed
  GDS (byte-identical regeneration), drivers landing on `WL<n>` pads at 5.40 µm pitch, pins
  matching `row_path.spice`, and `klt drc` / `klt lvs` against `row_path.spice`. They are
  architecture-dependent and blocked on ratification of this PR. Only the wordline RC gate
  item is addressed here, and then only at one corner.
* **#206 assembly dependencies after ratification**: the 16 + 16 slice placement, the
  second landing-pad strip, and the re-tiled or split array (#219) are assembly work that
  #206 would pick up. Existing decoder and slice cells may be reused as cells.
* **No physical claim.** No physical fit, regenerated array, or new DRC/LVS/connectivity
  result is claimed. The "committed and DRC/LVS clean" statements above describe the
  existing cells in their existing arrangement only.
* No layout or simulation execution is granted by this record.

## What this record does not do

Draw any layout, change `spec/sram.md`, change a ratified timing number, qualify any
topology at any corner, or show that the 4:1 organization or the left-fed arrangement
fails a write. It says the left-fed row does not meet the drafting agent's stated
criteria at one corner, and records the centre-fed row as the operator's preferred
candidate with its unresolved write-waveform concern.

## Ratification mechanism

Per 2AMLogic/2am#357, a builder drafts the decision record as a PR on the evidence collected and the
operator's approval of that PR is the ratification act. This record reflects the evidence and the
operator's stated preference; it is not a ruling by the drafting agent and not approval by the
operator.

## References

- `spec/periphery-architecture.md` — rows 1 and 4, "Wordline RC gate" (stands until ratified).
- `spec/write-pulse-width-decision.md` — the 2 ns floor.
- `sim/wordline-rc/` — bench, extracted DUTs, requests, raw reports, record.
- `sim/macro-smoke/records/20261018-082301-37ba562.md` — `wl_en` width (5.88 ns) and
  `s_en` delay (1.96 ns) at `ss_125c_2.97v`.
- `sim/access-time/records/20260817-011948-4448966.md` — read access time, 323 ps at `ss_125c_2.97v`.
- `sim/access-time/records/20260817-012005-4448966.md` — write access time with an ideal wordline (85 ps cell flip).
- 2AMLogic/klayout-tools#3937 — pin placement in `--distributed-rc` ladders.
