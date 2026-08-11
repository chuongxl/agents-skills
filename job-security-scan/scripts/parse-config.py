#!/usr/bin/env python3
"""
parse-config.py — Parse repository.md frontmatter into shell-compatible output.

Usage:
  python3 parse-config.py <repository.md> [--key KEY]

With no --key: prints all keys as shell export statements (source-able).
With --key KEY: prints only the value of that key (plain text, one item per line for lists).

Examples:
  source <(python3 scripts/parse-config.py assets/repository.md)
  REPOS=$(python3 scripts/parse-config.py assets/repository.md --key active-repos)
"""

import sys
import re

def parse_frontmatter(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    # Extract YAML between first pair of ---
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        print("ERROR: No YAML frontmatter found in " + filepath, file=sys.stderr)
        sys.exit(1)

    yaml_text = match.group(1)

    # Minimal YAML parser for the subset we need (no external deps required)
    data = {}
    current_key = None
    current_list = None
    in_repo_block = False
    current_repo = {}
    repos = []

    for raw_line in yaml_text.splitlines():
        line = raw_line.rstrip()

        # Skip comments
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        # Top-level key: value
        if indent == 0 and ":" in line and not line.startswith("-"):
            if in_repo_block and current_repo:
                repos.append(current_repo)
                current_repo = {}
                in_repo_block = False

            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")

            # Strip trailing inline YAML comments (e.g. value  # comment)
            val = re.sub(r'\s+#.*$', '', val).strip().strip('"').strip("'")

            if val == "":
                current_key = key
                current_list = []
            else:
                data[key] = val
                current_key = key
                current_list = None

        # List item at top level (stack, ci-branches, etc.)
        elif indent == 2 and line.lstrip().startswith("- ") and current_key and current_key != "repos":
            item = line.lstrip()[2:].strip().strip('"').strip("'")
            if current_list is not None:
                current_list.append(item)
                data[current_key] = current_list

        # Repo block start
        elif indent == 2 and line.lstrip().startswith("- name:") and current_key == "repos":
            if in_repo_block and current_repo:
                repos.append(current_repo)
            current_repo = {}
            in_repo_block = True
            current_repo["name"] = line.split("name:")[1].strip().strip('"').strip("'")

        # Repo block fields
        elif indent == 4 and in_repo_block and ":" in line:
            k, _, v = line.strip().partition(":")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if v.lower() == "true":
                v = "true"
            elif v.lower() == "false":
                v = "false"
            current_repo[k] = v

    # Flush last repo
    if in_repo_block and current_repo:
        repos.append(current_repo)

    data["_repos"] = repos
    return data


def active_repos(data):
    return [r["name"] for r in data.get("_repos", []) if r.get("active") == "true"]


def dockerfile_repos(data):
    return [r["name"] for r in data.get("_repos", []) if r.get("active") == "true" and r.get("has-dockerfile") == "true"]


def semgrep_rulesets(data):
    """Map stack entries to Semgrep ruleset IDs."""
    stack_map = {
        "typescript": "p/typescript",
        "nodejs": "p/nodejs",
        "nestjs": "p/nestjs",
        "nextjs": "p/typescript",
    }
    stack = data.get("stack", [])
    rulesets = {stack_map[s] for s in stack if s in stack_map}
    rulesets.update(["p/owasp-top-ten", "p/secrets"])
    return sorted(rulesets)


def allowlist_paths(data):
    return data.get("secret-allowlist-paths", [])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse-config.py <repository.md> [--key KEY]", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    key_filter = None
    if "--key" in sys.argv:
        idx = sys.argv.index("--key")
        key_filter = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    data = parse_frontmatter(filepath)

    # Computed keys
    data["active-repos"]       = active_repos(data)
    data["dockerfile-repos"]   = dockerfile_repos(data)
    data["semgrep-rulesets"]   = semgrep_rulesets(data)
    data["allowlist-paths"]    = allowlist_paths(data)

    if key_filter:
        val = data.get(key_filter, "")
        if isinstance(val, list):
            print("\n".join(val))
        else:
            print(val)
    else:
        # Shell-sourceable output
        scalar_keys = ["team", "org", "monorepo-root", "ci-runner", "package-manager", "fail-on-severity", "output-dir"]
        list_keys   = ["active-repos", "dockerfile-repos", "semgrep-rulesets", "ci-branches", "allowlist-paths"]

        for k in scalar_keys:
            v = data.get(k, "")
            shell_key = k.replace("-", "_").upper()
            print(f'export {shell_key}="{v}"')

        for k in list_keys:
            v = data.get(k, [])
            shell_key = k.replace("-", "_").upper()
            if isinstance(v, list):
                arr = " ".join(f'"{x}"' for x in v)
                print(f'export {shell_key}=({arr})')
