# Decision record: the wordline RC gate fails for the left-fed 4:1 array — choose a superseding row organization

**Status**: Proposed for ratification via PR approval (2AMLogic/2am#357 standing
policy — the operator's PR approval is the ratification act). The recommendation
below is the drafting agent's; the choice is the operator's.
**Resolves**: the "Wordline RC gate" of `spec/periphery-architecture.md`, assigned
to #204 (child of #201)
**Supersedes (if option A or B is ratified)**: rows 1 and 4 of
`spec/periphery-architecture.md` — "Decisions" table, and the "Wordline RC gate"
section's fallback list, which asked for exactly this record. Until ratified,
that record stands unedited.
**Amends**: nothing in `spec/sram.md` or `spec/macro-interface-decision.md`
(the 256 x 32 logical organization and the pins are unchanged by every option).

## Question

`spec/periphery-architecture.md` adopted a 4:1 column mux (physical array 64 rows
x 128 columns, row decoder and wordline drivers on the **left** edge) "conditionally":
#204 had to extract the far-end wordline delay at `ss_125c_2.97v` and compare it with
the 2 ns write pulse and the read path, and if it did not fit, file the superseding
record, centre decoder first, then 2:1. Does it fit?

## Answer

**No, not as a left-fed row.** `sim/wordline-rc/` (record
`sim/wordline-rc/records/20261018-124149-8d5a317.md`) drives the extracted 128-cell
wordline (571 µm of Poly2, 256 access gates) with the real `rowdrv` from the landing-pad end:

| Left-fed 128-cell row, `ss_125c_2.97v` | Poly2 R as extracted | Poly2 R x1.5 |
|---|---|---|
| Driver output reaches 50 % (after the input edge) | 0.22 ns | 0.21 ns |
| **Far end** reaches 50 % | **1.57 ns** | 2.16 ns (on a long pulse; never on 2.0 ns) |
| Far end reaches 90 % (5.88 ns pulse) | 3.92 ns | 5.59 ns |
| Far-end peak on a 2.0 ns pulse | **1.92 V (65 % of VDD)** | 1.43 V (48 %) |
| Far end above 50 % of VDD, 2.0 ns pulse | 1.38 ns | never |

Against the two comparisons the architecture record named:

* **2 ns write-pulse floor** (`spec/write-pulse-width-decision.md`): on a 2.0 ns pulse the
  far cell never sees a fully asserted wordline. **Fails** at the extractor's resistance and
  at 1.5x it. The macro's actual pulse at this corner is longer (`wl_en` 5.88 ns), and on
  that pulse the far end reaches 90 % at 3.92 ns and holds it 2.38 ns, so this record does
  **not** show that a write fails at this corner. It shows the 2 ns floor is not honoured at
  the far cell.
* **Read path**: the far cell's wordline passes 50 % at 1.57 ns; adding the single-cell read
  access time (0.32 ns) lands at 1.89 ns against the control block's 1.96 ns `s_en` delay,
  which is a schematic number with no wire RC. That is 0.07 ns of spare, and at 1.5x
  resistance it is 2.48 ns, past `s_en`. This sums numbers from three testbenches and is a
  proxy, not a simulated read.

The criteria are the drafting agent's (the repo ratifies no wordline number, and none is
invented here to make a result pass). The fallbacks pass them with margin at the same corner:

| Same bench, `ss_125c_2.97v` | Far end 50 % | Far end 90 % | Peak on 2.0 ns pulse | Above 90 %, 2.0 ns pulse |
|---|---|---|---|---|
| A. 4:1, centre decoder (two 64-cell halves, one `rowdrv` feeding both) | 0.69 ns | 1.46 ns | 2.90 V | 0.79 ns (0.38 ns at R x1.5) |
| B. 2:1 (128 rows x 64 cols, left-fed) | 0.57 ns | 1.23 ns | 2.94 V | 1.00 ns (0.59 ns at R x1.5) |

Not simulated: a **metal-strapped** left-fed 4:1 row (option C below). No strapped layout exists.

## Options, best to worst for this block

**A. 4:1 with a centre decoder (recommended).**
Keeps the 4:1 organization, the 17.84 µm column slice (#205, committed and DRC/LVS clean), the
64-row decoder netlist (`design/netlist/row_path.spice`, #203) and the one-`rowdrv`-per-row
sizing, which the bench shows still drives two halves at 0.69 ns. What changes is the
array assembly: two 64-column halves with a decoder strip between them, a second wordline
landing-pad strip, and the 32 column slices split 16 + 16 around the strip (#206 places them;
the committed 64 x 128 array GDS, #219, is re-tiled or split). Foundry macro precedent:
`gf180mcu_fd_ip_sram` drives from the middle (`LWL`/`RWL`) per `spec/periphery-architecture.md`.
Cost: array and band re-assembly work; the bitcell, slices and decoder cells are reused.

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

## What this record changes

Nothing is changed by drafting it. If A or B is ratified:

* `spec/periphery-architecture.md` rows 1 and 4, its "Floorplan" and "Consequences of 4:1"
  sections are superseded by the option chosen (it will carry a pointer to this record);
* #204's row-path layout resumes against the chosen organization (the leaf cells `and3`,
  `and4`, `rowdrv` are unaffected);
* the chosen option's wordline is re-run over the 27-corner set on the batch fleet, since
  this record covers one corner;
* the write-margin evidence is re-checked against the far-end waveform if the far end's
  fully asserted window is shorter than the 1.8 ns the testbench gives the cell (option A
  at R x1.5 has 0.38 ns above 90 % on a 2.0 ns pulse; the cell flips in 85 ps with an ideal
  wordline, `sim/access-time/records/20260817-012005-4448966.md`, but write trip voltage was
  not measured with this waveform).

## What this record does not do

Draw any layout, change `spec/sram.md`, change a ratified timing number, or choose between
A, B and C on evidence beyond the single-corner bench above. It does not say the 4:1
organization is wrong, only that left-fed is.

## Tool finding recorded with this result

The first version of the bench read as a pass because `klt extract --distributed-rc` puts the
net's pin on a mid-ladder terminal (the 129th of 256 gates), so driving the pin fed the line
from its centre. Filed as 2AMLogic/klayout-tools#3937. The figures above drive the pad-end node.

## Ratification mechanism

Per 2AMLogic/2am#357, a builder drafts the decision record as a PR on the evidence collected and the
operator's approval of that PR is the ratification act. This record reflects the evidence for the
operator to approve or reject; it is not a ruling by the drafting agent.

## References

- `spec/periphery-architecture.md` — rows 1 and 4, "Wordline RC gate".
- `spec/write-pulse-width-decision.md` — the 2 ns floor.
- `sim/wordline-rc/` — bench, extracted DUTs, requests, raw reports, record.
- `sim/macro-smoke/records/20261018-082301-37ba562.md` — `wl_en` width (5.88 ns) and
  `s_en` delay (1.96 ns) at `ss_125c_2.97v`.
- `sim/access-time/records/20260817-011948-4448966.md` — read access time, 323 ps at `ss_125c_2.97v`.
- 2AMLogic/klayout-tools#3937 — pin placement in `--distributed-rc` ladders.
