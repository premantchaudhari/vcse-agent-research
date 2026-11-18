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

## Publishing checklist for the maintainer
Before changing this repository from private to public:
1. Scan every tracked file and all reachable commits, tags and branches with a secret scanner such as Gitleaks.
2. Confirm the repository contains no real keys, tokens, cookies, session stores, client information or confidential logs.
3. Check the provenance and redistribution rights of every included code file and test fixture.
4. Install dependencies and rerun both test suites in a clean environment with Playwright Chromium available.
5. Confirm the README describes actual behavior and marks all hosted benchmark results unverified until reproduced.

If a secret was ever committed, revoke or rotate it first. Deleting a line from the latest commit does not remove it from Git history.
