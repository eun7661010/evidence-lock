# Troubleshooting

## `absolute evidence path is not portable`

Choose a common root and pass evidence paths relative to it.

```bash
evidence-lock create --root packet --source source/input.txt ...
```

The root may itself be absolute at runtime; it is not written to the receipt.

## `parent traversal is not allowed`

Move the file below the selected root or choose a broader root. Do not use `../` to reach evidence outside the declared boundary.

## `symbolic links are not allowed`

v0.1.0 rejects symbolic links for deterministic cross-platform behavior and root containment. Capture the real file or directory below the root instead. Do not copy sensitive content merely to bypass this rule.

## `output would be written inside captured evidence`

Place the receipt beside the captured directories, not inside one of them. Otherwise writing the receipt would change the very directory it describes.

## `refusing to overwrite existing output`

Use a new output name. `create`, `review`, and `schema` use exclusive creation so an earlier packet cannot be replaced accidentally.

## Verification returns `pending` with exit code 3

The file snapshot is current, but it has no review decision. Run `review` against that pending receipt and write a new reviewed receipt.

## Verification returns `rejected` with exit code 4

The evidence is current and the recorded decision is rejection. Do not rename or edit the decision. Address the review result, create a new snapshot if files change, and review that snapshot separately.

## Verification returns `stale` with exit code 5

At least one recorded file or directory is missing, unreadable, or different. The output lists relative paths and changed fields. If the change was intentional, create and review a new receipt. Do not recompute IDs inside the old approved file.

## Verification returns `invalid` with exit code 6

The JSON structure or internal IDs are inconsistent. Restore the original receipt from trusted storage or create a new snapshot. An invalid packet is not repaired automatically because doing so could hide an unauthorized edit.

## A directory changed but only the top-level path is named

The receipt stores a directory digest rather than its complete internal manifest. This reduces path disclosure and receipt size. Use an ordinary directory comparison tool to locate the internal change, then create a new snapshot if appropriate.

## A permission or timestamp change was not detected

v0.1.0 binds regular-file names, sizes, and contents. It intentionally ignores timestamps, permissions, ownership, extended attributes, and empty directories for portability. Choose a different attestation system if those properties are part of the approval basis.
