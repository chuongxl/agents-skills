# Pinned provider releases

The only place that names provider versions. Install flows and `--integration` setup read the values here and
never resolve "the newest tag" themselves: a tag can be moved, a commit cannot. Installs verify the commit.

| Provider | Release | Commit (immutable) | Verified |
|---|---|---|---|
| github-speckit (`github/spec-kit`) | `v1.4.0` | `0019fa14d12f45edabc2cc3176c9168a68bd0f97` | 2026-11-16, latest non-prerelease, published 2026-11-10 |
| superpowers (`obra/superpowers`) | `v7.0.2` | `22f0b463e7a5e579904dd6211a520321035526f7` | 2026-11-16, latest non-prerelease, published 2026-11-03 |

- Spec Kit installs by commit: `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@0019fa14d12f45edabc2cc3176c9168a68bd0f97`, then `specify version` must report `1.4.0`.
- Superpowers via a Copilot or Claude Code plugin marketplace cannot be pinned (the marketplace decides the
  version); tell the user that at the install ask. The OpenCode and Hermes clone path verifies the commit.

## Superpowers clone for OpenCode / Hermes Agent (pinned, verified, non-overwriting)

Used by `superpowers-install.md` and by `--integration` setup. Clone the pinned tag (never the default branch, never
"the newest tag") into a fresh private temp directory (never a fixed `/tmp` path another local user could pre-create),
verify the commit, and refuse to overwrite anything already installed:

```bash
tag=v7.0.2; sha=22f0b463e7a5e579904dd6211a520321035526f7
src="$(mktemp -d)" && git clone --depth 1 --branch "$tag" https://github.com/obra/superpowers.git "$src" \
  && [ "$(git -C "$src" rev-parse HEAD)" = "$sha" ] \
  || { echo "superpowers $tag does not match the pinned commit - not installed"; rm -rf "$src"; exit 1; }
mkdir -p <skills dir>
clash=""; for d in "$src"/skills/*/; do [ -e "<skills dir>/$(basename "$d")" ] && clash="$clash $(basename "$d")"; done
[ -z "$clash" ] || { echo "already present, not overwritten:$clash"; rm -rf "$src"; exit 2; }
cp -R "$src"/skills/* <skills dir>/ && rm -rf "$src"
```

`<skills dir>` is project-local by default: `.opencode/skills/` on OpenCode. Hermes Agent has only a global dir
(`~/.hermes/skills/`, `/opt/data/skills/` inside the Docker container): say at the install ask that this affects every
project. Exit 2 (name clash) → list the names and ask `Skip existing and install the rest` / `Stop`; never replace an
existing skill directory. Report the installed tag and commit.

## Bumping (a deliberate, reviewed change — never at run time)

1. Read the new release notes and advisories; check it is not a prerelease.
2. Resolve the commit: `git ls-remote https://github.com/<owner>/<repo>.git 'refs/tags/<tag>^{}'` (the `^{}` line
   is the commit an annotated tag points to; a lightweight tag has only the plain line).
3. Check the commands this skill uses still exist (`specify init --integration … --integration-options="--skills" --force`).
4. Replace the row above and the SHA in `github-speckit-install.md` / `superpowers-install.md` in one commit.
