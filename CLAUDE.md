# gf180-sram — agent instructions

Open-source canary block: an SRAM macro on the gf180mcu PDK, built and
verified by AI agents.

- **PDK**: gf180mcu (open PDK). Open-source flow: xschem + ngspice for
  design/sim, klayout-tools (`klt`) for layout, abstract, and view work.
- **The macro is the point.** This is the program's first memory block, so
  array generation, macro-level LVS, hierarchy handling, and LEF/Liberty view
  generation are all tool surface nothing here has touched. Expect the tools
  to be weakest at the array and abstract stages, and file what you find.
- **This block is not competing with OpenRAM.** Free gf180mcu and sky130 SRAM
  macros already exist. Use OpenRAM's output as a reference and a comparison
  where it helps, cite it when you do, and do not reimplement it. If the
  honest conclusion of some piece of work is "OpenRAM already does this
  correctly," record that — it is a real result.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue at
  `2AMLogic/klayout-tools` describing the tool gap generically — that tracker
  is scoped to the tool, so keep design-specific detail out of it and describe
  the gap, not the design.
- **Verification is the product**: no claim without a testbench. PVT corners
  on every recorded result; `sim/` results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not relax
  the ratified spec to make results pass.

## First question, before the spec

Does gf180mcu ship a usable 6T bitcell, or must one be drawn? That answer
sets the entire scope of this repo. Resolve it and record it in `spec/`
before ratification, not during.

<!-- BEGIN LOOM ORCHESTRATION -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration — see the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of that guide to `.loom/CLAUDE.md`.
<!-- END LOOM ORCHESTRATION -->
