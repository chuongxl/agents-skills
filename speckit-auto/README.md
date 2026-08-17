# Speckit Auto — End-to-End Spec-Driven Delivery Pipeline

**Version**: 0.0.2  
**Author**: Alex Nguyen  
**Status**: Production-ready  

---

## 1. Overview & Purpose

**Speckit Auto** is a comprehensive, provider-agnostic skill that automates the entire spec-driven delivery lifecycle from initial requirement through implementation and verification. It executes a 6-stage pipeline that transforms a requirement or Jira issue into a completed, tested, and committed feature—with optional human oversight or fully automated (YOLO) execution.

The skill acts as a **provider factory**, delegating each pipeline stage to a pluggable integration provider (GitHub Spec Kit or Superpowers skills library). This architecture ensures compatibility with multiple AI agents and delivery workflows while maintaining a consistent, battle-tested execution model.

Whether you're working with GitHub Copilot CLI, Claude Code, or running locally, Speckit Auto provides a single, unified interface for spec-driven delivery that eliminates context-switching and ensures every feature follows the same high-quality, requirements-focused process.

---

## 2. Core Concepts

### The 6-Stage Pipeline

Speckit Auto orchestrates delivery across six distinct stages:

1. **Stage 01: Preflight + Intake** — Validate the requirement, extract context from docs/guidelines, and prepare the project environment for spec authoring.
2. **Stage 02: Spec / Design** — Author a detailed feature specification including acceptance criteria, edge cases, and architectural decisions.
3. **Stage 03: Implement + Code Review Loop** — Execute implementation and automatically invoke speckit-code-review until the code passes the spec; no human approval required.
4. **Stage 04: Human Review + Commit** (default mode only) — Human reviewer validates the implementation against the spec and makes the final decision before merge.
5. **Stage 05: YOLO Commit Flow** (YOLO mode only) — Automatically merge and commit with zero human checkpoints.
6. **Stage 06: Spec Completion** — Mark the spec as completed and create a final commit.

**Key rule**: Stage 03 is a **NO-STOP ZONE** in both default and YOLO modes; code review loops continue automatically until the spec is satisfied.

<img width="754" height="501" alt="image" src="https://github.com/user-attachments/assets/bc5e90df-0523-4951-a195-3b740d1d38c6" />

<img width="2120" height="3775" alt="spec-driven-development-Speckit-Auto-Skill drawio" src="https://github.com/user-attachments/assets/cbe59272-6c75-4f33-bdf9-ad7d0f6aaa22" />

### Provider System

Speckit Auto resolves a **provider** at the start of each run using a precedence chain:

1. **Repo-local config**: `.speckit/integration.json` in the repository root
2. **User home config**: `~/.agents/skills/speckit-auto/.state/integration.json`
3. **First-run ask**: If neither exists, prompt once, persist, and continue

Supported providers:

| Provider | Location | Use Case |
|----------|----------|----------|
| `github-speckit` | Repo-installed GitHub Spec Kit agents | GitHub Actions + Spec Kit environment |
| `superpowers` | Superpowers skills library (obra/superpowers) | Local, Claude Code, flexible environments |

Each provider includes stage-specific reference files that implement the pipeline logic for that environment.

### YOLO vs Default Mode

**Default Mode** (recommended for critical features):
- Runs Stages 01–04 with mandatory human checkpoint at Stage 04
- Requires explicit human approval before code is merged
- Best for production, regulatory, or high-stakes work

**YOLO Mode** (`--yolo` flag):
- Skips Stage 04, uses Stage 05 instead
- Zero human checkpoints; fully automated merge and commit
- Ideal for internal tools, experiments, or when continuous delivery is the goal
- All code still passes speckit-code-review before merge

---

## 3. Quick Start

### Installation

#### GitHub Copilot CLI
Speckit Auto is auto-discovered from `~/.agents/skills/` or the repository's `.github/skills/` path, depending on how the skill is installed. No manual setup is required after copying the skill into one of those locations.

