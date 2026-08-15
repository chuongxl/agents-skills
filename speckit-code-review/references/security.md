# Security Review — `SEC-*`

Identify vulnerabilities and insecure patterns in the git change set (same scope as code quality)
that compromise confidentiality, integrity, or availability.

Record per issue: `file`, `method`, `line range`, issue type, description, severity
(scale defined in SKILL.md — `high` covers auth bypass, injection, hardcoded credentials, and
cryptography misuse).

## Checklist

- **Auth / AuthZ** — missing authentication, broken access control, privilege escalation, IDOR,
  missing ownership checks
- **Injection** — SQL, NoSQL, command, LDAP, XPath, template
- **XSS / output encoding** — stored, reflected, DOM-based
- **CSRF and SSRF**
- **Credential handling** — hardcoded secrets, keys/tokens in code or logs, credentials in URLs
- **Validation / sanitization** — missing input validation, unsafe deserialization, path traversal,
  unrestricted file upload
- **Cryptography misuse** — reused salts, weak password policy, broken algorithms, hardcoded IVs,
  insecure randomness, improper key management
- **Sensitive data exposure** — PII/secrets in logs, errors, or responses; missing encryption at
  rest or in transit
- **Session management** — weak tokens, missing expiry, insecure cookie flags
- **Misconfiguration** — verbose errors, debug mode in prod, permissive CORS, missing security headers
- **Dependency vulnerabilities** — known CVEs in libraries used by changed code
- **Rate limiting / DoS** — missing throttling, unbounded resource consumption
- **Logging & auditing** — missing audit trail for sensitive actions, over-logging of sensitive data

## Detail File — `security.json`

Full vulnerability details and OWASP references for `SEC-*` findings.

> Discard this file from context after the Security review area is complete.
