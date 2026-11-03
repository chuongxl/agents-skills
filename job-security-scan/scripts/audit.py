#!/usr/bin/env python3
"""audit.py - the deterministic half of the agent-driven code audit (SKILL.md Phase 10).

  python3 -I scripts/audit.py plan RUN_DIR [--budget N]
      Coverage plan in RUN_DIR/triage/audit-plan.json: one unit per repo x attack class (repos over 300 source
      files are split by top-level folder), starting paths, known scanner findings per repo. Units over the
      budget (12 on request, 24 with --profile deep) are recorded as deferred.
  python3 -I scripts/audit.py prompt RUN_DIR UNIT_ID       the exact hunter prompt for one planned unit
  python3 -I scripts/audit.py critic-prompt RUN_DIR        the coverage critic prompt
  python3 -I scripts/audit.py add-units RUN_DIR REPLY.json the critic's missing units (one extra wave)
  python3 -I scripts/audit.py collect RUN_DIR [RESULTS_DIR]
      Checks every hunter reply in RESULTS_DIR (default RUN_DIR/triage/audit-results) as a whole, turns
      candidates into code-audit findings (<repo>/code-audit.json), writes triage/audit-ledger.json and
      regenerates the reports. Verdicts already in the report are kept.

Prompts, attack classes and formats live in references/code-audit.md. Report-only: nothing in any repository is
run or changed. Exit codes: 0 done, 1 invalid input, 2 usage. Stdlib only; Python 3.8+.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))

import report_model  # noqa: E402
from shaihulud.findings import redact  # noqa: E402

REFERENCE = SKILL_DIR / "references" / "code-audit.md"
STANDARD = ["injection", "access-control", "obvious", "files-resources", "crypto-secrets", "business-logic"]
DEEP = STANDARD + ["feature-abuse", "chained-trust", "wildcard"]
BUDGET = {"standard": 12, "deep": 24}
SPLIT_AT = 300
MAX_START = 20
MAX_KNOWN = 30
MAX_TEXT = 1500
MAX_LIST = 200
MAX_RESULT_BYTES = 1024 * 1024
SOURCE_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".java", ".kt", ".rb", ".php", ".cs",
              ".rs", ".scala", ".swift", ".c", ".cc", ".cpp", ".h", ".sh", ".vue", ".svelte", ".erb", ".ex", ".exs"}
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target", ".venv", "venv", "__pycache__", "coverage",
             ".next", "out", ".tox", ".idea", ".vscode"}
ENTRY = re.compile(r"(route|router|controller|handler|api|server|app|main|index|cli|cmd|view|urls|endpoint|"
                   r"resolver|middleware|auth|admin|upload|download|webhook)", re.IGNORECASE)
REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
RESULT_KEYS = {"coverage_id", "disposition", "reviewed_paths", "checks", "candidates", "hardening", "unresolved",
               "uncovered"}
CANDIDATE_KEYS = {"title", "type", "severity", "boundary", "root_cause", "trace", "evidence"}
TRACE_KEYS = {"role", "file", "line", "note"}


def fail(msg):
    print("audit: %s" % msg, file=sys.stderr)
    return 1


# ── reference blocks ─────────────────────────────────────────────────────────

def blocks():
    text = REFERENCE.read_text(encoding="utf-8")
    out = {}
    for kind, name, body in re.findall(r"<!-- (block|class):([a-z-]+) -->\n(.*?)\n<!-- /(?:block|class) -->",
                                       text, re.S):
        out["%s:%s" % (kind, name)] = body.strip()
    return out


# ── run folder ───────────────────────────────────────────────────────────────

def load_doc(run_dir):
    doc = report_model.load_report(Path(run_dir) / "security-report.json")
    if doc is None:
        raise SystemExit(fail("%s/security-report.json is not a valid v2 report - run run-scan.sh first" % run_dir))
    return doc


def plan_path(run_dir):
    return Path(run_dir) / "triage" / "audit-plan.json"


def load_plan(run_dir):
    try:
        return json.loads(plan_path(run_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit(fail("no audit plan - run: audit.py plan %s" % run_dir))


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def repo_root(doc, repo):
    return Path((doc.get("run") or {}).get("repos_root") or ".") / repo


def source_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            if os.path.splitext(fn)[1].lower() in SOURCE_EXT:
                p = Path(dirpath) / fn
                if not p.is_symlink():
                    out.append(p.relative_to(root).as_posix())
    return out


def entry_points(files, root):
    hits = [f for f in files if ENTRY.search(f)]
    try:
        pkg = json.loads((Path(root) / "package.json").read_text(encoding="utf-8"))
        for k in ("main", "bin"):
            v = pkg.get(k)
            for p in ([v] if isinstance(v, str) else list(v.values()) if isinstance(v, dict) else []):
                p = os.path.normpath(str(p)).replace(os.sep, "/")
                if p in files and p not in hits:
                    hits.insert(0, p)
    except (OSError, ValueError, AttributeError):
        pass
    hits.sort(key=lambda f: (f.count("/"), len(f)))
    return hits[:MAX_START] or files[:MAX_START]


def known_findings(doc):
    out = {}
    for f in doc["findings"]:
        if f.get("scanner") == "code-audit" or f.get("verdict") == "rejected":
            continue
        where = "%s:%s" % (f.get("file") or "", f.get("line")) if f.get("line") else (f.get("file") or "")
        text = "%s %s %s %s" % (f.get("severity"), f.get("rule_id"), where, f.get("title") or "")
        out.setdefault(f["repo"], [])
        if len(out[f["repo"]]) < MAX_KNOWN:
            out[f["repo"]].append(redact(text.strip())[:200])
    return out


# ── plan ─────────────────────────────────────────────────────────────────────

def cmd_plan(run_dir, budget=None):
    doc = load_doc(run_dir)
    profile = (doc.get("run") or {}).get("profile") or "standard"
    if profile == "quick":
        return fail("the code audit runs with --profile deep or on request in standard; not in quick")
    classes = DEEP if profile == "deep" else STANDARD
    budget = budget if budget is not None else BUDGET["deep" if profile == "deep" else "standard"]
    repos = [r["name"] for r in doc["repos"] if r["name"] != "this machine" and repo_root(doc, r["name"]).is_dir()]
    areas = {}
    for repo in repos:
        root = repo_root(doc, repo)
        files = source_files(root)
        if len(files) > SPLIT_AT:
            groups = {}
            for f in files:
                groups.setdefault(f.split("/", 1)[0] if "/" in f else ".", []).append(f)
            areas[repo] = [(a, groups[a]) for a in sorted(groups)]
        else:
            areas[repo] = [(".", files)]
    # priority: class order first, then repo and area, so a small budget spreads across repos
    units = []
    for cls in classes:
        for repo in repos:
            for area, files in areas[repo]:
                units.append({"id": "%s/%s/%s" % (repo, area, cls), "repo": repo, "area": area, "attack_class": cls,
                              "starting_paths": entry_points(files, repo_root(doc, repo)), "wave": 1})
    for i, u in enumerate(units):
        u["status"], u["reason"] = ("planned", "") if i < budget else ("deferred", "over the budget of %d units" % budget)
    plan = {"schema_version": 1, "run_dir": doc["run_dir"], "profile": profile, "budget": budget,
            "classes": classes, "critic_waves": 0, "units": units, "known_findings": known_findings(doc)}
    save_json(plan_path(run_dir), plan)
    planned = sum(u["status"] == "planned" for u in units)
    print("audit: %d unit(s) planned, %d deferred (budget %d, profile %s) -> %s"
          % (planned, len(units) - planned, budget, profile, plan_path(run_dir)))
    return 0


# ── prompts ──────────────────────────────────────────────────────────────────

def cmd_prompt(run_dir, unit_id):
    plan = load_plan(run_dir)
    doc = load_doc(run_dir)
    unit = next((u for u in plan["units"] if u["id"] == unit_id), None)
    if unit is None:
        return fail("no unit %r in the plan" % unit_id)
    if unit["status"] != "planned":
        return fail("unit %s is %s (%s), not planned" % (unit_id, unit["status"], unit.get("reason") or ""))
    b = blocks()
    known = plan["known_findings"].get(unit["repo"], [])
    unit_view = dict((k, unit[k]) for k in ("id", "repo", "area", "attack_class", "starting_paths"))
    parts = [b["block:hunter-rules"], "", "## Your unit", "",
             "Repository folder: %s" % repo_root(doc, unit["repo"]),
             "Area: %s" % ("the whole repository" if unit["area"] == "." else "the %s/ folder" % unit["area"]),
             json.dumps(unit_view, indent=2), "", "## Attack class", "", b["class:" + unit["attack_class"]], "",
             "## Known findings (already reported by the scanners; do not repeat)", ""]
    parts += ["- %s" % k for k in known] or ["- none"]
    parts += ["", "## Result format", "", b["block:result-format"]]
    sys.stdout.write("\n".join(parts) + "\n")
    return 0


def cmd_critic_prompt(run_dir):
    plan = load_plan(run_dir)
    doc = load_doc(run_dir)
    ledger = load_ledger(run_dir)
    status = dict((u["id"], u) for u in ledger.get("units", []))
    lines = [blocks()["block:critic"], "", "## Coverage plan", "",
             "Attack class ids: %s" % ", ".join(DEEP), ""]
    for repo in sorted({u["repo"] for u in plan["units"]}):
        lines.append("Repository %s: %s" % (repo, repo_root(doc, repo)))
    lines.append("")
    for u in plan["units"]:
        s = status.get(u["id"], {})
        lines.append("- %s [%s%s] start: %s%s" % (
            u["id"], s.get("status") or u["status"], (": " + u["reason"]) if u.get("reason") else "",
            ", ".join(u["starting_paths"][:8]) or "-",
            ("; reviewed: " + ", ".join(s.get("reviewed_paths", [])[:12])) if s.get("reviewed_paths") else ""))
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def _safe_rel(path):
    p = str(path)
    if not p or p.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", p) or "\x00" in p:
        return None
    norm = os.path.normpath(p).replace(os.sep, "/")
    return None if norm == ".." or norm.startswith("../") or norm == "." else norm


def _inside(root, rel):
    root = os.path.realpath(str(root))
    full = os.path.realpath(os.path.join(root, rel))
    return full.startswith(root + os.sep)


def cmd_add_units(run_dir, reply_path):
    plan = load_plan(run_dir)
    doc = load_doc(run_dir)
    if plan.get("critic_waves", 0) >= 1:
        return fail("the critic's units were already added (one extra wave per run)")
    try:
        data = json.loads(Path(reply_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return fail("critic reply is not plain JSON (%s) - nothing changed" % exc)
    missing = data.get("missing_units") if isinstance(data, dict) else None
    if not isinstance(missing, list):
        return fail('expected {"missing_units": [...]} - nothing changed')
    repos = {u["repo"] for u in plan["units"]}
    errors, new = [], []
    for i, m in enumerate(missing):
        where = "missing_units[%d]" % i
        if not isinstance(m, dict):
            errors.append("%s: must be an object" % where)
            continue
        repo, cls = m.get("repo"), m.get("attack_class")
        if not isinstance(repo, str) or not REPO_RE.match(repo) or repo not in repos:
            errors.append("%s: unknown repo %r" % (where, repo))
            continue
        if cls not in DEEP:
            errors.append("%s: unknown attack class %r" % (where, cls))
            continue
        paths = m.get("starting_paths") if isinstance(m.get("starting_paths"), list) else []
        good = []
        for p in paths[:MAX_START]:
            rel = _safe_rel(p) if isinstance(p, str) else None
            if rel is None or not _inside(repo_root(doc, repo), rel) or not (repo_root(doc, repo) / rel).exists():
                errors.append("%s: starting path %r is not a file in %s" % (where, p, repo))
                break
            good.append(rel)
        else:
            new.append({"repo": repo, "attack_class": cls, "starting_paths": good,
                        "reason_added": redact(str(m.get("reason") or ""))[:300]})
    if errors:
        print("audit: critic reply refused, nothing changed:", file=sys.stderr)
        for e in errors[:30]:
            print("  - %s" % e, file=sys.stderr)
        return 1
    existing = {(u["repo"], u["attack_class"]) for u in plan["units"]}
    planned = sum(u["status"] == "planned" for u in plan["units"])
    added = 0
    for n, m in enumerate(new, 1):
        if (m["repo"], m["attack_class"]) in existing:
            continue                          # that repo and class already have a unit
        uid = "%s/critic-%d/%s" % (m["repo"], n, m["attack_class"])
        unit = {"id": uid, "repo": m["repo"], "area": ".", "attack_class": m["attack_class"],
                "starting_paths": m["starting_paths"], "wave": 2, "reason_added": m["reason_added"]}
        if planned < plan["budget"]:
            unit["status"], unit["reason"] = "planned", ""
            planned += 1
        else:
            unit["status"], unit["reason"] = "deferred", "over the budget of %d units" % plan["budget"]
        plan["units"].append(unit)
        existing.add((m["repo"], m["attack_class"]))
        added += 1
    plan["critic_waves"] = 1
    save_json(plan_path(run_dir), plan)
    print("audit: %d unit(s) added from the critic (%d planned overall, budget %d)" % (added, planned, plan["budget"]))
    return 0


# ── collect ──────────────────────────────────────────────────────────────────

def ledger_path(run_dir):
    return Path(run_dir) / "triage" / "audit-ledger.json"


def load_ledger(run_dir):
    try:
        return json.loads(ledger_path(run_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _text(value, limit=MAX_TEXT):
    return redact(str(value).strip())[:limit]


def _str_list(value, where, errors, limit=MAX_LIST):
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        errors.append("%s must be a list of text" % where)
        return []
    return [_text(x, 400) for x in value[:limit]]


def _line_count(path):
    try:
        if path.stat().st_size > 25 * 1024 * 1024:
            return 0
        with open(str(path), "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def check_result(data, unit, root):
    """(clean result, None) or (None, reason)."""
    if not isinstance(data, dict):
        return None, "not a JSON object"
    extra = sorted(set(data) - RESULT_KEYS)
    if extra:
        return None, "unknown field(s) %s" % ", ".join(extra)
    errors = []
    disposition = data.get("disposition")
    if disposition not in ("covered", "candidate", "blocked"):
        return None, "disposition must be covered, candidate or blocked"
    reviewed = data.get("reviewed_paths")
    if not isinstance(reviewed, list) or not reviewed:
        return None, "reviewed_paths must list the files read"
    paths = []
    for p in reviewed[:MAX_LIST]:
        rel = _safe_rel(p) if isinstance(p, str) else None
        if rel is None or not _inside(root, rel) or not (root / rel).exists():
            return None, "reviewed path %r is not in the repository" % (p,)
        paths.append(rel)
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks or not all(isinstance(c, dict) for c in checks):
        return None, "checks must list what was checked"
    clean_checks = [{"invariant": _text(c.get("invariant", ""), 400), "result": _text(c.get("result", ""), 600)}
                    for c in checks[:50]]
    hardening = _str_list(data.get("hardening", []), "hardening", errors, 30)
    unresolved = _str_list(data.get("unresolved", []), "unresolved", errors, 30)
    uncovered = _str_list(data.get("uncovered", []), "uncovered", errors, 30)
    cands = data.get("candidates", [])
    if not isinstance(cands, list):
        return None, "candidates must be a list"
    if errors:
        return None, "; ".join(errors)
    if disposition == "covered" and cands:
        return None, "a covered unit must not carry candidates"
    if disposition == "candidate" and not cands:
        return None, "disposition candidate needs at least one candidate"
    if disposition == "blocked" and (cands or not unresolved):
        return None, "a blocked unit needs 'unresolved' facts and no candidates"
    clean_cands = []
    for i, c in enumerate(cands[:20]):
        where = "candidates[%d]" % i
        if not isinstance(c, dict):
            return None, "%s must be an object" % where
        extra = sorted(set(c) - CANDIDATE_KEYS)
        if extra:
            return None, "%s: unknown field(s) %s" % (where, ", ".join(extra))
        for k in ("title", "boundary", "root_cause", "evidence"):
            if not isinstance(c.get(k), str) or not c[k].strip():
                return None, "%s: %s is required" % (where, k)
        if c.get("type", "sast") not in ("sast", "secret"):
            return None, "%s: type must be sast or secret" % where
        if c.get("severity") not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            return None, "%s: severity must be CRITICAL, HIGH, MEDIUM or LOW" % where
        trace = c.get("trace")
        if not isinstance(trace, list) or not trace:
            return None, "%s: trace from entrypoint to sink is required" % where
        steps = []
        for j, t in enumerate(trace[:30]):
            if not isinstance(t, dict) or set(t) - TRACE_KEYS:
                return None, "%s.trace[%d]: role, file, line, note only" % (where, j)
            rel = _safe_rel(t.get("file")) if isinstance(t.get("file"), str) else None
            line = t.get("line")
            if rel is None or not _inside(root, rel) or not (root / rel).is_file():
                return None, "%s.trace[%d]: file %r is not in the repository" % (where, j, t.get("file"))
            if not isinstance(line, int) or isinstance(line, bool) or line < 1 or line > _line_count(root / rel):
                return None, "%s.trace[%d]: line %r is not a line of %s" % (where, j, line, rel)
            if t.get("role") not in ("entrypoint", "propagation", "sink"):
                return None, "%s.trace[%d]: role must be entrypoint, propagation or sink" % (where, j)
            steps.append({"role": t["role"], "file": rel, "line": line, "note": _text(t.get("note", ""), 300)})
        if steps[-1]["role"] != "sink" or (len(steps) > 1 and steps[0]["role"] != "entrypoint"):
            return None, "%s: trace must start at the entrypoint and end at the sink" % where
        clean_cands.append({"title": _text(c["title"], 160), "type": c.get("type", "sast"), "severity": c["severity"],
                            "boundary": _text(c["boundary"], 400), "root_cause": _text(c["root_cause"], 600),
                            "evidence": _text(c["evidence"]), "trace": steps})
    return {"disposition": disposition, "reviewed_paths": paths, "checks": clean_checks, "candidates": clean_cands,
            "hardening": hardening, "unresolved": unresolved, "uncovered": uncovered}, None


def cmd_collect(run_dir, results_dir=None):
    run_dir = Path(run_dir)
    doc = load_doc(run_dir)
    plan = load_plan(run_dir)
    results_dir = Path(results_dir) if results_dir else run_dir / "triage" / "audit-results"
    units = dict((u["id"], u) for u in plan["units"])
    seen, rejected, accepted = set(), [], {}
    files = sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []
    for path in files:
        try:
            if path.stat().st_size > MAX_RESULT_BYTES:
                raise ValueError("larger than %d bytes" % MAX_RESULT_BYTES)
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            uid = _guess_unit(path, units)
            rejected.append({"file": path.name, "unit": uid, "reason": _text("not plain JSON: %s" % exc, 300)})
            continue
        uid = data.get("coverage_id") if isinstance(data, dict) else None
        unit = units.get(uid) if isinstance(uid, str) else None
        if unit is None or unit["status"] != "planned":
            rejected.append({"file": path.name, "unit": uid if isinstance(uid, str) else None,
                             "reason": "coverage_id %r is not a planned unit" % (uid,)})
            continue
        if uid in seen:
            rejected.append({"file": path.name, "unit": uid, "reason": "second result for this unit"})
            accepted.pop(uid, None)
            continue
        seen.add(uid)
        clean, reason = check_result(data, unit, repo_root(doc, unit["repo"]))
        if clean is None:
            rejected.append({"file": path.name, "unit": uid, "reason": _text(reason, 300)})
            continue
        accepted[uid] = clean
    failed = {r["unit"] for r in rejected if r.get("unit") in units}
    ledger_units, by_repo = [], {}
    for u in plan["units"]:
        entry = {"id": u["id"], "repo": u["repo"], "area": u["area"], "attack_class": u["attack_class"],
                 "wave": u.get("wave", 1), "reason": u.get("reason") or ""}
        res = accepted.get(u["id"])
        if u["status"] == "deferred":
            entry["status"] = "deferred"
        elif res is not None:
            entry.update(status=res["disposition"], reviewed_paths=res["reviewed_paths"], checks=res["checks"],
                         candidates=len(res["candidates"]), hardening=res["hardening"],
                         unresolved=res["unresolved"], uncovered=res["uncovered"])
            for c in res["candidates"]:
                sink = c["trace"][-1]
                by_repo.setdefault(u["repo"], []).append({
                    "unit": u["id"], "attack_class": u["attack_class"], "title": c["title"], "type": c["type"],
                    "severity": c["severity"], "file": sink["file"], "line": sink["line"], "boundary": c["boundary"],
                    "root_cause": c["root_cause"], "evidence": c["evidence"], "trace": c["trace"]})
        elif u["id"] in failed:
            entry["status"] = "failed"
        else:
            entry["status"] = "not-run"
        ledger_units.append(entry)
    repos = {u["repo"] for u in plan["units"]}
    for repo in repos:
        out = run_dir / repo / "code-audit.json"
        if by_repo.get(repo):
            save_json(out, {"scanner": "code-audit", "repo": repo, "candidates": by_repo[repo]})
        elif out.exists():
            out.unlink()
    ledger = {"schema_version": 1, "profile": plan["profile"], "budget": plan["budget"], "classes": plan["classes"],
              "units": ledger_units, "rejected_results": rejected}
    save_json(ledger_path(run_dir), ledger)
    rc = regenerate(run_dir, doc)
    counts = {}
    for e in ledger_units:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print("audit: %s; %d candidate(s); %d reply(ies) refused" % (
        ", ".join("%d %s" % (n, s) for s, n in sorted(counts.items())),
        sum(len(v) for v in by_repo.values()), len(rejected)))
    for r in rejected:
        print("  refused %s (%s): %s" % (r["file"], r.get("unit") or "?", r["reason"]))
    return rc


def _guess_unit(path, units):
    try:
        m = re.search(r'"coverage_id"\s*:\s*"([^"]{1,200})"', path.read_text(encoding="utf-8", errors="replace")[:20000])
    except OSError:
        return None
    return m.group(1) if m and m.group(1) in units else None


def regenerate(run_dir, doc):
    """Re-run generate-report.py for this run with the arguments recorded in the report."""
    run = doc.get("run") or {}
    args = [sys.executable, "-I", str(SCRIPT_DIR / "generate-report.py"), "--results-dir", str(run_dir),
            "--out-dir", str(run_dir), "--config", doc.get("config") or "", "--profile", run.get("profile") or "standard"]
    for flag, key in (("--workspace", "workspace"), ("--repos-root", "repos_root"), ("--home", "home")):
        if run.get(key):
            args += [flag, run[key]]
    if run.get("since"):
        args += ["--since", run["since"]]
        if (Path(run_dir) / "changed-files.json").is_file():
            args += ["--changed-files", str(Path(run_dir) / "changed-files.json")]
    elif run.get("partial"):
        args.append("--partial")
    r = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    (Path(run_dir) / "report.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode != 0:
        print("audit: report regeneration failed - see %s/report.log" % run_dir, file=sys.stderr)
    return 0 if r.returncode == 0 else 1


def main(argv):
    args = argv[1:]
    if len(args) >= 2 and args[0] == "plan":
        budget = None
        if len(args) == 4 and args[2] == "--budget" and args[3].isdigit():
            budget = int(args[3])
        elif len(args) != 2:
            print(__doc__, file=sys.stderr)
            return 2
        return cmd_plan(args[1], budget)
    if len(args) == 3 and args[0] == "prompt":
        return cmd_prompt(args[1], args[2])
    if len(args) == 2 and args[0] == "critic-prompt":
        return cmd_critic_prompt(args[1])
    if len(args) == 3 and args[0] == "add-units":
        return cmd_add_units(args[1], args[2])
    if len(args) in (2, 3) and args[0] == "collect":
        return cmd_collect(args[1], args[2] if len(args) == 3 else None)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
