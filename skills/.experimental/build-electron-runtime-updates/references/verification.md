# Verification and Release Checklist

## Contents

1. Unit tests
2. Transaction tests
3. Packaging and platform smoke tests
4. Release preflight
5. Post-publish verification

## 1. Unit tests

Cover pure behavior for both channels:

- strict SemVer comparison, including prerelease ordering if supported;
- tag normalization and exact version/tag agreement;
- platform/architecture to artifact mapping;
- unsupported targets;
- progress normalization with missing or invalid `Content-Length`;
- redirect and non-200 handling with a redirect limit;
- request and download timeouts;
- valid and invalid SHA-256 text;
- manifest schema, protocol, engine, and minimum desktop compatibility;
- safe and unsafe entrypoint paths, including Windows drive paths and NUL bytes;
- realpath containment and executable permissions;
- IPC input validation and cleanup of progress listeners.

## 2. Transaction tests

Use temporary directories and injected download/extract/start/health functions. Assert state after every failure:

| Injected failure | Required result |
| --- | --- |
| Manifest fetch or JSON parse | Active state unchanged |
| Unsupported target or protocol | No download and state unchanged |
| Interrupted download | Partial archive removed; state unchanged |
| Digest mismatch | No extraction; state unchanged |
| Archive traversal or escaping link | Extraction rejected; outside files unchanged |
| Missing or unsafe entrypoint | Candidate rejected; state unchanged |
| Activation write interruption | Previous valid state remains readable |
| Candidate process exits early | Candidate stopped/quarantined; old state restored |
| Health timeout or wrong response | Candidate rolled back; old runtime restarted |
| Successful health check | Rollback pointer removed; retention policy applied |
| Two concurrent install requests | One transaction runs; the other joins or fails clearly |

Also test first run with no previous runtime, startup with corrupt `current.json`, and recovery when the selected runtime directory is missing.

## 3. Packaging and platform smoke tests

For each supported target:

1. Build the exact artifact name expected by the client.
2. Inspect the packaged Electron version and confirm it matches the desktop tag.
3. Inspect the runtime archive and verify `runtime-manifest.json` plus the declared entrypoint exist.
4. Run the manifest validator against downloaded workflow artifacts.
5. Install over an older desktop version and confirm the install directory and user data survive.
6. Install a runtime update, observe progress, restart the runtime, and confirm the objective health signal.
7. Force a bad candidate and confirm rollback to the previous runtime.

Do not infer Windows behavior from Wine or macOS behavior from an unsigned local bundle. Use real target runners for installer and permission behavior.

## 4. Release preflight

- Working tree contains only intended release changes.
- Desktop and runtime versions were changed only for channels being released.
- Version sync scripts updated package metadata and lockfiles together.
- New version is greater than the public latest marker and has never been published.
- Tag exactly matches the relevant version source.
- Required tests, builds, signing, and notarization pass.
- Required target list matches the manifest and client artifact map.
- Object-store credentials are present only in protected CI secrets.
- Versioned destination keys do not already exist.
- Latest publication job depends on every required artifact job.

## 5. Post-publish verification

Fetch public objects rather than trusting upload logs:

- `desktop/latest.txt` equals the released desktop tag.
- Every desktop installer and sidecar is reachable; recomputed digests match.
- `runtime/latest.json` parses, passes the bundled validator, and names the released runtime tag.
- Every runtime artifact is reachable and matches its manifest digest.
- Cache headers are immutable for versioned objects and revalidated for latest metadata.
- A previous installed version detects the update and completes the intended install/restart flow.

If any verification fails, do not point `latest` at a different partial build. Restore the last known-good latest metadata or publish a new, strictly greater corrected version according to repository policy.
