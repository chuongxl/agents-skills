# speckit-auto test cases

Scope: decision flow and outputs only, covering both `github-speckit` and `superpowers`, across
all three host agents (GitHub Copilot, Claude Code, OpenCode).

| ID | Scenario | Preconditions | Steps | Expected result | Provider coverage |
|---|---|---|---|---|---|
| T01 | Setup: valid `--integration github-speckit` | No config exists | Run `/speckit-auto --integration github-speckit` | Writes repo-local `.speckit/integration.json`, reports resolved provider, file path, next command | Both |
| T02 | Setup: valid `--integration superpowers` | No config exists | Run `/speckit-auto --integration superpowers` | Writes repo-local `.speckit/integration.json`, reports resolved provider, file path, next command | Both |
| T03 | Setup: alias normalization | Any | Run `/speckit-auto --integration github` or `/speckit-auto --integration superpower` | Normalizes to supported provider and persists canonical value | Both |
| T04 | Setup: invalid integration value | Any | Run `/speckit-auto --integration banana` | Fails fast, reports only supported values, writes nothing | Both |
| T05 | Missing provider config | No `.speckit/integration.json` in repo | Run `/speckit-auto "..."` | Stops immediately, tells user to run `/speckit-auto --integration <provider>` first; no pipeline stage runs | Both |
| T06 | Unparseable / unsupported stored value | `.speckit/integration.json` has bad JSON or unknown provider | Run `/speckit-auto "..."` | Stops with the same configure-first message; no fallback | Both |
| T07 | Setup: `--global` rejected | Any | Run `/speckit-auto --integration github-speckit --global` | Rejects `--global` (global state unsupported); nothing written globally | Both |
| T08 | Manual requirement intake | Provider already resolved | Run `/speckit-auto "add X"` | Starts Stage 01 immediately from requirement text | Both |
| T09 | Jira intake happy path | `.env` has Jira creds, valid issue URL | Run `/speckit-auto --issue <url>` | Invokes `jira-to-speckit`, gets compact brief + ticket snapshot path, continues pipeline same turn | Both |
| T10 | Jira URL resolution from turn text | No explicit `--issue`, but URL appears in user message | Paste Jira URL in text | Treats as `--issue` mode and runs Jira intake | Both |
| T11 | Jira creds missing | `--issue` used, `.env` incomplete | Run `/speckit-auto --issue <url>` | Stops with clear `.env` request; no downstream stage runs | Both |
| T12 | Jira 401/403 | Invalid Jira credentials | Run `/speckit-auto --issue <url>` | Reports auth/permission error, stops | Both |
| T13 | Jira 404 | Bad issue key/URL | Run `/speckit-auto --issue <url>` | Reports issue not found, asks to confirm key | Both |
| T14 | Stage 01 branch gate | Clean repo | Run normal pipeline | Creates/switches branch before any other stage work | Both |
| T15 | Stage 01 provider-specific preflight | Framework missing | Run normal pipeline | Triggers install recovery path for the selected provider | Both |
| T16 | Stage 02 spec creation | Valid requirement | Run normal pipeline to Stage 02 | Produces spec/design output only for current provider | Both |
| T17 | Stage 02 self-review gate passes | Spec is complete | Run Stage 02 review | Passes placeholder/consistency/scope checks and moves on | Both |
| T18 | Stage 02 self-review gate fails | Spec has ambiguity or placeholders | Run Stage 02 review | Fails with actionable corrections; no Stage 03 entry | Both |
| T19 | Stage 03 code-review loop success | Implementation reviewable | Run Stage 03 | Reaches `speckit-code-review pass` and advances | Both |
| T20 | Stage 03 review failure loop | Review fails | Run Stage 03 | Applies fixes and reruns until pass; no human stop inside Stage 03 | Both |
| T21 | Default-mode checkpoint | Mode = default | Reach Stage 02 → Stage 03 boundary | Asks for start-implementation confirmation before entering Stage 03 | Both |
| T22 | YOLO mode skips human gates | Mode = yolo | Run with `--yolo` | Skips human Stage 02 interviews/approvals; performs autonomous Entry Gate and Stage 04 commit/spec completion with no human waits | Both |
| T23 | Provider-specific stage routing | Provider resolved | Run pipeline | Loads stage files only from selected provider tree | Both |
| T24 | Missing provider config + no selection | No persisted provider anywhere | Run pipeline | Asks once, persists selection, continues without restart | Both |
| T25 | Unsupported stored provider | Corrupt `integration.json` | Run pipeline | Ignores bad value, falls through to next precedence or selection | Both |

## Host-specific checks

