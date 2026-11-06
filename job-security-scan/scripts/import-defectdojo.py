#!/usr/bin/env python3
"""Import a v2 or v3 security report into DefectDojo. Stdlib only; Python 3.8+.

Dry-run by default. --upload requires DEFECTDOJO_API_TOKEN or --token-file.
Never closes/reopens old findings or changes the input. Source excerpts are opt-in.
"""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib import error, parse, request

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import report_model  # noqa: E402
import report_store  # noqa: E402
import defectdojo_enrich as enrichment  # noqa: E402

MAX_BYTES = 50 * 1024 * 1024
TOOL_TYPE = "Job Security Scan"
HOST_REPOS = {"this machine", "_host", "host"}
SEVERITIES = dict(zip(report_model.SEVERITIES, ("Critical", "High", "Medium", "Low", "Info")))


def load_report(path, enrich=True):
    path = Path(path).expanduser()
    if path.is_dir():
        run_dir = path
    elif path.name == report_store.INDEX_NAME and path.is_file():
        run_dir = path.parent
    else:
        raise ValueError("report must be a run folder or its security-report.json file")
    report_path = run_dir / report_store.INDEX_NAME
    if report_path.stat().st_size > MAX_BYTES:
        raise ValueError("report exceeds the 50 MiB import limit")
    try:
        doc = report_store.load_full(run_dir)
    except report_store.ReportError as exc:
        raise ValueError(str(exc)) from None
    for f in doc["findings"]:
        if not re.fullmatch(r"[0-9a-f]{16}", f["fingerprint"]):
            raise ValueError("invalid finding fingerprint")
        for key in ("repo", "scanner", "title", "file", "rule_id"):
            if not isinstance(f.get(key), str):
                raise ValueError("finding %s must be text" % key)
    return enrichment.enrich(doc, run_dir) if enrich else doc


