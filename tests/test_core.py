from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from evidence_lock.core import (
    ReceiptError,
    apply_review,
    create_receipt,
    load_receipt,
    validate_receipt,
    verify_receipt,
)


def make_receipt(project: Path) -> dict[str, object]:
    return create_receipt(
        project,
        sources=["source/draft.txt"],
        artifacts=["artifact/report.txt"],
        policies=["policy/review.json"],
        created_at="2026-01-01T00:00:00Z",
    )


def test_created_receipt_is_pending_and_path_portable(project: Path) -> None:
    receipt = make_receipt(project)
    result = verify_receipt(receipt, project)
    serialized = json.dumps(receipt)
    assert result.status == "pending"
    assert result.exit_code == 3
    assert not result.ok
    assert str(project) not in serialized
    assert receipt["review"] is None


def test_receipt_matches_bundled_json_schema(project: Path) -> None:
    receipt = make_receipt(project)
    schema_path = (
        Path(__file__).parents[1] / "src" / "evidence_lock" / "schemas" / "receipt-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(receipt)


def test_human_approval_is_fresh(project: Path) -> None:
    approved = apply_review(
        make_receipt(project),
        project,
        reviewer="reviewer-01",
        reviewer_type="human",
        decision="approved",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    result = verify_receipt(approved, project)
    assert result.status == "approved"
    assert result.exit_code == 0
    assert result.ok
    assert result.review_id == approved["review"]["review_id"]  # type: ignore[index]


def test_ai_rejection_is_fresh_but_not_approved(project: Path) -> None:
    rejected = apply_review(
        make_receipt(project),
        project,
        reviewer="synthetic-review-agent",
        reviewer_type="ai",
        decision="rejected",
        summary="The synthetic policy was not satisfied.",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    result = verify_receipt(rejected, project)
    assert result.status == "rejected"
    assert result.exit_code == 4
    assert not result.ok


@pytest.mark.parametrize(
    ("relative", "replacement", "prefix"),
    [
        ("source/draft.txt", "changed source\n", "sources:"),
        ("artifact/report.txt", "changed artifact\n", "artifacts:"),
        ("policy/review.json", "{}\n", "policies:"),
    ],
)
def test_any_evidence_change_makes_approval_stale(
    project: Path, relative: str, replacement: str, prefix: str
) -> None:
    approved = apply_review(
        make_receipt(project),
        project,
        reviewer="reviewer-01",
        reviewer_type="human",
        decision="approved",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    (project / relative).write_text(replacement, encoding="utf-8")
    result = verify_receipt(approved, project)
    assert result.status == "stale"
    assert result.exit_code == 5
    assert any(change.startswith(prefix) for change in result.changes)


def test_deleted_evidence_is_stale(project: Path) -> None:
    receipt = make_receipt(project)
    (project / "source" / "draft.txt").unlink()
    result = verify_receipt(receipt, project)
    assert result.status == "stale"
    assert "missing" in result.changes[0]


def test_tampered_snapshot_id_is_invalid(project: Path) -> None:
    receipt = make_receipt(project)
    receipt["created_at"] = "2026-01-02T00:00:00Z"
    result = verify_receipt(receipt, project)
    assert result.status == "invalid"
    assert result.exit_code == 6
    assert "snapshot_id" in result.errors[0]


def test_tampered_review_id_is_invalid(project: Path) -> None:
    receipt = apply_review(
        make_receipt(project),
        project,
        reviewer="reviewer-01",
        reviewer_type="human",
        decision="approved",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    receipt["review"]["decision"] = "rejected"  # type: ignore[index]
    result = verify_receipt(receipt, project)
    assert result.status == "invalid"
    assert "review_id" in result.errors[0]


def test_unknown_field_is_invalid(project: Path) -> None:
    receipt = make_receipt(project)
    receipt["unexpected"] = True
    assert verify_receipt(receipt, project).status == "invalid"


def test_reviewed_receipt_is_immutable(project: Path) -> None:
    pending = make_receipt(project)
    reviewed = apply_review(
        pending,
        project,
        reviewer="reviewer-01",
        reviewer_type="human",
        decision="approved",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    with pytest.raises(ReceiptError, match="immutable"):
        apply_review(
            reviewed,
            project,
            reviewer="reviewer-02",
            reviewer_type="human",
            decision="rejected",
        )


def test_stale_pending_receipt_cannot_be_reviewed(project: Path) -> None:
    pending = make_receipt(project)
    (project / "artifact" / "report.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ReceiptError, match="not fresh"):
        apply_review(
            pending,
            project,
            reviewer="reviewer-01",
            reviewer_type="human",
            decision="approved",
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"reviewer": "", "reviewer_type": "human", "decision": "approved"}, "reviewer"),
        ({"reviewer": "r", "reviewer_type": "robot", "decision": "approved"}, "reviewer_type"),
        ({"reviewer": "r", "reviewer_type": "human", "decision": "maybe"}, "decision"),
        (
            {"reviewer": "r", "reviewer_type": "human", "decision": "approved", "summary": "x\x00"},
            "control",
        ),
    ],
)
def test_review_fields_are_strict(project: Path, kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ReceiptError, match=message):
        apply_review(make_receipt(project), project, **kwargs)


def test_duplicate_evidence_path_is_rejected(project: Path) -> None:
    with pytest.raises(ReceiptError, match="same evidence path"):
        create_receipt(
            project,
            sources=["source/draft.txt"],
            artifacts=["source/draft.txt"],
            policies=["policy/review.json"],
        )


def test_each_evidence_group_is_required(project: Path) -> None:
    with pytest.raises(ReceiptError, match="source"):
        create_receipt(
            project,
            sources=[],
            artifacts=["artifact/report.txt"],
            policies=["policy/review.json"],
        )


def test_timestamp_requires_timezone(project: Path) -> None:
    with pytest.raises(ReceiptError, match="timezone"):
        create_receipt(
            project,
            sources=["source/draft.txt"],
            artifacts=["artifact/report.txt"],
            policies=["policy/review.json"],
            created_at="2026-01-01T00:00:00",
        )


def test_directory_evidence_becomes_stale(project: Path) -> None:
    receipt = create_receipt(
        project,
        sources=["source"],
        artifacts=["artifact"],
        policies=["policy"],
        created_at="2026-01-01T00:00:00Z",
    )
    (project / "source" / "new.txt").write_text("new", encoding="utf-8")
    result = verify_receipt(receipt, project)
    assert result.status == "stale"
    assert any("files changed" in change for change in result.changes)


def test_load_receipt_round_trip(project: Path) -> None:
    receipt = make_receipt(project)
    path = project / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert load_receipt(path) == receipt


def test_load_receipt_rejects_bad_json(project: Path) -> None:
    path = project / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ReceiptError, match="valid UTF-8 JSON"):
        load_receipt(path)


def test_load_receipt_rejects_duplicate_json_keys(project: Path) -> None:
    receipt = make_receipt(project)
    raw = '{"snapshot_id":"sha256:' + ("0" * 64) + '",' + json.dumps(receipt)[1:]
    path = project / "duplicate.json"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(ReceiptError, match="Duplicate JSON key"):
        load_receipt(path)


def test_load_receipt_rejects_lone_surrogate_as_invalid_json(project: Path) -> None:
    receipt = make_receipt(project)
    raw = json.dumps(receipt).replace("source/draft.txt", r"\ud800")
    path = project / "surrogate.json"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(ReceiptError, match="Unicode"):
        load_receipt(path)


def test_structural_type_tampering_is_invalid(project: Path) -> None:
    receipt = copy.deepcopy(make_receipt(project))
    receipt["evidence"]["sources"][0]["size"] = True  # type: ignore[index]
    assert verify_receipt(receipt, project).status == "invalid"


def test_verification_result_serializes(project: Path) -> None:
    result = verify_receipt(make_receipt(project), project).to_dict()
    assert result["result_version"] == "evidence-lock/verification/v1"
    assert result["status"] == "pending"
    assert result["changes"] == []


def test_validate_receipt_returns_same_object(project: Path) -> None:
    receipt = make_receipt(project)
    assert validate_receipt(receipt) is receipt


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda receipt: receipt.update({"$schema": "https://example.invalid/schema"}),
            "schema URL",
        ),
        (lambda receipt: receipt.update({"receipt_version": "future"}), "version"),
        (lambda receipt: receipt.update({"snapshot_id": "not-a-digest"}), "snapshot_id"),
        (lambda receipt: receipt.update({"evidence": []}), "evidence must be"),
        (lambda receipt: receipt["evidence"].pop("sources"), "exactly"),
        (lambda receipt: receipt["evidence"].update({"sources": []}), "non-empty"),
        (lambda receipt: receipt["evidence"]["sources"].__setitem__(0, "bad"), "entry"),
        (
            lambda receipt: receipt["evidence"]["sources"][0].pop("size"),
            "contain exactly",
        ),
        (
            lambda receipt: receipt["evidence"]["sources"][0].update({"path": "bad\\path"}),
            "portable",
        ),
        (
            lambda receipt: receipt["evidence"]["sources"][0].update({"path": "C:relative"}),
            "drive prefix",
        ),
        (
            lambda receipt: receipt["evidence"]["sources"][0].update({"kind": "device"}),
            "kind",
        ),
        (
            lambda receipt: receipt["evidence"]["sources"][0].update({"sha256": "ABC"}),
            "lowercase",
        ),
        (lambda receipt: receipt["evidence"]["sources"][0].update({"size": -1}), "size"),
        (lambda receipt: receipt["evidence"]["sources"][0].update({"files": -1}), "files"),
        (lambda receipt: receipt["evidence"]["sources"][0].update({"files": 2}), "must be 1"),
    ],
)
def test_receipt_structure_rejects_invalid_fields(
    project: Path, mutation: object, message: str
) -> None:
    receipt = make_receipt(project)
    mutation(receipt)  # type: ignore[operator]
    with pytest.raises(ReceiptError, match=message):
        validate_receipt(receipt)


