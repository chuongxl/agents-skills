#!/usr/bin/env python3
"""triage.py - the deterministic half of independent verification (SKILL.md Phase 9).

  python3 -I scripts/triage.py queue RUN_DIR [--limit N | --all] [--repo NAME ...] [--no-group]
      Queues the findings the run's profile sends to verification (standard: CRITICAL+HIGH, deep: +MEDIUM,
      quick: none), minus those that already have a verdict (including verdicts carried over from the
      previous run). Findings with the same root cause in one repo become one item (one verifier):
      dependency findings by advisory + package + version (all scanners, all lockfiles), misconfigurations
      by scanner + rule. Items are ordered most severe first and capped at --limit (default 25, the
      batch size, not a total verification budget); the summary says how many findings stay pending.
      --repo restricts the queue to those repos. Writes RUN_DIR/triage/queue-index.json (summary; per item fingerprint, repo,
      severity, group size, batch file; no code) and triage/batch-NNN.json files of 10 items. Each item
      carries a context window of +/-15 lines from the repository. Secrets, credential files and symlinks
      get no context and no code.

  python3 -I scripts/triage.py next RUN_DIR
      Prints the next queued item that has no recorded verdict, or {"done": true, "scope": "current_queue",
      "next_action": "status"}. Queue exhaustion does not mean run-wide verification is complete.

  python3 -I scripts/triage.py status RUN_DIR [--require-complete]
      Prints compact run-wide verification counts, current batch progress and the next action.
      --require-complete exits 1 while eligible findings remain pending or saved verdicts remain unapplied.
      Needs-validation verdicts are processed findings, not pending work; this check does not prove a
      clean scan or a completed deep audit.

  python3 -I scripts/triage.py record RUN_DIR FILE|- [--replace]
      Checks one verdict object (see references/verification.md) and saves it as
      triage/verdicts/<fingerprint>.json. A second verdict for the same finding needs --replace.

  python3 -I scripts/triage.py apply RUN_DIR [VERDICTS.json]
      Checks every verdict (the recorded ones in triage/verdicts/, or the given file), then merges them
      into the report, regenerates SUMMARY.md, the Markdown and HTML reports and writes NEEDS-VALIDATION.md.
      A grouped item's verdict covers its members unless they already have, or are given, their own verdict.
      All or nothing: one bad record and nothing changes. Applying the same verdicts twice gives the same report.

Exit codes: 0 done, 1 invalid input or report, 2 usage. Report-only: nothing in any repository is changed.
Stdlib only; Python 3.8+.
"""

import argparse
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
import report_store    # noqa: E402
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
BATCH_SIZE = 10
DEFAULT_LIMIT = 25
MAX_GROUP_LOCATIONS = 50
_SEV_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_RECORD_BYTES = 64 * 1024
FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")
QUEUE_KEYS = ("fingerprint", "repo", "scanner", "type", "severity", "file", "line", "code", "package",
              "installed_version", "fixed_version", "rule_id", "title", "description", "url")


def fail(msg):
    print("triage: %s" % msg, file=sys.stderr)
    return 1


def load_run(run_dir):
    try:
        return report_model.load_report(run_dir)
    except report_store.ReportError as exc:
        raise SystemExit(fail(str(exc)))


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