def convert_finding(f, doc, include_code=False):
    verdict = f.get("verdict")
    detail = f.get("verdict_detail") or {}
    identity = "\x1f".join((doc["org"], doc["team"], f["repo"], f["fingerprint"]))
    uid = "job-security-scan:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
    description = [
        "job-security-scan fingerprint: " + f["fingerprint"],
        "Scanner: " + f["scanner"],
        "Rule: " + f["rule_id"],
        "Verification: " + (verdict or "unverified"),
        "Repository: " + f["repo"],
        "Finding type: " + str(f.get("type") or ""),
        "Change: %s; carried verdict: %s" % (f.get("change"), bool(f.get("carried"))),
        "Scanner severity: %s; verified severity: %s" % (f["severity"], f.get("verified_severity")),
    ]
    # Secret rows export location/rule only, never free-text evidence or excerpts.
    secret = enrichment.protected(f)
    extra = {} if secret else f.get("scanner_detail") or {}
    if not secret:
        description.append("Reported title: " + f["title"])
        if f.get("description"):
            description.append(f["description"])
        if extra.get("description") and extra["description"] != f.get("description"):
            description.append("Full scanner description:\n" + extra["description"])
        if detail:
            description.append("Verification detail:\n" + enrichment.safe_text(detail))
        if extra.get("scanner_context"):
            description.append("Scanner metadata:\n" + enrichment.safe_text(extra["scanner_context"]))
        if extra.get("purl"):
            description.append("Package URL: " + extra["purl"])
        if include_code and f.get("code"):
            description.append("Source excerpt:\n\n```text\n%s\n```" % enrichment.safe_text(f["code"]))
        # Preserve untruncated source values alongside bounded native columns.
        description.append("Reported location: %s:%s\nRule: %s\nPackage: %s\nInstalled: %s\nFix: %s"
                           % (f["file"], f.get("line"), f["rule_id"], f.get("package") or "",
                              f.get("installed_version") or "",
                              f.get("fixed_version") or extra.get("fixed_version") or ""))
    finding = {
        "title": (("Secret detected: " + f["rule_id"]) if secret else f["title"])[:511],
        "description": enrichment.safe_text("\n\n".join(description)),
        "date": datetime.fromisoformat(doc["generated_at"].replace("Z", "+00:00")).date().isoformat(),
        "severity": SEVERITIES[report_model.effective_severity(f)],
        "unique_id_from_tool": uid,
        "vuln_id_from_tool": f["rule_id"][:500],
        "verified": verdict == "confirmed",
        "active": True,
        "static_finding": True,
        "dynamic_finding": False,
        "tags": ["job-security-scan", "scanner:" + f["scanner"], "verdict:" + (verdict or "unverified")],
    }
    if f.get("file"):
        finding["file_path"] = f["file"][:4000]
    if f.get("line"):
        finding["line"] = f["line"]
    if not secret:
        refs = ([f["url"]] if f.get("url") else []) + extra.get("references", [])
        if refs:
            finding["references"] = enrichment.safe_text("\n".join(dict.fromkeys(refs)))
        if f.get("package"):
            finding["component_name"] = f["package"][:500]
            finding["component_version"] = (f.get("installed_version") or "")[:100]
        ids = ([f["rule_id"]] if re.fullmatch(r"(?:CVE-\d{4}-\d+|GHSA-[a-z0-9-]+)", f["rule_id"]) else [])
        ids += extra.get("vulnerability_ids", [])
        if ids:
            finding["vulnerability_ids"] = list(dict.fromkeys(v for v in ids if v))
        fix = f.get("fixed_version") or extra.get("fixed_version")
        if f.get("type") == "vulnerability" and f.get("package") and fix:
            finding["fix_available"] = True
            finding["fix_version"] = fix[:100]
            finding["mitigation"] = "Upgrade to: " + fix
        elif f.get("fixed_version"):
            finding["mitigation"] = f["fixed_version"]
        if extra.get("mitigation"):
            finding["mitigation"] = extra["mitigation"]
        if detail.get("remediation_guidance"):
            finding["mitigation"] = detail["remediation_guidance"]
        if finding.get("mitigation"):
            finding["mitigation"] = enrichment.safe_text(finding["mitigation"])
        if detail.get("evidence") or detail.get("validation_plan"):
            finding["steps_to_reproduce"] = enrichment.safe_text(
                "\n\n".join(str(detail[k]) for k in ("evidence", "validation_plan") if detail.get(k)))
        if detail.get("impact"):
            finding["impact"] = enrichment.safe_text(detail["impact"])
        if detail.get("likelihood") or detail.get("impact"):
            finding["severity_justification"] = enrichment.safe_text(
                "Likelihood: %s; demonstrated impact: %s" % (detail.get("likelihood"), detail.get("impact")))
        if isinstance(detail.get("confidence"), int) and not isinstance(detail["confidence"], bool):
            finding["scanner_confidence"] = detail["confidence"]
        for key in ("cvssv3", "cvssv3_score", "cvssv4", "cvssv4_score", "publish_date",
                    "known_exploited", "purl"):
            if extra.get(key) is not None:
                finding[key] = extra[key]
        if extra.get("cwes"):
            finding["cwes"] = extra["cwes"]
            finding["cwe"] = extra["cwes"][0]
    return finding


