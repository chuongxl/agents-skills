#!/usr/bin/env python3
"""triage.py - the deterministic half of independent verification (SKILL.md Phase 9).

  python3 -I scripts/triage.py queue RUN_DIR
      Writes RUN_DIR/triage/queue.json: the findings the run's profile queues for verification
      (standard: CRITICAL+HIGH, deep: +MEDIUM, quick: none), minus those that already have a verdict
      (including verdicts carried over from the previous run). Each item carries a context window of
      +/-15 lines from the repository. Secrets, credential files and symlinks get no context and no code.

  python3 -I scripts/triage.py apply RUN_DIR VERDICTS.json
      Checks every verdict (see references/verification.md for the format), then merges them into
      security-report.json, regenerates the Markdown and HTML reports and writes NEEDS-VALIDATION.md.
      All or nothing: one bad record and nothing changes. Applying the same file twice gives the same report.

Exit codes: 0 done, 1 invalid input or report, 2 usage. Report-only: nothing in any repository is changed.
Stdlib only; Python 3.8+.
"""

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))

import report_formats  # noqa: E402
import report_locate   # noqa: E402
import report_model    # noqa: E402
import report_schema   # noqa: E402
from shaihulud.findings import redact  # noqa: E402

CONTEXT = 15
MAX_LINE = 400
MAX_TEXT = 2000
MAX_VERDICT_BYTES = 2 * 1024 * 1024
VERDICT_FIELDS = ("fingerprint", "verdict", "severity", "likelihood", "impact", "evidence", "blocker",
                  "validation_plan", "reason")
TEXT_FIELDS = ("evidence", "blocker", "validation_plan", "reason")
# Files that hold credentials are never opened for context, whatever the finding says.
CREDENTIAL_NAME = re.compile(r"(^\.env(\..*)?$|^\.npmrc$|^\.pypirc$|^\.netrc$|^\.git-credentials$|^\.dockercfg$|"
                             r"^credentials(\.json)?$|^id_(rsa|dsa|ecdsa|ed25519)$|\.(pem|key|p12|pfx|jks|keystore)$)",
                             re.IGNORECASE)
QUEUE_KEYS = ("fingerprint", "repo", "scanner", "type", "severity", "file", "line", "code", "package",
              "installed_version", "fixed_version", "rule_id", "title", "description", "url")


def fail(msg):
    print("triage: %s" % msg, file=sys.stderr)
    return 1


def load_run(run_dir):
    path = Path(run_dir) / "security-report.json"
    doc = report_model.load_report(path)
    if doc is None:
        errors = []
        try:
            errors = report_schema.validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            errors = [str(exc)]
        raise SystemExit(fail("%s is not a valid v2 report (%s) - run run-scan.sh again"
                              % (path, "; ".join(errors[:3]) or "unreadable")))
    return doc


def _inside(path, root):
    try:
        path = os.path.realpath(str(path))
        root = os.path.realpath(str(root))
    except OSError:
        return False
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def context_for(f, run):
    """+/-CONTEXT redacted lines around the finding, or None when the file must not or cannot be shown."""
    if f.get("type") in report_locate.NO_EXCERPT_TYPES or f.get("rule_id") in report_locate.NO_EXCERPT_RULES:
        return None
    if not f.get("file") or not f.get("line"):
        return None
    home = run.get("home") or str(Path.home())
    host = f.get("repo") in report_locate.HOST_REPO_LABELS
    root = Path(home) if host else Path(run.get("repos_root") or ".") / f["repo"]
    path = report_locate.resolve(f["file"], None if host else root, home)
    if path is None or CREDENTIAL_NAME.search(path.name) or not _inside(path, root):
        return None
    lines = report_locate._read_lines(path)   # no symlinks, size cap, no binaries
    if not lines:
        return None
    line = int(f["line"])
    if line > len(lines):
        return None
    start, end = max(1, line - CONTEXT), min(len(lines), line + CONTEXT)
    out = []
    for n in range(start, end + 1):
        text = redact(lines[n - 1])[:MAX_LINE]
        out.append("%s %4d | %s" % (">" if n == line else " ", n, text))
    return {"file": f["file"], "start_line": start, "end_line": end, "lines": out}


def _audit_detail(run_dir, f):
    """The hunter's boundary, root cause and entry-to-sink trace for a code-audit candidate (from
    <repo>/code-audit.json), so the verifier can follow the whole path."""
    path = Path(run_dir) / f["repo"] / "code-audit.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.stat().st_size < 5 * 1024 * 1024 else {}
    except (OSError, ValueError):
        data = {}
    for c in data.get("candidates", []) if isinstance(data, dict) else []:
        if (isinstance(c, dict) and c.get("file") == f.get("file") and c.get("line") == f.get("line")
                and c.get("attack_class") == f.get("rule_id") and str(c.get("title"))[:160] == f.get("title")):
            secret = f.get("type") == "secret"
            trace = [{"role": s.get("role"), "file": s.get("file"), "line": s.get("line"),
                      "note": "" if secret else redact(str(s.get("note") or ""))[:300]}
                     for s in c.get("trace", []) if isinstance(s, dict)][:30]
            return {"boundary": redact(str(c.get("boundary") or ""))[:400],
                    "root_cause": redact(str(c.get("root_cause") or ""))[:600],
                    "hunter_evidence": "" if secret else redact(str(c.get("evidence") or ""))[:1500], "trace": trace}
    return {"boundary": "", "root_cause": "", "hunter_evidence": "", "trace": []}


