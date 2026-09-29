#!/usr/bin/env bash
# Test suite for the claim-label issue/PR-mismatch guard in
# .loom/hooks/guard-loom-workflow.sh (issue #141).
#
# Usage: ./.loom/hooks/tests/test-guard-loom-workflow-claim-label-pr-mismatch.sh
#
# Background: `loom:curating` is an issue-only claim label, but issue and PR
# numbers share one namespace per repo, and `gh issue edit <N> --add-label
# <label>` -- whose underlying REST endpoint, `/repos/OWNER/REPO/issues/<N>
# /labels`, is IDENTICAL for issues and PRs -- succeeds whether <N> is an
# issue or a PR. Observed live on this repo's PR #139: a Curator dispatch
# pass claimed it by mistake and `loom:curating` sat on the draft PR for 2+
# days with no daemon-side reconciliation, making it invisible to both Judge
# review queues.
#
# The guard's discriminator is a LIVE forge lookup (`gh api
# repos/OWNER/REPO/issues/<N> --jq 'has("pull_request")'`), since `gh issue
# view <N>` succeeds for both issues and PRs and cannot tell them apart. This
# suite stubs `gh` on PATH so no real network/auth is exercised, and covers:
#
#   (a) `gh issue edit <PR-number> --add-label loom:curating`     -> deny
#   (b) `gh issue edit <issue-number> --add-label loom:curating`  -> allow
#   (c) simulated `gh api` failure (network/auth/rate-limit)      -> allow,
#       not hung (fail-open contract)
#   (d) the equivalent REST form, `gh api .../issues/<N>/labels`  -> deny
#   (e) a different label (`loom:issue`) on the same PR number    -> allow
#       (narrow: only loom:curating is guarded today)
#   (f) an unrelated command mentioning the label as inert text   -> allow
#   (g) no configured git remote (OWNER/REPO unresolvable)        -> allow
#       (fail-open on resolution failure, not just gh-call failure)
#   (h) contract: exit is always 0; deny output is well-formed JSON with
#       permissionDecision == "deny"
#
# The hook under test is copied into an isolated temp git tree (mirroring
# .loom/hooks/tests/test-guard-worktree-unresolved-var-pdk-env.sh's own
# convention) so REPO_ROOT resolves there, never against the real repo. Exit
# 0 = all pass, 1 = fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SRC_HOOK="$REPO_ROOT/.loom/hooks/guard-loom-workflow.sh"

PASS=0
FAIL=0
TOTAL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

git init -q "$TMPROOT"
git -C "$TMPROOT" config user.email "test@example.com"
git -C "$TMPROOT" config user.name "Test"
touch "$TMPROOT/README.md"
git -C "$TMPROOT" add README.md
git -C "$TMPROOT" commit -q -m "init"
git -C "$TMPROOT" remote add origin "https://github.com/2AMLogic/gf180-sram.git"

mkdir -p "$TMPROOT/.loom/hooks" "$TMPROOT/.loom/scripts/lib" "$TMPROOT/bin"
cp "$SRC_HOOK" "$TMPROOT/.loom/hooks/guard-loom-workflow.sh"
chmod +x "$TMPROOT/.loom/hooks/guard-loom-workflow.sh"
# Best-effort: stage the real config-resolver.sh so guards.claimLabelPrMismatch
# reads through the actual tiered resolver rather than the source-missing
# fallback. Not fatal if absent -- the hook's own `source ... || true` covers it.
if [[ -f "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" ]]; then
    cp "$REPO_ROOT/.loom/scripts/lib/config-resolver.sh" "$TMPROOT/.loom/scripts/lib/config-resolver.sh"
fi
HOOK="$TMPROOT/.loom/hooks/guard-loom-workflow.sh"

# --- Stub `gh` on PATH: no real network/auth is ever exercised. ------------
# Understands exactly the one live call this guard makes:
#   gh api repos/OWNER/REPO/issues/<N> --jq 'has("pull_request")'
# Issue-number -> behavior mapping, controlled by GH_STUB_MODE:
#   default mode: 139 -> "true" (PR), 141 -> "false" (issue), anything else -> "false"
#   "fail" mode:  every call exits 1 with a stderr message (simulated gh api error)
cat >"$TMPROOT/bin/gh" <<'GHSTUB'
#!/usr/bin/env bash
if [[ "${GH_STUB_MODE:-}" == "fail" ]]; then
    echo "gh: simulated network/auth failure" >&2
    exit 1
fi
if [[ "$1" == "api" ]]; then
    path="$2"
    num="${path##*/issues/}"
    num="${num%%/*}"
    case "$num" in
        139) printf 'true\n' ;;
        *) printf 'false\n' ;;
    esac
    exit 0
fi
echo "gh-stub: unhandled invocation: $*" >&2
exit 1
GHSTUB
chmod +x "$TMPROOT/bin/gh"
STUB_PATH="$TMPROOT/bin:$PATH"

pass() { PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1)); printf "${GREEN}PASS${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1)); printf "${RED}FAIL${NC} %s\n" "$1"; }