#### Claude Code
Install the skill from the Superpowers skills library, or copy the skill directory to `~/.claude/skills/`.

#### Local Usage (Standalone)
Clone the skill and ensure `.env` credentials are configured if using `--issue` with Jira.

### First Use: Default Mode (With Human Review)

```bash
# Basic invocation with a requirement
skill speckit-auto "Add two-factor authentication to login form"

# With Jira integration (requires .env JIRA_* credentials)
skill speckit-auto --issue https://jira.example.com/browse/PROJ-123
```

**What happens next**: The skill resolves your provider, loads the pipeline, and begins Stage 01 (Preflight + Intake) immediately—same turn, no acknowledgements.

### First Use: YOLO Mode (Fully Automated)

```bash
# Fully automated pipeline with no human checkpoints
skill speckit-auto --yolo "Refactor user authentication module"

# With Jira
skill speckit-auto --yolo --issue https://jira.example.com/browse/PROJ-456
```

**Execution**: Runs all 6 stages automatically; commits result without human approval.

### Provider Setup

To explicitly set or change your provider (one-time setup):

```bash
# Setup mode: no pipeline runs
skill speckit-auto --integration github-speckit
skill speckit-auto --integration superpowers
```

This writes to `.speckit/integration.json` (repo-local) and persists for all future runs.

---

## 4. How It Works

### Entry & Dispatch (Every Invocation)

1. **Parse command line flags**:
   - `--integration <value>` → setup intent (configure provider, exit)
   - `--issue <url>` → Jira pipeline intent (fetch, compact, run pipeline)
   - `--yolo` → mode = automated (else default = human-gated)
   - Free text → requirement pipeline intent

2. **Resolve provider**:
   - Check `.speckit/integration.json` (repo-local)
   - Fall back to `~/.agents/skills/speckit-auto/.state/integration.json` (user home)
   - If neither exists, prompt once, persist, continue in same turn

3. **Load shared and provider rules**:
   - Load `references/shared/global-rules.md` (canonical operating rules)
   - Load `references/<provider>/provider-rules.md` (provider-specific overrides)

4. **Enter Stage 01 immediately** in the same turn (no acknowledgement delays).

### Pipeline Execution Flow

**Stage 01 (Preflight + Intake)**:
- Validate requirement syntax and scope
- Extract project context from `docs/guidelines/architecture.md` if present
- Build an in-memory **Project Context** with repo layout, workspace map, and architecture
- Load referenced guideline files lazily and cache
- Prepare branching strategy and feature branch

**Stage 02 (Spec / Design)**:
- Author feature specification with acceptance criteria
- Define edge cases, API contracts, and architectural decisions
- Default mode: generate review interview questions for human feedback
- Persist spec to `specs/<feature-folder>/spec.md`

**Stage 03 (Implement + Code Review Loop)** — *NO-STOP ZONE*:
- Implement feature based on spec
- **Invoke `speckit-code-review` as a sub-skill** (provider-independent)
- If review fails: fix code, loop back to review
- If review passes: advance to Stage 04/05

**Stage 04 (Human Review + Commit, default mode only)**:
- Present implementation summary and code diff to human reviewer
- Human approves or requests changes (returns to Stage 03)
- Approved code triggers merge and commit

**Stage 05 (YOLO Commit Flow, YOLO mode only)**:
- Automatically merge feature branch to main
- Create implementation commit with linked spec

**Stage 06 (Spec Completion)**:
- Mark spec completed in spec file
- Create final completion commit
- Report results and commit hashes

---

## 5. Detailed Features

### Spec-Driven Delivery Automation
Every feature is authored to a specification first, implementation follows the spec, and code review is gated by spec compliance. This eliminates scope creep, improves testability, and creates audit trails.

### Automatic Code Review Loops
Stage 03 automatically invokes `speckit-code-review` until the implementation passes. Loop continues until spec compliance achieved—humans can't bypass the gate.

