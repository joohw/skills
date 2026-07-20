# Implementation Map

## Contents

1. Repository responsibilities
2. Consumer sequence
3. IPC surface
4. Release DAG
5. Version rules
6. Common mistakes

## 1. Repository responsibilities

Map responsibilities onto existing files; do not force these exact names:

| Responsibility | Typical location |
| --- | --- |
| Desktop check, download, checksum, installer handoff | `electron/desktop-update.*` |
| Runtime manifest, compatibility, staging, state | `electron/runtime-update.*` |
| Runtime process start, stop, health, rollback | `electron/runtime-process.*` |
| First-run and recovery orchestration | `electron/runtime-bootstrap.*` |
| IPC handlers and app lifecycle | `electron/main.*` |
| Narrow renderer bridge | `electron/preload.*` |
| Runtime assembly | `scripts/prepare-runtime.*` |
| Version synchronization | `scripts/sync-*-version.*` |
| Artifact publication | `scripts/publish-release.*` |
| Per-channel CI | `.github/workflows/release-*.yml` |

Keep pure functions and injected I/O seams so URL resolution, compatibility, activation, and rollback can be tested without network or Electron.

## 2. Consumer sequence

Desktop check:

```text
current = app.getVersion()
latest = fetch(desktop/latest.txt)
if semver.gt(latest, current):
  target = installerMap[platform + "-" + arch]
  offer exact version and target
```

Desktop install:

```text
serialize install
download immutable installer to temp
download expected digest or signed metadata
verify bytes
spawn platform installer detached
quit Electron only after spawn succeeds
```

Runtime preparation must not activate:

```text
latest = fetch(runtime/latest.json)
validate latest and compatibility
artifact = latest.artifacts[target]
download -> verify -> safe extract -> inspect
rename staging -> versions/version
return candidate
```

Activation and health validation belong to the process owner:

```text
oldState = read current.json
activate(candidate, previous=oldState.version)
stop old runtime
try:
  start candidate without shell
  wait for health endpoint or readiness protocol
  finalize state
  prune old versions
catch:
  stop candidate
  quarantine candidate
  restore oldState
  start old runtime when present
  surface failure
```

This separation prevents a checksum or extraction failure from changing the active runtime and ensures only one component owns process transitions.

## 3. IPC surface

Expose domain methods, not generic IPC:

```js
contextBridge.exposeInMainWorld("desktopUpdates", {
  checkDesktop: () => ipcRenderer.invoke("desktop:update-check"),
  installDesktop: (tag) => ipcRenderer.invoke("desktop:update-install", tag),
  checkRuntime: () => ipcRenderer.invoke("runtime:update-check"),
  installRuntime: (tag) => ipcRenderer.invoke("runtime:update-install", tag),
  onProgress: (listener) => {
    const handler = (_event, progress) => listener(progress);
    ipcRenderer.on("update:progress", handler);
    return () => ipcRenderer.removeListener("update:progress", handler);
  }
});
```

Validate requested tags in the main process. Prefer letting the main process refetch authoritative metadata rather than accepting a renderer-provided URL, hash, destination, command, or path.

Return bounded serializable objects such as `{ ok, channel, phase, current_version, latest_version, percent, error }`. Prevent concurrent installs with an in-flight promise or mutex and clear it in `finally`.

## 4. Release DAG

Use two tag-triggered workflows:

```text
vX.Y.Z
  -> validate tag == desktop package version
  -> build/sign/notarize macOS arm64
  -> build/sign/notarize macOS x64
  -> build/sign Windows x64
  -> upload each installer + digest to immutable versioned keys
  -> publish desktop/latest.txt only after all required jobs succeed

runtime-vX.Y.Z
  -> validate tag == runtime package version
  -> build runtime matrix
  -> upload immutable artifacts
  -> collect the exact artifacts produced by those jobs
  -> calculate digests
  -> publish runtime/latest.json only after all required jobs succeed
```

Fail when signing credentials required by the release policy are missing. Do not silently publish unsigned production artifacts. Use an explicit dry-run or skip state for forks and development environments.

Prefer a generic S3-compatible upload helper for R2, S3, MinIO, or another object store. Keep provider credentials in CI secrets and never place them in client code or skill output.

## 5. Version rules

- Desktop version source: Electron package metadata used by the packager and `app.getVersion()`.
- Runtime version source: runtime package or build metadata embedded into `runtime-manifest.json`.
- Desktop tag: `v<desktop-version>`.
- Runtime tag: `runtime-v<runtime-version>`.
- Synchronize package files and lockfiles with scripts; do not hand-edit only one copy.
- Require a new version to be strictly greater than the production latest marker.
- Default ordinary fixes and UI changes to PATCH unless project policy says otherwise.

The two numeric versions may coincide, but they remain independent. Never infer runtime compatibility merely because the numbers match.

## 6. Common mistakes

- Publishing `latest` from every matrix job, allowing the fastest target to expose a partial release.
- Updating the runtime in place or deleting the old version before health validation.
- Trusting archive paths because the archive hash matched.
- Checking a hard-coded UI version instead of the installed Electron version.
- Accepting arbitrary download URLs or commands from the renderer.
- Treating a successful process spawn as a successful health check.
- Using one tag namespace or one package version for both channels.
- Calculating a hash from a local file that is not byte-identical to the uploaded object.
- Supporting SemVer prereleases with a comparator that ignores prerelease ordering.
- Forgetting listener cleanup, install serialization, temporary-file cleanup, or request timeouts.
