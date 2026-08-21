"""Command-line interface for portable review receipts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any

from evidence_lock import __version__
from evidence_lock.core import (
    ReceiptError,
    apply_review,
    create_receipt,
    load_receipt,
    verify_receipt,
)
from evidence_lock.hashing import output_overlaps_evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidence-lock",
        description=(
            "Bind a review decision to exact source, artifact, and policy hashes, then detect "
            "stale approvals."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create an unreviewed evidence snapshot")
    create.add_argument("--root", type=Path, default=Path("."), help="evidence root (default: .)")
    create.add_argument("--source", action="append", required=True, help="relative source path")
    create.add_argument("--artifact", action="append", required=True, help="relative artifact path")
    create.add_argument("--policy", action="append", required=True, help="relative policy path")
    create.add_argument("--output", type=Path, required=True, help="new receipt JSON path")
    create.add_argument("--format", choices=("human", "json"), default="human")

    review = subparsers.add_parser("review", help="bind a decision to a fresh pending receipt")
    review.add_argument("receipt", type=Path, help="pending receipt JSON")
    review.add_argument("--root", type=Path, default=Path("."), help="evidence root (default: .)")
    review.add_argument("--reviewer", required=True, help="reviewer label; avoid personal data")
    review.add_argument("--reviewer-type", choices=("human", "ai"), required=True)
    review.add_argument("--decision", choices=("approved", "rejected"), required=True)
    review.add_argument("--summary", help="short non-sensitive review summary")
    review.add_argument("--output", type=Path, required=True, help="new reviewed receipt JSON path")
    review.add_argument("--format", choices=("human", "json"), default="human")

    verify = subparsers.add_parser("verify", help="verify receipt integrity and freshness")
    verify.add_argument("receipt", type=Path, help="receipt JSON")
    verify.add_argument("--root", type=Path, default=Path("."), help="evidence root (default: .)")
    verify.add_argument("--format", choices=("human", "json"), default="human")

    schema = subparsers.add_parser("schema", help="print or save the bundled receipt schema")
    schema.add_argument("--output", type=Path, help="new output path; stdout when omitted")
    return parser


def _write_json(path: Path, value: object) -> None:
    output = Path(path)
    if not output.parent.exists():
        raise ReceiptError(f"output directory does not exist: {output.parent.name!r}")
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError as error:
        raise ReceiptError(f"refusing to overwrite existing output: {output.name!r}") from error
    except OSError as error:
        raise ReceiptError(f"cannot write output: {output.name!r}") from error


def _require_output_parent(path: Path) -> None:
    if not Path(path).parent.exists():
        raise ReceiptError(f"output directory does not exist: {Path(path).parent.name!r}")


def _emit(value: MappingLike, output_format: str, human_lines: Sequence[str]) -> None:
    if output_format == "json":
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    else:
        print("\n".join(human_lines))


MappingLike = dict[str, Any]


def _create(args: argparse.Namespace) -> int:
    receipt = create_receipt(
        args.root,
        sources=args.source,
        artifacts=args.artifact,
        policies=args.policy,
    )
    _require_output_parent(args.output)
    if output_overlaps_evidence(receipt, args.root, args.output):
        raise ReceiptError(
            "output would be written inside captured evidence and become stale immediately"
        )
    _write_json(args.output, receipt)
    result: MappingLike = {
        "result_version": "evidence-lock/command/v1",
        "ok": True,
        "command": "create",
        "status": "pending",
        "output_name": args.output.name,
        "snapshot_id": receipt["snapshot_id"],
    }
    _emit(
        result,
        args.format,
        (
            f"Created pending receipt: {args.output.name}",
            f"Snapshot: {receipt['snapshot_id']}",
        ),
    )
    return 0


def _review(args: argparse.Namespace) -> int:
    pending = load_receipt(args.receipt)
    reviewed = apply_review(
        pending,
        args.root,
        reviewer=args.reviewer,
        reviewer_type=args.reviewer_type,
        decision=args.decision,
        summary=args.summary,
    )
    _require_output_parent(args.output)
    if output_overlaps_evidence(reviewed, args.root, args.output):
        raise ReceiptError(
            "output would be written inside captured evidence and become stale immediately"
        )
    _write_json(args.output, reviewed)
    review = reviewed["review"]
    result: MappingLike = {
        "result_version": "evidence-lock/command/v1",
        "ok": True,
        "command": "review",
        "status": review["decision"],
        "output_name": args.output.name,
        "snapshot_id": reviewed["snapshot_id"],
        "review_id": review["review_id"],
    }
    _emit(
        result,
        args.format,
        (
            f"Recorded {review['decision']} review: {args.output.name}",
            f"Review: {review['review_id']}",
        ),
    )
    return 0


def _verify(args: argparse.Namespace) -> int:
    try:
        receipt = load_receipt(args.receipt)
    except ReceiptError as receipt_error:
        status = "invalid"
        exit_code = 6
        snapshot_id = None
        review_id = None
        changes: list[str] = []
        errors = [str(receipt_error)]
    else:
        verification = verify_receipt(receipt, args.root)
        status = verification.status
        exit_code = verification.exit_code
        snapshot_id = verification.snapshot_id
        review_id = verification.review_id
        changes = list(verification.changes)
        errors = list(verification.errors)

    result: MappingLike = {
        "result_version": "evidence-lock/verification/v1",
        "ok": status == "approved",
        "status": status,
        "exit_code": exit_code,
        "snapshot_id": snapshot_id,
        "review_id": review_id,
        "changes": changes,
        "errors": errors,
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"{status.upper()}: {args.receipt.name}")
        for change in changes:
            print(f"- {change}")
        for message in errors:
            print(f"- {message}")
    return exit_code


def _schema(args: argparse.Namespace) -> int:
    resource = files("evidence_lock.schemas").joinpath("receipt-v1.schema.json")
    content = resource.read_text(encoding="utf-8")
    if args.output is None:
        print(content, end="" if content.endswith("\n") else "\n")
    else:
        try:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
        except FileExistsError as error:
            raise ReceiptError(
                f"refusing to overwrite existing output: {args.output.name!r}"
            ) from error
        except OSError as error:
            raise ReceiptError(f"cannot write output: {args.output.name!r}") from error
        print(f"Wrote receipt schema: {args.output.name}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            return _create(args)
        if args.command == "review":
            return _review(args)
        if args.command == "verify":
            return _verify(args)
        if args.command == "schema":
            return _schema(args)
    except ReceiptError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    parser.error("unknown command")
    return 2
