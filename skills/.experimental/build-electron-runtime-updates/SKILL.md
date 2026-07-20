---
name: build-electron-runtime-updates
description: Design, implement, audit, or repair a dual-channel auto-update system for an Electron desktop shell and a separately released local runtime or binary backend. Use for Electron apps that must update macOS/Windows installers independently from Node, Bun, Go, Rust, or other runtime artifacts; for manifest, checksum, staging, atomic activation, health-check, rollback, IPC, versioning, object-storage, or GitHub Actions release work; and for diagnosing update or bootstrap failures.
---

# Build Electron Runtime Updates

Treat the Electron shell and runtime as two products with separate versions, artifacts, compatibility rules, and release triggers. Keep the shell stable while allowing the runtime to move quickly.

## Required Flow

1. Read repository instructions and inspect the existing implementation before editing. Identify:
   - desktop and runtime version sources;
   - Electron packaging targets and artifact names;
   - runtime entrypoint, process lifecycle, and health endpoint;
   - user-data paths and active-version state;
   - update UI, preload bridge, and IPC handlers;
   - storage layout, CI release workflows, signing, and current tests.
2. State assumptions and define observable success criteria. Do not silently choose a packaging format, supported target, health signal, storage provider, or rollback policy when the repository does not establish one.
3. Read [references/architecture.md](references/architecture.md) before changing the release or activation model.
4. Read [references/implementation-map.md](references/implementation-map.md) while mapping the model onto repository files. Preserve local conventions and make the smallest complete edit set.
5. Implement or repair the consumer before the publisher:
   - Make the desktop shell read its installed version from Electron's `app.getVersion()`.
   - Make runtime selection, validation, activation, launch, and rollback work against local fixtures.
   - Add the manifest and artifact publisher only after the client contract is executable.
6. Expose narrow preload methods and IPC events for check, install, and progress. Keep filesystem paths, arbitrary URLs, process spawning, and raw IPC unavailable to the renderer.
7. Build a release DAG in which immutable versioned artifacts and hashes finish first. Publish the mutable `latest` marker or manifest only from a job that depends on every required target.
8. Read [references/verification.md](references/verification.md), add failure-injection tests, and run the repository's relevant format, build, unit, packaging, and smoke checks.
9. If a runtime manifest is produced locally, run:

```bash
python3 <skill-dir>/scripts/validate_runtime_manifest.py path/to/latest.json \
  --require-target darwin-arm64 \
  --require-target darwin-x64 \
  --require-target win32-x64 \
  --artifact-dir path/to/artifacts
```

10. Do not create tags, publish artifacts, move a production `latest` marker, or trigger a live updater unless the user explicitly requested release or deployment. When authorized, verify the public artifacts and hashes before moving `latest`.

## Non-Negotiable Contracts

### Desktop channel

- Use its own SemVer source and `vX.Y.Z`-style tag namespace.
- Resolve an installer by exact platform and architecture.
- Download to a temporary path, verify a SHA-256 sidecar or signed metadata, then hand off to the platform installer.
- Exit only after the installer launch succeeds. Keep Linux unsupported unless Linux artifacts and install behavior are explicitly implemented.

### Runtime channel

- Use its own SemVer source and a distinct tag namespace such as `runtime-vX.Y.Z`.
- Fetch a JSON manifest that declares protocol, compatibility, entrypoint, and exact artifact hashes.
- Reject unsupported platform/architecture, protocol, minimum desktop version, runtime engine, unsafe paths, malformed hashes, and mismatched artifact names before activation.
- Download and verify before extraction. Extract into a unique staging directory with traversal and escaping-link protection.
- Validate the staged runtime, atomically rename it to a versioned directory, and only then update the active pointer.
- Retain the previous pointer during startup health validation. On failure, quarantine the candidate and restore the previous state; on success, finalize and prune according to policy.
- Use the same transaction for first-run bootstrap, recovery, and normal runtime updates.

### Publisher

- Keep versioned keys immutable and cacheable; keep `latest` metadata non-cacheable or revalidated.
- Validate that a release tag exactly matches its channel's version source.
- Generate hashes from the exact uploaded bytes.
- Never publish partial target coverage as latest.
- Never reuse or overwrite a released version.

## Security and Correctness Boundaries

- Treat SHA-256 as corruption/integrity detection, not publisher authentication. Rely on protected CI credentials and TLS for a trusted-channel design; add signed manifests when the threat model includes storage or delivery compromise.
- Reject absolute paths, `..`, NUL bytes, archive traversal entries, and symlinks or junctions that resolve outside staging.
- Spawn runtime entrypoints without a shell. Pass argument arrays and a minimal environment.
- Serialize update installation so two transactions cannot mutate state concurrently.
- Use atomic same-filesystem writes and renames for state and activation.
- Preserve the old runtime until the new process passes an objective health check.
- Do not expand an updater task into an account, ACL, token, or multi-user authorization system unless the product threat model explicitly requires it.
- Use a real SemVer implementation when prereleases or build metadata are supported; do not approximate SemVer with naive numeric splitting.

## Completion Standard

Report the two channel versions, supported targets, manifest protocol, storage paths, activation/rollback behavior, tests run, and any release action taken. Call out signing gaps, unsupported targets, and live-release steps that were intentionally not executed.