def _write(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


def group_key(f, grouping=True):
    """Findings sharing a key have one root cause in one repo and get one verifier and one verdict."""
    if grouping and f.get("type") in report_model.DEPENDENCY_TYPES and f.get("rule_id") and f.get("package"):
        return ("dependency", f["repo"], f["rule_id"], f["package"], f.get("installed_version") or "")
    if grouping and f.get("type") == "misconfig" and f.get("rule_id"):
        return ("misconfig", f["repo"], f["scanner"], f["rule_id"])
    return ("finding", f["fingerprint"])


def _order(f):
    return (_SEV_RANK.get((report_model.effective_severity(f) or "").upper(), 9), f.get("change") != "new",
            f.get("repo") or "", f.get("file") or "", f.get("line") or 0, f["fingerprint"])


def unapplied_records(doc, run_dir):
    if not any((Path(run_dir) / "triage" / "verdicts").glob("*.json")):
        return set()
    by_fp = {f["fingerprint"]: f for f in doc["findings"]}
    try:
        records = parse_verdicts(_recorded_verdicts(run_dir), by_fp)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise SystemExit(fail("cannot read recorded verdicts: %s" % exc))
    return {fp for fp, verdict, severity, detail in records
            if (by_fp[fp].get("verdict"), by_fp[fp].get("verified_severity"), by_fp[fp].get("verdict_detail") or {})
            != (verdict, severity, detail)}


def cmd_queue(run_dir, limit=DEFAULT_LIMIT, repos=None, grouping=True):
    doc = load_run(run_dir)
    run = doc.get("run") or {}
    profile = run.get("profile")
    known = set(r["name"] for r in doc.get("repos", []))
    unknown = sorted(set(repos or ()) - known)
    if unknown:
        return fail("--repo %s is not in this report (repos: %s)" % (", ".join(unknown), ", ".join(sorted(known))))
    if unapplied_records(doc, run_dir):
        return fail("recorded verdicts have not been applied - run: triage.py apply %s before rebuilding the queue"
                    % run_dir)
    eligible = [f for f in doc["findings"] if not f.get("verdict") and report_model.is_queued(f, profile)
                and (not repos or f.get("repo") in repos)]
    groups = {}
    for f in sorted(eligible, key=_order):
        groups.setdefault(group_key(f, grouping), []).append(f)
    ordered = sorted(groups.values(), key=lambda members: _order(members[0]))
    selected = ordered if limit is None else ordered[:limit]
    out_dir = Path(run_dir) / "triage"
    out_dir.mkdir(exist_ok=True)
    for old in list(out_dir.glob("batch-*.json")) + [out_dir / "queue.json"]:
        if old.exists():
            old.unlink()
    index_items = []
    for start in range(0, len(selected), BATCH_SIZE):
        name = "batch-%03d.json" % (start // BATCH_SIZE + 1)
        items = []
        for members in selected[start:start + BATCH_SIZE]:
            f = members[0]
            item = dict((k, f.get(k)) for k in QUEUE_KEYS)
            if f.get("type") == "secret":
                item["code"] = ""
            item["context"] = context_for(f, run)
            if len(members) > 1:
                item["group"] = {
                    "size": len(members),
                    "fingerprints": [m["fingerprint"] for m in members],
                    "scanners": sorted(set(m["scanner"] for m in members)),
                    "locations": [{"file": m.get("file"), "line": m.get("line"), "scanner": m["scanner"]}
                                  for m in members[:MAX_GROUP_LOCATIONS]],
                    "locations_omitted": max(0, len(members) - MAX_GROUP_LOCATIONS)}
            items.append(item)
            index_items.append({"fingerprint": f["fingerprint"], "repo": f.get("repo"),
                                "severity": report_model.effective_severity(f), "group_size": len(members),
                                "batch": name})
        _write(out_dir / name, json.dumps({"items": items}, indent=2) + "\n")
    chosen = sum(len(m) for m in selected)
    summary = {"eligible_findings": len(eligible), "groups": len(ordered), "queued_items": len(selected),
               "queued_findings": chosen, "remaining_items": len(ordered) - len(selected),
               "remaining_findings": len(eligible) - chosen, "limit": limit, "repos": sorted(repos or []),
               "grouping": grouping}
    index = {"schema_version": 2, "run_dir": doc["run_dir"], "profile": profile,
             "instructions": "references/verification.md of the job-security-scan skill",
             "verdicts_dir": str(out_dir / "verdicts"), "summary": summary, "items": index_items}
    _write(out_dir / "queue-index.json", json.dumps(index, separators=(",", ":")) + "\n")
    skipped = sum(1 for f in doc["findings"] if f.get("verdict") and report_model.is_queued(f, profile))
    print("triage: %d item(s) queued for verification covering %d finding(s) (profile %s%s, %d already have a "
          "verdict) in %d batch(es) -> %s" % (len(selected), chosen, profile,
                                              ", repos " + ", ".join(sorted(repos)) if repos else "", skipped,
                                              -(-len(selected) // BATCH_SIZE), out_dir / "queue-index.json"))
    if summary["remaining_items"]:
        print("triage: %d more item(s) (%d finding(s)) stay pending - queue again after apply, or raise --limit"
              % (summary["remaining_items"], summary["remaining_findings"]))
    return 0


def load_groups(run_dir):
    """{representative fingerprint: [member fingerprints]} from the current queue's batch files, or {}."""
    triage = Path(run_dir) / "triage"
    try:
        index = json.loads((triage / "queue-index.json").read_text(encoding="utf-8"))
        names = sorted(set(i["batch"] for i in index["items"] if i.get("group_size", 1) > 1))
        groups = {}
        for name in names:
            if not re.match(r"^batch-[0-9]{3,}\.json$", name):
                continue
            for i in json.loads((triage / name).read_text(encoding="utf-8"))["items"]:
                if isinstance(i, dict) and isinstance(i.get("group"), dict):
                    groups[i["fingerprint"]] = list(i["group"]["fingerprints"])
        return groups
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _queue_index(run_dir):
    path = Path(run_dir) / "triage" / "queue-index.json"
    try:
        if path.stat().st_size > MAX_INDEX_BYTES:
            raise SystemExit(fail("%s is larger than %d bytes" % (path, MAX_INDEX_BYTES)))
        index = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(fail("no queue in %s - run: triage.py queue %s" % (path.parent, run_dir)))
    except (OSError, ValueError) as exc:
        raise SystemExit(fail("cannot read %s: %s" % (path, exc)))
    if not isinstance(index, dict) or index.get("schema_version") != 2 or not isinstance(index.get("items"), list):
        raise SystemExit(fail("%s is not a queue index (schema_version 2) - run: triage.py queue %s"
                              % (path, run_dir)))
    return index


def _verdict_path(run_dir, fp):
    return Path(run_dir) / "triage" / "verdicts" / (fp + ".json")


def cmd_next(run_dir):
    index = _queue_index(run_dir)
    pending = [i for i in index["items"] if isinstance(i, dict) and FINGERPRINT.match(str(i.get("fingerprint")))
               and not _verdict_path(run_dir, i["fingerprint"]).exists()]
    if not pending:
        print(json.dumps({"done": True, "scope": "current_queue", "next_action": "status"}))
        return 0
    head = pending[0]
    batch = str(head.get("batch") or "")
    if not re.match(r"^batch-[0-9]{3,}\.json$", batch):
        return fail("queue index names a bad batch file %r" % batch)
    try:
        items = json.loads((Path(run_dir) / "triage" / batch).read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return fail("cannot read %s: %s - run: triage.py queue %s" % (batch, exc, run_dir))
    for item in items:
        if isinstance(item, dict) and item.get("fingerprint") == head["fingerprint"]:
            print(json.dumps(item, indent=2))
            print("triage: %d left after this one" % (len(pending) - 1), file=sys.stderr)
            return 0
    return fail("%s does not hold %s - run: triage.py queue %s" % (batch, head["fingerprint"], run_dir))


def cmd_status(run_dir, require_complete=False):
    doc = load_run(run_dir)
    by_fp = {f["fingerprint"]: f for f in doc["findings"]}
    items = []
    if (Path(run_dir) / "triage" / "queue-index.json").exists():
        items = _queue_index(run_dir)["items"]
    unrecorded = sum(1 for i in items if isinstance(i, dict) and i.get("fingerprint") in by_fp
                     and not by_fp[i["fingerprint"]].get("verdict")
                     and not _verdict_path(run_dir, i["fingerprint"]).exists())
    unapplied = len(unapplied_records(doc, run_dir))
    complete = doc["verification"]["pending"] == 0 and not unapplied
    action = "apply" if unapplied else "next" if unrecorded else "done" if complete else "queue"
    print(json.dumps({"profile": doc["run"]["profile"], "verification": doc["verification"],
                      "verification_complete": complete, "next_action": action,
                      "batch": {"queued_items": len(items), "unrecorded_items": unrecorded,
                                "unapplied_items": unapplied}}))
    return 1 if require_complete and not complete else 0


def cmd_record(run_dir, source, replace):
    index = _queue_index(run_dir)
    try:
        if source == "-":
            text = sys.stdin.read(MAX_RECORD_BYTES + 1)
        else:
            if os.path.getsize(source) > MAX_RECORD_BYTES:
                return fail("%s is larger than %d bytes" % (source, MAX_RECORD_BYTES))
            text = Path(source).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return fail("cannot read %s: %s" % (source, exc))
    if len(text.encode("utf-8")) > MAX_RECORD_BYTES:
        return fail("verdict is larger than %d bytes" % MAX_RECORD_BYTES)
    try:
        obj = json.loads(text)
    except ValueError as exc:
        return fail("verdict is not plain JSON (%s) - send only the JSON object, no prose" % exc)
    if not isinstance(obj, dict):
        return fail("expected one verdict object {\"fingerprint\": ..., \"verdict\": ...}")
    known = set(i.get("fingerprint") for i in index["items"] if isinstance(i, dict))
    try:
        parse_verdicts(json.dumps({"verdicts": [obj]}), known)
    except ValueError as exc:
        print("triage: verdict rejected, nothing recorded:", file=sys.stderr)
        for e in exc.args[0][:50]:
            print("  - %s" % e, file=sys.stderr)
        return 1
    fp = obj["fingerprint"]
    if not FINGERPRINT.match(fp):
        return fail("fingerprint %r is not 16 hex characters" % fp)
    path = _verdict_path(run_dir, fp)
    if path.exists() and not replace:
        return fail("%s already recorded (%s); use --replace to change it" % (fp, path))
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, json.dumps(obj, indent=2) + "\n")
    print("triage: recorded %s %s" % (obj.get("verdict"), fp))
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


def _recorded_verdicts(run_dir):
    """The verdict objects saved by `record`, as one {"verdicts": [...]} text."""
    records = []
    for path in sorted((Path(run_dir) / "triage" / "verdicts").glob("*.json")):
        if os.path.getsize(str(path)) > MAX_RECORD_BYTES:
            raise ValueError("%s is larger than %d bytes" % (path, MAX_RECORD_BYTES))
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as exc:
            raise ValueError("%s: not JSON (%s)" % (path, exc))
    if not records:
        raise ValueError("no recorded verdicts in %s - use triage.py record" % (Path(run_dir) / "triage" / "verdicts"))
    return json.dumps({"verdicts": records})


def cmd_apply(run_dir, verdicts_path=None):
    doc = load_run(run_dir)
    try:
        if verdicts_path is None:
            text = _recorded_verdicts(run_dir)
        elif os.path.getsize(verdicts_path) > MAX_VERDICT_BYTES:
            return fail("%s is larger than %d bytes" % (verdicts_path, MAX_VERDICT_BYTES))
        else:
            text = Path(verdicts_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return fail("cannot read verdicts: %s" % exc)
    by_fp = dict((f["fingerprint"], f) for f in doc["findings"])
    try:
        records = parse_verdicts(text, by_fp)
    except ValueError as exc:
        print("triage: verdicts rejected, nothing changed:", file=sys.stderr)
        for e in exc.args[0][:50]:
            print("  - %s" % e, file=sys.stderr)
        return 1
    explicit = set(fp for fp, _, _, _ in records)
    groups = load_groups(run_dir)
    shared = 0
    for fp, verdict, verified, detail in records:
        targets = [fp] + [m for m in groups.get(fp, []) if m != fp and m in by_fp and m not in explicit
                          and not by_fp[m].get("verdict")]
        shared += len(targets) - 1
        for m in targets:
            by_fp[m].update(verdict=verdict, verified_severity=verified, verdict_detail=dict(detail), carried=False)
    report_model.refresh(doc)
    errors = report_schema.validate(doc)
    if errors:
        return fail("merged report would be invalid, nothing changed: %s" % "; ".join(errors[:5]))
    gen = load_generator()
    _, errors = gen.write_reports(doc, {"team": doc.get("team", ""), "org": doc.get("org", "")}, run_dir, run_dir)
    (Path(run_dir) / "NEEDS-VALIDATION.md").write_text(report_formats.render_needs_validation(doc), encoding="utf-8")
    v = doc["verification"]
    print("triage: applied %d verdict(s) (+%d grouped finding(s)): %d confirmed, %d need validation, "
          "%d dismissed, %d still pending" % (len(records), shared, v["confirmed"], v["needs_validation"],
                                               v["rejected"], v["pending"]))
    return 1 if errors else 0


def _limit(text):
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return n


def main(argv):
    if len(argv) >= 3 and argv[1] == "queue":
        ap = argparse.ArgumentParser(prog="triage.py queue", usage=__doc__)
        ap.add_argument("run_dir")
        cap = ap.add_mutually_exclusive_group()
        cap.add_argument("--limit", type=_limit, default=DEFAULT_LIMIT)
        cap.add_argument("--all", action="store_true")
        ap.add_argument("--repo", action="append", default=[])
        ap.add_argument("--no-group", action="store_true")
        a = ap.parse_args(argv[2:])
        return cmd_queue(a.run_dir, None if a.all else a.limit, set(a.repo), not a.no_group)
    if len(argv) == 3 and argv[1] == "next":
        return cmd_next(argv[2])
    if len(argv) in (3, 4) and argv[1] == "status" and (len(argv) == 3 or argv[3] == "--require-complete"):
        return cmd_status(argv[2], len(argv) == 4)
    if len(argv) in (4, 5) and argv[1] == "record" and (len(argv) == 4 or argv[4] == "--replace"):
        return cmd_record(argv[2], argv[3], len(argv) == 5)
    if len(argv) in (3, 4) and argv[1] == "apply":
        return cmd_apply(argv[2], argv[3] if len(argv) == 4 else None)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
