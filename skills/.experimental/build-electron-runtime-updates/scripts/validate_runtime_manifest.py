#!/usr/bin/env python3
"""Validate a dual-channel updater runtime manifest and optional artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath


IDENTIFIER = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(
    rf"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    rf"(?:-{IDENTIFIER}(?:\.{IDENTIFIER})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TARGET = re.compile(r"^[a-z0-9]+-[a-z0-9_]+$")


def safe_relative(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"{field} must be a non-empty string without NUL bytes")
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or ".." in posix.parts:
        raise ValueError(f"{field} must be a safe relative path")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(manifest: object, required_targets: list[str], artifact_dir: Path | None) -> dict[str, object]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")

    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError("version must be strict SemVer")
    if manifest.get("tag") != f"runtime-v{version}":
        raise ValueError("tag must equal runtime-v<version>")

    protocol = manifest.get("runtime_protocol")
    if not isinstance(protocol, int) or isinstance(protocol, bool) or protocol < 1:
        raise ValueError("runtime_protocol must be a positive integer")

    minimum = manifest.get("min_desktop_version")
    if minimum is not None and (not isinstance(minimum, str) or not SEMVER.fullmatch(minimum)):
        raise ValueError("min_desktop_version must be strict SemVer")

    entrypoint = manifest.get("entrypoint")
    if not isinstance(entrypoint, dict) or entrypoint.get("kind") not in {"node", "executable"}:
        raise ValueError("entrypoint.kind must be node or executable")
    safe_relative(entrypoint.get("path"), "entrypoint.path")
    args = entrypoint.get("args", [])
    if not isinstance(args, list) or any(not isinstance(arg, str) or "\x00" in arg for arg in args):
        raise ValueError("entrypoint.args must be an array of strings without NUL bytes")
    if entrypoint["kind"] == "node":
        node_major = manifest.get("min_node_major")
        if not isinstance(node_major, int) or isinstance(node_major, bool) or node_major < 1:
            raise ValueError("min_node_major must be a positive integer for a Node entrypoint")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("artifacts must be a non-empty object")
    missing = sorted(set(required_targets) - set(artifacts))
    if missing:
        raise ValueError(f"missing required targets: {', '.join(missing)}")

    checked_files: list[str] = []
    for target, artifact in artifacts.items():
        if not isinstance(target, str) or not TARGET.fullmatch(target):
            raise ValueError(f"invalid target key: {target!r}")
        if not isinstance(artifact, dict):
            raise ValueError(f"artifact {target} must be an object")
        name = safe_relative(artifact.get("name"), f"artifacts.{target}.name")
        if "/" in name or "\\" in name:
            raise ValueError(f"artifacts.{target}.name must be a basename")
        expected = artifact.get("sha256")
        if not isinstance(expected, str) or not SHA256.fullmatch(expected):
            raise ValueError(f"artifacts.{target}.sha256 must be 64 lowercase hex characters")
        if artifact_dir is not None:
            artifact_path = artifact_dir / name
            if not artifact_path.is_file():
                raise ValueError(f"artifact file is missing: {artifact_path}")
            actual = file_sha256(artifact_path)
            if actual != expected:
                raise ValueError(f"checksum mismatch for {artifact_path}: expected {expected}, got {actual}")
            checked_files.append(str(artifact_path))

    return {
        "ok": True,
        "version": version,
        "tag": manifest["tag"],
        "runtime_protocol": protocol,
        "targets": sorted(artifacts),
        "checked_files": checked_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-target", action="append", default=[])
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = validate(manifest, args.require_target, args.artifact_dir)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
