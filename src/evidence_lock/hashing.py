"""Portable path validation and SHA-256 evidence snapshots."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class EvidencePathError(ValueError):
    """Raised when an evidence path cannot be captured safely."""


def canonical_json_bytes(value: object) -> bytes:
    """Serialize a JSON-compatible value deterministically for hashing."""

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    """Return a lowercase SHA-256 digest."""

    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _looks_absolute(raw: str) -> bool:
    return PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute()


def _has_symlink_component(path: Path) -> bool:
    lexical = path if path.is_absolute() else Path.cwd() / path
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current = current / part
        if current.is_symlink():
            return True
    return False


def resolve_evidence_path(root: Path, raw: str) -> tuple[Path, str]:
    """Resolve a relative path below root without allowing symlink traversal."""

    if not raw or "\x00" in raw:
        raise EvidencePathError("evidence paths must be non-empty and contain no NUL bytes")
    windows_path = PureWindowsPath(raw)
    if (
        _looks_absolute(raw)
        or windows_path.drive
        or windows_path.root
        or "\\" in raw
        or any(character in raw for character in "\r\n\t")
    ):
        raise EvidencePathError("evidence paths must use a portable relative POSIX form")

    root_path = Path(root)
    if _has_symlink_component(root_path):
        raise EvidencePathError("the evidence root must not be a symbolic link")
    try:
        root_resolved = root_path.resolve(strict=True)
    except OSError as error:
        raise EvidencePathError("the evidence root does not exist or cannot be read") from error
    if not root_resolved.is_dir():
        raise EvidencePathError("the evidence root must be a directory")

    relative = Path(raw)
    if any(part == ".." for part in relative.parts):
        raise EvidencePathError(f"parent traversal is not allowed: {raw!r}")

    lexical = root_resolved / relative
    current = root_resolved
    for part in relative.parts:
        if part in {"", "."}:
            continue
        current = current / part
        if current.is_symlink():
            raise EvidencePathError(f"symbolic links are not allowed in evidence paths: {raw!r}")

    try:
        resolved = lexical.resolve(strict=True)
    except OSError as error:
        raise EvidencePathError(f"evidence path is missing or unreadable: {raw!r}") from error
    if not resolved.is_relative_to(root_resolved):
        raise EvidencePathError(f"evidence path escapes the root: {raw!r}")

    stored = resolved.relative_to(root_resolved).as_posix()
    if stored in {"", "."}:
        raise EvidencePathError("the evidence root itself cannot be captured; choose a child path")
    return resolved, stored


def _directory_snapshot(path: Path) -> tuple[str, int, int]:
    manifest: list[dict[str, Any]] = []
    casefolded: dict[str, str] = {}

    candidates: list[Path] = []
    pending = [path]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as error:
            relative = directory.relative_to(path).as_posix() or "."
            raise EvidencePathError(
                f"directory inside evidence is unreadable: {relative!r}"
            ) from error

        child_directories: list[Path] = []
        for entry in entries:
            candidate = Path(entry.path)
            relative = candidate.relative_to(path).as_posix()
            try:
                if entry.is_symlink():
                    raise EvidencePathError(
                        f"symbolic links are not allowed inside evidence: {relative!r}"
                    )
                if entry.is_dir(follow_symlinks=False):
                    child_directories.append(candidate)
                elif entry.is_file(follow_symlinks=False):
                    candidates.append(candidate)
                else:
                    raise EvidencePathError(
                        f"unsupported filesystem entry inside evidence: {relative!r}"
                    )
            except OSError as error:
                raise EvidencePathError(
                    f"filesystem entry inside evidence is unreadable: {relative!r}"
                ) from error
        pending.extend(reversed(child_directories))

    candidates.sort(key=lambda item: item.relative_to(path).as_posix())
    for candidate in candidates:
        relative = candidate.relative_to(path).as_posix()
        folded = relative.casefold()
        previous = casefolded.get(folded)
        if previous is not None and previous != relative:
            raise EvidencePathError(
                f"case-insensitive path collision is not portable: {previous!r} and {relative!r}"
            )
        casefolded[folded] = relative
        digest, size = _sha256_file(candidate)
        manifest.append({"path": relative, "sha256": digest, "size": size})

    total_size = sum(entry["size"] for entry in manifest)
    directory_digest = sha256_bytes(canonical_json_bytes({"files": manifest}))
    return directory_digest, total_size, len(manifest)


def capture_path(root: Path, raw: str) -> dict[str, Any]:
    """Capture one file or directory as a portable evidence item."""

    resolved, stored = resolve_evidence_path(root, raw)
    try:
        if resolved.is_file():
            digest, size = _sha256_file(resolved)
            return {
                "path": stored,
                "kind": "file",
                "sha256": digest,
                "size": size,
                "files": 1,
            }
        if resolved.is_dir():
            digest, size, files = _directory_snapshot(resolved)
            return {
                "path": stored,
                "kind": "directory",
                "sha256": digest,
                "size": size,
                "files": files,
            }
    except OSError as error:
        raise EvidencePathError(f"evidence path is unreadable: {stored!r}") from error
    raise EvidencePathError(f"unsupported evidence path type: {raw!r}")


def candidate_output_path(output: Path) -> Path:
    """Resolve a not-yet-created output path without storing it in a receipt."""

    output_path = Path(output)
    parent = output_path.parent.resolve(strict=True)
    return parent / output_path.name


def output_overlaps_evidence(receipt: dict[str, Any], root: Path, output: Path) -> bool:
    """Return whether writing output would immediately make captured evidence stale."""

    candidate = candidate_output_path(output)
    root_resolved = Path(root).resolve(strict=True)
    evidence = receipt["evidence"]
    for group in ("sources", "artifacts", "policies"):
        for item in evidence[group]:
            target = root_resolved / Path(item["path"])
            if item["kind"] == "file" and candidate == target:
                return True
            if item["kind"] == "directory" and candidate.is_relative_to(target):
                return True
    return False


def platform_path_separator() -> str:
    """Expose the current separator for a small portability test."""

    return os.sep
