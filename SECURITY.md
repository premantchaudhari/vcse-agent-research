# Security policy

VCSE is experimental research software, not a production automation service.

## Safe usage
- Run benchmark experiments only against sites and accounts you are authorized to access.
- Treat webpage content and model output as untrusted.
- Keep tokens, provider API keys, browser profiles, cookies and test artifacts out of Git.
- Use low-cost test accounts and enforce model-call, cost and time budgets.
- Review the allowlisted destinations and side effects before enabling any browser automation.
- Do not upload private customer data or credentials to model endpoints.

## Reporting vulnerabilities
Please use GitHub's private vulnerability reporting feature if enabled. Otherwise contact the maintainer privately through a verified channel rather than opening a public issue containing exploit steps or sensitive data.

## Disclosure
This project has no production security certification, external audit or guarantee of agent safety. Tests and simulated fixtures do not establish safety on unrestricted live websites.

## Public repository security checklist

This repository is public under the MIT License. The following are ongoing security and research validation tasks; they are **not all confirmed complete**:

1. Run a dedicated secret scan over every tracked file and all reachable commits, tags and branches, such as Gitleaks.
2. Verify no keys, tokens, cookies, session stores, client data or confidential logs are present, including in Git history.
3. Check provenance and redistribution rights of every included code file and test fixture; third-party licenses remain applicable.
4. Re-run both test suites in a clean environment with Playwright Chromium installed.
5. Verify hosted benchmark outcomes before making performance claims and keep the README's research limitations accurate.

If a secret was ever committed, revoke or rotate it first. Deleting a line from the latest commit does not remove it from Git history.