### Human-in-the-Loop vs Fully Automated
- **Default mode**: Strategic checkpoint at Stage 04 allows human judgment on merge timing, additional testing, or deployment readiness
- **YOLO mode**: Removes human checkpoint for continuous delivery workflows; all code still passes spec review

### Provider Flexibility
Two execution engines (github-speckit, superpowers) mean you can use the same pipeline across GitHub Actions, local dev, Claude Code, or AI agent environments without code changes.

### Jira Integration
Supply `--issue <jira-url>` and Speckit Auto invokes `jira-to-speckit` to fetch, compact, and import the ticket as a requirement. Requires `.env` JIRA credentials.

### Project Context Awareness
Speckit Auto builds an in-memory model of your codebase from `docs/guidelines/architecture.md`, including:
- Repo layout (monorepo vs single repo)
- Workspace responsibilities (frontend, backend, shared, database)
- Architecture patterns and linked guideline files
- Never re-reads loaded files; reuses context across all stages

---

## 6. Installation & Setup

### GitHub Copilot CLI

**Auto-discovery**: Speckit Auto is discovered from `~/.agents/skills/` automatically.

**First run**: Invokes the skill with any requirement; provider is resolved on first use (prompted, then persisted).

```bash
skill speckit-auto "Your requirement here"
```

### Claude Code

**Installation**: Add the skill from the Superpowers library, or install manually:
```bash
cp -r speckit-auto ~/.claude/skills/
```

**Invocation**: Use the skill tool within Claude Code:
```
skill speckit-auto --yolo "Your requirement"
```

### Local Usage (Standalone)

**Prerequisites**:
- Bash shell
- Git
- Network access for Jira API calls (if using `--issue`)

**Setup**:
```bash
# Clone or copy the skill
git clone <repo> speckit-auto
cd speckit-auto

# Create .env for Jira (optional)
echo "JIRA_URL=https://your-jira.example.com" > .env
echo "JIRA_USERNAME=your-username" >> .env
echo "JIRA_API_TOKEN=your-token" >> .env

# Run
bash speckit-auto/run.sh "Your requirement here"
```

### Provider Configuration

**Repo-local config** (repo root, `.speckit/integration.json`):
```json
{
  "integration": "github-speckit"
}
```

**User home config** (`~/.agents/skills/speckit-auto/.state/integration.json`):
```json
{
  "integration": "superpowers"
}
```

Setup command (persists to repo-local automatically):
```bash
skill speckit-auto --integration superpowers
```

---

## 7. Compatibility Matrix

| Platform | Supported | Notes |
|----------|-----------|-------|
| GitHub Copilot CLI | ✅ Yes | Auto-discovered from `~/.agents/skills/` |
| Claude Code | ✅ Yes | Skill invocation via Superpowers library |
| Local Bash | ✅ Yes | Standalone shell scripts; requires .env for Jira |
| GitHub Actions | ✅ Yes | Via github-speckit provider |
| VS Code (local) | ✅ Yes | Via bash or Claude Code extension |
| macOS | ✅ Yes | Full support |
| Linux | ✅ Yes | Full support |
| Windows | ⚠️ Partial | WSL2 recommended |

**Prerequisites by platform**:
- All: Git, Bash
- Jira intake (`--issue`): .env with JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN

---

## 8. Usage Examples

### Example 1: Default Mode Workflow (With Human Review)

```bash
skill speckit-auto "Add OIDC single sign-on to authentication module"
```

**Execution**:
1. **Stage 01**: Scans docs/guidelines, identifies backend/frontend workspaces
2. **Stage 02**: Authors OIDC spec with integration points and acceptance criteria
3. **You're prompted**: "Review spec?" (accepts changes or proceeds)
4. **Stage 03**: Implementation loop runs; speckit-code-review validates OIDC provider integration
5. **Stage 04**: Human reviewer receives code diff, approves or requests changes
6. **Stage 05** (not used): Skipped in default mode
7. **Stage 06**: Spec marked completed, final commit created

