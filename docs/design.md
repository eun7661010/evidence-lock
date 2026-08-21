# Design and receipt semantics

## Design goal

`evidence-lock` preserves the answer to a small workflow question: which exact source, artifact, and policy bytes did a recorded reviewer approve or reject, and do those bytes still exist now?

The format is intentionally local and non-cryptographic. A receipt can be inspected without special software, verified without a network connection, and moved to another operating system without preserving the original absolute root.

## Receipt layers

A v1 receipt has two binding layers.

### Snapshot layer

The snapshot ID is SHA-256 over canonical JSON containing:

- the schema URL;
- `receipt_version`;
- `created_at`;
- all evidence items in `sources`, `artifacts`, and `policies`.

Canonical JSON sorts object keys, emits UTF-8, keeps array order, and removes insignificant whitespace. Changing a path, evidence role, hash, byte count, file count, creation time, schema URL, or version changes the snapshot ID.

### Review layer

The review ID is SHA-256 over canonical JSON containing:

- the snapshot ID;
- reviewer label and `human` or `ai` type;
- `approved` or `rejected` decision;
- review time;
- optional summary.

Changing any review field without recomputing the ID makes the receipt invalid. Recomputing the ID is possible for anyone because it is an unkeyed hash. The ID detects accidental edits and inconsistent packets; it does not authenticate the reviewer.

## Evidence items

Every item records:

| Field | Meaning |
| --- | --- |
| `path` | Relative POSIX path below the caller-supplied root |
| `kind` | `file` or `directory` |
| `sha256` | File content hash or canonical directory-manifest hash |
| `size` | File bytes or the sum of regular-file bytes in a directory |
| `files` | `1` for a file; regular-file count for a directory |

The three roles are semantic, not merely labels. Keeping source, output artifact, and review policy separate lets a human or CI report which part of the review basis changed.

All three lists must be non-empty. Paths must be unique across the lists so the same bytes cannot be presented as two different roles in one receipt.

## Directory snapshots

For a directory, the engine walks every regular file recursively and builds an in-memory manifest of:

```json
{"path":"relative/name.txt","sha256":"…","size":123}
```

Entries are sorted by their POSIX relative path. The directory digest is SHA-256 over canonical JSON containing that ordered manifest. The manifest itself is not stored in the receipt, which keeps the public packet small and avoids exposing every nested name. Verification reports the top-level captured directory that changed. Directory traversal is fail-closed: an unreadable subtree or entry aborts capture instead of producing a partial manifest.

The snapshot ignores empty directories, timestamps, permission bits, ownership, extended attributes, and platform-specific metadata. It rejects symbolic links, non-regular special files, and file names that collide after Unicode case folding.

## State machine

`create` produces a `pending` receipt. `review` accepts only a structurally valid, fresh, pending receipt and writes a separate output file. It never modifies the pending receipt in place. To record a new decision, review the original pending receipt again and write another reviewed receipt.

`verify` applies checks in this order:

1. Parse UTF-8 JSON and reject duplicate object keys.
2. Enforce the exact v1 object shape and field types.
3. Recompute the snapshot ID and, when present, review ID.
4. Resolve each stored relative path below the supplied root.
5. Recompute file and directory evidence.
6. Return `stale` when current evidence differs.
7. Otherwise return `pending`, `approved`, or `rejected` from the recorded review state.

Structural inconsistency is `invalid`; a valid receipt whose external evidence changed is `stale`. This distinction is useful in CI because the remedies differ: replace or investigate an invalid receipt, but create and review a new snapshot after an intentional file change.

## Path portability

The root is operational context and is never serialized. Stored paths use `/` regardless of the current platform. Inputs with an absolute POSIX path, Windows drive or UNC path, backslash, NUL byte, control whitespace, or parent traversal are rejected.

Each recorded evidence path must be unique and non-overlapping. For example, recording `source` and `source/draft.txt` in separate roles is rejected because the same bytes would otherwise have two ambiguous roles in one snapshot.

The implementation rejects symbolic links in the root path and captured tree. This conservative rule avoids platform-dependent link semantics and prevents a relative-looking path from reading outside the declared root.

## Output safety

Receipt and schema outputs use exclusive file creation. Existing files are not overwritten. A receipt output inside a captured directory, or on top of a captured file, is rejected because writing it would immediately change the snapshot it describes.

The output path itself is not serialized. Human output prints only the output file name, not its absolute location.

## Versioning

The JSON contract is identified by `evidence-lock/receipt/v1` and a versioned schema URL. Backward-compatible implementation fixes keep the same receipt version. A semantic or structural breaking change requires a new receipt version and schema path.

Unknown fields are rejected in v1. This keeps hash and review semantics explicit instead of silently accepting metadata that older verifiers do not understand.
