# manifests -- stored-evidence manifests

New sim and signoff evidence **bytes** go to the fleet's common artifact
store, not to git. Git keeps, per run, a small manifest and a Markdown
summary under `manifests/artifacts/`. Evidence bytes are private; manifests
are public, so committing one is safe. This is manifest-forward only: evidence
already committed (including the append-only `corners/*.log` and
`mc/raw-logs/` trails) stays where it is, and history is not rewritten.

## Flow

1. Stage the run's raw outputs in the git-ignored `.artifact-scratch/<bench>-<run-id>/`
   (or any directory outside the repo).
2. From a fleet worker (`$KLT_ARTIFACT_BROKER` is set for agent sessions there):

   ```
   python3 scripts/store_artifacts.py <bench> <run-id> .artifact-scratch/<bench>-<run-id>
   ```

   This runs `klt artifact put` per file and writes
   `manifests/artifacts/<bench>-<run-id>.manifest.json` plus
   `manifests/artifacts/<bench>-<run-id>.summary.md` (name, size, sha256 per object).
3. Commit those two files. Check them with
   `klt artifact verify manifests/artifacts/<bench>-<run-id>.manifest.json`
   (needs the broker; exits 0 when every object matches).

The writer **fails closed**: if `$KLT_ARTIFACT_BROKER` is unset, `klt` lacks
`artifact put` (needs klayout-tools `7e3561f` or later), or the broker is
unreachable or refuses, it exits 10 and writes nothing. There is no fallback
to committing bytes. Never write the broker URL, a bucket, an account ID or a
storage-scheme URI into this repo.

## CI

`scripts/ci/check-artifact-manifests.sh` (job `evidence-format`, and
`npm run lint`) validates every manifest's schema, accepts only
`artifact:<key>` URIs, rejects any bucket-scheme or cloud-ARN text, and fails if a
stored object's bytes (by sha256) are also tracked in git. It does not contact
the broker, so it proves the schema, not the hashes; `klt artifact verify` does
that. Unit tests: `python3 scripts/tests/test_check_artifact_manifests.py`.
