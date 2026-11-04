#!/usr/bin/env python3
"""Prepare the deep audit (Phase 10) of one repo: run metadata, prior-run links, reconnaissance hints.

run-scan.sh --scanner audit calls this once per repo. It does the deterministic part of upstream Phase 1
and never reads secrets, runs target code or contacts the network:

  <run>/<repo>/audit/run-metadata.json   run id, target, source ref (commit + dirty), profile, scope, budget,
                                          execution policy (+ sandbox self-test), prior runs, run_status
  <run>/<repo>/audit/recon-hints.json    detected ecosystems and candidate entry surfaces with file:line,
                                          grouped by the companion file they point to (hints, not findings)
  <run>/<repo>/audit/AGENT-TASK.md       the resolved instructions the agent follows next
  <run>/<repo>/audit/agents/             per-agent scratch/ and artifacts/ roots go here

The agent then runs the method in references/audit/WORKFLOW.md and writes coverage-ledger.json and
findings.json. Stdlib only; Python 3.8+.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "lib"))
import ecosystems  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv", "venv", "__pycache__",
             ".next", ".gradle", ".idea", "coverage", ".terraform"}
MAX_FILES = 5000
MAX_FILE_BYTES = 512 * 1024
MAX_HITS_PER_GROUP = 60
SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/~^@{}+-]{0,199}$")
TEXT_EXT = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".go", ".java", ".kt", ".rb", ".php", ".cs",
            ".rs", ".scala", ".swift", ".yml", ".yaml", ".tf", ".json", ".toml", ".xml", ".gradle", ".proto",
            ".graphql", ".gql", ".c", ".cc", ".cpp", ".h", ".hpp", ".sh", ".dockerfile"}

# (group, companion file, compiled pattern). Patterns only point a reconnaissance agent at code to read.
HINTS = [
    ("http-routes", "WEB-PROTOCOL-AND-AUTH.md", re.compile(
        r"\b(app|router|server|api)\.(get|post|put|patch|delete|all|use|route)\s*\(|@(Get|Post|Put|Patch|Delete|"
        r"Request)Mapping\b|@(Get|Post|Put|Patch|Delete|Controller)\(|@app\.(route|get|post|put|delete)\b|"
        r"\bpath\(\s*['\"]|http\.HandleFunc\(|\bHandleFunc\(|\bfastify\.|\bRoute::(get|post|put|delete)\b|"
        r"\bcreateServer\(|\b(req\.)?method\s*===?\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]|"
        r"\bexport\s+(async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b")),
    ("auth-and-sessions", "WEB-PROTOCOL-AND-AUTH.md", re.compile(
        r"\b(jwt|jsonwebtoken|passport|oauth|oidc|saml|session|bcrypt|argon2|csrf|requireAuth|isAuthenticated|"
        r"authorize|authorization|bearer|authenticate|@PreAuthorize|@Secured|login_required|permission_required)\b",
        re.I)),
    ("ci-and-release", "SUPPLY-CHAIN-AND-RELEASE.md", re.compile(
        r"^\s*(on:|pull_request_target|workflow_run|permissions:|uses:\s|secrets\.)")),
    ("cloud-and-containers", "CLOUD-AND-DEPLOYMENT.md", re.compile(
        r"^\s*(FROM\s|USER\s|resource\s+\"|kind:\s*(Deployment|Role|ClusterRole|Ingress|Service)\b|"
        r"\"Effect\"\s*:|privileged:\s*true|hostNetwork:)")),
    ("ai-and-llm", "AI-AND-LLM.md", re.compile(
        r"\b(openai|anthropic|langchain|llamaindex|@modelcontextprotocol|mcp\.server|ChatCompletion|"
        r"messages\.create|tool_choice|function_call)\b", re.I)),
    ("rpc-and-messaging", "PROTOCOLS-RPC-AND-MESSAGING.md", re.compile(
        r"\b(grpc|protobuf|graphql|apollo|kafka|rabbitmq|amqp|sqs|pubsub|nats|websocket|webhook)\b", re.I)),
    ("client-side", "CLIENT-SIDE.md", re.compile(
        r"(dangerouslySetInnerHTML|innerHTML\s*=|postMessage\(|addEventListener\(\s*['\"]message|"
        r"v-html|bypassSecurityTrust|localStorage\.)")),
    ("data-isolation", "DATA-ISOLATION-AND-LIFECYCLE.md", re.compile(
        r"\b(tenant|tenantId|tenant_id|org_id|orgId|owner|owner_id|ownerId|userId|user_id|account_id)\b")),
    ("file-and-process-sinks", "ATTACK-CLASSES.md", re.compile(
        r"\b(exec|execSync|spawn|child_process|subprocess|os\.system|Runtime\.getRuntime|eval|"
        r"readFile|writeFile|sendFile|open\(|unzip|extract|deserialize|pickle\.loads|yaml\.load)\b")),
    ("native-code", "MEMORY-SAFETY-AND-BINARY.md", re.compile(r"\b(unsafe\s*\{|memcpy|strcpy|malloc|ffi|cgo)\b")),
    ("desktop-mobile-ipc", "DESKTOP-MOBILE-AND-LOCAL-IPC.md", re.compile(
        r"\b(electron|ipcMain|ipcRenderer|contextBridge|deeplink|WebView|AndroidManifest|XPC|D-Bus|"
        r"unix_socket|AF_UNIX)\b")),
]


def git(path, *args):
    try:
        r = subprocess.run(["git", "-C", path] + list(args), capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def source_ref(path):
    commit = git(path, "rev-parse", "HEAD")
    status = git(path, "status", "--porcelain", "--untracked-files=normal")
    return {"commit": commit.strip() if commit else None,
            "dirty": bool(status.strip()) if status is not None else None,
            "vcs": "git" if commit else None}


def scope_from_since(path, since):
    if not SAFE_REF.match(since):
        raise ValueError("--since ref %r is not a plain git ref" % since)
    if git(path, "rev-parse", "--verify", "--quiet", "--end-of-options", since + "^{commit}") is None:
        raise ValueError("--since ref %r does not resolve to a commit in %s" % (since, path))
    out = git(path, "diff", "--name-only", "--end-of-options", since, "--") or ""
    untracked = git(path, "ls-files", "--others", "--exclude-standard") or ""
    return sorted(set(p for p in (out + untracked).splitlines() if p.strip()))


def iter_files(root):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            ext = os.path.splitext(name)[1].lower()
            if os.path.islink(full) or not (ext in TEXT_EXT or name == "Dockerfile" or name.startswith("Dockerfile.")):
                continue
            count += 1
            if count > MAX_FILES:
                return
            yield full


def recon_hints(root, scope):
    groups = dict((g, {"companion": c, "hits": [], "truncated": False}) for g, c, _ in HINTS)
    files = 0
    for full in iter_files(root):
        rel = os.path.relpath(full, root).replace(os.sep, "/")
        if scope and rel not in scope:
            continue
        try:
            if os.path.getsize(full) > MAX_FILE_BYTES:
                continue
            with open(full, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        files += 1
        is_workflow = rel.startswith(".github/workflows/")
        for group, _, pattern in HINTS:
            if group == "ci-and-release" and not is_workflow:
                continue
            bucket = groups[group]
            for n, line in enumerate(lines, 1):
                if pattern.search(line):
                    if len(bucket["hits"]) >= MAX_HITS_PER_GROUP:
                        bucket["truncated"] = True
                        break
                    bucket["hits"].append({"file": rel, "line": n, "text": line.strip()[:160]})
    return files, dict((g, b) for g, b in groups.items() if b["hits"])


def prior_runs(runs_root, current_run, repo):
    out = []
    try:
        names = sorted(n for n in os.listdir(runs_root) if n.startswith("security-run-"))
    except OSError:
        return out
    for name in names:
        run = os.path.join(runs_root, name)
        if os.path.abspath(run) == os.path.abspath(current_run):
            continue
        audit_dir = os.path.join(run, repo, "audit")
        files = [f for f in ("coverage-ledger.json", "findings.json", "run-metadata.json")
                 if os.path.isfile(os.path.join(audit_dir, f))]
        if "coverage-ledger.json" in files or "findings.json" in files:
            out.append({"path": audit_dir, "files": files})
    return out


def sandbox_status(audit_dir):
    if os.environ.get("JOB_SECURITY_SCAN_AUDIT_EXEC") != "1":
        return "source-only", {"enabled": False, "reason": "JOB_SECURITY_SCAN_AUDIT_EXEC is not 1"}
    probe = os.path.join(audit_dir, "agents", "sandbox-selftest", "scratch")
    os.makedirs(probe, exist_ok=True)
    r = subprocess.run([sys.executable, "-I", os.path.join(SCRIPT_DIR, "audit-sandbox.py"), "--self-test",
                        "--scratch", probe], capture_output=True, text=True)
    detail = (r.stdout.strip() or r.stderr.strip())[-2000:]
    if r.returncode == 0:
        return "sandboxed-source-and-local-only", {"enabled": True, "self_test": json.loads(r.stdout)}
    return "source-only", {"enabled": False, "reason": "sandbox self-test failed: " + detail}


TASK = """# Deep audit task - {repo}

