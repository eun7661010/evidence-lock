# Security policy

## Supported versions

Security fixes are applied to the latest published minor release. Version 0.x is an evolving API; verify behavior again after upgrading.

## Report privately

Use the repository's GitHub **Security → Report a vulnerability** form. Do not open a public issue for path escape, symlink bypass, unsafe overwrite, receipt path leakage, malformed JSON handling, or a demonstrated hash/identifier validation flaw.

Include the affected version, operating system, Python version, expected behavior, and a minimal synthetic reproduction. Remove personal data, private documents, real review packets, credentials, and private paths before submitting.

## Scope

Security reports may cover:

- evidence escaping the declared root;
- symbolic-link or filesystem-entry bypasses;
- output overwrite or self-staleness bypasses;
- absolute root disclosure by normal library or CLI use;
- malformed receipts being accepted as approved;
- reviewed fields not being bound to `review_id`;
- captured bytes changing without a stale result under the documented file model.

The following are documented non-goals rather than vulnerabilities by themselves:

- reviewer authentication, signatures, key management, and trusted timestamps;
- protection when an attacker can rewrite both evidence and receipts;
- semantic review quality, factual correctness, malware detection, and legal compliance;
- timestamps, permissions, ownership, extended attributes, and empty-directory tracking;
- denial of service from hostile or unbounded local input.
