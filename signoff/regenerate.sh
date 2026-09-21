#!/usr/bin/env bash
# Regenerate signoff/signoff-report.json -- the committed `klt signoff
# --manifest` tier-verdict report this repo treats as the verdict of record
# for its T1 checklist state (issue #125).
#
# Run from the repo root:
#     ./signoff/regenerate.sh
#
# Grader distribution discipline (load-bearing): this script grades with a
# throwaway venv + the *pip registry wheel* of the pinned klayout-tools
# version, NOT the `klt` already on PATH. An `uv tool install
# git+https://github.com/2AMLogic/klayout-tools` snapshot and the PyPI wheel
# of the same version string are NOT the same code -- observed live for
# 0.5.0: the git-tag snapshot predates the checklist's eleventh item
# ("Power delivery (structural)") and its grading rules, while the PyPI
# 0.5.0 wheel grades all 11 items and quotes DRC `coverage` in item 3's
# citation. Grading with the same distribution CI grades with
# (.github/workflows/ci.yml `signoff` job) is what makes the committed
# report byte-reproducible; keep this pin and that pin in sync.
set -euo pipefail

# Keep in sync with the `signoff` job's pip install in
# .github/workflows/ci.yml.
KLT_VERSION="0.5.0"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 1. Refresh the generic-evidence wrapper's pinned hash of the aggregated
#    characterization report (T1 item 8 cites this wrapper; its pin is a
#    pure derivation from the report it wraps, so refreshing is mechanical).
CHAR_HASH="$(sha256sum measurements/characterization-report.md | cut -d' ' -f1)"
python3 - "$CHAR_HASH" <<'EOF'
import json
import pathlib
import sys

path = pathlib.Path("measurements/characterization.signoff.json")
doc = json.loads(path.read_text())
doc["provenance"]["input"]["content_hash"] = f"sha256:{sys.argv[1]}"
path.write_text(json.dumps(doc, indent=2) + "\n")
EOF

# 2. Grade the block manifest with the pinned registry wheel. Exit code 3 is
#    `klt signoff`'s documented "ran successfully, but at least one T1 item
#    is unmet" -- expected for this block today -- so only the other exit
#    codes (1 = bad manifest/unparseable doc, 2 = usage error) are failures.
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install --quiet "klayout-tools==$KLT_VERSION"

# The *identity* of the grading build matters as much as its version string:
# a `uv tool install git+...` snapshot or a full-checkout install of the
# same version can grade differently (observed live: an 11-item-era
# full-repo install under the name "0.5.0"). The released registry wheel
# reports the git tag it was built from -- assert it.
python3 - "$WORK" "$KLT_VERSION" <<'EOF'
import json
import subprocess
import sys

venv_bin, version = sys.argv[1], sys.argv[2]
info = json.loads(subprocess.run(
    [f"{venv_bin}/venv/bin/klt", "version", "--format", "json"],
    capture_output=True, text=True, check=True).stdout)
if info.get("package_version") != version or info.get("git_tag") != f"v{version}" \
        or info.get("is_release") is not True:
    print(f"FATAL: grading klt is not the released {version} registry wheel -- "
          f"got package_version={info.get('package_version')} "
          f"git_tag={info.get('git_tag')} is_release={info.get('is_release')}. "
          "A same-version snapshot/full-checkout install grades differently "
          "(e.g. it may carry checklist item 11's rules while the release "
          "does not); refusing to grade with it.", file=sys.stderr)
    sys.exit(1)
EOF

set +e
"$WORK/venv/bin/klt" signoff \
    --manifest signoff/block-manifest.json \
    --tiers-doc signoff/design-evidence-tiers.md \
    --format json > signoff/signoff-report.json
SIGNOFF_RC=$?
set -e
if [ "$SIGNOFF_RC" -ne 0 ] && [ "$SIGNOFF_RC" -ne 3 ]; then
    echo "FATAL: klt signoff exited $SIGNOFF_RC (not a rendered tier report)" >&2
    exit "$SIGNOFF_RC"
fi

python3 - "$KLT_VERSION" <<'EOF'
import json
import sys

report = json.load(open("signoff/signoff-report.json"))
print(f"graded with klayout-tools=={sys.argv[1]} (PyPI registry wheel)")
print(f"{report['block']}: kind={report['kind']} tier={report['tier']} "
      f"T1 {report['t1_met_count']}/{report['t1_item_count']} items met")
for item in report["items"]:
    if item["tier"] == "T1":
        marker = "MET  " if item["status"] == "met" else "UNMET"
        print(f"  [{marker}] #{item['id']:<2} {item['title']}"
              f"{'' if item['status'] == 'met' else ' -- ' + str(item['reason'])}")
EOF