# run_hook <command> <cwd> [extra PATH-prefixed env assignment...]
# Prints "<exit_code>|<stdout>".
run_hook() {
    local cmd="$1" cwd="$2"
    local exit_code=0 output
    output=$(jq -n --arg cmd "$cmd" --arg cwd "$cwd" \
        '{tool_name:"Bash", tool_input:{command:$cmd}, cwd:$cwd}' \
        | PATH="$STUB_PATH" bash "$HOOK" 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

# run_hook_env <command> <cwd> <extra-env-assignment...> — same as run_hook
# but with additional env vars (e.g. GH_STUB_MODE=fail) exported for the call.
run_hook_env() {
    local cmd="$1" cwd="$2"
    shift 2
    local exit_code=0 output
    output=$(jq -n --arg cmd "$cmd" --arg cwd "$cwd" \
        '{tool_name:"Bash", tool_input:{command:$cmd}, cwd:$cwd}' \
        | env "$@" PATH="$STUB_PATH" bash "$HOOK" 2>/dev/null) || exit_code=$?
    printf '%s|%s' "$exit_code" "$output"
}

assert_allow() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    local decision
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    if [[ "$code" == "0" && "$decision" != "deny" ]]; then
        pass "$desc"
    else
        fail "$desc (expected allow, got exit=$code output=$out)"
    fi
}

assert_deny() {
    local desc="$1" result="$2"
    local code="${result%%|*}" out="${result#*|}"
    if [[ "$code" != "0" ]]; then
        fail "$desc (expected exit 0 with deny JSON, got NONZERO exit=$code)"
        return
    fi
    local decision
    decision=$(echo "$out" | jq -r '.hookSpecificOutput.permissionDecision // empty' 2>/dev/null || true)
    if [[ "$decision" == "deny" ]]; then
        pass "$desc"
    else
        fail "$desc (expected permissionDecision=deny, got: $out)"
    fi
}

echo "=== guard-loom-workflow.sh claim-label PR/issue mismatch tests (#141) ==="

# (a) `gh issue edit <PR-number> --add-label loom:curating` -> deny.
result=$(run_hook 'gh issue edit 139 --add-label loom:curating' "$TMPROOT")
assert_deny "(a) gh issue edit on a PR number, loom:curating -> deny" "$result"

# (b) `gh issue edit <issue-number> --add-label loom:curating` -> allow
# (unchanged/allowed).
result=$(run_hook 'gh issue edit 141 --add-label loom:curating' "$TMPROOT")
assert_allow "(b) gh issue edit on a real issue number, loom:curating -> allow" "$result"

# (c) simulated `gh api` failure (network/auth/rate-limit) -> allow, not hung
# (fail-open contract). Uses the PR number from (a) -- if the lookup
# succeeded it would deny, so this specifically proves the failure path
# falls through to allow rather than denying blind or hanging.
result=$(run_hook_env 'gh issue edit 139 --add-label loom:curating' "$TMPROOT" GH_STUB_MODE=fail)
assert_allow "(c) simulated gh api failure -> allow (fail-open)" "$result"

# (d) the equivalent REST form, `gh api .../issues/<N>/labels`, adding the
# same label -> deny.
result=$(run_hook 'gh api repos/2AMLogic/gf180-sram/issues/139/labels -f "labels[]=loom:curating"' "$TMPROOT")
assert_deny "(d) gh api issues/<PR-number>/labels REST form -> deny" "$result"

# (e) a DIFFERENT label on the same PR number -> allow (guard is narrowly
# scoped to loom:curating only, per issue #141's own scope note).
result=$(run_hook 'gh issue edit 139 --add-label loom:issue' "$TMPROOT")
assert_allow "(e) different label (loom:issue) on a PR number -> allow (out of scope)" "$result"

# (f) an unrelated command that merely mentions the phrase as inert text
# (e.g. documenting this very guard) -> allow.
result=$(run_hook 'echo "the loom:curating claim-label guard covers gh issue edit 139 --add-label loom:curating"' "$TMPROOT")
assert_allow "(f) inert narration mentioning the phrase -> allow" "$result"

# (g) no configured git remote -> OWNER/REPO is unresolvable -> allow
# (fail-open on resolution failure, not just on a gh-call failure).
NOREMOTE="$TMPROOT-noremote"
git init -q "$NOREMOTE"
git -C "$NOREMOTE" config user.email "test@example.com"
git -C "$NOREMOTE" config user.name "Test"
touch "$NOREMOTE/README.md"
git -C "$NOREMOTE" add README.md
git -C "$NOREMOTE" commit -q -m "init"
mkdir -p "$NOREMOTE/.loom/hooks" "$NOREMOTE/.loom/scripts/lib"
cp "$SRC_HOOK" "$NOREMOTE/.loom/hooks/guard-loom-workflow.sh"
chmod +x "$NOREMOTE/.loom/hooks/guard-loom-workflow.sh"
NOREMOTE_HOOK="$NOREMOTE/.loom/hooks/guard-loom-workflow.sh"
result_noremote=$(jq -n --arg cmd 'gh issue edit 139 --add-label loom:curating' --arg cwd "$NOREMOTE" \
    '{tool_name:"Bash", tool_input:{command:$cmd}, cwd:$cwd}' \
    | PATH="$STUB_PATH" bash "$NOREMOTE_HOOK" 2>/dev/null; printf '|EXIT=%s' "$?")
noremote_out="${result_noremote%|EXIT=*}"
noremote_code="${result_noremote##*|EXIT=}"
result="${noremote_code}|${noremote_out}"
assert_allow "(g) no git remote configured -> allow (fail-open on resolution failure)" "$result"
rm -rf "$NOREMOTE"

# (h) contract check: a genuine deny's JSON is well-formed with
# permissionDecision == "deny" and hookEventName == "PreToolUse" (already
# implicitly checked by assert_deny's jq parse above, asserted explicitly
# here for (a)'s case).
result=$(run_hook 'gh issue edit 139 --add-label loom:curating' "$TMPROOT")
out="${result#*|}"
event_name=$(echo "$out" | jq -r '.hookSpecificOutput.hookEventName // empty' 2>/dev/null || true)
if [[ "$event_name" == "PreToolUse" ]]; then
    pass "(h) deny JSON carries hookEventName=PreToolUse"
else
    fail "(h) deny JSON missing/wrong hookEventName (got: $out)"
fi

echo
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0
