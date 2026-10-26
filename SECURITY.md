# Security Policy

## Supported versions

Security fixes are applied to the `main` branch and production deployment at
[operationchildshield.org](https://operationchildshield.org).

## Reporting a vulnerability

Please email **Contact@OperationChildShield.org** with:

- A clear description of the issue and impact
- Steps to reproduce (or a proof-of-concept that does not harm production)
- Any suggested remediation

Do **not** open a public GitHub issue for unfixed vulnerabilities.

We aim to acknowledge reports within a few business days and will coordinate
disclosure timing after a fix is available.

## Scope notes

- Public transparency data only; no end-user accounts or payment processing yet.
- Production secrets and deploy credentials are never committed (see `AGENTS.md`).
- Independent production scans: see the SquidScanner badge/link in `README.md`.
