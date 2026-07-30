# Security Review

Load this file when performing the Security review area.

## Goal

Identify vulnerabilities and insecure patterns in the git change set that could compromise confidentiality, integrity, or availability.

## Step-by-Step

1. Scope is the same git change set used for code quality review.
2. Review every changed file for the categories below.
3. For each issue: record `file`, `method`, `line range`, issue type, description, and severity.

## Checklist

- **Auth / AuthZ flaws** — missing authentication, broken access control, privilege escalation, IDOR, missing ownership checks
- **Injection** — SQL, NoSQL, command, LDAP, XPath, template injection
- **XSS and output encoding failures** — stored, reflected, DOM-based
- **CSRF and SSRF**
- **Unsafe credential handling** — hardcoded secrets, keys/tokens in code or logs, credentials in URLs
- **Weak validation / sanitization** — missing input validation, unsafe deserialization, path traversal, unrestricted file upload
- **Cryptography misuse** — reused salts, weak password policy, weak/broken algorithms, hardcoded IVs, insecure randomness, improper key management
- **Sensitive data exposure** — PII/secrets in logs, error messages, or responses; missing encryption at rest/in transit
- **Session management flaws** — weak tokens, missing expiry, insecure cookie flags
- **Security misconfiguration** — verbose errors, debug mode in prod, permissive CORS, missing security headers
- **Dependency vulnerabilities** — known CVEs in third-party libraries used by changed code
- **Rate limiting / DoS exposure** — missing throttling, unbounded resource consumption
- **Logging & auditing gaps** — missing audit trail for sensitive actions, over-logging of sensitive data

## Severity Guidance

| Severity | Examples |
|----------|----------|
| `high`   | Auth bypass, injection, hardcoded credentials, cryptography misuse |
| `medium` | Missing rate limiting, verbose error exposure, insecure cookie flags |
| `low`    | Minor logging gap, weak but non-exploitable pattern |

## Output Fields Produced

Populate these JSON fields from this review:

- `security issue` → `"none"` if clean
- `security issue` → array of issue objects if any found
