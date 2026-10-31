# Ecosystems: language support and how to add one

The scanner is not tied to one language. Each language is described by one JSON file in
`ecosystems/`. For every repo the scanner detects which ecosystems are present, then:

- runs OSV-Scanner on every lockfile it found (`osv`),
- adds that language's Semgrep rulesets (`semgrep`),
- falls back to a CycloneDX SBOM when nothing was recognised or an ecosystem has no
  lockfile (`sbom`).

See what is detected for a repo:

    python3 -I scripts/detect-ecosystems.py path/to/repo
    python3 -I scripts/detect-ecosystems.py path/to/repo --format json

Supported out of the box: node (npm, yarn, pnpm, bun), java-maven, java-gradle, python,
go, dotnet, php, ruby, rust.

Detection walks up to 4 directory levels, so monorepos work. It skips `node_modules`,
`vendor`, `target`, `build`, `dist`, virtualenvs and other generated directories.

## Add an ecosystem

Create `ecosystems/<id>.json` (the file name must equal `id`). No script changes needed.

    {
      "schema_version": 1,
      "id": "elixir",
      "name": "Elixir (Hex)",
      "detect": ["mix.exs"],
      "lockfiles": ["mix.lock"],
      "osv_ecosystem": "Hex",
      "semgrep": ["p/elixir"],
      "docker": { "images": ["elixir"] },
      "runtime": {
        "name": "elixir",
        "extractors": [{ "file": ".tool-versions", "regex": "^elixir\\s+(\\S+)" }],
        "eol_product": "elixir"
      }
    }

| Field | Meaning |
| --- | --- |
| `detect` | File-name globs (no `/`) whose presence means the ecosystem is used |
| `lockfiles` | File names OSV-Scanner can read; its parser is chosen from the name. May overlap `detect` (for example `pom.xml`, `go.mod`) |
| `osv_ecosystem` | The ecosystem name OSV.dev uses |
| `semgrep` | Semgrep registry rulesets for the language |
| `docker.images` | Base-image names that signal this ecosystem (used by the image checks in a later phase) |
| `runtime` | How to read the runtime version and which endoflife.date product applies (used by the runtime checks in a later phase) |

Check it: `python3 -I scripts/detect-ecosystems.py --validate`.

## Where scanning stops

An ecosystem with a manifest but no lockfile (for example a Gradle project without
`gradle.lockfile`, or a `pyproject.toml` without `poetry.lock`) cannot be matched exactly
by OSV-Scanner, so the SBOM fallback runs for it. The SBOM is only as complete as what
Trivy can read from the repo.

## Deprecated config

`package-manager:` and `stack:` in `repository.md` still work and print a warning.
`stack` rulesets are added on top of the detected ones.