def test_receipt_must_be_an_object() -> None:
    with pytest.raises(ReceiptError, match="JSON object"):
        validate_receipt([])


@pytest.mark.parametrize("timestamp", [None, "not-a-time"])
def test_created_timestamp_must_be_rfc3339(project: Path, timestamp: object) -> None:
    receipt = make_receipt(project)
    receipt["created_at"] = timestamp
    with pytest.raises(ReceiptError, match="RFC 3339"):
        validate_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("reviewer", "x" * 129, "at most"),
        ("reviewer_type", "robot", "reviewer_type"),
        ("decision", "maybe", "decision"),
        ("reviewed_at", "not-a-time", "RFC 3339"),
        ("summary", "", "non-empty"),
        ("review_id", "bad", "sha256 identifier"),
    ],
)
def test_review_structure_rejects_invalid_fields(
    project: Path, field: str, value: object, message: str
) -> None:
    receipt = apply_review(
        make_receipt(project),
        project,
        reviewer="reviewer-01",
        reviewer_type="human",
        decision="approved",
        summary="synthetic summary",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    receipt["review"][field] = value  # type: ignore[index]
    with pytest.raises(ReceiptError, match=message):
        validate_receipt(receipt)


def test_review_must_be_null_or_object(project: Path) -> None:
    receipt = make_receipt(project)
    receipt["review"] = []
    with pytest.raises(ReceiptError, match="null or an object"):
        validate_receipt(receipt)


def test_review_requires_exact_fields(project: Path) -> None:
    receipt = apply_review(
        make_receipt(project),
        project,
        reviewer="reviewer-01",
        reviewer_type="human",
        decision="approved",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    receipt["review"].pop("summary")  # type: ignore[union-attr]
    with pytest.raises(ReceiptError, match="contain exactly"):
        validate_receipt(receipt)


def test_duplicate_paths_in_loaded_receipt_are_invalid(project: Path) -> None:
    receipt = make_receipt(project)
    receipt["evidence"]["artifacts"][0]["path"] = "source/draft.txt"  # type: ignore[index]
    with pytest.raises(ReceiptError, match="unique"):
        validate_receipt(receipt)


def test_ancestor_and_descendant_evidence_paths_cannot_overlap(project: Path) -> None:
    with pytest.raises(ReceiptError, match="overlap"):
        create_receipt(
            project,
            sources=["source"],
            artifacts=["source/draft.txt"],
            policies=["policy/review.json"],
        )


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-01-01 00:00:00+00:00",
        "20260101T000000+00:00",
        "2026-W01-4T00:00:00+00:00",
        "2026-01-01T00:00:00+00:00:30",
    ],
)
def test_create_rejects_non_rfc3339_timestamps(project: Path, timestamp: str) -> None:
    with pytest.raises(ReceiptError, match="RFC 3339"):
        create_receipt(
            project,
            sources=["source/draft.txt"],
            artifacts=["artifact/report.txt"],
            policies=["policy/review.json"],
            created_at=timestamp,
        )
