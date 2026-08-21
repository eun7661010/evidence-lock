## Problem

What user problem does this change solve?

## Change

Describe the implementation and any receipt-schema, exit-code, path, compatibility, or privacy impact.

## Verification

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `mypy src`
- [ ] `pytest --cov=evidence_lock --cov-branch --cov-report=term-missing`
- [ ] Synthetic receipts regenerated and `git diff --exit-code` checked
- [ ] English and Korean public docs updated when behavior changed

## Public-safety check

- [ ] Fixtures and examples are newly written and synthetic.
- [ ] No personal data, private paths, credentials, service IDs, real approvals, or private project material is included.
- [ ] Security guarantees and non-goals remain accurate.
