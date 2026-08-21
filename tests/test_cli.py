from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence_lock.cli import main


def create_args(output: str = "pending.json", output_format: str = "human") -> list[str]:
    return [
        "create",
        "--source",
        "source/draft.txt",
        "--artifact",
        "artifact/report.txt",
        "--policy",
        "policy/review.json",
        "--output",
        output,
        "--format",
        output_format,
    ]


def test_cli_create_review_verify_json(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args(output_format="json")) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["status"] == "pending"

    assert (
        main(
            [
                "review",
                "pending.json",
                "--reviewer",
                "reviewer-01",
                "--reviewer-type",
                "human",
                "--decision",
                "approved",
                "--output",
                "approved.json",
                "--format",
                "json",
            ]
        )
        == 0
    )
    reviewed = json.loads(capsys.readouterr().out)
    assert reviewed["status"] == "approved"

    assert main(["verify", "approved.json", "--format", "json"]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["ok"] is True
    assert verified["status"] == "approved"


def test_cli_verify_pending_exit_code(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args()) == 0
    capsys.readouterr()
    assert main(["verify", "pending.json"]) == 3
    assert "PENDING" in capsys.readouterr().out


def test_cli_rejected_exit_code(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args()) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "review",
                "pending.json",
                "--reviewer",
                "synthetic-agent",
                "--reviewer-type",
                "ai",
                "--decision",
                "rejected",
                "--output",
                "rejected.json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["verify", "rejected.json"]) == 4


def test_cli_stale_exit_code(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args()) == 0
    capsys.readouterr()
    (project / "source" / "draft.txt").write_text("changed", encoding="utf-8")
    assert main(["verify", "pending.json"]) == 5
    assert "STALE" in capsys.readouterr().out


def test_cli_invalid_json_exit_code(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    Path("bad.json").write_text("{", encoding="utf-8")
    assert main(["verify", "bad.json", "--format", "json"]) == 6
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "invalid"


def test_cli_refuses_overwrite(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args()) == 0
    capsys.readouterr()
    assert main(create_args()) == 1
    assert "refusing to overwrite" in capsys.readouterr().err


def test_cli_refuses_output_inside_evidence(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    args = create_args("source/pending.json")
    args[2] = "source"
    assert main(args) == 1
    assert "inside captured evidence" in capsys.readouterr().err
    assert not (project / "source" / "pending.json").exists()


def test_cli_receipt_contains_no_absolute_root(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args()) == 0
    capsys.readouterr()
    raw = Path("pending.json").read_text(encoding="utf-8")
    assert str(project) not in raw
    assert "source/draft.txt" in raw


def test_cli_schema_stdout_and_file(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(["schema"]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "evidence-lock receipt v1"
    assert main(["schema", "--output", "receipt.schema.json"]) == 0
    capsys.readouterr()
    assert json.loads(Path("receipt.schema.json").read_text(encoding="utf-8"))["title"]
    assert main(["schema", "--output", "receipt.schema.json"]) == 1


def test_cli_review_refuses_stale_receipt(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args()) == 0
    capsys.readouterr()
    (project / "policy" / "review.json").write_text("{}", encoding="utf-8")
    code = main(
        [
            "review",
            "pending.json",
            "--reviewer",
            "reviewer-01",
            "--reviewer-type",
            "human",
            "--decision",
            "approved",
            "--output",
            "approved.json",
        ]
    )
    assert code == 1
    assert "not fresh" in capsys.readouterr().err


def test_cli_output_directory_must_exist(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(project)
    assert main(create_args("missing/pending.json")) == 1
    assert "output directory" in capsys.readouterr().err
