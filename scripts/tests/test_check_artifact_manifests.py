#!/usr/bin/env python3
"""Unit tests for scripts/check_artifact_manifests.py and store_artifacts.py.

Run: python3 scripts/tests/test_check_artifact_manifests.py
Never contacts a broker.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import check_artifact_manifests as chk  # noqa: E402
import store_artifacts as store  # noqa: E402

BLOB = b"stored object bytes\n"
SHA = hashlib.sha256(BLOB).hexdigest()


def entry(**over):
    e = {
        "sha256": SHA,
        "size": len(BLOB),
        "kind": "evidence",
        "name": "bench/run1/out.raw",
        "producer": {"tool": "klt", "version": "1", "loom.repo": "o/r", "commit": None},
        "uri": f"artifact:evidence/o__r/{SHA}",
    }
    e.update(over)
    return e


class Repo:
    def __init__(self, tmp):
        self.root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def manifest(self, entries, name="b-run1.manifest.json"):
        d = self.root / "manifests" / "artifacts"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps({"schema_version": 1, "entries": entries}))

    def track(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        subprocess.run(["git", "-C", str(self.root), "add", "-f", rel], check=True)


class CheckTests(unittest.TestCase):
    def run_check(self, repo):
        return chk.check(repo.root)

    def test_good_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry()])
            self.assertEqual(self.run_check(r), 0)

    def test_empty_dir_ok(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self.run_check(Repo(t)), 0)

    def test_non_artifact_uri(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry(uri=f"https://example.invalid/{SHA}")])
            self.assertEqual(self.run_check(r), 1)

    def test_s3_string_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry(uri="s3://bucket/key")])
            self.assertEqual(self.run_check(r), 1)
            r.manifest([entry(name="bench/s3://x")])
            self.assertEqual(self.run_check(r), 1)

    def test_committed_duplicate_of_stored_object(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry()])
            r.track("sim/bench/copy.dat", BLOB)
            self.assertEqual(self.run_check(r), 1)

    def test_same_size_different_bytes_ok(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry()])
            r.track("sim/bench/other.dat", b"x" * len(BLOB))
            self.assertEqual(self.run_check(r), 0)

    def test_key_must_end_in_sha(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry(uri="artifact:evidence/o__r/" + "0" * 64)])
            self.assertEqual(self.run_check(r), 1)

    def test_unknown_field_and_duplicate_name(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry(extra=1)])
            self.assertEqual(self.run_check(r), 1)
            r.manifest([entry(), entry()])
            self.assertEqual(self.run_check(r), 1)

    def test_stray_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r = Repo(t)
            r.manifest([entry()])
            (r.root / "manifests/artifacts/notes.txt").write_text("x")
            self.assertEqual(self.run_check(r), 1)


class WriterFailClosedTests(unittest.TestCase):
    def test_broker_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "KLT_ARTIFACT_BROKER"}
        old = os.environ
        os.environ = env
        try:
            with self.assertRaises(store.NotStored):
                store.preflight()
        finally:
            os.environ = old

    def test_klt_missing_or_without_artifact(self):
        with tempfile.TemporaryDirectory() as t:
            fake = Path(t) / "klt"
            fake.write_text("#!/bin/sh\nexit 2\n")
            fake.chmod(0o755)
            old = dict(os.environ)
            os.environ["KLT_ARTIFACT_BROKER"] = "http://127.0.0.1:1"
            try:
                os.environ["PATH"] = t
                with self.assertRaises(store.NotStored):
                    store.preflight()
                fake.unlink()
                with self.assertRaises(store.NotStored):
                    store.preflight()
            finally:
                os.environ.clear()
                os.environ.update(old)

    def test_unreachable_broker_writes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            staged = Path(t) / "staged"
            staged.mkdir()
            (staged / "a.raw").write_bytes(BLOB)
            fake = Path(t) / "klt"
            fake.write_text("#!/bin/sh\necho 'broker unreachable' >&2\nexit 1\n")
            fake.chmod(0o755)
            with self.assertRaises(store.NotStored):
                store.store(str(fake), "b", "run1", staged, repo)
            self.assertFalse((repo / "manifests").exists())

    def test_scratch_policy(self):
        self.assertIsNotNone(store.staged_problem(store.REPO_ROOT / "sim"))
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(store.staged_problem(Path(t)))


if __name__ == "__main__":
    unittest.main()
