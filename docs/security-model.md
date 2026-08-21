# Security and privacy model

## The guarantee this tool makes

Given a receipt and a caller-selected root directory, `evidence-lock` deterministically checks whether:

1. the receipt has the exact supported v1 structure;
2. its unkeyed snapshot and review identifiers match their recorded fields;
3. every recorded relative path still resolves below the root without symbolic links;
4. current file or directory bytes match the stored SHA-256 values;
5. the fresh receipt records an approved, rejected, or pending state.

This is a local consistency guarantee. It is not a cryptographic identity or hostile-storage guarantee.

## Trust assumptions

The verifier must trust:

- the Python interpreter and installed `evidence-lock` package;
- the operating system while files are read;
- the root directory mapping chosen at verification time;
- storage controls that keep an attacker from replacing both the receipt and all evidence;
- the process that assigned the reviewer label and type.

If an attacker can rewrite the evidence and then generate a matching receipt and approval, verification will succeed. The project has no secret key or external transparency record with which to distinguish that packet.

## Threats addressed

- Accidental approval reuse after source, artifact, or policy content changes.
- Manual edits that make receipt fields inconsistent with their IDs.
- Missing or unreadable evidence paths.
- Personal absolute-root leakage through normal receipt generation.
- Path traversal and symlink escape outside the declared root.
- Immediate self-staleness caused by writing a receipt into captured evidence.
- Silent overwrite of an earlier receipt or schema output.
- Cross-platform ambiguity caused by case-insensitive file-name collisions.

## Threats not addressed

- Reviewer impersonation, compromised hosts, malicious administrators, or forged caller metadata.
- Collision or preimage attacks beyond the normal security assumptions of SHA-256.
- Time-of-check/time-of-use changes after verification returns.
- Content safety, malware detection, legal review, copyright review, factual accuracy, or model quality.
- Confidentiality. Receipts are not encrypted.
- Availability attacks, very large inputs, filesystem races, or denial of service.
- Signed provenance, artifact origin, build isolation, transparency, non-repudiation, or trusted timestamps.

## Plaintext metadata

The tool deliberately does not store file contents, absolute roots, environment variables, command arguments, URLs, host names, or user account names by default. It does store relative file names, a reviewer label, reviewer type, decision, timestamps, and optional summary.

Relative names can still disclose project structure, and free-text review fields can contain personal or confidential information. Use neutral labels and short non-sensitive summaries. Inspect a receipt before making it public.

## Path handling

Absolute Windows, UNC, and POSIX paths are rejected as evidence inputs. Parent traversal and NUL bytes are rejected. Symbolic links are rejected in the root path, named evidence path, and captured directory tree.

The receipt output is not part of the receipt. The CLI prints only its file name. Errors are written to avoid including a resolved absolute path.

## Hash interpretation

SHA-256 values and the two IDs are not message authentication codes or signatures. Anyone can recompute them. They are useful for deterministic freshness checks in trusted storage and workflow boundaries, but they do not establish who approved anything.

For authenticated attestations, evaluate in-toto, Witness, Sigstore, or another system with explicit key and identity management. A future integration may wrap an `evidence-lock` receipt in such a system, but v0.1.0 does not implement or claim that integration.

## Reporting a vulnerability

Follow [SECURITY.md](../SECURITY.md). Use a newly written synthetic reproduction and GitHub's private vulnerability reporting form. Do not attach a real review packet, private source, credentials, personal paths, or customer data.