Prepared by job-security-scan at {created}. Follow `references/audit/WORKFLOW.md` in the skill folder,
which adapts the method in `references/audit/METHOD.md` to this skill. Report only: never edit the target.

| Value | |
|---|---|
| Skill directory | `{skill}` |
| Target | `{target}` |
| Audit output directory | `{audit}` |
| Source ref | `{commit}`{dirty} |
| Profile | `{profile}` |
| Scope | {scope} |
| Budget (agent invocations) | {budget} |
| Execution policy | `{policy}` |
| Prior runs | {prior} |

1. Read `run-metadata.json` and `recon-hints.json` here. The hints are grep hits to start reading from, not
   findings and not coverage.
2. Phase 1-6 as in WORKFLOW.md: reconnaissance -> `architecture.md` + `coverage-ledger.json`
   (`python3 -I {skill}/scripts/audit-ledger.py seed units.json --out {audit}/coverage-ledger.json`),
   hunting waves, independent validation, `findings.json`, fresh-eyes verification.
3. Validate after every ledger or findings update:
   `python3 -I {skill}/scripts/validate-audit.py run {audit}`
4. Set `run_status` in `run-metadata.json` to `complete` or `incomplete` (+ `incomplete_reason`).
5. Regenerate the run's reports so the audit appears next to the scanner findings:
   `{regen}`
   (same scope as this run; it also merges the audit, or says why it could not)
