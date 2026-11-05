"""report_store - the only reader and writer of a run's security report.

Schema v3 splits a run's report in two so no file grows with the number of findings:

  <run>/security-report.json      index: every v2 top-level key except `findings`, plus `shards`,
                                  `findings_total`, `fixed_total` and `fixed_shards`
  <run>/findings/<repo>-NNN-<sha12>.json  {"schema_version": 3, "repo", "rules", "findings": [...]}, compact
                                  JSON, at most SHARD_ROWS rows and SHARD_BYTES bytes each

Shard names end in the first 12 hex of their own sha256, so a save never overwrites a shard the current index
lists: if the process stops before the new index is in place, the previous report is still whole.

A shard's `rules` table holds title/description/url once per rule_id; rows that match it drop those fields and
get them back on load. Every shard is checked against the size and sha256 recorded in the index.

v2 reports (one file, `findings` inline) are still read, so earlier runs keep working for change tracking.
In memory a loaded report always looks like v2: `doc["findings"]` is the full list, `schema_version` is 3.
Every failure raises a ReportError naming the file, the size or problem, and what to do next.
Stdlib only; Python 3.8+.
"""

import hashlib
import json
import os
import re
from pathlib import Path

INDEX_NAME = "security-report.json"
SHARD_DIR = "findings"
SHARD_ROWS = 2000
SHARD_BYTES = 4 * 1024 * 1024
MAX_SHARD_FILE = 5 * 1024 * 1024
MAX_INDEX_FILE = 5 * 1024 * 1024
MAX_V2_FILE = 64 * 1024 * 1024
MAX_TOTAL = 200 * 1024 * 1024
MAX_FINDINGS = 200000
MAX_ROW = 64 * 1024
MAX_FIXED_INLINE = 2000
MAX_RULE_DESCRIPTION = 4000
RULE_FIELDS = ("title", "description", "url")
INDEX_ONLY = ("shards", "findings_total", "fixed_total", "fixed_shards")
SHARD_FILE = re.compile(r"^findings/[A-Za-z0-9._-]+\.json$")
_SEV_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


class ReportError(Exception):
    pass


class ReportTooLarge(ReportError):
    pass


class ReportCorrupt(ReportError):
    pass


class ReportMissing(ReportError):
    pass


