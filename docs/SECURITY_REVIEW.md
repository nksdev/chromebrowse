# Security Review: chromebrowse

**Review type:** Static code and configuration review  
**Scope:** The opt-in `public_only` URL policy, browser routing, session handling, and package integration  
**Status:** Engineering review, not a penetration test or a security certification  
**Reviewed against:** Repository source on the `main` branch on 2026-10-28

## Executive summary

`chromebrowse` is a general-purpose browser automation library. Its default configuration permits navigation to arbitrary destinations because local labs, authorized security testing, and ordinary browser workflows may require private network access.

The optional `BrowserConfig(public_only=True)` policy rejects non-HTTP(S) URLs, URL credentials, localhost names, and hostnames that resolve to non-global addresses. It is useful defense in depth, but **must not be treated as a complete server-side request forgery (SSRF) defense**.

Do not expose an unrestricted browser endpoint to untrusted callers based on this flag alone. Use network-level egress controls, destination allowlists where practical, authentication, quotas, timeouts, and isolation.

## Findings

### F-01 — URL filtering is not a complete SSRF boundary

**Severity:** High if an application exposes browsing to untrusted callers; context-dependent for a local library  
**Status:** Limitation is documented in the project README and code comments

The validator resolves a hostname and checks that all returned IP addresses are global. Chromium makes its own network connection after validation, so DNS answers can change between the check and connection (a time-of-check/time-of-use gap). URL validation alone cannot guarantee which destination the browser ultimately reaches.

**Recommendation**

- Enforce outbound network policy outside the Python process (firewall, isolated network namespace, or controlled egress proxy).
- Deny loopback, private, link-local, metadata, and other restricted destinations at the network boundary.
- Prefer explicit destination allowlists for public services.
- Do not claim `public_only=True` alone prevents SSRF.

### F-02 — Browser networking mechanisms may not all pass through URL routing

**Severity:** High when the browser is used as a public URL-fetching service  
**Status:** Requires deployment-level mitigation

The policy is applied through Playwright's browser-context route handler. Route interception is not a universal network firewall; browser features or protocols not covered by the configured route handler may not receive the same policy checks. WebSocket traffic is a known consideration for Playwright routing, and browser networking can evolve across versions.

**Recommendation**

- Keep network egress restrictions in place even when routing checks are enabled.
- If WebSocket interception is added in a future release, gate it against the minimum supported Playwright version and test it explicitly; do not rely on it as the only boundary.
- Reassess the routing model when upgrading Playwright.

### F-03 — Saved session state contains sensitive authentication material

**Severity:** High if state files are exposed  
**Status:** Operational risk

Session storage can contain cookies and local storage values that grant access to authenticated accounts. A copied or committed state file may allow session reuse.

**Recommendation**

- Never commit session-state files, cookies, or browser profiles.
- Restrict permissions on the configured state directory and on backups.
- Avoid logging cookie values or raw storage state.
- Use dedicated, least-privilege accounts for automation.

### F-04 — Page JavaScript evaluation is intentionally powerful

**Severity:** Context-dependent  
**Status:** API behavior

The `Page.evaluate()` API executes JavaScript in the context of the loaded page. That is useful for automation, but scripts supplied by untrusted users can inspect and manipulate the page and may act using the current site's authenticated context.

**Recommendation**

- Do not pass arbitrary user-supplied JavaScript directly to `evaluate()`.
- Treat page content and scripts as untrusted data.
- Use separate browser contexts and least-privilege accounts for tasks with different trust levels.

### F-05 — Browser execution should be isolated in multi-user services

**Severity:** High for multi-tenant deployments if isolation is absent  
**Status:** Deployment architecture requirement

A shared browser context can share cookies, storage, and page state across tasks. A browser process also has filesystem and network access according to the operating system account and environment in which it runs.

**Recommendation**

- Do not share an authenticated context across mutually untrusted users.
- Consider per-job or per-tenant contexts, process/container isolation, filesystem restrictions, resource limits, and controlled downloads.
- Bound concurrency and apply job timeouts to reduce resource-exhaustion risk.

## Existing defensive behavior observed

The source and tests show that the URL policy:

- Accepts only HTTP and HTTPS schemes.
- Rejects URLs containing credentials.
- Rejects localhost hostnames and non-global IP destinations.
- Rejects a hostname if any resolved address is non-global.
- Rejects DNS resolution failures and empty address results.
- Is exercised by unit tests for private, loopback, link-local, multicast, reserved, and mixed DNS answers.
- Is applied by the request router when `public_only=True`.

These are useful controls, but they do not remove the deployment risks described above.

## Release-validation recommendations

Before promoting the package for use in a public service:

1. Keep the offline regression suite and live browser integration tests in CI.
2. Build both wheel and source distribution and check metadata.
3. Install the built wheel in CI and smoke-test its import and CLI entry point.
4. Test the supported Python versions and operating systems in the CI matrix.
5. Test SSRF behavior in an isolated lab with controlled DNS and network rules; do not test against real internal infrastructure.
6. Document the supported Playwright version range and re-test routing behavior on dependency upgrades.
7. Review dependencies and release provenance before publishing to PyPI.

## Limitations of this review

This review was based on static inspection of repository source and tests. It did not perform a live penetration test, exhaustive browser protocol testing, DNS-rebinding lab test, dependency vulnerability scan, or independent third-party assessment. Findings should be treated as engineering guidance, not a guarantee that the package is secure.
