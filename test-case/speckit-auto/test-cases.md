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
| T22 | YOLO mode skips human gates | Mode = yolo | Run with `--yolo` | Skips Stage 02 interview/confirmation and Stage 04's human-approval interaction (Stage 04 itself still runs: implementation is still committed) | Both |
| T23 | Provider-specific stage routing | Provider resolved | Run pipeline | Loads stage files only from selected provider tree | Both |
| T24 | Missing provider config + no selection | No persisted provider anywhere | Run pipeline | Asks once, persists selection, continues without restart | Both |
| T25 | Unsupported stored provider | Corrupt `integration.json` | Run pipeline | Ignores bad value, falls through to next precedence or selection | Both |
| T26 | Verification opt-in at setup | Running `--integration` for the first time on a repo | Answer "Yes" to the verification question | Generates `.cursor/skills/verify-<app>/`, proves it once, commits it, persists `verification: true` | Both |
| T27 | Verification opt-out at setup | Running `--integration` for the first time on a repo | Answer "No" (or no answer) | Persists `verification: false`; nothing generated | Both |
| T28 | Stage 05 skipped when disabled | `verification: false` in `.speckit/integration.json` | Run pipeline through Stage 04 | Stage 05 is skipped; report shows `verification: skipped`; proceeds straight to Stage 06 | Both |
| T29 | Stage 05 runs when enabled | `verification: true` | Run pipeline through Stage 04 | Invokes `create-verification-skill` in update mode for the implemented feature, runs `verify-<app>`, asks pass/investigate | Both |
| T30 | Stage 05 investigate loop | Verification enabled; human answers "Investigate further" | Reach Stage 05's confirmation | Routes back like a Stage 04 "Request changes"; re-enters Stage 05 after re-verification | Both |
| T31 | Stage 06 always runs | Any mode, verification enabled or not | Reach end of Stage 05 | Cleans up (if Stage 05 ran), marks spec completed, pushes, attempts PR creation per repo | Both |
| T32 | PR creation on GitHub remote | Parent repo (or submodule) origin is a `github.com` URL, `gh` installed and authenticated | Reach Stage 06 PR step | Runs `gh pr create`; treats an already-existing PR for the branch as success | Both |
| T33 | PR creation skipped on non-GitHub or missing `gh` | Origin is not `github.com`, or `gh` unavailable | Reach Stage 06 PR step | Reports "PR not created for `<repo>`: `<reason>`" and continues; does not stop the stage | Both |
| T34 | Submodule PR fan-out | Repo has submodules with local commits ahead of base | Reach Stage 06 PR step | Attempts a PR for the parent and for each such submodule independently; one failing does not block another | Both |

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
