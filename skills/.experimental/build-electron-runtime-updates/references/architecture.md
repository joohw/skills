# Dual-Channel Update Architecture

## Contents

1. Ownership split
2. Remote layout
3. Runtime manifest
4. Local layout and state
5. Runtime transaction
6. Compatibility and trust

## 1. Ownership split

The Electron shell owns windowing, updater orchestration, local runtime process lifecycle, recovery UI, and the stable shell/runtime protocol. The runtime owns application behavior and may be Node-based or a standalone binary.

Release the shell only when shell code, packaging, signing, protocol support, or native integration changes. Release the runtime for backend or web application changes that remain compatible with an installed shell.

Do not bundle a second production runtime inside a bootstrap-only installer unless offline first launch is an explicit requirement. If a fallback runtime is bundled, define whether it is immutable recovery media or participates in normal version selection.

## 2. Remote layout

Use immutable versioned objects and one mutable pointer per channel:

```text
desktop/
  latest.txt
  v1.4.2/
    product-desktop-darwin-arm64.dmg
    product-desktop-darwin-arm64.dmg.sha256
    product-desktop-darwin-x64.dmg
    product-desktop-darwin-x64.dmg.sha256
    product-desktop-windows-x64.exe
    product-desktop-windows-x64.exe.sha256
runtime/
  latest.json
  runtime-v8.12.0/
    product-runtime-darwin-arm64.tar.gz
    product-runtime-darwin-x64.tar.gz
    product-runtime-windows-x64.zip
```

Give versioned objects long immutable cache headers. Give `latest.txt` and `latest.json` `no-cache, must-revalidate` or an equivalent short policy.

## 3. Runtime manifest

Keep the manifest small and explicit:

```json
{
  "version": "8.12.0",
  "tag": "runtime-v8.12.0",
  "runtime_protocol": 2,
  "min_desktop_version": "1.4.0",
  "min_node_major": 22,
  "entrypoint": {
    "kind": "node",
    "path": "scripts/start-runtime.mjs",
    "args": []
  },
  "artifacts": {
    "darwin-arm64": {
      "name": "product-runtime-darwin-arm64.tar.gz",
      "sha256": "<64 lowercase hex characters>"
    },
    "darwin-x64": {
      "name": "product-runtime-darwin-x64.tar.gz",
      "sha256": "<64 lowercase hex characters>"
    },
    "win32-x64": {
      "name": "product-runtime-windows-x64.zip",
      "sha256": "<64 lowercase hex characters>"
    }
  }
}
```

For `entrypoint.kind: "node"`, launch the entrypoint with Electron's executable in Node mode or with a bundled compatible Node executable. For `entrypoint.kind: "executable"`, launch the resolved file directly. Only include `min_node_major` when the runtime actually depends on Node.

Increment `runtime_protocol` only for a contract change that older shells must reject. Use `min_desktop_version` for additive shell capabilities that a runtime requires.

## 4. Local layout and state

Store runtime data under the application's user-data root, not beside the signed application:

```text
runtimes/
  current.json
  versions/
    8.11.3/
      runtime-manifest.json
      ...
    8.12.0/
      runtime-manifest.json
      ...
```

During validation, state can temporarily retain a rollback pointer:

```json
{
  "version": "8.12.0",
  "previous_version": "8.11.3",
  "updated_at": "2026-07-21T00:00:00.000Z"
}
```

Write state to a sibling temporary file with user-only permissions, then rename it over `current.json`. The temporary file and destination must be on the same filesystem.

## 5. Runtime transaction

Use this state sequence:

```text
fetch manifest
  -> validate schema and compatibility
  -> select exact target
  -> download to temporary archive
  -> verify digest/signature
  -> inspect archive entries
  -> extract to unique staging directory
  -> validate manifest, required files, containment, and executable bit
  -> rename staging to versions/<version>
  -> atomically activate with previous_version
  -> launch candidate
  -> wait for objective health signal
       success -> remove previous_version -> prune old versions
       failure -> mark candidate failed -> restore old state -> relaunch old runtime
```

Do not mutate the active version directory in place. Do not delete the previous runtime until health validation finishes. Define a bounded health timeout and stop the candidate process before rollback.

First-run bootstrap follows the same path but has no previous state. If it fails, show a local recovery surface with the concrete error and a retry action.

## 6. Compatibility and trust

Validate at least:

- strict SemVer and exact tag/version correspondence;
- supported manifest protocol;
- minimum desktop version;
- engine requirement for Node entrypoints;
- platform and architecture;
- exact artifact basename and 64-hex digest;
- safe relative entrypoint and string-only argument list;
- realpath containment inside the runtime root;
- executable permission where applicable.

A hash hosted beside an artifact detects accidental corruption and inconsistent bytes. It does not authenticate a publisher if both files can be replaced. For a stronger model, sign a canonical manifest, pin the public verification key in the shell, and rotate keys through an explicit shell release.
