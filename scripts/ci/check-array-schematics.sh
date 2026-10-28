#!/usr/bin/env bash
# Drift gate for the committed, machine-generated array schematics.
#
# Usage: scripts/ci/check-array-schematics.sh
#
# design/sram_256x32_array.sch and design/sram_64x128_array.sch are pure
# output of design/generate_array.py (deterministic; see design/README.md,
# "Freshness"). They stay tracked so a reader can see the netlist's source
# without running anything (issue #21 evidence), and this check is what makes
# the committed copy trustworthy: it regenerates each one into a temp dir and
# fails on any byte difference. Needs only python3 (no xschem, no klt).
# Keep the rows/cols below in step with design/regen_periphery.sh.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

status=0
# name rows cols
for spec in "sram_256x32_array 256 32" "sram_64x128_array 64 128"; do
    read -r name rows cols <<<"$spec"
    python3 design/generate_array.py --rows "$rows" --cols "$cols" \
        --out "$tmp/$name.sch" 2>/dev/null
    if cmp -s "$tmp/$name.sch" "design/$name.sch"; then
        echo "ok: design/$name.sch matches generate_array.py --rows $rows --cols $cols"
    else
        echo "DRIFT: design/$name.sch differs from generate_array.py --rows $rows --cols $cols" >&2
        diff -u "design/$name.sch" "$tmp/$name.sch" | head -20 >&2 || true
        status=1
    fi
done

if [[ $status -ne 0 ]]; then
    echo "Regenerate and commit: python3 design/generate_array.py --rows R --cols C --out design/<name>.sch" >&2
fi
exit "$status"
