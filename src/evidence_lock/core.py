"""Receipt creation, review binding, and freshness verification."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence_lock.hashing import (
    EvidencePathError,
    canonical_json_bytes,
    capture_path,
    sha256_bytes,
)

RECEIPT_VERSION = "evidence-lock/receipt/v1"
SCHEMA_URL = (
    "https://raw.githubusercontent.com/eun7661010/evidence-lock/"
    "v0.1.0/src/evidence_lock/schemas/receipt-v1.schema.json"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

VERIFY_EXIT_CODES = {
    "approved": 0,
    "pending": 3,
    "rejected": 4,
    "stale": 5,
    "invalid": 6,
}


class ReceiptError(ValueError):
    """Raised when a receipt cannot be safely created or reviewed."""


@dataclass(frozen=True)
class VerificationResult:
    """A stable, JSON-ready verification result."""

    status: str
    snapshot_id: str | None
    review_id: str | None
    changes: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "approved"

    @property
    def exit_code(self) -> int:
        return VERIFY_EXIT_CODES[self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_version": "evidence-lock/verification/v1",
            "ok": self.ok,
            "status": self.status,
            "exit_code": self.exit_code,
            "snapshot_id": self.snapshot_id,
            "review_id": self.review_id,
            "changes": list(self.changes),
            "errors": list(self.errors),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ReceiptError(f"{field} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReceiptError(f"{field} must be an RFC 3339 timestamp") from error
    if parsed.tzinfo is None:
        raise ReceiptError(f"{field} must include a timezone")
    return value


def _validate_text(value: object, field: str, *, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ReceiptError(f"{field} must be a non-empty string")
    if len(value) > maximum:
        raise ReceiptError(f"{field} must be at most {maximum} characters")
    if CONTROL_PATTERN.search(value):
        raise ReceiptError(f"{field} contains a disallowed control character")
    return value


def _snapshot_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "$schema": receipt["$schema"],
        "receipt_version": receipt["receipt_version"],
        "created_at": receipt["created_at"],
        "evidence": receipt["evidence"],
    }


def _snapshot_id(receipt: Mapping[str, Any]) -> str:
    return f"sha256:{sha256_bytes(canonical_json_bytes(_snapshot_payload(receipt)))}"


def _review_payload(snapshot_id: str, review: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "reviewer": review["reviewer"],
        "reviewer_type": review["reviewer_type"],
        "decision": review["decision"],
        "reviewed_at": review["reviewed_at"],
        "summary": review["summary"],
    }


def _review_id(snapshot_id: str, review: Mapping[str, Any]) -> str:
    return f"sha256:{sha256_bytes(canonical_json_bytes(_review_payload(snapshot_id, review)))}"


def _capture_group(root: Path, paths: Sequence[str], group: str) -> list[dict[str, Any]]:
    if not paths:
        raise ReceiptError(f"at least one {group} path is required")
    try:
        return [capture_path(root, path) for path in paths]
    except EvidencePathError as error:
        raise ReceiptError(str(error)) from error


def create_receipt(
    root: Path,
    *,
    sources: Sequence[str],
    artifacts: Sequence[str],
    policies: Sequence[str],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create an unreviewed receipt from exact file and directory bytes."""

    evidence = {
        "sources": _capture_group(root, sources, "source"),
        "artifacts": _capture_group(root, artifacts, "artifact"),
        "policies": _capture_group(root, policies, "policy"),
    }
    all_paths = [item["path"] for items in evidence.values() for item in items]
    if len(all_paths) != len(set(all_paths)):
        raise ReceiptError("the same evidence path cannot appear in more than one group")

    receipt: dict[str, Any] = {
        "$schema": SCHEMA_URL,
        "receipt_version": RECEIPT_VERSION,
        "created_at": _validate_timestamp(created_at or _now(), "created_at"),
        "snapshot_id": "",
        "evidence": evidence,
        "review": None,
    }
    receipt["snapshot_id"] = _snapshot_id(receipt)
    return receipt