**Commits produced**: Spec commit + implementation commit

### Example 2: YOLO Mode (Fully Automated)

```bash
skill speckit-auto --yolo "Add Sentry error reporting to API server"
```

**Execution**:
1. **Stages 01–03**: Same as default, but no human prompts
2. **Stage 04**: Skipped (YOLO mode)
3. **Stage 05**: Automatic merge to main
4. **Stage 06**: Completion commit

**Commits produced**: Spec commit + implementation commit (no approval review)

### Example 3: Jira Integration

```bash
skill speckit-auto --issue https://jira.company.com/browse/PLATFORM-891
```

**Execution**:
1. Invokes `jira-to-speckit` sub-skill
2. Fetches ticket, extracts description, compacts to requirement text
3. Enters normal pipeline at Stage 01 with Jira context
4. Spec automatically linked to Jira ticket

### Example 4: Resuming After Interrupt

If the pipeline is interrupted (network, session timeout), on next invocation:
```bash
skill speckit-auto --resume
```

The skill resumes from the current stage using run state (resolved provider, current stage, prior commits). **Note**: Run state is stored per-session; always re-invoke in the same session if possible.

---

## 9. Sub-Skill Dependencies

Speckit Auto delegates critical functions to two provider-independent sub-skills:

### `jira-to-speckit`
- **Purpose**: Fetch Jira issue, compact into requirement text, support Stage 01 intake
- **Invocation**: Automatic when `--issue <url>` is passed
- **Requirement**: `.env` with JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
- **Output**: Requirement text + Jira context injected into Stage 01

### `speckit-code-review`
- **Purpose**: Authoritative JSON pass/fail review of code against spec.md
- **Invocation**: Automatic at Stage 03 (code review loop)
- **Input**: Staged diff + active spec file
- **Output**: JSON pass/fail + violation list; loops until pass
- **Non-negotiable**: No human can approve code that fails speckit-code-review

Both sub-skills are **provider-independent** and invoked the same way by every provider.

---

## 10. Troubleshooting & Best Practices

### Common Issues & Solutions

**Provider not resolved**:
- Symptom: Prompt asking "Which provider?" on every run
- Solution: Run `skill speckit-auto --integration <provider>` once to persist

**Stage hangs or timeout**:
- Symptom: No activity for >5 minutes
- Solution: Check network (Jira API, Git hosting); restart session if needed
- Prevention: Use local requirement (no `--issue`) for faster iteration

**Spec review fails repeatedly**:
- Symptom: speckit-code-review rejects code; loop doesn't converge
- Solution: Review spec for overconstrained requirements; simplify acceptance criteria
- Prevention: Write achievable specs; avoid vague language ("elegant", "performant")

**Jira integration fails**:
- Symptom: "JIRA_URL not found in .env"
- Solution: Ensure `.env` exists with all three keys: JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
- Prevention: Use `jira-to-speckit` skill first to test credentials separately

### Best Practices

1. **Start with a clear requirement**: The more specific your input, the better the spec and implementation.
2. **Use default mode for critical work**: Human checkpoints catch edge cases AI may miss.
3. **Enable YOLO only for low-risk changes**: Refactors, docs, internal tools—not customer-facing features.
4. **Review generated specs carefully**: Specs are auto-authored; human feedback at Stage 02 prevents wasted implementation cycles.
5. **Maintain docs/guidelines/architecture.md**: Project context improves workspace targeting and architectural consistency.
6. **Keep Jira credentials in .env, never in code**: Rotate tokens regularly and never commit .env.
7. **Chain multiple features with repos**: Each pipeline run is independent; git worktrees avoid merge conflicts if running in parallel.

---

## Conclusion

**Speckit Auto** streamlines spec-driven delivery by automating routine stages while preserving human judgment where it matters most. Whether you choose default mode (human-gated) or YOLO mode (fully automated), the same 6-stage pipeline ensures consistent, high-quality, specification-compliant features every time.

Invoke it, let it run—your spec and implementation come out the other side.
