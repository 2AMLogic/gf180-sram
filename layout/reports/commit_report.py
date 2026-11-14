#!/usr/bin/env python3
"""The single path by which layout/reports/generate.sh commits a klt report.

Issue #340. Every committed report under `layout/reports/` used to be written
by its own inline `python3 -c "..."` block in `generate.sh` -- ten of them,
each hand-listing the subset of fields it happened to know carried a
host-absolute path (`netlist_path` here, `layout`/`reference` there, `file` in
one case, nothing at all in two). Ten hand-maintained field lists drifted, as
hand-maintained lists do: the oldest blocks scrubbed almost nothing and the
committed reports showed it (`klt env-provenance scan` found home-directory
paths in three of them, and `klt env-provenance lint-envelope` found
`/tmp/tmp.<random>/...` scratch paths in five).

This script replaces all of that with one rule applied to the WHOLE document
plus one check that the rule worked:

  1. **Rewrite, not allow-list.** Every string anywhere in the JSON -- at any
     nesting depth, in any field, including ones klt has not invented yet --
     has the generating checkout's root (`--root`) and the run's scratch dir
     (`--work`) stripped out of it. A `$ROOT/`-rooted path becomes its
     repo-relative form; a `$WORK/`-rooted path collapses to its basename
     (the scratch dir does not survive the run, and `netlist_sha256` /
     `provenance.input.content_hash` are what actually pin that file's
     content). No field is named anywhere in this script, so no field can be
     forgotten.
  2. **Then let the tool check it.** The rewritten report is handed to
     `klt env-provenance lint-envelope`, klayout-tools' own absolute-path
     linter, BEFORE it is moved into place. A report that still carries an
     absolute path is never committed -- the run fails instead, loudly, with
     the offending field named. That is the structural half of the fix: the
     generator *cannot* mint a leak any more, rather than being documented
     not to.

`lint-envelope` is deliberately stricter than the `klt env-provenance scan`
that `scripts/ci/check-provenance-hygiene.sh` runs at PR time: `scan` asks
"does this record name a person" (home-shaped paths), `lint-envelope` asks
"does every reference still resolve on another checkout" (ANY absolute path,
including the `/tmp/...` scratch paths that made `extract-array.json` and
`lvs-array.json` non-reproducible). Mint time can afford the stricter
question because nothing is grandfathered there -- the report does not exist
yet. See `layout/reports/README.md`, "Provenance hygiene: one scrub path".

This implements issue #109's ratified rule (repo-relative paths in committed
evidence; existing records never rewritten retroactively) with one
implementation instead of ten.

Usage (from `generate.sh`, which wraps both forms in shell functions):

    commit_report.py commit RAW OUT --root ROOT --work WORK \
        [--set FIELD=VALUE ...] [--drop FIELD ...] \
        [--print FORMAT] [--allow-prefix PREFIX ...] [--skip-lint]

    commit_report.py status JSON --print FORMAT

`--set` overrides a top-level field AFTER the rewrite (for the cases where the
honest value is prose, not a path: the scratch abutted composite's `file`, the
PDK-native deck's `deck`, the bulk-omission `_note`). `--drop` removes a
top-level field (the ~18 MB `devices[]`/`nets[]` arrays). `--print` is a
`str.format` template over the report's top-level fields, e.g.
`'status: {status} | violations: {violation_count}'`. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

LINT_SUBCOMMAND = ("env-provenance", "lint-envelope")


def _prefixes(root: str, work: str) -> list[tuple[str, str]]:
    """Path prefixes to strip, longest first, each with its replacement.

    Both the logical path and its `realpath` are included: `$ROOT` comes from
    `cd ... && pwd` (logical) while a tool may echo back the resolved form,
    and `mktemp -d` differs from its realpath on macOS (`/var/folders/...`
    vs `/private/var/folders/...`).
    """
    out: dict[str, str] = {}
    for raw, replacement in ((work, ""), (root, "")):
        if not raw:
            continue
        for form in (raw, os.path.realpath(raw)):
            form = form.rstrip(os.sep)
            if form and form != os.sep:
                out[form] = replacement
    # Longest first so a $WORK nested inside $ROOT is matched as $WORK.
    return sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True)


def _rewrite_string(value: str, prefixes: list[tuple[str, str]]) -> str:
    for prefix, _ in prefixes:
        if value == prefix:
            return "."
        value = value.replace(prefix + os.sep, "")
    return value


def _rewrite(node: Any, prefixes: list[tuple[str, str]]) -> Any:
    if isinstance(node, str):
        return _rewrite_string(node, prefixes)
    if isinstance(node, dict):
        return {k: _rewrite(v, prefixes) for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite(v, prefixes) for v in node]
    return node


def _lint(path: str, allow_prefix: list[str]) -> None:
    """Fail unless klt's own envelope linter finds no absolute path.

    A check that cannot run must never look like one that passed, so a
    missing or too-old `klt` is a hard failure here, not a warning.
    """
    if shutil.which("klt") is None:
        sys.exit(
            "FATAL: klt (klayout-tools) is required on PATH to lint "
            f"{path} before committing it.\n"
            "       pip install klayout-tools==0.8.0   # first release with "
            "`klt env-provenance lint-envelope`"
        )
    cmd = ["klt", *LINT_SUBCOMMAND, "--format", "json"]
    for prefix in allow_prefix:
        cmd += ["--allow-prefix", prefix]
    cmd.append(path)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return
    if proc.returncode != 3:
        sys.exit(
            f"FATAL: `{' '.join(cmd)}` exited {proc.returncode} "
            "(expected 0 = clean or 3 = findings), so the provenance of "
            f"{path} is unverified and it was NOT committed.\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    # Exit 3: real findings. Name the offending fields, but do not echo the
    # matched text -- it is the leaking host path, and this message can end
    # up in a log that outlives the host (`klt env-provenance scan --help`
    # makes the same point about its own findings).
    try:
        report = json.loads(proc.stdout)
        fields = [
            finding.get("field", "<unnamed>")
            for entry in report.get("files", [])
            for finding in entry.get("findings", [])
        ]
    except (json.JSONDecodeError, AttributeError, TypeError):
        fields = []
    sys.exit(
        f"FATAL: {path} still holds an absolute host path after the "
        f"$ROOT/$WORK rewrite, in field(s): {', '.join(fields) or '<unparsed>'}.\n"
        "       The report was NOT committed. Inspect it with:\n"
        f"           klt {' '.join(LINT_SUBCOMMAND)} {path}\n"
        "       Then either make the generator pass the path in a "
        "$ROOT-/$WORK-rooted form, override the field with "
        "`commit_report --set FIELD=<prose>` if the honest value is not a "
        "repo path, or declare a genuinely machine-wide install location "
        "with `--allow-prefix`."
    )


def _do_commit(args: argparse.Namespace) -> int:
    with open(args.raw) as handle:
        data = json.load(handle)

    data = _rewrite(data, _prefixes(args.root, args.work))

    for field in args.drop:
        data.pop(field, None)
    for assignment in args.set:
        field, _, value = assignment.partition("=")
        if not field or "." in field:
            sys.exit(
                f"FATAL: --set expects a top-level FIELD=VALUE, got {assignment!r}"
            )
        data[field] = value

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    os.makedirs(out_dir, exist_ok=True)
    # Write beside the destination, lint, and only then move into place, so a
    # leaking report never lands on top of a committed one.
    fd, staged = tempfile.mkstemp(
        dir=out_dir, prefix=f".{os.path.basename(args.out)}.", suffix=".staged"
    )
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        if not args.skip_lint:
            _lint(staged, args.allow_prefix)
        os.replace(staged, args.out)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)

    if args.print:
        print(args.print.format(**data))
    return 0


def _do_status(args: argparse.Namespace) -> int:
    with open(args.json) as handle:
        data = json.load(handle)
    print(args.print.format(**data))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    commit = sub.add_parser(
        "commit",
        help="rewrite host paths out of a raw klt report, lint it, commit it",
    )
    commit.add_argument("raw", metavar="RAW", help="the raw `klt --format json` output")
    commit.add_argument("out", metavar="OUT", help="the committed report to write")
    commit.add_argument(
        "--root", required=True, help="the generating checkout's root ($ROOT)"
    )
    commit.add_argument(
        "--work", required=True, help="the run's scratch directory ($WORK)"
    )
    commit.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="override a top-level field after the rewrite (repeatable)",
    )
    commit.add_argument(
        "--drop",
        action="append",
        default=[],
        metavar="FIELD",
        help="remove a top-level field, e.g. a bulk array (repeatable)",
    )
    commit.add_argument(
        "--print",
        metavar="FORMAT",
        help="str.format template over the report's top-level fields",
    )
    commit.add_argument(
        "--allow-prefix",
        action="append",
        default=[],
        metavar="PREFIX",
        help="passed through to `klt env-provenance lint-envelope` for a "
        "genuinely machine-wide install location (repeatable)",
    )
    commit.add_argument(
        "--skip-lint",
        action="store_true",
        help="skip the lint-envelope self-check (for this script's own tests "
        "only -- never in generate.sh)",
    )
    commit.set_defaults(func=_do_commit)

    status = sub.add_parser(
        "status", help="print a status line from an already-committed report"
    )
    status.add_argument("json", metavar="JSON", help="the committed report to read")
    status.add_argument(
        "--print",
        required=True,
        metavar="FORMAT",
        help="str.format template over the report's top-level fields",
    )
    status.set_defaults(func=_do_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