| ID | Scenario | Preconditions | Steps | Expected result | Provider coverage |
|---|---|---|---|---|---|
| H01 | Host detection from discovery dir | Skill installed in `~/.claude/skills/` (Claude) or `~/.config/opencode/skills/` (OpenCode) | Invoke the skill | Detects the host, records it, and keeps it fixed for the whole run | Both |
| H02 | Flag parsing without slash commands (OpenCode) | OpenCode host | Message: "run speckit-auto --yolo on this requirement: …" | Parses `--yolo` from natural language and enters pipeline in YOLO mode | Both |
| H03 | Slash-command flag parsing (Copilot/Claude) | Copilot or Claude host | `/speckit-auto --issue <url> --yolo` | Parses flags from slash body and enters Jira pipeline in YOLO mode | Both |
| H04 | Mid-run resume marker per host | Pipeline interrupted mid-Stage 02 | New turn contains `<available_skills>` (OpenCode) or `<skill-context>` (Claude) | Resumes from current stage without asking the user to re-trigger the skill | Both |
| H05 | github-speckit source check per host | `github-speckit` selected | Run normal pipeline | Probes `.github/skills/speckit-*/SKILL.md` (Copilot), `.claude/skills/speckit-*/SKILL.md` (Claude), `.opencode/skills/speckit-*/SKILL.md` (OpenCode); records resolved layout | github-speckit |
| H06 | github-speckit install key per host | `github-speckit` selected, repo files missing | Accept install during recovery | Runs `specify init . --integration <host-key>` (`copilot` / `claude` / `opencode`); never a mismatched key | github-speckit |
| H07 | Invocation channel per host | `github-speckit` selected | Stage 02/03 | Slash commands on Copilot/Claude Code; `skill` tool by resolved name on OpenCode; never `task` with `speckit.*` agent_type | github-speckit |
| H08 | superpowers availability probe per host | `superpowers` selected | Run normal pipeline | Probes host skill dirs (`~/.claude/skills/`, `.claude/skills/`, `~/.config/opencode/skills/`, `.opencode/skills/` in addition to Copilot paths) | superpowers |
| H09 | superpowers install on OpenCode | OpenCode host, superpowers missing | Accept install during recovery | Asks Install/Stop, then git-clones superpowers and copies `skills/*` into the opencode skills dir | superpowers |
| H10 | Host ask tool naming | Default mode | Stage 02 interview / Stage 03 confirmation | Uses `ask_user` (Copilot), `question` (OpenCode), `AskUser` (Claude Code); one question at a time | Both |
| H11 | Tool names vary by host | Any host | Any file/git operation | Performs the action via the host's equivalent tool name; never refuses because `allowed-tools` lists different names | Both |

## Provider-specific checks

- `github-speckit`: pipeline stage refs live under `references/pipeline/` and the provider adapter under `references/providers/github-speckit.md`; output mentions repo-installed agents.
- `superpowers`: pipeline stage refs live under `references/pipeline/` and the provider adapter under `references/providers/superpowers.md`; output mentions `superpowers:*` skills.
- Both: the chosen provider never changes mid-run; stage files load only the selected provider's adapter.

## Minimum pass criteria

- All setup, precedence, intake, stage-boundary, and failure-path cases return the expected output shape.
- Both providers behave identically at the `speckit-auto` contract level, differing only in provider-specific stage refs and wording.

## Structured events, version 0.5.0

Use isolated source repos/worktrees, Node.js >=22.13, and only the bundled helper.
Inspect JSONL and discovery as data, not prose logs. Exercise host argument-vector tools
and quoted bash invocations, including paths with spaces and shell metacharacters.

| ID | Scenario | Steps | Expected result | Provider coverage |
|---|---|---|---|---|
| E01 | Default happy path | Run with a known Jira URL and UUID; approve all existing gates | Init before provider/intake emits run_started + 01-intake start; successful boundaries for all four stages; spec-approval, plan-approval, implementation-start, implementation-approval waits immediately before actual asks and answers immediately after; completion only after final spec push | Both |
| E02 | Native approvals | Exercise all github-speckit step approvals and superpowers brainstorming approval | Existing asks retained exactly, stable spec/plan gate mapping; superpowers waiting occurs at actual native ask, not while generating design; no added writing-plans handoff | Both |
| E03 | YOLO happy path | Run with --yolo, valid inputs and installed provider | Same stage boundaries and required autonomous gates/commits/push; no human waiting/answered events for skipped approvals or commit-message ask | Both |
| E04 | Request changes | Request edits at spec approval, implementation-start, and implementation approval | gate_answered recorded without raw feedback; detail ask uses question_waiting then progress; restarted stage gets a new start; no failure or abandoned-stage finish; mandatory gates repeated | Both |
| E05 | Resume and move | Pause an active run, resume with same UUID; move provisional worktree safely | init validates history, no duplicated starts/answers, next sequence retained; source discovery points to canonical moved path; helper absolute path still works | Both |
| E06 | Fresh retry | Complete/fail an attempt, then retry in same worktree | New UUID and independent sequence starting at 1; old history stays intact; reusing terminal UUID errors | Both |
| E07 | Failed event write | Make writer path unwritable or hold producer lock before a boundary/final emit | Explicit diagnostic and stop; no following stage action, recursive failure emit, or completion claim; inspect/repair before resume | Both |
| E08 | Manual questions | Ask clarification, concern, constraints, feedback details, install recovery, and commit message | Each initialized-run ask gets exactly one question_waiting before ask and stage_started after response, no answer text; named approvals are not double-wrapped; Stage 03 adds no questions | Both |
| E09 | Terminal exits | Exhaust Stage 02 retries/Stage 03 circuit breaker; force required git push failure | One run_failed with classified bounded reason, no success boundary; ordinary failed reviews and warnings keep looping without terminal events | Both |
| E10 | PR confirmation | Finish without a PR, with a successful PR, then with failed optional PR creation | pr_opened only after actual verified HTTPS URL; none on placeholder/failure/no PR; optional PR failure remains non-blocking; no duplicate URL on resume | Both |
| E11 | Runtime and identity | Use old/missing Node, invalid/missing --run-id value, standalone requirement, and known Jira URL | New pipeline rejects bad runtime/UUID; standalone generates UUID once; ticket key present from init, no late key attachment; setup-only runs emit nothing | Both |
| E12 | Payload hygiene and portability | Use Unicode and shell metacharacters in paths and input, inspect events and staged files | Builtin Node JSON stdin invocation executes no injected command; composed/redacted bounded text, no raw answers/tool output/secrets; no events/discovery/locks staged; installed skill folder is self-contained | Both |
| E13 | Completion push failure | Fail only the spec completion push after successful implementation push | git_error failure; no stage_finished for 04-finish or run_completed; clean-tree commit skips remain success paths | Both |
