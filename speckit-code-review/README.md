# Speckit Code Review

Perform deep, specification-driven code reviews that compare implementation against feature requirements. This skill delivers structured pass/fail judgments with actionable fix recommendations, enabling continuous spec compliance validation throughout the development lifecycle.

## Overview & Purpose

`speckit-code-review` is a rigorous code review framework designed to answer one question: *Does this code fully implement the feature specification?* Rather than generic linting or style checks, it performs requirement-by-requirement analysis across five review dimensions: business requirements coverage, code quality, security posture, architectural integrity, and unit test coverage.

The skill works with specs from any source — numbered requirement lists (GitHub Spec Kit format) or narrative design documents (Superpowers brainstorming output). It synthesizes requirement checklists when specifications lack pre-numbered identifiers, ensuring consistent coverage analysis across diverse spec formats.

**Key use cases:**
- Validate pull requests against feature specs before merge
- Ensure all requirements are coded and tested
- Catch security vulnerabilities and architectural violations early
- Identify test coverage gaps systematically
- Resume interrupted reviews via saved state files

## Core Concepts

### The Five-Category Review Framework

Every review examines code through five distinct lenses, each generating findings with unique ID prefixes:

1. **Business Gap (FR-*/NFR-*)** — Validates that functional and non-functional requirements from the spec are actually implemented. Covers correctness, completeness, and behavior against acceptance criteria.

2. **Code Quality (CODE-*)** — Assesses maintainability, complexity, readability, and adherence to project conventions. Includes SonarQube integration for static analysis metrics.

3. **Security (SEC-*)** — Identifies vulnerability patterns (injection, auth bypasses, sensitive data exposure), OWASP Top 10 violations, and cryptographic weaknesses.

4. **Architecture (ARCH-*)** — Examines structural soundness: layer violations, coupling, dependency patterns, scalability concerns, and adherence to project architecture guidelines.

5. **Unit Tests (TEST-*)** — Measures coverage gaps, missing test cases for error paths, and inadequate assertion depth. Failures occur at <80% coverage or missing critical scenarios.

### Requirement ID Synthesis

Specs often arrive without pre-numbered requirements. The skill never skips coverage analysis due to missing requirement IDs — instead, it synthesizes them:

**Input:** Narrative spec with acceptance criteria and "must/should" statements
**Process:**
1. Extract one testable statement per requirement (user story, acceptance criterion, explicit constraint, "must" statement)
2. Classify as Functional (FR-*) or Non-Functional (NFR-*)
3. Number sequentially in document order: FR-001, FR-002, … NFR-001, … (stable across reruns)
4. Record each with spec anchor (heading/line number) for traceability

**Output:** `synthesized_requirements` list in the business-gap detail file, with `id`, `statement`, and `spec_anchor` fields so reviewers can verify each requirement back to its source.

Example:
```
FR-001: User account creation form must validate email format before submission
  → spec_anchor: "Acceptance Criteria / Valid Inputs section, line 24"
NFR-001: Password hashing must complete in under 100ms
  → spec_anchor: "Non-Functional Requirements / Performance subsection"
```

### Two-Tier Output Structure

Results are returned at two fidelity levels:

**Tier 1 (Compact)** — Small JSON object (≤400 tokens) returned directly to caller:
- `status`: pass or failed
- `Business cover`: percentage of requirements implemented
- `unit-test-coverage`: measured coverage or "N/A"
- `state_file`: path for resumable state
- `fixes`: top 3 most critical issues (high → medium → low severity)
- `detail_files`: map of category names to file paths

**Tier 2 (Detailed)** — Five per-category JSON files written to disk:
- `business-gap.json`: FR-*/NFR-* findings + synthesized requirements checklist
- `code-quality.json`: CODE-* findings + SonarQube results
- `security.json`: SEC-* findings + OWASP references
- `architecture.json`: ARCH-* findings
- `unit-tests.json`: TEST-* findings + per-method coverage gaps

This separation keeps the inline response small and safe for retry logic, while preserving full context in detail files for detailed remediation.

## Quick Start

### Installation

```bash
# Automatic discovery (Copilot CLI)
# Place this skill in ~/.agents/skills/ or .github/skills/ and it's automatically available

# Manual installation
cp -r speckit-code-review ~/.agents/skills/
```

### Standalone Use

```bash
# Review current changes against the most relevant spec
skill speckit-code-review

# Review with explicit spec path
skill speckit-code-review --spec specs/010-user-login/spec.md

# Include project guidelines context
# (must have docs/guidelines/architecture.md or references/project-guidelines-review.md)
skill speckit-code-review --with-guidelines
```

### Integration with speckit-auto