def build_batches(doc, branch=None, repo=None, batch_size=500, include_code=False):
    groups = {}
    skipped = Counter()
    refs = doc["run"].get("source_refs") or {}
    for f in doc["findings"]:
        if repo and f["repo"] != repo:
            skipped["other_repo"] += 1
            continue
        if f["repo"] in HOST_REPOS:
            skipped["host"] += 1
            continue
        if f.get("verdict") == "rejected":
            skipped["rejected"] += 1
            continue
        ref = refs.get(f["repo"]) or {}
        target_branch = branch or ref.get("branch")
        if not target_branch:
            raise ValueError("branch unavailable for %s; pass --branch to isolate its engagement" % f["repo"])
        mode = (doc["run"].get("coverage") or {}).get(f["repo"], {}).get(f["scanner"], "unknown")
        key = (f["repo"], f["scanner"], mode, target_branch)
        groups.setdefault(key, []).append(convert_finding(f, doc, include_code))
    for name, scanners in (doc["run"].get("coverage") or {}).items():
        if (repo and name != repo) or name in HOST_REPOS:
            continue
        ref = refs.get(name) or {}
        target_branch = branch or ref.get("branch")
        if not target_branch:
            raise ValueError("branch unavailable for %s; pass --branch to isolate its engagement" % name)
        for scanner, mode in scanners.items():
            groups.setdefault((name, scanner, mode, target_branch), [])
    if repo and repo not in {r["name"] for r in doc["repos"]}:
        raise ValueError("requested --repo is not in this report")
    scan_date = datetime.fromisoformat(doc["generated_at"].replace("Z", "+00:00")).date().isoformat()
    batches = []
    for (name, scanner, mode, target_branch), findings in sorted(groups.items()):
        ref = refs.get(name) or {}
        fields = {
            "scan_type": "Generic Findings Import",
            "product_type_name": "%s / %s" % (doc["org"], doc["team"]),
            "product_name": name,
            "engagement_name": "job-security-scan / " + target_branch,
            "test_title": "job-security-scan / %s / %s" % (scanner, mode),
            "auto_create_context": "true",
            "deduplication_on_engagement": "true",
            "close_old_findings": "false",
            "do_not_reactivate": "true",
            "minimum_severity": "Info",
            "scan_date": scan_date,
            "branch_tag": target_branch,
            "build_id": Path(doc["run_dir"]).name,
        }
        if ref.get("commit"):
            fields["commit_hash"] = ref["commit"]
        context = enrichment.test_context(doc, name, scanner, mode)
        for start in range(0, max(1, len(findings)), batch_size):
            batches.append({
                "fields": dict(fields),
                "report": {"type": TOOL_TYPE, "description": context,
                           "findings": findings[start:start + batch_size]},
            })
    return batches, dict(skipped)


def validate_url(url):
    parts = parse.urlsplit(url)
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError("URL must be HTTP(S), without credentials, query, or fragment")
    if parts.scheme == "http":
        try:
            local = ipaddress.ip_address(parts.hostname).is_loopback
        except ValueError:
            local = parts.hostname == "localhost"
        if not local:
            raise ValueError("HTTP is allowed only on loopback; use HTTPS for remote DefectDojo")
    return url.rstrip("/")


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def multipart(fields, report):
    boundary = "job-security-scan-" + uuid.uuid4().hex
    body = bytearray()
    for key, value in fields.items():
        body.extend(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                     % (boundary, key, value)).encode("utf-8"))
    body.extend(("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
                 "filename=\"findings.json\"\r\nContent-Type: application/json\r\n\r\n" % boundary).encode())
    body.extend(json.dumps(report, ensure_ascii=True).encode("utf-8"))
    body.extend(("\r\n--%s--\r\n" % boundary).encode())
    return bytes(body), "multipart/form-data; boundary=" + boundary


def upload_batch(url, token, batch, timeout):
    body, content_type = multipart(batch["fields"], batch["report"])
    req = request.Request(url + "/api/v2/reimport-scan/", data=body, headers={
        "Authorization": "Token " + token,
        "Content-Type": content_type,
        "Accept": "application/json",
    })
    # Do not send API tokens through environment-configured proxies or redirects.
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            result = json.loads(response.read(MAX_BYTES))
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise ValueError("DefectDojo HTTP %d; import stopped, no automatic retry" % code) from None
    except (error.URLError, TimeoutError, OSError):
        raise ValueError("DefectDojo connection failed; check server state before retrying") from None
    test_id = result.get("test_id") or result.get("test")
    if not isinstance(test_id, int):
        raise ValueError("DefectDojo response has no test ID; check server state before retrying")
    return {"test_id": test_id, "product_id": result.get("product_id"),
            "engagement_id": result.get("engagement_id"), "url": url + "/test/%d" % test_id}