def _validate_item(item: object, group: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ReceiptError(f"every {group} entry must be an object")
    expected = {"path", "kind", "sha256", "size", "files"}
    if set(item) != expected:
        raise ReceiptError(f"every {group} entry must contain exactly {sorted(expected)}")
    path = _validate_text(item["path"], f"{group}.path", maximum=1024)
    if path.startswith("/") or "\\" in path or ".." in Path(path).parts:
        raise ReceiptError(f"{group}.path must be a portable relative POSIX path")
    if re.match(r"^[A-Za-z]:", path):
        raise ReceiptError(f"{group}.path must not contain a drive prefix")
    if item["kind"] not in {"file", "directory"}:
        raise ReceiptError(f"{group}.kind must be file or directory")
    if not isinstance(item["sha256"], str) or not SHA256_PATTERN.fullmatch(item["sha256"]):
        raise ReceiptError(f"{group}.sha256 must be a lowercase SHA-256 digest")
    if not isinstance(item["size"], int) or isinstance(item["size"], bool) or item["size"] < 0:
        raise ReceiptError(f"{group}.size must be a non-negative integer")
    if not isinstance(item["files"], int) or isinstance(item["files"], bool) or item["files"] < 0:
        raise ReceiptError(f"{group}.files must be a non-negative integer")
    if item["kind"] == "file" and item["files"] != 1:
        raise ReceiptError(f"{group}.files must be 1 for a file")
    return item


def _validate_review(review: object, snapshot_id: str) -> dict[str, Any] | None:
    if review is None:
        return None
    if not isinstance(review, dict):
        raise ReceiptError("review must be null or an object")
    expected = {"reviewer", "reviewer_type", "decision", "reviewed_at", "summary", "review_id"}
    if set(review) != expected:
        raise ReceiptError(f"review must contain exactly {sorted(expected)}")
    _validate_text(review["reviewer"], "review.reviewer", maximum=128)
    if review["reviewer_type"] not in {"human", "ai"}:
        raise ReceiptError("review.reviewer_type must be human or ai")
    if review["decision"] not in {"approved", "rejected"}:
        raise ReceiptError("review.decision must be approved or rejected")
    _validate_timestamp(review["reviewed_at"], "review.reviewed_at")
    if review["summary"] is not None:
        _validate_text(review["summary"], "review.summary", maximum=1000, allow_empty=False)
    if not isinstance(review["review_id"], str) or not IDENTIFIER_PATTERN.fullmatch(
        review["review_id"]
    ):
        raise ReceiptError("review.review_id must be a sha256 identifier")
    if review["review_id"] != _review_id(snapshot_id, review):
        raise ReceiptError("review.review_id does not match the review fields")
    return review


def validate_receipt(receipt: object) -> dict[str, Any]:
    """Validate strict v1 receipt structure and internal identifiers."""

    if not isinstance(receipt, dict):
        raise ReceiptError("receipt must be a JSON object")
    expected = {"$schema", "receipt_version", "created_at", "snapshot_id", "evidence", "review"}
    if set(receipt) != expected:
        raise ReceiptError(f"receipt must contain exactly {sorted(expected)}")
    if receipt["$schema"] != SCHEMA_URL:
        raise ReceiptError("unsupported receipt schema URL")
    if receipt["receipt_version"] != RECEIPT_VERSION:
        raise ReceiptError("unsupported receipt version")
    _validate_timestamp(receipt["created_at"], "created_at")
    if not isinstance(receipt["snapshot_id"], str) or not IDENTIFIER_PATTERN.fullmatch(
        receipt["snapshot_id"]
    ):
        raise ReceiptError("snapshot_id must be a sha256 identifier")
    if not isinstance(receipt["evidence"], dict):
        raise ReceiptError("evidence must be an object")
    groups = {"sources", "artifacts", "policies"}
    if set(receipt["evidence"]) != groups:
        raise ReceiptError(f"evidence must contain exactly {sorted(groups)}")
    paths: list[str] = []
    for group in sorted(groups):
        entries = receipt["evidence"][group]
        if not isinstance(entries, list) or not entries:
            raise ReceiptError(f"evidence.{group} must be a non-empty array")
        for entry in entries:
            item = _validate_item(entry, f"evidence.{group}")
            paths.append(item["path"])
    if len(paths) != len(set(paths)):
        raise ReceiptError("evidence paths must be unique across all groups")
    if receipt["snapshot_id"] != _snapshot_id(receipt):
        raise ReceiptError("snapshot_id does not match the receipt fields")
    _validate_review(receipt["review"], receipt["snapshot_id"])
    return receipt


def load_receipt(path: Path) -> dict[str, Any]:
    """Load a receipt as JSON without exposing an absolute path in errors."""

    receipt_path = Path(path)
    try:
        raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReceiptError(f"cannot read valid UTF-8 JSON from {receipt_path.name!r}") from error
    return validate_receipt(raw)


def verify_receipt(receipt: object, root: Path) -> VerificationResult:
    """Verify receipt structure, current evidence bytes, and review state."""

    try:
        validated = validate_receipt(receipt)
    except ReceiptError as error:
        return VerificationResult(
            status="invalid", snapshot_id=None, review_id=None, errors=(str(error),)
        )

    changes: list[str] = []
    for group in ("sources", "artifacts", "policies"):
        for expected in validated["evidence"][group]:
            try:
                current = capture_path(Path(root), expected["path"])
            except EvidencePathError as error:
                changes.append(f"{group}:{expected['path']}: {error}")
                continue
            for field in ("kind", "sha256", "size", "files"):
                if current[field] != expected[field]:
                    changes.append(f"{group}:{expected['path']}: {field} changed")

    review = validated["review"]
    review_id = review["review_id"] if review else None
    if changes:
        return VerificationResult(
            status="stale",
            snapshot_id=validated["snapshot_id"],
            review_id=review_id,
            changes=tuple(changes),
        )
    status = "pending" if review is None else review["decision"]
    return VerificationResult(
        status=status,
        snapshot_id=validated["snapshot_id"],
        review_id=review_id,
    )


def apply_review(
    receipt: object,
    root: Path,
    *,
    reviewer: str,
    reviewer_type: str,
    decision: str,
    summary: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    """Bind a human or AI review decision to a fresh, unreviewed receipt."""

    validated = validate_receipt(receipt)
    if validated["review"] is not None:
        raise ReceiptError(
            "a reviewed receipt is immutable; review the original pending receipt again"
        )
    result = verify_receipt(validated, root)
    if result.status != "pending":
        raise ReceiptError(
            "the receipt is not fresh and pending; create a new snapshot before review"
        )

    reviewer_value = _validate_text(reviewer, "reviewer", maximum=128)
    if reviewer_type not in {"human", "ai"}:
        raise ReceiptError("reviewer_type must be human or ai")
    if decision not in {"approved", "rejected"}:
        raise ReceiptError("decision must be approved or rejected")
    if summary is not None:
        _validate_text(summary, "summary", maximum=1000)

    review: dict[str, Any] = {
        "reviewer": reviewer_value,
        "reviewer_type": reviewer_type,
        "decision": decision,
        "reviewed_at": _validate_timestamp(reviewed_at or _now(), "reviewed_at"),
        "summary": summary,
        "review_id": "",
    }
    review["review_id"] = _review_id(validated["snapshot_id"], review)
    reviewed = dict(validated)
    reviewed["review"] = review
    return reviewed