"""


def main():
    ap = argparse.ArgumentParser(description="Prepare the deep audit of one repo")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--path", required=True, help="repository root to audit")
    ap.add_argument("--run-dir", required=True, help="the security-run-<datetime> folder")
    ap.add_argument("--runs-root", required=True, help="folder holding security-run-* folders")
    ap.add_argument("--profile", default="standard", choices=("quick", "standard", "deep"))
    ap.add_argument("--since", default="", help="scope to files changed since this git ref")
    ap.add_argument("--budget", default="", help="max agent invocations (empty = unset)")
    ap.add_argument("--config", default="")
    ap.add_argument("--baseline", default="", help="accepted-findings file used by this run")
    ap.add_argument("--workspace", default=".")
    args = ap.parse_args()

    target = os.path.abspath(args.path)
    audit_dir = os.path.join(os.path.abspath(args.run_dir), args.repo, "audit")
    os.makedirs(os.path.join(audit_dir, "agents"), exist_ok=True)
    budget = None
    if args.budget:
        if not args.budget.isdigit() or int(args.budget) < 1:
            print("error: --budget must be a positive integer", file=sys.stderr)
            return 2
        budget = int(args.budget)
    try:
        scope = scope_from_since(target, args.since) if args.since else []
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    policy, sandbox = sandbox_status(audit_dir)
    ref = source_ref(target)
    try:
        detected = ecosystems.detect(target, ecosystems.load_descriptors())
        eco = sorted(set(e["id"] for e in detected.get("ecosystems", [])))
    except Exception as exc:  # detection is a hint; never block preparation
        eco = ["detection failed: %s" % type(exc).__name__]
    files, hints = recon_hints(target, set(scope))
    priors = prior_runs(os.path.abspath(args.runs_root), args.run_dir, args.repo)
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    meta = {
        "run_id": "%s/%s" % (os.path.basename(os.path.abspath(args.run_dir)), args.repo),
        "repo": args.repo,
        "target": target,
        "source_ref": ref,
        "profile": args.profile,
        "scope_paths": scope,
        "since_ref": args.since or None,
        "budget": budget,
        "execution_policy": policy,
        "sandbox": sandbox,
        "selected_companions": [],
        "prior_runs": priors,
        "shared_file_owner": "parent",
        "run_status": "awaiting_agent",
        "created_at": created,
    }
    hints_doc = {"target": target, "ecosystems": eco, "files_scanned": files, "scope_paths": scope,
                 "groups": hints,
                 "note": "Grep hits to start reconnaissance from. Not findings, not coverage evidence."}
    with open(os.path.join(audit_dir, "run-metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(audit_dir, "recon-hints.json"), "w", encoding="utf-8") as fh:
        json.dump(hints_doc, fh, indent=2)
        fh.write("\n")
    skill = os.path.dirname(SCRIPT_DIR)
    run_abs = os.path.abspath(args.run_dir)
    regen = ["python3", "-I", os.path.join(skill, "scripts", "generate-report.py"), "--results-dir", run_abs,
             "--out-dir", run_abs, "--config", os.path.abspath(args.config) if args.config else "<config>",
             "--workspace", os.path.abspath(args.workspace), "--repos-root", os.path.dirname(target),
             "--home", os.path.expanduser("~"), "--profile", args.profile, "--keep-verdicts"]
    if args.since:
        regen += ["--since", args.since, "--changed-files", os.path.join(run_abs, "changed-files.json")]
    if args.baseline:
        regen += ["--baseline", os.path.abspath(args.baseline)]
    with open(os.path.join(audit_dir, "AGENT-TASK.md"), "w", encoding="utf-8") as fh:
        fh.write(TASK.format(
            repo=args.repo, created=created, skill=skill, target=target, audit=audit_dir,
            commit=ref["commit"] or "not a git repository", dirty=" (dirty worktree)" if ref["dirty"] else "",
            profile=args.profile,
            scope=("%d file(s) changed since `%s`" % (len(scope), args.since)) if args.since else "whole repository",
            budget=budget if budget is not None else "unset", policy=policy,
            prior=", ".join("`%s`" % p["path"] for p in priors) or "none",
            regen=" ".join(shlex.quote(a) for a in regen)))
    print("prepared %s (profile %s, %s, %d hint group(s), %d prior run(s))"
          % (audit_dir, args.profile, policy, len(hints), len(priors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