def api_json(url, token, path, timeout, data=None, method="GET"):
    req = request.Request(url + "/api/v2/" + path, method=method,
                          data=json.dumps(data).encode() if data is not None else None,
                          headers={"Authorization": "Token " + token, "Accept": "application/json",
                                   "Content-Type": "application/json"})
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            return json.loads(response.read(MAX_BYTES))
    except error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise ValueError("DefectDojo detail refresh HTTP %d; stopped without retry" % code) from None
    except (error.URLError, TimeoutError, OSError):
        raise ValueError("DefectDojo detail refresh connection failed; check server before retrying") from None


DETAIL_FIELDS = {
    "title", "description", "mitigation", "references", "file_path", "line",
    "component_name", "component_version", "fix_available", "fix_version",
    "steps_to_reproduce", "impact", "severity_justification", "scanner_confidence",
    "cvssv3", "cvssv3_score", "cvssv4", "cvssv4_score", "publish_date", "known_exploited", "cwe",
}


def detail_matches(key, stored, desired):
    if isinstance(desired, str):
        stored, desired = (stored or "").strip(), desired.strip()
        if key == "title":
            stored, desired = stored.casefold(), desired.casefold()
        if key == "cvssv4":
            # DefectDojo drops optional "Not Defined" metrics when saving vectors.
            stored, desired = ("/".join(p for p in v.split("/") if not p.endswith(":X"))
                               for v in (stored, desired))
    return stored == desired


def refresh_details(url, token, test_id, batch, timeout):
    """Refresh scanner-owned detail only; lifecycle, severity and review decisions stay untouched."""
    desired = {f["unique_id_from_tool"]: f for f in batch["report"]["findings"]}
    if not desired:
        return 0
    found = {}
    offset = 0
    while True:
        result = api_json(url, token, "findings/?test=%d&limit=1000&offset=%d" % (test_id, offset), timeout)
        rows = result.get("results")
        if not isinstance(rows, list):
            raise ValueError("unexpected finding list during detail refresh")
        for row in rows:
            uid = row.get("unique_id_from_tool")
            if row.get("test") != test_id or uid not in desired:
                continue
            if uid in found:
                raise ValueError("ambiguous finding identity; refusing detail refresh")
            found[uid] = row
        if not result.get("next"):
            break
        if not rows:
            raise ValueError("empty finding page during detail refresh")
        offset += len(rows)
    if set(found) != set(desired):
        raise ValueError("imported finding identity not found; check matching configuration before retrying")
    updated = 0
    for uid, target in desired.items():
        existing = found[uid]
        changes = {key: value for key, value in target.items()
                   if key in DETAIL_FIELDS and not detail_matches(key, existing.get(key), value)}
        # Finding API relations use objects, unlike Generic Import's scalar lists.
        # Union preserves manually added aliases and weakness classifications.
        for key, entry_key, incoming in (
                ("cwes", "cwe", target.get("cwes", [])),
                ("vulnerability_ids", "vulnerability_id", target.get("vulnerability_ids", []))):
            def canonical(value):
                if key == "cwes":
                    match = re.fullmatch(r"(?:CWE-)?([1-9]\d*)", str(value))
                    return "CWE-" + match.group(1) if match else None
                return value if isinstance(value, str) and value else None
            current = [canonical(v.get(entry_key) if isinstance(v, dict) else v)
                       for v in existing.get(key, [])]
            additions = [canonical(v) for v in incoming]
            merged = list(dict.fromkeys(v for v in current + additions if v))
            if any(v and v not in current for v in additions):
                changes[key] = [{entry_key: v} for v in merged]
        if changes:
            api_json(url, token, "findings/%d/" % existing["id"], timeout, changes, method="PATCH")
            updated += 1
    return updated


