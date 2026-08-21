from __future__ import annotations

import os
from pathlib import Path

import pytest

import evidence_lock.hashing as hashing
from evidence_lock.core import create_receipt
from evidence_lock.hashing import (
    EvidencePathError,
    canonical_json_bytes,
    capture_path,
    output_overlaps_evidence,
    platform_path_separator,
)


def test_canonical_json_is_order_independent() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


def test_capture_file_uses_relative_path(project: Path) -> None:
    item = capture_path(project, "source/draft.txt")
    assert item["path"] == "source/draft.txt"
    assert item["kind"] == "file"
    assert item["files"] == 1
    assert item["size"] == len("synthetic draft\n")
    assert len(item["sha256"]) == 64


def test_directory_digest_changes_with_content(project: Path) -> None:
    before = capture_path(project, "source")
    (project / "source" / "second.txt").write_text("second\n", encoding="utf-8")
    after = capture_path(project, "source")
    assert before["sha256"] != after["sha256"]
    assert after["files"] == 2


def test_directory_digest_ignores_mtime(project: Path) -> None:
    before = capture_path(project, "source")
    target = project / "source" / "draft.txt"
    os.utime(target, (target.stat().st_atime + 10, target.stat().st_mtime + 10))
    after = capture_path(project, "source")
    assert before == after


@pytest.mark.parametrize("raw", ["../outside.txt", "/tmp/outside.txt", "C:\\Private\\x.txt"])
def test_rejects_nonportable_paths(project: Path, raw: str) -> None:
    with pytest.raises(EvidencePathError):
        capture_path(project, raw)


def test_absolute_path_error_does_not_echo_private_path(project: Path) -> None:
    private_path = "D:\\synthetic-private\\secret.txt"
    with pytest.raises(EvidencePathError) as caught:
        capture_path(project, private_path)
    assert private_path not in str(caught.value)


def test_rejects_missing_path(project: Path) -> None:
    with pytest.raises(EvidencePathError, match="missing"):
        capture_path(project, "missing.txt")


def test_rejects_root_itself(project: Path) -> None:
    with pytest.raises(EvidencePathError, match="root itself"):
        capture_path(project, ".")


@pytest.mark.parametrize("raw", ["", "bad\x00name"])
def test_rejects_empty_or_nul_path(project: Path, raw: str) -> None:
    with pytest.raises(EvidencePathError, match="non-empty"):
        capture_path(project, raw)


def test_rejects_missing_root(project: Path) -> None:
    with pytest.raises(EvidencePathError, match="root does not exist"):
        capture_path(project / "missing-root", "file.txt")


def test_rejects_file_as_root(project: Path) -> None:
    with pytest.raises(EvidencePathError, match="must be a directory"):
        capture_path(project / "source" / "draft.txt", "child.txt")


def test_read_error_uses_only_relative_path(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_read(path: Path) -> tuple[str, int]:
        raise PermissionError(path)

    monkeypatch.setattr(hashing, "_sha256_file", fail_read)
    with pytest.raises(EvidencePathError, match=r"source/draft\.txt") as caught:
        capture_path(project, "source/draft.txt")
    assert str(project) not in str(caught.value)


def test_rejects_symlink(project: Path) -> None:
    link = project / "source-link"
    try:
        link.symlink_to(project / "source", target_is_directory=True)
    except OSError:
        pytest.skip("symbolic link creation is unavailable")
    with pytest.raises(EvidencePathError, match="symbolic links"):
        capture_path(project, "source-link")


def test_rejects_symlink_in_root_path(project: Path) -> None:
    root_link = project.parent / f"{project.name}-root-link"
    try:
        root_link.symlink_to(project, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic link creation is unavailable")
    with pytest.raises(EvidencePathError, match="root must not"):
        capture_path(root_link, "source/draft.txt")


@pytest.mark.skipif(os.name == "nt", reason="Windows cannot create a portable case collision")
def test_rejects_casefold_collision(project: Path) -> None:
    (project / "source" / "A.txt").write_text("A", encoding="utf-8")
    (project / "source" / "a.txt").write_text("a", encoding="utf-8")
    with pytest.raises(EvidencePathError, match="collision"):
        capture_path(project, "source")


def test_output_overlap_detects_file_and_directory(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = create_receipt(
        project,
        sources=["source"],
        artifacts=["artifact/report.txt"],
        policies=["policy/review.json"],
        created_at="2026-01-01T00:00:00Z",
    )
    monkeypatch.chdir(project)
    assert output_overlaps_evidence(receipt, project, Path("source/receipt.json"))
    assert output_overlaps_evidence(receipt, project, Path("artifact/report.txt"))
    assert not output_overlaps_evidence(receipt, project, Path("receipt.json"))


def test_platform_separator_is_exposed() -> None:
    assert platform_path_separator() == os.sep
