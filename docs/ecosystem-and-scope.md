# Ecosystem comparison and project scope

## The pain point

Many workflows record “approved” separately from the files and rules that were actually reviewed. A later edit can leave the label intact while changing its subject. Hosted code-review systems can dismiss stale approvals for repository commits, and supply-chain systems can produce signed attestations, but small local document, data, model-output, and release workflows often need a portable file-level check without adopting either platform.

`evidence-lock` fills that narrow gap. It binds three explicit file roles and one review decision in a readable JSON packet. It does not execute the work, sign the packet, or operate a server.

## Adjacent projects

| Project | Primary job | What `evidence-lock` does differently |
| --- | --- | --- |
| [in-toto](https://in-toto.io/docs/getting-started/) | Verify signed supply-chain steps against a layout, including materials and products | No layout, keys, signatures, functionaries, or command steps; one local review binding only |
| [Witness](https://github.com/in-toto/witness) | Generate and verify attestations with policies, identity integrations, and optional provenance storage | No attestation platform, policy engine, process tracing, signing, or storage service |
| [Sigstore Cosign](https://docs.sigstore.dev/cosign/verifying/verify/) | Sign and verify software artifacts and attestations with identity and transparency support | Uses unkeyed hashes and makes no identity or signature claim |
| [SLSA provenance](https://slsa.dev/spec/v1.2/provenance) | Describe where, when, and how software was produced | Records a review decision over arbitrary files, not build provenance or an SLSA level |
| [DVC](https://dvc.org/doc/user-guide/project-structure/pipelines-files) | Version data, outputs, parameters, and reproducible pipeline state | Does not cache, restore, run, or version data; only checks whether reviewed bytes changed |
| [GitHub stale review dismissal](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/reviewing-proposed-changes-in-a-pull-request) | Dismiss a pull-request approval after relevant repository changes | Works outside Git and hosted pull requests, and binds an explicit policy file alongside source and artifact |
| [BeforeDone](https://github.com/rrrrrredy/beforedone) | Require fresh command-check receipts for coding-agent completion claims | Does not run verifiers or bind to Git-relevant files; records a human/AI decision over caller-selected file roles |
| [Agent Receipts](https://github.com/inchwormz/agent-receipts) | Capture hash-chained agent execution evidence and evaluate claims | No agent protocol, command capture, signed journal, calibration, or claim engine |
| [Treeship](https://github.com/zerkerlabs/treeship) | Provide signed, chained trust receipts and scoped approvals for agent actions | No keys, Merkle chain, nonce, action authorization, network hub, or agent bridge |

The overlap is intentional at the level of a general principle: evidence should be bound to the exact subject it supports. The implementation and product boundary are different.

## Target users

- Teams that review generated documents, datasets, configuration bundles, model outputs, or release packets.
- CI maintainers who need a local “approval is still current” gate with meaningful non-zero states.
- Human-in-the-loop and AI-review workflow authors who want to keep the evaluation policy bytes beside the result.
- Tool builders who need a small standard-library Python API rather than a hosted service or full attestation stack.

## Chosen scope for v0.1.0

- One versioned JSON receipt schema.
- Required source, artifact, and policy groups.
- Deterministic file and directory SHA-256 snapshots.
- Explicit `human` or `ai` review type and approved/rejected decision.
- Strict internal IDs and immutable review outputs.
- Human and JSON verification results with distinct exit codes.
- No network, runtime dependency, Git requirement, or background service.

## Non-goals

- Authentication, authorization, signing, key management, or transparency.
- Standardization as an in-toto predicate, SLSA claim, or legal evidence format.
- Workflow orchestration, command execution, agent monitoring, or approval user interface.
- Data storage, diff rendering, content extraction, semantic evaluation, or automatic policy decisions.
- Backward compatibility with unrelated receipt formats.

Keeping these non-goals explicit prevents a small freshness tool from being presented as a supply-chain security product.
