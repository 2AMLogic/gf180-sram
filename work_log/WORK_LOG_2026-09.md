# Work Log Archive — 2026-09

Sections moved byte-for-byte from [WORK_LOG.md](../WORK_LOG.md) by `loom-daemon work-docs archive`.

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

