#!/usr/bin/env python3
"""Execution-based automation test for the speckit-auto skill.

This ACTUALLY runs the speckit-auto skill through a coding agent (OpenCode by default,
Claude Code and GitHub Copilot also supported) against a real scenario — building a
to-do application — then validates the on-disk outcomes and prints a coverage report
with per-check PASS/FAIL detail.

How it works:
    1. Installs the current repo's skills (speckit-auto, speckit-code-review,
       jira-to-speckit) into the agent's skill directory.
    2. Creates a fresh git repo seeded as a minimal to-do app (package.json +
       docs/guidelines/architecture.md + an initial commit).
    3. Resolves the provider (default superpowers — its skills are already installed)
       by writing <repo>/.speckit/integration.json, so no first-run prompt.
    4. Invokes the agent headlessly to run `speckit-auto --yolo` on the to-do
       requirement.
    5. Validates the artifacts the pipeline should have produced and reports
       coverage (pass/fail per check + summary + token cost).

Usage:
    python3 tools/test_speckit_auto.py                     # full run (local)
    python3 tools/test_speckit_auto.py --model opencode-go/deepseek-v4-pro
    python3 tools/test_speckit_auto.py --timeout 900 --keep
    python3 tools/test_speckit_auto.py --json

Note: this requires an agent CLI with credentials (e.g. `opencode auth login`). It is
a local/developer tool — not wired into CI, where no agent credentials exist.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILLS_TO_INSTALL = ["speckit-auto", "speckit-code-review", "jira-to-speckit"]

SCENARIO = {
    "name": "build-a-todo-application",
    "requirement": (
        "Build a to-do application that lets users create, edit, complete, and delete tasks, "
        "organize tasks into lists, and set due dates. Keep it small: plain Node.js, no "
        "external dependencies, use the built-in `node --test` runner."
    ),
    "feature_slug": "001-todo-app",
}

SEED_FILES: dict[str, str] = {
    "README.md": "# Todo App\n\nA minimal to-do application.\n",
    "package.json": json.dumps(
        {
            "name": "todo-app",
            "version": "0.0.0",
            "description": "Minimal to-do application (no external deps)",
            "scripts": {"test": "node --test"},
        },
        indent=2,
    )
    + "\n",
    "docs/guidelines/architecture.md": (
        "# Architecture\n\n"
        "## Repository Map\n\n"
        "- `src/` -> backend (Node.js)\n"
        "- `test/` -> tests\n\n"
        "## Pattern\n\n"
        "Layered Node.js app: model -> service -> CLI.\n"
    ),
}


def log(msg: str) -> None:
    print(msg, flush=True)


def sh(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")
    return proc


def install_skills(skills_dir: Path) -> list[str]:
    skills_dir.mkdir(parents=True, exist_ok=True)
    installed = []
    for name in SKILLS_TO_INSTALL:
        src = REPO_ROOT / name
        if not (src / "SKILL.md").exists():
            raise RuntimeError(f"skill not found in repo: {name}")
        dst = skills_dir / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        installed.append(str(dst))
    return installed


def setup_workspace(workdir: Path) -> Path:
    ws = workdir / "todo-app"
    ws.mkdir(parents=True, exist_ok=True)
    for rel, content in SEED_FILES.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    sh(["git", "init", "-b", "main"], ws)
    sh(["git", "config", "user.email", "test@example.com"], ws)
    sh(["git", "config", "user.name", "Automation Test"], ws)
    sh(["git", "add", "-A"], ws)
    sh(["git", "commit", "-m", "chore: seed todo app"], ws)
    # Provider config (superpowers) — avoid the first-run selection prompt.
    speckit = ws / ".speckit"
    speckit.mkdir(exist_ok=True)
    (speckit / "integration.json").write_text(
        json.dumps({"integration": "superpowers", "updated_at": "2026-01-01T00:00:00Z",
                    "set_by": "speckit-auto"}), encoding="utf-8"
    )
    return ws


def run_agent(agent: str, model: str, ws: Path, prompt: str, timeout: int) -> dict:
    if agent == "opencode":
        cmd = ["opencode", "run", "--dir", str(ws), "--auto", "--format", "json"]
        if model:
            cmd += ["--model", model]
        cmd += [prompt]
    elif agent == "claude":
        cmd = ["claude", "-p", "--output-format", "json", prompt]
        if model:
            cmd += ["--model", model]
    elif agent == "copilot":
        cmd = ["copilot", "run", prompt]
        if model:
            cmd += ["--model", model]
    else:
        raise ValueError(f"unsupported agent: {agent}")

    log(f"[run] {agent} model={model or 'default'} timeout={timeout}s")
    start = time.time()
    text_parts: list[str] = []
    total_tokens: dict = {}
    total_cost = 0.0
    raw_lines = 0
    timed_out = False
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, _err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _err = proc.communicate()
        timed_out = True

    (ws / ".agent-output.jsonl").write_text(out, encoding="utf-8")

    def scan(obj: object) -> None:
        nonlocal total_cost, total_tokens
        if not isinstance(obj, dict):
            return
        if isinstance(obj.get("text"), str) and obj.get("type") in (None, "text"):
            text_parts.append(obj["text"])
        if isinstance(obj.get("cost"), (int, float)):
            total_cost = max(total_cost, float(obj["cost"]))
        if isinstance(obj.get("tokens"), dict):
            total_tokens = obj["tokens"]
        for v in obj.values():
            if isinstance(v, dict):
                scan(v)

    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        raw_lines += 1
        try:
            scan(json.loads(line))
        except json.JSONDecodeError:
            continue

    elapsed = round(time.time() - start)
    return {
        "text": "\n".join(text_parts),
        "tokens": total_tokens,
        "cost": total_cost,
        "elapsed": elapsed,
        "timed_out": timed_out,
        "events": raw_lines,
    }


def find_worktree(ws: Path) -> Path:
    """Return the linked worktree the pipeline ran in, else the base checkout."""
    out = sh(["git", "worktree", "list", "--porcelain"], ws, check=False).stdout
    for line in out.splitlines():
        if line.startswith("worktree "):
            p = Path(line[len("worktree "):])
            if p.resolve() != ws.resolve():
                return p
    return ws


def find(ws: Path, pattern: str) -> list[Path]:
    return [Path(p) for p in glob.glob(str(ws / pattern), recursive=True)]


def validate(wt: Path, ws: Path, run: dict) -> list[dict]:
    checks: list[dict] = []

    def add(cid: str, title: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "title": title, "status": "pass" if ok else "fail",
                       "detail": detail})

    specs = find(wt, "specs/**/spec.md")
    plans = find(wt, "specs/**/plan.md")
    add("V01", "spec.md produced (design spec)",
        bool(specs), ", ".join(str(p.relative_to(wt)) for p in specs) or "none")
    add("V02", "plan.md produced (implementation plan)",
        bool(plans), ", ".join(str(p.relative_to(wt)) for p in plans) or "none")

    src = [p for p in find(wt, "src/**/*") if p.is_file()]
    add("V03", "implementation code written under src/",
        bool(src), f"{len(src)} file(s)")

    tests = [p for p in find(wt, "**/*.test.js") if ".opencode" not in str(p)]
    add("V04", "tests written (TDD via node --test)",
        bool(tests), ", ".join(str(p.relative_to(wt)) for p in tests) or "none")

    log_ = sh(["git", "log", "--oneline"], wt, check=False).stdout.strip().splitlines()
    add("V05", "commits made on top of the seed",
        len(log_) >= 2, f"{len(log_)} commit(s): {'; '.join(log_[:4])}")

    state = wt / ".speckit" / "run-state.json"
    add("V06", ".speckit/run-state.json persisted",
        state.exists(), str(state.relative_to(wt)) if state.exists() else "none")

    reviews = find(wt, ".speckit/review-*/state.json")
    add("V09", "speckit-code-review gate ran (state.json written)",
        bool(reviews), ", ".join(str(p.relative_to(wt)) for p in reviews) or "none")

    wt_list = sh(["git", "worktree", "list"], ws, check=False).stdout.strip()
    branch = sh(["git", "branch", "--show-current"], wt, check=False).stdout.strip()
    add("V07", "isolated worktree / feature branch created",
        (".worktrees" in wt_list) or (branch and branch != "main"),
        f"branch={branch}; worktrees={wt_list.replace(chr(10), ' | ')}")

    add("V08", "agent run completed without timeout",
        not run["timed_out"],
        f"elapsed={run['elapsed']}s events={run['events']} "
        f"tokens={run['tokens']} cost={run['cost']:.4f}")
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Execution-based test of speckit-auto (build a to-do app)")
    ap.add_argument("--agent", default="opencode", choices=["opencode", "claude", "copilot"])
    ap.add_argument("--model", default="opencode-go/deepseek-v4-pro")
    ap.add_argument("--timeout", type=int, default=1200, help="agent run timeout in seconds")
    ap.add_argument("--workdir", default=None, help="workspace parent dir (default: temp)")
    ap.add_argument("--skills-dir", default=str(Path.home() / ".config" / "opencode" / "skills"))
    ap.add_argument("--no-install", action="store_true", help="skip installing repo skills")
    ap.add_argument("--keep", action="store_true", help="keep the workspace for inspection")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args(argv)

    agent_bin = shutil.which(args.agent)
    if not agent_bin:
        log(f"ERROR: agent CLI not found: {args.agent} (install/login first)")
        return 2

    skills_dir = Path(args.skills_dir)
    if not args.no_install:
        installed = install_skills(skills_dir)
        log(f"[install] copied repo skills -> {skills_dir}")
        for p in installed:
            log(f"    {p}")

    tmp = None
    if args.workdir:
        parent = Path(args.workdir)
        parent.mkdir(parents=True, exist_ok=True)
    else:
        tmp = tempfile.TemporaryDirectory()
        parent = Path(tmp.name)

    ws = setup_workspace(parent)
    log(f"[workspace] {ws}")

    prompt = (
        f"Run the speckit-auto skill with --yolo on this requirement: {SCENARIO['requirement']}"
    )
    run = run_agent(args.agent, args.model, ws, prompt, args.timeout)
    log(f"[done] elapsed={run['elapsed']}s timed_out={run['timed_out']} "
        f"tokens={run['tokens']} cost={run['cost']:.4f}")
    if run["text"]:
        log(f"[agent final text] {run['text'][-800:]}")

    wt = find_worktree(ws)
    log(f"[worktree] {wt}")
    checks = validate(wt, ws, run)
    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    coverage = (passed / len(checks) * 100) if checks else 0.0

    if args.as_json:
        print(json.dumps({
            "scenario": SCENARIO, "agent": args.agent, "model": args.model,
            "workspace": str(ws), "worktree": str(wt), "elapsed_s": run["elapsed"],
            "tokens": run["tokens"], "cost": run["cost"],
            "checks": checks, "passed": passed, "failed": failed,
            "coverage_pct": round(coverage, 1),
        }, indent=2))
    else:
        print("\n" + "=" * 78)
        print(f"Coverage report: speckit-auto live execution")
        print(f"Scenario: {SCENARIO['name']}  agent={args.agent} model={args.model or 'default'}")
        print(f"Workspace: {ws}")
        print(f"Worktree : {wt}")
        print("=" * 78)
        for c in checks:
            mark = "PASS" if c["status"] == "pass" else "FAIL"
            print(f"  {mark}  {c['id']}  {c['title']}")
            if c["status"] == "fail" or args.keep:
                print(f"         -> {c['detail']}")
        print("-" * 78)
        print(f"Summary: {passed} passed, {failed} failed, {len(checks)} total  "
              f"(coverage {coverage:.1f}%)  |  elapsed {run['elapsed']}s  "
              f"cost ${run['cost']:.4f}")
        print("-" * 78)

    if tmp is not None and not args.keep:
        tmp.cleanup()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
