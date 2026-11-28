<!-- speckit-auto:coding-rules:start v1 -->
## Coding rules

Managed by `speckit-auto --integration`. Edits inside this block are overwritten; put project-specific rules outside it.

- **Reuse first.** Before writing a helper or utility, search this repo and the dependency manifests. When an existing dependency or in-repo module already does the job, use it.
- **Never hand-write what a maintained library does:** date and time-zone math, cryptography and password hashing, auth and token protocols, parsers for standard formats (CSV, XML, YAML, URLs), retry and backoff, schema validation.
- **Preferred libraries.** When this file has a `## Preferred libraries` section, use the library it names for that concern.
- **No new dependency without approval.** State its name, purpose and license and why nothing existing fits, then wait for a human to approve. In a `speckit-auto` run, list it under `Reuse & dependencies` in `plan.md`.
- **Keep changes small.** One concern per task. Split a task whose diff would pass about 400 changed lines.
- **Say what you reused.** In the plan or change summary, name the libraries and modules reused and what was written by hand.
<!-- speckit-auto:coding-rules:end -->