The skill is automatically invoked by `speckit-auto` during the implementation phase:

```bash
speckit-auto --yolo  # Launches brainstorming → implementation → review loop
```

Reviewers iterate on fixes via `speckit-auto` without re-invoking `speckit-code-review` manually — the tool manages the review cycle.

## How It Works

### The Review Procedure

1. **Parse Requirements** — Extract or synthesize the requirement checklist from `specs/<feature>/spec.md`. If no requirement IDs exist, generate FR-*/NFR-* identifiers synthetically (see Requirement ID Synthesis above).

2. **Define Scope** — Identify changed files from git (staged + unstaged). This defines which code paths require review.

3. **Load Guidelines** — Optionally load project-specific reference files (architecture.md, code-style.md, etc.) to incorporate team-defined standards. Each reference file is discarded after use to avoid context bloat.

4. **Execute Five Reviews** — Run business gap, code quality, security, architecture, and unit test reviews sequentially. Each loads its reference file, performs analysis, records findings, and discards the reference.

5. **Advanced Project Guidelines Pass** — If project guidelines were loaded, run one additional pass per guideline file to catch cross-cutting concerns.

6. **Compute Coverage** — Calculate `Business cover = (covered_requirements / total_requirements) * 100`, rounded to whole percent.

7. **Write Findings** — Persist all findings (standard + guideline-based) to per-category detail files and state file. Include `guideline_source` field for findings raised by project reference files.

8. **Build Fix Queue** — Extract the top 3 most critical issues (highest severity first) into the compact `fixes` array. Remaining issues go to `state_file` for speckit-auto to process.

9. **Decide Status** — Return `pass` only when: (a) `fixes` array is empty, (b) `unit-test-coverage ≥ 80%`, (c) requirement checklist is non-empty. Otherwise, return `failed`.

### Category-by-Category Review

**Business Gap** — For each FR-*/NFR-* requirement, trace through implementation code:
- Is there a code path that implements this requirement?
- Does it match the acceptance criteria?
- Are edge cases and error paths covered?

