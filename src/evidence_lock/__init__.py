"""Bind review decisions to exact source, artifact, and policy bytes."""

from evidence_lock.core import (
    ReceiptError,
    VerificationResult,
    apply_review,
    create_receipt,
    load_receipt,
    verify_receipt,
)

__all__ = [
    "ReceiptError",
    "VerificationResult",
    "apply_review",
    "create_receipt",
    "load_receipt",
    "verify_receipt",
]

__version__ = "0.1.0"
