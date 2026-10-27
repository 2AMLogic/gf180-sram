#!/usr/bin/env bash
# sim/lib/pdk_env.sh -- resolve the gf180mcu PDK install used by every
# testbench in sim/, and print it as shell variable assignments.
#
# Mirrors the resolution order design/xschemrc already established for this
# repo (issue #21):
#   1. GF180_PDK_PATH (already a full variant dir, e.g. .../gf180mcuD)
#   2. PDK_ROOT + PDK (default variant: gf180mcuD)
#   3. common install prefixes, ciel first: ~/.ciel, then (only so a stray
#      tree is *found and rejected*, never silently used) ~/.volare,
#      /usr/share/pdk, /usr/local/share/pdk, ~/share/pdk, /opt/pdk
#
# Whatever tree is resolved, its open_pdks revision is checked against the
# single pin in sim/lib/pdk_pin.txt (issue #173); a mismatch -- or a revision
# that cannot be determined -- is a hard failure naming found vs pinned.
#
# Usage (sourced, not executed):
#   source "$(dirname "$0")/pdk_env.sh"
#   echo "$GF180_MODEL_FILE"
#
# Sets on success:
#   GF180_VARIANT_DIR   -- .../gf180mcuD (or whichever variant)
#   GF180_MODEL_FILE     -- .../libs.tech/ngspice/sm141064.ngspice
#   GF180_DESIGN_INC      -- .../libs.tech/ngspice/design.ngspice (default
#                            corner-switch params sm141064.ngspice's `.LIB`
#                            sections require, e.g. `fnoicor`)
#   GF180_PDK_VERSION      -- resolved-symlink version string, if
#                            discoverable (best-effort; empty otherwise)
#
# Exits non-zero (returning from a `source`, not killing the parent shell)
# with a message on stderr if no PDK install can be found.

_pdk_env_variant="${PDK:-gf180mcuD}"
_pdk_env_root=""

if [[ -n "${GF180_PDK_PATH:-}" ]]; then
  GF180_VARIANT_DIR="$GF180_PDK_PATH"
elif [[ -n "${PDK_ROOT:-}" ]]; then
  _pdk_env_root="$PDK_ROOT"
  GF180_VARIANT_DIR="$_pdk_env_root/$_pdk_env_variant"
else
  for candidate in "$HOME/.ciel" "$HOME/.volare" /usr/share/pdk /usr/local/share/pdk "$HOME/share/pdk" /opt/pdk; do
    if [[ -d "$candidate/$_pdk_env_variant/libs.tech/ngspice" ]]; then
      _pdk_env_root="$candidate"
      break
    fi
  done
  if [[ -z "$_pdk_env_root" ]]; then
    echo "pdk_env.sh: no gf180mcu install found (checked GF180_PDK_PATH, PDK_ROOT+PDK, ~/.ciel, ~/.volare, /usr/share/pdk, /usr/local/share/pdk, ~/share/pdk, /opt/pdk)." >&2
    echo "pdk_env.sh: set PDK_ROOT (parent of gf180mcuD/) and PDK=gf180mcuD, or GF180_PDK_PATH=<.../gf180mcuD>, and re-run." >&2
    return 1 2>/dev/null || exit 1
  fi
  GF180_VARIANT_DIR="$_pdk_env_root/$_pdk_env_variant"
fi

if [[ ! -d "$GF180_VARIANT_DIR/libs.tech/ngspice" ]]; then
  echo "pdk_env.sh: resolved GF180_VARIANT_DIR=$GF180_VARIANT_DIR has no libs.tech/ngspice -- not a valid gf180mcu install." >&2
  return 1 2>/dev/null || exit 1
fi

GF180_MODEL_FILE="$GF180_VARIANT_DIR/libs.tech/ngspice/sm141064.ngspice"
GF180_DESIGN_INC="$GF180_VARIANT_DIR/libs.tech/ngspice/design.ngspice"

if [[ ! -f "$GF180_MODEL_FILE" ]]; then
  echo "pdk_env.sh: expected model file not found: $GF180_MODEL_FILE" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ ! -f "$GF180_DESIGN_INC" ]]; then
  echo "pdk_env.sh: expected corner-switch defaults file not found: $GF180_DESIGN_INC" >&2
  return 1 2>/dev/null || exit 1
fi

# Revision discovery. Order: (1) a `/versions/<open_pdks-sha>/` component in
# the symlink-resolved path (volare layout; ciel's layout is expected to match
# but is not verified here), then (2) the first 40-hex sha in a SOURCES file
# in the variant dir or its parent. Empty if neither yields one.
_pdk_env_resolved="$(cd "$GF180_VARIANT_DIR" 2>/dev/null && pwd -P || true)"
GF180_PDK_VERSION=""
if [[ "$_pdk_env_resolved" == *"/versions/"* ]]; then
  GF180_PDK_VERSION="${_pdk_env_resolved#*/versions/}"
  GF180_PDK_VERSION="${GF180_PDK_VERSION%%/*}"
fi
if [[ ! "$GF180_PDK_VERSION" =~ ^[0-9a-f]{40}$ ]]; then
  GF180_PDK_VERSION=""
  for _pdk_env_src in "$GF180_VARIANT_DIR/SOURCES" "$_pdk_env_resolved/SOURCES" "$_pdk_env_resolved/../SOURCES"; do
    if [[ -f "$_pdk_env_src" ]]; then
      GF180_PDK_VERSION="$(grep -Eo '[0-9a-f]{40}' "$_pdk_env_src" | head -n1 || true)"
      [[ -n "$GF180_PDK_VERSION" ]] && break
    fi
  done
fi

_pdk_env_pin="$(tr -d '[:space:]' < "$(dirname "${BASH_SOURCE[0]}")/pdk_pin.txt")"
if [[ "$GF180_PDK_VERSION" != "$_pdk_env_pin" ]]; then
  echo "pdk_env.sh: PDK revision mismatch for $GF180_VARIANT_DIR: found open_pdks '${GF180_PDK_VERSION:-<undeterminable>}', pinned $_pdk_env_pin (sim/lib/pdk_pin.txt)." >&2
  echo "pdk_env.sh: install the pin with: ciel enable --pdk-family gf180mcu -l gf180mcu_fd_pr $_pdk_env_pin (PDK root ~/.ciel), and remove or bypass any stale ~/.volare tree." >&2
  unset _pdk_env_variant _pdk_env_root _pdk_env_resolved _pdk_env_src _pdk_env_pin _pdk_env_src _pdk_env_pin
  return 1 2>/dev/null || exit 1
fi

export GF180_VARIANT_DIR GF180_MODEL_FILE GF180_DESIGN_INC GF180_PDK_VERSION
unset _pdk_env_variant _pdk_env_root _pdk_env_resolved _pdk_env_src _pdk_env_pin
