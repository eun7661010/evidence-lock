"""Regenerate deterministic receipts for the public synthetic example."""

from __future__ import annotations

import json
from pathlib import Path

from evidence_lock import apply_review, create_receipt

ROOT = Path(__file__).resolve().parents[1] / "examples" / "synthetic-project"
RECEIPTS = ROOT / "receipts"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    pending = create_receipt(
        ROOT,
        sources=["source/draft.txt"],
        artifacts=["artifact/report.txt"],
        policies=["policy/review-policy.json"],
        created_at="2026-01-01T00:00:00Z",
    )
    approved = apply_review(
        pending,
        ROOT,
        reviewer="reviewer-01",
        reviewer_type="human",
        decision="approved",
        summary="The synthetic report follows the synthetic review policy.",
        reviewed_at="2026-01-01T00:05:00Z",
    )
    _write(RECEIPTS / "pending.json", pending)
    _write(RECEIPTS / "approved.json", approved)


if __name__ == "__main__":
    main()
