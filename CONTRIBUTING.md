# Contributing

Thank you for helping make review receipts smaller, clearer, and safer.

## Before opening an issue

- Search existing issues and read the documented non-goals.
- Reduce the problem to a newly written synthetic packet.
- Remove personal names, private paths, repository names, credentials, service IDs, and real review content.
- Report security-sensitive behavior through the private process in `SECURITY.md`.

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
pytest --cov=evidence_lock --cov-branch --cov-report=term-missing
python tools/generate_synthetic_receipts.py
git diff --exit-code
```

Run `python -m build` and `python -m twine check dist/*` when changing packaging or documentation metadata.

## Design constraints

- Preserve the standard-library-only runtime unless a proposal demonstrates a clear need and migration cost.
- Keep receipt and verification formats versioned and strict.
- Never turn unkeyed identifiers into claims of authentication or signatures.
- Continue to omit the absolute root and refuse symlink escape.
- Keep human-readable and JSON CLI behavior stable.
- Prefer explicit failure over silently skipping an evidence path.
- Do not overwrite user outputs.
- Keep Windows, macOS, and Linux behavior aligned.

## Fixtures and documentation

All fixtures must be synthetic and created specifically for this repository. Do not submit:

- real approvals, model transcripts, customer or student documents;
- private source, policies, generated reports, screenshots, or logs;
- copied content with unclear rights;
- personal absolute paths or account identifiers;
- secrets, `.env` files, credentials, tokens, cookies, certificates, or service configuration.

Use reviewer labels such as `reviewer-01` and `synthetic-review-agent`. Document limits in complete sentences and avoid security claims that the implementation does not support.

## Pull requests

Keep each pull request focused. Explain the user problem, receipt-format impact, privacy impact, compatibility impact, and tests. Update English and Korean public documentation together when behavior changes. A maintainer may ask for an additional synthetic regression case.

By contributing, you agree that your contribution is licensed under Apache License 2.0.
