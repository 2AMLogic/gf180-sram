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
# 0.5.0: the git-tag snapshot predated the checklist's eleventh item
# ("Power delivery (structural)") and its grading rules, while the PyPI
# 0.5.0 wheel rendered all 11 item rows only from a vendored `--tiers-doc`
# copy of the checklist, with grading rules that predated item 11. The
# active pin is 0.8.0, whose released wheel bundles the eleven-item
# checklist and item 11's grading rules itself, so no `--tiers-doc` is
# passed and the report's `source_doc` is the bundled checklist. Grading
# with the same distribution CI grades with (.github/workflows/ci.yml
# `signoff` job) is what makes the committed report byte-reproducible;
# keep this pin and that pin in sync.
set -euo pipefail

# Keep in sync with the `signoff` job's pip install in
# .github/workflows/ci.yml.
KLT_VERSION="0.8.0"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 0. The grading venv (the pinned registry wheel, which also brings the
#    `klayout` module the layout generator needs). Created first because
#    step 1b regenerates the array GDS with it.
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install --quiet "klayout-tools==$KLT_VERSION"

# 1. Refresh the generic-evidence wrappers' pinned hashes (T1 items 1, 8, 9
#    and 10 cite these wrappers; each pin is a pure derivation from the file
#    or file set the wrapper names, so refreshing is mechanical). A wrapper
#    names either one `source` file (item 8) or an anchored
#    `provenance.input.paths` set (items 1, 9, 10), whose combined digest is
#    klt's input_set_digest: sha256 over "<hex>  <path>\n" lines sorted
#    bytewise by path. The block manifest pins the same hash (the wrapper's
#    own provenance.input.content_hash).
python3 - <<'EOF'
import hashlib
import json
import pathlib

wrappers = {
    "1": "design/design.signoff.json",
    "8": "measurements/characterization.signoff.json",
    "9": "sim/testbenches.signoff.json",
    "10": "repo-hygiene.signoff.json",
}


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


manifest_path = pathlib.Path("signoff/block-manifest.json")
manifest = json.loads(manifest_path.read_text())
for item, wrapper in wrappers.items():
    path = pathlib.Path(wrapper)
    doc = json.loads(path.read_text())
    input_block = doc["provenance"]["input"]
    if "paths" in input_block:
        for member in input_block["paths"]:
            member["content_hash"] = f"sha256:{sha(member['path'])}"
        lines = "".join(
            f"{m['content_hash'].removeprefix('sha256:')}  {m['path']}\n"
            for m in sorted(input_block["paths"], key=lambda m: m["path"].encode())
        )
        digest = hashlib.sha256(lines.encode()).hexdigest()
    else:
        digest = sha(doc["source"])
    input_block["content_hash"] = f"sha256:{digest}"
    path.write_text(json.dumps(doc, indent=2) + "\n")
    assert manifest["evidence"][item]["file"] == wrapper
    manifest["evidence"][item]["content_hash"] = f"sha256:{digest}"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
EOF

# 1b. Item 2 (Layout) cites layout/layout.signoff.json, an artifact-anchored
#     generic envelope binding the committed array GDS. Its regeneration claim
#     is minted here from a real run: the generator writes into the $WORK
#     scratch dir and the *regenerated* output is what gets hashed, never the
#     committed file, so the claim cannot be self-fulfilling. If the generator
#     stops reproducing the committed stream byte-for-byte, regenerated_hash
#     differs from the bound input hash and the grader reports stale_artifact.
#     `generator` is echoed by klt, never executed by it.
"$WORK/venv/bin/python" layout/sram_256x32/generate.py -o "$WORK/regen_array.gds" >/dev/null
python3 - "$WORK/regen_array.gds" <<'EOF'
import hashlib
import json
import pathlib
import sys

regen = f"sha256:{hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()}"
gds = "layout/sram_256x32/sram_256x32_array.gds"
committed = f"sha256:{hashlib.sha256(pathlib.Path(gds).read_bytes()).hexdigest()}"

path = pathlib.Path("layout/layout.signoff.json")
doc = json.loads(path.read_text())
doc["provenance"]["input"] = {"path": gds, "content_hash": committed}
doc["provenance"]["regeneration"] = {
    "generator": "python3 layout/sram_256x32/generate.py",
    "regenerated_hash": regen,
}
path.write_text(json.dumps(doc, indent=2) + "\n")

manifest_path = pathlib.Path("signoff/block-manifest.json")
manifest = json.loads(manifest_path.read_text())
assert manifest["evidence"]["2"]["file"] == "layout/layout.signoff.json"
manifest["evidence"]["2"]["content_hash"] = committed
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
EOF

# 2. Grade the block manifest with the pinned registry wheel. Exit code 3 is
#    `klt signoff`'s documented "ran successfully, but at least one T1 item
#    is unmet" -- expected for this block today -- so only the other exit
#    codes (1 = bad manifest/unparseable doc, 2 = usage error) are failures.

# The *identity* of the grading build matters as much as its version string:
# a `uv tool install git+...` snapshot or a full-checkout install of the
# same version can grade differently (observed live under the old 0.5.0
# pin: an 11-item-era full-repo install under the name "0.5.0"). The
# released registry wheel reports the git tag it was built from -- assert it.
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
          "(e.g. its bundled checklist or grading rules may differ from "
          "the release's); refusing to grade with it.", file=sys.stderr)
    sys.exit(1)
EOF

set +e
"$WORK/venv/bin/klt" signoff \
    --manifest signoff/block-manifest.json \
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