def write_private(path, data):
    # Refuse symlinks/existing files so exports never clobber another run.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Run folder or security-report.json")
    parser.add_argument("--url", help="DefectDojo base URL; required with --upload")
    parser.add_argument("--branch", help="Engagement branch/scope; required when absent from report")
    parser.add_argument("--repo", help="Import only this repository")
    parser.add_argument("--upload", action="store_true", help="Send results; otherwise dry-run only")
    parser.add_argument("--token-file", type=Path, help="Private file holding the API token")
    parser.add_argument("--output-dir", type=Path, help="New directory for payloads and an import receipt")
    parser.add_argument("--batch-size", type=int, default=500, help="Findings per request, 1-1000")
    parser.add_argument("--timeout", type=int, default=300, help="HTTP timeout in seconds")
    parser.add_argument("--include-code", action="store_true", help="Include redacted non-secret report excerpts")
    parser.add_argument("--no-enrich", action="store_true", help="Do not read adjacent scanner JSON or run metadata")
    parser.add_argument("--update-existing", action="store_true",
                        help="Refresh scanner-owned descriptive fields on matched findings, not review status")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.batch_size <= 1000 or args.timeout < 1:
            raise ValueError("batch size must be 1-1000 and timeout must be positive")
        if args.upload and not args.url:
            raise ValueError("--upload requires an explicit --url for the authorized DefectDojo instance")
        url = validate_url(args.url) if args.url else None
        doc = load_report(args.report, enrich=not args.no_enrich)
        batches, skipped = build_batches(doc, args.branch, args.repo, args.batch_size, args.include_code)
        token = None
        if args.upload:
            token = (args.token_file.expanduser().read_text().strip() if args.token_file
                     else os.environ.get("DEFECTDOJO_API_TOKEN", "").strip())
            if not token or not re.fullmatch(r"[A-Za-z0-9]+", token):
                raise ValueError("set DEFECTDOJO_API_TOKEN or supply --token-file with a valid API token")
        if args.output_dir:
            args.output_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        pending = doc["verification"]["pending"]
        if pending:
            print("Warning: %d findings await verification; imported as unverified." % pending)
        incomplete = sum(1 for s in (doc.get("audit") or {}).values()
                         if not s.get("valid") or s.get("run_status") != "complete")
        if incomplete:
            print("Warning: %d incomplete/invalid audits; their unconfirmed leads are not imported." % incomplete)
        enriched = sum(bool(f.get("scanner_detail")) for f in doc["findings"])
        print("Scanner metadata matched: %d findings; source excerpts: %s"
              % (enriched, "redacted non-secret only" if args.include_code else "excluded"))
        receipt = {"url": url, "uploaded": args.upload, "findings": 0, "skipped": skipped,
                   "enriched": enriched, "include_code": args.include_code, "batches": []}
        print("%s: %d findings in %d requests; skipped %s"
              % ("Upload" if args.upload else "Dry run",
                 sum(len(b["report"]["findings"]) for b in batches), len(batches), skipped))
        for index, batch in enumerate(batches, 1):
            count = len(batch["report"]["findings"])
            name = batch["fields"]["product_name"]
            if args.output_dir:
                write_private(args.output_dir / ("%04d.json" % index), batch)
            result = upload_batch(url, token, batch, args.timeout) if args.upload else {}
            if args.upload and args.update_existing:
                result["refreshed"] = refresh_details(url, token, result["test_id"], batch, args.timeout)
            receipt["findings"] += count
            receipt["batches"].append(dict(result, repo=name, findings=count,
                                           test_title=batch["fields"]["test_title"]))
            print("[%d/%d] %s: %d%s" % (index, len(batches), name, count,
                                       " -> " + result["url"] if result else ""), flush=True)
            if args.output_dir:
                write_private(args.output_dir / ("%04d-receipt.json" % index), receipt["batches"][-1])
        if args.output_dir:
            write_private(args.output_dir / "summary.json", receipt)
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print("import-defectdojo: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
