# CLI and Python library reference

## Install

```bash
python -m pip install .
evidence-lock --version
evidence-lock --help
```

The runtime has no third-party dependency. Development tools are available with `python -m pip install -e ".[dev]"`.

## `create`

```text
evidence-lock create
  [--root ROOT]
  --source PATH [--source PATH ...]
  --artifact PATH [--artifact PATH ...]
  --policy PATH [--policy PATH ...]
  --output NEW.json
  [--format human|json]
```

Every evidence path is interpreted relative to `ROOT`, which defaults to the current directory. The output path is interpreted by the shell in the usual way and may be outside the root. Its parent directory must already exist.

`create` validates all paths and computes all evidence before writing. It returns `0` on success and `1` for a safe input or output error. It refuses existing outputs.

Example with multiple sources:

```bash
evidence-lock create \
  --root review-packet \
  --source source/request.json \
  --source source/context.txt \
  --artifact output/result.json \
  --policy policy/rules.json \
  --output pending.json \
  --format json
```

## `review`

```text
evidence-lock review PENDING.json
  [--root ROOT]
  --reviewer LABEL
  --reviewer-type human|ai
  --decision approved|rejected
  [--summary TEXT]
  --output NEW.json
  [--format human|json]
```

The command validates the pending receipt, recomputes current evidence, and stops if the snapshot is stale or already reviewed. It then binds all review fields to the snapshot and writes a new file.

`LABEL` is an unauthenticated label. Prefer a non-personal identifier such as `reviewer-01` or `synthetic-review-agent`. The optional summary is plaintext and limited to 1,000 characters. Neither field is redacted.

## `verify`

```text
evidence-lock verify RECEIPT.json [--root ROOT] [--format human|json]
```

Human output names the state and changed relative paths. JSON output follows `evidence-lock/verification/v1`:

```json
{
  "result_version": "evidence-lock/verification/v1",
  "ok": false,
  "status": "stale",
  "exit_code": 5,
  "snapshot_id": "sha256:…",
  "review_id": "sha256:…",
  "changes": ["artifacts:output/result.json: sha256 changed"],
  "errors": []
}
```

Only fresh approval returns `ok: true` and exit code `0`. See the README state table for every code.

## `schema`

```bash
evidence-lock schema
evidence-lock schema --output receipt-v1.schema.json
```

The command exposes the same Draft 2020-12 schema bundled in the installed wheel. It refuses to overwrite an existing schema file.

## Python API

```python
from pathlib import Path

from evidence_lock import apply_review, create_receipt, verify_receipt

root = Path("review-packet")
pending = create_receipt(
    root,
    sources=["source/request.json"],
    artifacts=["output/result.json"],
    policies=["policy/rules.json"],
)

approved = apply_review(
    pending,
    root,
    reviewer="reviewer-01",
    reviewer_type="human",
    decision="approved",
    summary="The synthetic packet satisfies the review rules.",
)

result = verify_receipt(approved, root)
assert result.status == "approved"
assert result.ok
assert result.exit_code == 0
```

### `create_receipt`

```python
create_receipt(
    root: Path,
    *,
    sources: Sequence[str],
    artifacts: Sequence[str],
    policies: Sequence[str],
    created_at: str | None = None,
) -> dict[str, Any]
```

`created_at` exists for deterministic tests and migration tools. Ordinary callers should omit it so the library records the current UTC time.

### `apply_review`

```python
apply_review(
    receipt: object,
    root: Path,
    *,
    reviewer: str,
    reviewer_type: str,
    decision: str,
    summary: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]
```

The function does not mutate the input receipt. `reviewed_at` is intended for deterministic tests and controlled import tools.

### `verify_receipt`

```python
verify_receipt(receipt: object, root: Path) -> VerificationResult
```

`VerificationResult` exposes `status`, `ok`, `exit_code`, `snapshot_id`, `review_id`, `changes`, `errors`, and `to_dict()`.

### `load_receipt`

```python
load_receipt(path: Path) -> dict[str, Any]
```

This function parses UTF-8 JSON and applies strict structural and identifier validation. Safe creation and review errors raise `ReceiptError`.

## CI example

```yaml
- name: Require a fresh approved review receipt
  run: evidence-lock verify release-review.json --root release-packet --format json
```

Do not use `continue-on-error` for the gate. A pending, rejected, stale, or invalid receipt intentionally returns non-zero.