**Code Quality** — Static analysis: cyclomatic complexity, duplication, naming conventions, dead code. Runs SonarQube scan if runner is detected (Java, C#, Python projects).

**Security** — Pattern scanning for hardcoded secrets, weak authentication, SQL injection vectors, unsafe deserialization, cryptographic weaknesses. Cross-references OWASP Top 10.

**Architecture** — Validates layer boundaries, dependency inversion, scalability assumptions, and any constraints defined in project architecture guidelines.

**Unit Tests** — Measures line coverage via `.coverage`, `coverage.xml`, or test runner output. Flags missing tests for error paths and conditional branches.

## Detailed Features

### Business Gap Analysis (FR-*/NFR-*)

- Validates each requirement is implemented and testable
- Checks acceptance criteria coverage
- Verifies error handling for constraint violations
- Ensures non-functional requirements (performance, scalability, security posture) are met
- Flags incomplete implementations even if code compiles

### Code Quality (CODE-*)

- Enforces naming conventions (camelCase, snake_case, PascalCase per language)
- Detects cyclomatic complexity exceeding thresholds (>10 branches)
- Identifies code duplication (>3 consecutive identical lines)
- Flags unused imports, unreachable code, and shadowed variables
- SonarQube integration (when available) for language-specific metrics

### Security (SEC-*)

- Hardcoded credentials (API keys, passwords, connection strings)
- Weak password validation (< 8 chars or no character class requirements)
- SQL injection vectors (string concatenation in queries)
- Unsafe deserialization or expression evaluation
- Missing CORS/CSP headers in web contexts
- Weak TLS configuration or missing certificate validation
- OWASP Top 10 pattern detection

### Architecture (ARCH-*)

- Layer violations (e.g., UI calling database directly)
- Circular dependencies or tight coupling
- Scalability concerns (non-idempotent operations, unbounded loops)
- Stateless service assumptions violated
- Missing abstraction or leaky abstractions
- Incompatible with project architecture guidelines (when loaded)

### Unit Test Coverage (TEST-*)

- Line coverage < 80% (threshold; configurable)
- Missing tests for error paths and exception handling
- Single-assertion tests covering multiple code paths
- Untested edge cases (null, empty, boundary values)
- Missing tests for performance-critical or security-sensitive code

## Requirement ID Synthesis

When a spec lacks pre-numbered requirements, the skill synthesizes IDs automatically:

**Step 1: Extraction**
Parse the spec document for testable statements in order of priority:
- Acceptance criteria
- Requirements/behavior sections
- User stories
- Explicit constraints
- "Must/should" sentences in narrative prose

**Step 2: Classification**
Assign each requirement to Functional (FR-) or Non-Functional (NFR-):
- FR-*: User-facing behavior, feature completeness
- NFR-*: Performance, reliability, security posture, scalability, maintainability, compliance, UX polish

**Step 3: Numbering**
Number sequentially in document order. Always restart NFR-* numbering from 001:
- FR-001, FR-002, FR-003, …
- NFR-001, NFR-002, …
This ensures stable IDs across reruns as long as the spec is unchanged.

**Step 4: Traceability**
Record in `business-gap.json`:
```json
{
  "synthesized_requirements": [
    {
      "id": "FR-001",
      "statement": "User can log in with email and password",
      "spec_anchor": "Acceptance Criteria, line 24"
    }
  ],
  "requirements_source": "synthesized"
}
```

If the spec yields zero extractable requirements, the review returns `failed` with a single fix recommending addition of testable requirements to the spec. A `pass` with an empty requirement checklist is never returned.

## Installation & Setup

### Platforms

**macOS / Linux:**
```bash
mkdir -p ~/.agents/skills
cp -r speckit-code-review ~/.agents/skills/
```

**Windows:**
```powershell
$skillPath = "$env:USERPROFILE\.agents\skills"
mkdir -p $skillPath -ErrorAction SilentlyContinue
Copy-Item -Recurse speckit-code-review $skillPath
```

### Prerequisites

- Git (for scope detection and file changes)
- Bash or shell environment (for reference file loading)
- Optional: SonarQube CLI, test coverage tool (coverage.py, Jest, NUnit)
- Optional: Project guidelines at `docs/guidelines/` or `references/`

## Compatibility Matrix

| Platform | Support | Notes |
|----------|---------|-------|
| GitHub Copilot CLI | ✅ Full | Auto-discovered from `~/.agents/skills/` |
| Superpowers | ✅ Full | Invoked by speckit-auto skill |
| GitHub Spec Kit | ✅ Full | Specs with pre-numbered FR-*/NFR-* requirements |
| Superpowers Brainstorming | ✅ Full | Narrative specs; requires synthesis |
| macOS | ✅ Full | Bash, git, ripgrep |
| Linux (x86_64, ARM64) | ✅ Full | Bash, git, ripgrep |
| Windows (WSL2) | ✅ Full | Bash via WSL; native Windows untested |
| Java/Maven | ✅ Full | SonarQube integration when available |
| TypeScript/Node.js | ✅ Full | Jest/Vitest coverage parsing |
| Python | ✅ Full | coverage.py, pytest output parsing |
| C# / .NET | ✅ Full | NUnit/xUnit, OpenCover output |
| Go | ✅ Partial | Basic coverage; no industry-standard SonarQube |

## Usage Examples

### Standalone Review

```bash
cd my-feature-repo
git checkout feature/user-login
skill speckit-code-review

# Output: compact JSON to stdout
# Detail files written to .speckit/review-<spec-id>-<timestamp>/
```

### With Explicit Spec Path

```bash
skill speckit-code-review --spec specs/010-user-auth/spec.md
```

### As Part of speckit-auto

```bash
# Launches interactive loop: brainstorm → implement → review
speckit-auto --spec "Add real-time notifications"

# With zero-human-in-the-loop execution
speckit-auto --spec "Add real-time notifications" --yolo
```

The skill is automatically invoked in the review phase; you never call it directly in this mode.

### Example Output (Failed Review)

```json
{
  "status": "failed",
  "Business cover": "65%",
  "unit-test-coverage": "71.2%",
  "state_file": ".speckit/review-010-1722348000/state.json",
  "detail_files": {
    "business-gap": ".speckit/review-010-1722348000/business-gap.json",
    "security": ".speckit/review-010-1722348000/security.json",
    "unit-tests": ".speckit/review-010-1722348000/unit-tests.json"
  },
  "fixes": [
    {
      "id": "FR-004",
      "file": "src/account/service.ts",
      "method": "AccountService::createAccount",
      "lines": "88-140",
      "action": "Add password minimum-length validation (≥8 chars) before calling hashPassword"
    },
    {
      "id": "TEST-001",
      "file": "src/account/service.spec.ts",
      "method": "AccountService::createAccount",
      "lines": "new",
      "action": "Add test case: password shorter than 8 chars should throw ValidationException"
    },
    {
      "id": "SEC-001",
      "file": "src/auth/password.ts",
      "method": "validatePassword",
      "lines": "5-20",
      "action": "Enforce min 12 chars, 1 uppercase, 1 digit, 1 symbol in password policy"
    }
  ]
}
```

### Example Output (Passed Review)

```json
{
  "status": "pass",
  "Business cover": "100%",
  "unit-test-coverage": "87.5%",
  "state_file": ".speckit/review-010-1722348000/state.json",
  "detail_files": {},
  "fixes": []
}
```

## Output Contract & Detail Files

### Compact Inline JSON (≤400 tokens)

Returned directly to caller with these fields (exact names and capitalization preserved):

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"pass"` or `"failed"` |
| `Business cover` | string | e.g., `"85%"` — (requirements_met / total_requirements) × 100, rounded |
| `unit-test-coverage` | string | e.g., `"82.1%"` or `"N/A"` if no test runner detected |
| `state_file` | string | Path to resumable state; always included |
| `detail_files` | object | Map of category → file path; omit categories with no issues |
| `fixes` | array | Top 3 most critical issues (high → medium → low severity); limit to 3 |

Each `fixes` entry:
```json
{
  "id": "FR-001",
  "file": "src/feature/file.ts",
  "method": "ClassName::methodName",
  "lines": "42-67",
  "action": "Single imperative sentence describing required change"
}
```

- `lines: "new"` — file or method must be created
- `action` — one-line imperative only; no bullets, no multi-line

### Detail Files (Tier 2)

Written to `.speckit/review-<spec-id>-<timestamp>/` with full findings per category:

**business-gap.json** — All FR-*/NFR-* findings plus:
```json
{
  "synthesized_requirements": [
    {"id": "FR-001", "statement": "...", "spec_anchor": "..."}
  ],
  "requirements_source": "synthesized" | "declared",
  "findings": [{"id": "FR-002", "status": "not_implemented", "detail": "..."}]
}
```

**code-quality.json** — CODE-* findings plus SonarQube results:
```json
{
  "sonarqube_scan": "path/to/report.xml",
  "findings": [{"id": "CODE-001", "issue": "High complexity", "detail": "..."}]
}
```

**security.json** — SEC-* findings with OWASP references:
```json
{
  "findings": [
    {"id": "SEC-001", "vulnerability": "Hardcoded secret", "owasp": "A02:2021", "detail": "..."}
  ]
}
```

**architecture.json** — ARCH-* findings:
```json
{
  "findings": [{"id": "ARCH-001", "violation": "Layer boundary", "detail": "..."}]
}
```

**unit-tests.json** — TEST-* findings plus coverage data:
```json
{
  "total_coverage": 71.2,
  "findings": [{"id": "TEST-001", "gap": "Missing error path", "detail": "..."}]
}
```

### State File

`.speckit/review-<spec-id>-<timestamp>/state.json` contains:
- Ordered issue inventory from all categories
- Current fix queue position (resumable)
- Timestamp and spec ID for tracking

Used by speckit-auto to resume reviews without reloading verbose findings.

## Troubleshooting & Best Practices

### Common Issues

**Q: Review fails with "zero extractable requirements"**
A: The spec lacks testable statements. Add acceptance criteria, constraints, or "must/should" sentences to the spec. The skill cannot review against an empty requirement list.

**Q: Synthesized requirement IDs change between reruns**
A: Requirement IDs are based on document order. Reordering spec sections will change IDs. To maintain stable IDs, keep requirement order consistent.

**Q: `unit-test-coverage: "N/A"`**
A: No test runner or coverage tool detected in the project. Add test coverage output (coverage.xml, .coverage, Jest report) to the repo root or CI artifacts.

**Q: Too many findings in the fixes array**
A: By design, only top 3 most critical items appear inline. Review full findings in detail files (in `.speckit/` directory). speckit-auto loads these files as needed.

**Q: Security findings seem incomplete**
A: Load project security guidelines to enhance the review. Create `references/security.md` with project-specific vulnerability rules and OWASP constraints.

### Best Practices

1. **Version Your Specs** — Keep specs immutable once review begins. Changes mid-review alter requirement IDs and coverage calculations.

2. **Load Guidelines** — For team consistency, commit `docs/guidelines/architecture.md` and `references/security.md`. The skill automatically loads and applies these.

3. **Review Detail Files** — Inline `fixes` array shows only top 3 issues. Always inspect full detail files for comprehensive context on all findings.

4. **Inspect Synthesized Requirements** — If using narrative specs, verify synthesized requirements in `business-gap.json` match your intent. Adjust spec wording if IDs seem wrong.

5. **Iterate with speckit-auto** — Don't manually fix issues one by one. Use `speckit-auto` to generate code changes, re-run review, and loop until `status: pass`.

6. **Use State Files for Debugging** — If a review seems incomplete, check the state file to see all findings and current queue position.

---

**Version:** 0.0.2  
**Author:** Alex Nguyen  
**Spec:** agentskills.io/specification  
**License:** See repository LICENSE
