#!/usr/bin/env bash
# sim/lib/pdk_env.sh -- resolve the gf180mcu PDK install used by every
# testbench in sim/, and print it as shell variable assignments.
#
# Mirrors the resolution order design/xschemrc already established for this
# repo (issue #21):
#   1. GF180_PDK_PATH (already a full variant dir, e.g. .../gf180mcuD)
#   2. PDK_ROOT + PDK (default variant: gf180mcuD)
#   3. common install prefixes, volare first: ~/.volare, ~/.ciel,
#      /usr/share/pdk, /usr/local/share/pdk, ~/share/pdk, /opt/pdk
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
  for candidate in "$HOME/.volare" "$HOME/.ciel" /usr/share/pdk /usr/local/share/pdk "$HOME/share/pdk" /opt/pdk; do
    if [[ -d "$candidate/$_pdk_env_variant/libs.tech/ngspice" ]]; then
      _pdk_env_root="$candidate"
      break
    fi
  done
  if [[ -z "$_pdk_env_root" ]]; then
    echo "pdk_env.sh: no gf180mcu install found (checked GF180_PDK_PATH, PDK_ROOT+PDK, ~/.volare, ~/.ciel, /usr/share/pdk, /usr/local/share/pdk, ~/share/pdk, /opt/pdk)." >&2
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

# Best-effort version discovery: volare installs each variant as a symlink
# into volare/<pdk>/versions/<open_pdks-sha>/<variant>. If GF180_VARIANT_DIR
# resolves through such a symlink, the sha is recoverable from the resolved
# path. Not fatal if this doesn't match (e.g. a non-volare install) -- record
# an empty version rather than guessing.
_pdk_env_resolved="$(cd "$GF180_VARIANT_DIR" 2>/dev/null && pwd -P || true)"
GF180_PDK_VERSION=""
if [[ "$_pdk_env_resolved" == *"/versions/"* ]]; then
  GF180_PDK_VERSION="${_pdk_env_resolved#*/versions/}"
  GF180_PDK_VERSION="${GF180_PDK_VERSION%%/*}"
fi

export GF180_VARIANT_DIR GF180_MODEL_FILE GF180_DESIGN_INC GF180_PDK_VERSION
unset _pdk_env_variant _pdk_env_root _pdk_env_resolved