def cmd_queue(run_dir):
    doc = load_run(run_dir)
    run = doc.get("run") or {}
    profile = run.get("profile")
    items = []
    for f in doc["findings"]:
        if f.get("verdict") or not report_model.is_queued(f, profile):
            continue
        item = dict((k, f.get(k)) for k in QUEUE_KEYS)
        if f.get("type") == "secret":
            item["code"] = ""
        item["context"] = context_for(f, run)
        if f.get("scanner") == "code-audit":
            item.update(_audit_detail(run_dir, f))
        items.append(item)
    out_dir = Path(run_dir) / "triage"
    out_dir.mkdir(exist_ok=True)
    queue = {"schema_version": 1, "run_dir": doc["run_dir"], "profile": profile,
             "instructions": "references/verification.md of the job-security-scan skill",
             "verdicts_file": str(out_dir / "verdicts.json"), "items": items}
    (out_dir / "queue.json").write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    skipped = sum(1 for f in doc["findings"] if f.get("verdict") and report_model.is_queued(f, profile))
    print("triage: %d finding(s) queued for verification (profile %s, %d already have a verdict) -> %s"
          % (len(items), profile, skipped, out_dir / "queue.json"))
    return 0


def parse_verdicts(text, known):
    """[(fingerprint, verdict, verified_severity, detail)] or raise ValueError listing every problem."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(["not plain JSON (%s) - the file must hold only the JSON object, no prose" % exc])
    records = data.get("verdicts") if isinstance(data, dict) else data
    if not isinstance(records, list) or not records:
        raise ValueError(['expected {"verdicts": [ ... ]} with at least one record'])
    errors, out, seen = [], [], set()
    for i, r in enumerate(records):
        where = "verdicts[%d]" % i
        if not isinstance(r, dict):
            errors.append("%s: must be an object" % where)
            continue
        extra = sorted(set(r) - set(VERDICT_FIELDS))
        if extra:
            errors.append("%s: unknown field(s) %s" % (where, ", ".join(extra)))
        fp = r.get("fingerprint")
        if fp not in known:
            errors.append("%s: fingerprint %r is not in this report" % (where, fp))
        elif fp in seen:
            errors.append("%s: second verdict for %s" % (where, fp))
        seen.add(fp)
        bad_text = [k for k in TEXT_FIELDS + ("verdict", "severity", "likelihood", "impact")
                    if k in r and not isinstance(r[k], str)]
        if bad_text:
            errors.append("%s: %s must be text" % (where, ", ".join(bad_text)))
            continue
        too_long = [k for k in TEXT_FIELDS if len(r.get(k) or "") > MAX_TEXT]
        if too_long:
            errors.append("%s: %s longer than %d characters" % (where, ", ".join(too_long), MAX_TEXT))
        verdict = r.get("verdict")
        sev = (r.get("severity") or "").upper() or None
        detail = {}
        for k in TEXT_FIELDS:
            if (r.get(k) or "").strip():
                detail[k] = redact(r[k].strip())
        for k in ("likelihood", "impact"):
            if r.get(k):
                detail[k] = r[k].strip().lower()
        verified = sev if verdict == "confirmed" else None
        if verdict != "confirmed" and sev:
            errors.append("%s: only a confirmed verdict sets severity" % where)
        errors.extend(report_schema.validate_verdict(verdict, verified, detail, where))
        out.append((fp, verdict, verified, detail))
    if errors:
        raise ValueError(errors)
    return out


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_report", str(SCRIPT_DIR / "generate-report.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_apply(run_dir, verdicts_path):
    doc = load_run(run_dir)
    try:
        if os.path.getsize(verdicts_path) > MAX_VERDICT_BYTES:
            return fail("%s is larger than %d bytes" % (verdicts_path, MAX_VERDICT_BYTES))
        text = Path(verdicts_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return fail("cannot read %s: %s" % (verdicts_path, exc))
    by_fp = dict((f["fingerprint"], f) for f in doc["findings"])
    try:
        records = parse_verdicts(text, by_fp)
    except ValueError as exc:
        print("triage: verdicts rejected, nothing changed:", file=sys.stderr)
        for e in exc.args[0][:50]:
            print("  - %s" % e, file=sys.stderr)
        return 1
    for fp, verdict, verified, detail in records:
        f = by_fp[fp]
        f.update(verdict=verdict, verified_severity=verified, verdict_detail=detail, carried=False)
    report_model.refresh(doc)
    errors = report_schema.validate(doc)
    if errors:
        return fail("merged report would be invalid, nothing changed: %s" % "; ".join(errors[:5]))
    gen = load_generator()
    _, errors = gen.write_reports(doc, {"team": doc.get("team", ""), "org": doc.get("org", "")}, run_dir, run_dir)
    (Path(run_dir) / "NEEDS-VALIDATION.md").write_text(report_formats.render_needs_validation(doc), encoding="utf-8")
    v = doc["verification"]
    print("triage: applied %d verdict(s): %d confirmed, %d need validation, %d dismissed, %d still pending"
          % (len(records), v["confirmed"], v["needs_validation"], v["rejected"], v["pending"]))
    return 1 if errors else 0


def main(argv):
    if len(argv) == 3 and argv[1] == "queue":
        return cmd_queue(argv[2])
    if len(argv) == 4 and argv[1] == "apply":
        return cmd_apply(argv[2], argv[3])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
