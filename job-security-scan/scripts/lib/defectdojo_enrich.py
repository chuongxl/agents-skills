"""Recover scanner metadata omitted by the normalized report, without reading source."""

import json
import re
from pathlib import Path

from shaihulud.findings import _REDACTIONS

MAX_BYTES = 50 * 1024 * 1024
PROTECTED_RULES = {"credential-store", "credential-permissions"}


def safe_text(value):
    """Apply the scanner's secret masks without its 120-character display limit."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True, indent=2)
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def protected(f):
    return f.get("type") == "secret" or f.get("rule_id") in PROTECTED_RULES


def read_adjacent(root, relative):
    path = root
    for part in Path(relative).parts:
        if part in ("..", "/"):
            raise ValueError("unsafe adjacent report path")
        path /= part
        if path.is_symlink():
            raise ValueError("refusing symlink in adjacent scanner data")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("adjacent scanner data is not a regular file under 50 MiB")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise ValueError("invalid adjacent scanner JSON: %s" % relative) from None


def normalized_path(value, repo, doc):
    value = str(value or "").replace("\\", "/")
    root = str(doc["run"].get("repos_root") or "").rstrip("/")
    if root and value.startswith(root + "/" + repo + "/"):
        return value[len(root + "/" + repo + "/"):]
    marker = "/" + repo + "/"
    if value.startswith("/") and marker in value:
        return value.split(marker, 1)[1]
    return value[2:] if value.startswith("./") else value


def key_for(f, doc):
    return (normalized_path(f.get("file"), f["repo"], doc), f.get("rule_id") or "",
            f.get("package") or "", f.get("installed_version") or "",
            f.get("line") if f.get("type") in ("sast", "misconfig") else None)


def cwes(values):
    if not isinstance(values, list):
        values = [values]
    return sorted({int(m.group(1)) for value in values
                   for m in re.finditer(r"(?:CWE-)?(\d+)", str(value).split(":", 1)[0])})


def add_common(data, description="", references=(), ids=(), weakness=()):
    data["description"] = description
    data["references"] = list(dict.fromkeys(r for r in references if isinstance(r, str)))
    data["vulnerability_ids"] = list(dict.fromkeys(v for v in ids if isinstance(v, str)))
    data["cwes"] = cwes(weakness)
    return data


def trivy_rows(raw):
    for result in raw.get("Results", []):
        target = result.get("Target", "")
        for item in result.get("Vulnerabilities", []):
            scores = item.get("CVSS") or {}
            score = scores.get(item.get("SeveritySource")) or scores.get("nvd") or next(iter(scores.values()), {})
            data = add_common({}, item.get("Description", ""), item.get("References") or [],
                              [item.get("VulnerabilityID", "")] + (item.get("VendorIDs") or []),
                              item.get("CweIDs") or [])
            data["scanner_context"] = {k: item[k] for k in
                                       ("Status", "DataSource", "VendorSeverity", "CVSS", "LastModifiedDate")
                                       if k in item}
            for version in ("3", "4"):
                if score.get("V%sVector" % version):
                    data["cvssv%s" % version] = score["V%sVector" % version]
                if score.get("V%sScore" % version) is not None:
                    data["cvssv%s_score" % version] = score["V%sScore" % version]
            if item.get("PublishedDate"):
                data["publish_date"] = item["PublishedDate"][:10]
            data["fixed_version"] = item.get("FixedVersion") or ""
            if item.get("PkgIdentifier", {}).get("PURL"):
                data["purl"] = item["PkgIdentifier"]["PURL"]
            yield {"file": target, "rule_id": item.get("VulnerabilityID"),
                   "package": item.get("PkgName"), "installed_version": item.get("InstalledVersion")}, data
        for item in result.get("Misconfigurations", []):
            data = add_common({}, item.get("Description", ""), item.get("References") or [])
            data["scanner_context"] = {k: item[k] for k in ("Message", "Resolution", "Status", "Namespace")
                                       if k in item}
            yield {"file": target, "rule_id": item.get("ID"), "type": "misconfig",
                   "line": (item.get("CauseMetadata") or {}).get("StartLine") or
                           (item.get("CauseMetadata") or {}).get("EndLine")}, data


def semgrep_rows(raw):
    for item in raw.get("results", []):
        extra = item.get("extra") or {}
        meta = extra.get("metadata") or {}
        data = add_common({}, extra.get("message", ""), meta.get("references") or [],
                          weakness=meta.get("cwe") or [])
        data["scanner_context"] = {k: meta[k] for k in
                                   ("confidence", "owasp", "impact", "likelihood", "technology",
                                    "vulnerability_class", "category", "subcategory", "source", "shortlink")
                                   if k in meta}
        if extra.get("fix"):
            data["mitigation"] = extra["fix"]
        yield {"file": item.get("path"), "rule_id": item.get("check_id"),
               "line": (item.get("start") or {}).get("line"), "type": "sast"}, data


def osv_rows(raw):
    for result in raw.get("results", []):
        for package in result.get("packages", []):
            info = package.get("package") or {}
            for item in package.get("vulnerabilities", []):
                data = add_common({}, item.get("details", ""),
                                  [r.get("url") for r in item.get("references", [])],
                                  [item.get("id", "")] + (item.get("aliases") or []),
                                  (item.get("database_specific") or {}).get("cwe_ids") or [])
                data["scanner_context"] = {k: item[k] for k in
                                           ("affected", "severity", "database_specific", "published", "modified")
                                           if k in item}
                for severity in item.get("severity", []):
                    vector = severity.get("score") or ""
                    if vector.startswith(("CVSS:3.0/", "CVSS:3.1/")):
                        data.setdefault("cvssv3", vector)
                    elif vector.startswith("CVSS:4.0/"):
                        data.setdefault("cvssv4", vector)
                fixes = []
                for affected in item.get("affected", []):
                    identity = affected.get("package") or {}
                    if identity.get("name") != info.get("name"):
                        continue
                    if info.get("ecosystem") and identity.get("ecosystem") != info["ecosystem"]:
                        continue
                    fixes.extend(event["fixed"] for span in affected.get("ranges", [])
                                 for event in span.get("events", []) if event.get("fixed"))
                data["fixed_version"] = ", ".join(dict.fromkeys(fixes))
                if item.get("published"):
                    data["publish_date"] = item["published"][:10]
                yield {"file": (result.get("source") or {}).get("path"), "rule_id": item.get("id"),
                       "package": info.get("name"), "installed_version": info.get("version")}, data


def advisory_rows(raw):
    for item in raw.get("findings", []):
        data = add_common({}, references=[(item.get("source") or {}).get("url")],
                          ids=[item.get("id", "")] + (item.get("aliases") or []))
        if item.get("exploited"):
            data["known_exploited"] = True
        data["scanner_context"] = {k: item[k] for k in
                                   ("state", "unmet_conditions", "conflicts", "merged_from", "source",
                                    "kev_raised_from") if k in item}
        yield {"file": item.get("location") or item.get("component"), "rule_id": item.get("id"),
               "package": item.get("component"), "installed_version": item.get("installed")}, data


SCANNERS = {"trivy": ("trivy.json", trivy_rows), "semgrep": ("semgrep.json", semgrep_rows),
            "osv": ("osv.json", osv_rows), "advisory": ("advisories.json", advisory_rows)}


def enrich(doc, root):
    metadata = read_adjacent(root, "run-metadata.json")
    if metadata:
        refs = metadata.get("source_refs")
        if isinstance(refs, dict):
            existing = doc["run"].setdefault("source_refs", {})
            for repo, ref in refs.items():
                if isinstance(ref, dict):
                    existing.setdefault(repo, {k: ref[k] for k in ("branch", "commit", "dirty", "vcs") if k in ref})
    groups = {}
    for finding in doc["findings"]:
        repo = finding["repo"]
        if repo in ("this machine", "_host", "host"):
            continue
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,99}", repo) or ".." in repo:
            raise ValueError("unsafe repository name in report")
        if not protected(finding):
            groups.setdefault((repo, finding["scanner"]), []).append(finding)
    for (repo, scanner), findings in groups.items():
        if scanner not in SCANNERS:
            continue
        filename, rows = SCANNERS[scanner]
        raw = read_adjacent(root, repo + "/" + filename)
        if raw is None:
            continue
        index = {}
        for identity, data in rows(raw):
            identity["repo"] = repo
            key = key_for(identity, doc)
            # Ambiguous matches must not borrow metadata from another occurrence.
            if key in index and index[key] != data:
                index[key] = None
            else:
                index[key] = data
        for finding in findings:
            key = key_for(finding, doc)
            data = index.get(key)
            if key not in index and finding.get("type") == "misconfig" and finding.get("line") == 1:
                # File-level rules have no scanner line; report locating assigns line 1.
                data = index.get(key[:-1] + (None,))
            if data:
                finding["scanner_detail"] = data
    return doc


def test_context(doc, repo, scanner, mode):
    run = doc["run"]
    target = next((t for t in doc["shai_hulud"].get("targets", []) if t.get("repo") == repo), {})
    summary = {
        "org": doc["org"], "team": doc["team"], "repository": repo,
        "generated_at": doc["generated_at"], "run": Path(doc["run_dir"]).name,
        "profile": run["profile"], "partial": run.get("partial"), "since": run.get("since"),
        "scanner": scanner, "coverage_mode": mode, "coverage": (run.get("coverage") or {}).get(repo, {}),
        "source_ref": (run.get("source_refs") or {}).get(repo),
        "counts": next((r["counts"] for r in doc["repos"] if r["name"] == repo), {}),
        "verification": doc["verification"], "audit": (doc.get("audit") or {}).get(repo),
        "shai_hulud": {k: target[k] for k in ("verdict", "checked", "counts", "error") if k in target},
    }
    for category, rows in (
            ("rejected", [f for f in doc["findings"] if f.get("verdict") == "rejected"]),
            ("accepted", (doc.get("baseline") or {}).get("accepted", [])),
            ("fixed", doc.get("fixed", []))):
        selected = [f for f in rows if f.get("repo") == repo and f.get("scanner") == scanner]
        summary[category] = [{"fingerprint": f.get("fingerprint"), "rule_id": f.get("rule_id"),
                              "file": f.get("file"), "reason": "[see local report]" if protected(f) else
                              (f.get("accepted_reason") or (f.get("verdict_detail") or {}).get("reason"))}
                             for f in selected]
    return "job-security-scan run context\n\n```json\n%s\n```" % safe_text(summary)