def _dumps(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def shard_name(repo, n):
    """File name for the n-th shard of a run (n is unique across the run, so names never collide)."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(repo or "_"))
    if safe.startswith("."):
        safe = "_" + safe[1:]
    return "%s-%03d.json" % (safe, n)


def _too_many(findings):
    by = {}
    for f in findings:
        key = "%s/%s" % (f.get("repo"), f.get("scanner"))
        by[key] = by.get(key, 0) + 1
    top = ", ".join("%s (%d)" % kv for kv in sorted(by.items(), key=lambda kv: -kv[1])[:3])
    return ReportTooLarge("%d findings is more than the %d a report can hold; most come from %s - narrow the "
                          "run with --profile standard, --repo or --scanner" % (len(findings), MAX_FINDINGS, top))


def _sort_key(f):
    return (str(f.get("repo") or ""), _SEV_RANK.get(f.get("severity"), 9), str(f.get("file") or ""),
            f.get("line") or 0, str(f.get("fingerprint") or ""))


def _rule_of(row):
    rule = dict((k, row.get(k)) for k in RULE_FIELDS)
    if isinstance(rule.get("description"), str):
        rule["description"] = rule["description"][:MAX_RULE_DESCRIPTION]
    return rule


def _compact(f, rules):
    """(row text, new rule entry or None) for one finding against a shard's current rules table."""
    row = dict(f)
    rid = row.get("rule_id")
    new_rule = None
    if rid:
        rule = rules.get(rid)
        if rule is None:
            rule = new_rule = _rule_of(row)
        for k in RULE_FIELDS:
            if row.get(k) == rule.get(k):
                row.pop(k, None)
    text = _dumps(row)
    size = len(text.encode("utf-8"))
    if size > MAX_ROW:
        raise ReportTooLarge("finding %s in %s is %d bytes, more than %d - the scanner output for it is "
                             "unexpectedly large" % (f.get("fingerprint"), f.get("file"), size, MAX_ROW))
    return text, new_rule


def _shard_text(repo, rules, rows):
    return '{"schema_version":3,"repo":%s,"rules":%s,"findings":[%s]}' % (_dumps(repo), _dumps(rules),
                                                                          ",".join(rows))


def _split(rows, repo, n):
    """Shards for the rows of one repo as [(name, repo, count, text)], and the next shard number."""
    shards, cur, rules, size = [], [], {}, 0
    for f in rows:
        text, new_rule = _compact(f, rules)
        add = len(text.encode("utf-8")) + 1
        if new_rule is not None:
            add += len(_dumps({f["rule_id"]: new_rule}).encode("utf-8"))
        if cur and (len(cur) >= SHARD_ROWS or size + add + 200 > SHARD_BYTES):
            shards.append((shard_name(repo, n), repo, len(cur), _shard_text(repo, rules, cur)))
            n += 1
            cur, rules, size = [], {}, 0
            text, new_rule = _compact(f, rules)
            add = len(text.encode("utf-8")) + 1
            if new_rule is not None:
                add += len(_dumps({f["rule_id"]: new_rule}).encode("utf-8"))
        if new_rule is not None:
            rules[f["rule_id"]] = new_rule
        cur.append(text)
        size += add
    if cur:
        shards.append((shard_name(repo, n), repo, len(cur), _shard_text(repo, rules, cur)))
        n += 1
    return shards, n


def _write(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


def _entry(name, repo, count, text):
    data = text.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    return {"file": "%s/%s-%s.json" % (SHARD_DIR, name[:-len(".json")], digest[:12]), "repo": repo,
            "count": count, "bytes": len(data), "sha256": digest}


def _shard_dir(run_dir):
    """<run>/findings, refused when it is a symlink or resolves outside the run folder."""
    d = Path(run_dir) / SHARD_DIR
    if d.is_symlink() or (d.exists() and os.path.realpath(str(d)) != os.path.join(
            os.path.realpath(str(run_dir)), SHARD_DIR)):
        raise ReportCorrupt("%s is a link or leaves the run folder - remove it and regenerate the report" % d)
    return d


def save(doc, run_dir):
    """Write doc (in-memory, findings inline) as index + shards; the index is written last. Returns its path."""
    run_dir = Path(run_dir)
    findings = list(doc.get("findings") or [])
    if len(findings) > MAX_FINDINGS:
        raise _too_many(findings)
    by_repo = {}
    for f in sorted(findings, key=_sort_key):
        by_repo.setdefault(str(f.get("repo") or ""), []).append(f)
    planned, n = [], 1
    for repo in sorted(by_repo):
        shards, n = _split(by_repo[repo], repo, n)
        planned.extend(shards)
    fixed = list(doc.get("fixed") or [])
    fixed_planned = []
    rest = fixed[MAX_FIXED_INLINE:]
    for i in range(0, len(rest), SHARD_ROWS):
        chunk = rest[i:i + SHARD_ROWS]
        fixed_planned.append((shard_name("_fixed", n), "_fixed", len(chunk),
                              _shard_text("_fixed", {}, [_dumps(r) for r in chunk])))
        n += 1
    index = dict((k, v) for k, v in doc.items() if k != "findings")
    index["schema_version"] = 3
    index["fixed"] = fixed[:MAX_FIXED_INLINE]
    index["fixed_total"] = len(fixed)
    index["findings_total"] = len(findings)
    index["shards"] = [_entry(*s) for s in planned]
    index["fixed_shards"] = [_entry(*s) for s in fixed_planned]
    total = sum(e["bytes"] for e in index["shards"] + index["fixed_shards"])
    if total > MAX_TOTAL:
        raise ReportTooLarge("the report would be %d bytes of shards, more than the %d allowed - narrow the run "
                             "with --profile standard, --repo or --scanner" % (total, MAX_TOTAL))
    shard_dir = _shard_dir(run_dir)
    shard_dir.mkdir(parents=True, exist_ok=True)
    texts = [s[3] for s in planned + fixed_planned]
    for entry, text in zip(index["shards"] + index["fixed_shards"], texts):
        _write(run_dir / entry["file"], text)
    path = run_dir / INDEX_NAME
    _write(path, json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    keep = set(Path(e["file"]).name for e in index["shards"] + index["fixed_shards"])
    for p in list(shard_dir.glob("*.json")) + list(shard_dir.glob("*.tmp")):
        if p.name not in keep:
            p.unlink()
    return path


def _read_capped(path, limit, what):
    try:
        size = os.path.getsize(str(path))
    except OSError:
        return None
    if size > limit:
        raise ReportTooLarge("%s is %d bytes, more than the %d allowed for %s - regenerate the report with "
                             "this version of the skill" % (path, size, limit, what))
    with open(str(path), "rb") as fh:
        return fh.read()


def load_index(run_dir):
    """The index of a v3 run, or the whole document of a v2 run (findings inline). Not yet validated."""
    path = Path(run_dir) / INDEX_NAME
    if not path.is_file():
        raise ReportMissing("%s does not exist - run run-scan.sh first" % path)
    data = _read_capped(path, MAX_V2_FILE, "a report")
    try:
        doc = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ReportCorrupt("%s is not valid JSON (%s)" % (path, exc))
    if not isinstance(doc, dict):
        raise ReportCorrupt("%s is not a JSON object" % path)
    if doc.get("schema_version") == 3:
        if len(data) > MAX_INDEX_FILE:
            raise ReportTooLarge("%s is %d bytes, more than the %d allowed for a v3 index"
                                 % (path, len(data), MAX_INDEX_FILE))
        import report_schema
        errors = report_schema.validate_index(doc)
        if errors:
            raise ReportCorrupt("%s is not a valid report index: %s" % (path, "; ".join(errors[:3])))
    return doc


def _read_shard(run_dir, entry, budget):
    rel = entry.get("file") or ""
    path = Path(run_dir) / rel
    _shard_dir(run_dir)
    if not SHARD_FILE.match(rel) or not path.is_file() or path.is_symlink():
        raise ReportCorrupt("shard %s listed in %s is missing - regenerate the report"
                            % (path, Path(run_dir) / INDEX_NAME))
    data = _read_capped(path, MAX_SHARD_FILE, "a shard")
    budget[0] += len(data)
    if budget[0] > MAX_TOTAL:
        raise ReportTooLarge("%s: shards add up to more than %d bytes" % (run_dir, MAX_TOTAL))
    if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
        raise ReportCorrupt("shard %s was changed after the report was written (sha256 mismatch) - "
                            "regenerate the report" % path)
    try:
        shard = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ReportCorrupt("shard %s is not valid JSON (%s)" % (path, exc))
    rows = shard.get("findings") if isinstance(shard, dict) else None
    if not isinstance(rows, list) or len(rows) != entry.get("count"):
        raise ReportCorrupt("shard %s does not hold the %s findings the index lists" % (path, entry.get("count")))
    return shard, rows


def iter_findings(run_dir, index, budget=None):
    """Yield every finding, one shard at a time, with rule fields restored. v2: the inline list.
    budget is a one-item list of bytes read so far, shared with other shard reads of the same run."""
    if index.get("schema_version") != 3:
        for f in index.get("findings") or []:
            yield f
        return
    budget = [0] if budget is None else budget
    for entry in index.get("shards") or []:
        shard, rows = _read_shard(run_dir, entry, budget)
        rules = shard.get("rules") or {}
        for row in rows:
            rule = rules.get(row.get("rule_id")) if isinstance(row, dict) else None
            if rule:
                for k in RULE_FIELDS:
                    if k not in row:
                        row[k] = rule.get(k)
            yield row


def load_full(run_dir):
    """The whole report in memory (findings and fixed inline, schema_version 3), validated."""
    import report_schema
    index = load_index(run_dir)
    if index.get("schema_version") == 3:
        doc = dict((k, v) for k, v in index.items() if k not in INDEX_ONLY)
        budget = [0]
        doc["findings"] = list(iter_findings(run_dir, index, budget))
        fixed = list(index.get("fixed") or [])
        for entry in index.get("fixed_shards") or []:
            fixed.extend(_read_shard(run_dir, entry, budget)[1])
        doc["fixed"] = fixed
    else:
        doc = index
    errors = report_schema.validate(doc)
    if errors:
        raise ReportCorrupt("%s is not a valid report: %s" % (Path(run_dir) / INDEX_NAME, "; ".join(errors[:3])))
    doc["schema_version"] = 3
    return doc
