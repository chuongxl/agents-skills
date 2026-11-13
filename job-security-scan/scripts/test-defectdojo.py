#!/usr/bin/env python3
"""Offline tests for the DefectDojo importer. Run: python3 -I scripts/test-defectdojo.py."""

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib import error

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS / "lib"))
import report_model  # noqa: E402
import report_store  # noqa: E402

spec = importlib.util.spec_from_file_location("import_defectdojo", SCRIPTS / "import-defectdojo.py")
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def document():
    row = {"repo": "app", "scanner": "trivy", "type": "vulnerability", "severity": "HIGH",
           "file": "package-lock.json", "line": 8, "code": "SOURCE MUST NOT LEAVE",
           "package": "example", "installed_version": "1.0", "fixed_version": "2.0",
           "rule_id": "CVE-2026-1234", "title": "Outdated dependency", "description": "Upgrade it.",
           "url": "https://example.com/advisory"}
    doc = report_model.build_document([row], {
        "org": "org", "team": "team", "repos": ["app"], "run_dir": "/tmp/security-run-example",
        "profile": "standard", "coverage": {"app": {"trivy": "medium"}},
        "generated_at": "2026-11-05T14:09:18+07:00",
    })
    doc["schema_version"] = 2
    return doc


class ConversionTests(unittest.TestCase):
    def test_complete_detail_mapping_retains_context_and_structured_fix(self):
        doc = document()
        f = doc["findings"][0]
        f.update(verdict="confirmed", verified_severity="MEDIUM", change="unchanged", carried=True,
                 verdict_detail={"evidence": "Observed read of another user's record.",
                                 "likelihood": "high", "impact": "medium", "root_cause": "Owner check absent",
                                 "intended_behavior": "Only owners can read", "confidence": 8,
                                 "trace": ["src/app.py:8 handler", "src/db.py:12 query"],
                                 "remediation_guidance": "Check the owner first."})
        row = importer.convert_finding(f, doc)
        self.assertEqual(row.get("fix_version"), "2.0")
        self.assertTrue(row.get("fix_available"))
        for value in ("app", "vulnerability", "unchanged", "Owner check absent",
                      "Only owners can read", "src/db.py:12 query", "HIGH", "MEDIUM"):
            self.assertIn(value, row["description"])
        self.assertIn("Observed read", row.get("steps_to_reproduce", ""))
        self.assertIn("high", row.get("severity_justification", ""))
        self.assertEqual(row.get("scanner_confidence"), 8)
        self.assertNotIn("SOURCE MUST NOT LEAVE", json.dumps(row))
        f.update(type="misconfig", package="", fixed_version="Set readOnlyRootFilesystem to true")
        config = importer.convert_finding(f, doc)
        self.assertNotIn("fix_version", config)
        self.assertNotIn("fix_available", config)

    def test_approved_excerpts_are_redacted_but_secret_rows_stay_minimal(self):
        doc = document()
        f = doc["findings"][0]
        f["code"] = 'password=not-a-real-password-value'
        row = importer.convert_finding(f, doc, include_code=True)
        self.assertIn("Source excerpt", row["description"])
        self.assertNotIn("not-a-real-password-value", row["description"])
        f.update(type="secret", title="SECRET FREE TEXT", description="SECRET FREE TEXT",
                 verdict_detail={"evidence": "SECRET FREE TEXT"})
        secret = importer.convert_finding(f, doc, include_code=True)
        self.assertNotIn("SECRET FREE TEXT", json.dumps(secret))
        self.assertNotIn("password=", json.dumps(secret))
        f.update(type="exposure", rule_id="credential-store")
        protected = importer.convert_finding(f, doc, include_code=True)
        self.assertNotIn("SECRET FREE TEXT", json.dumps(protected))

    def test_test_context_includes_clean_scanners_and_run_summaries(self):
        doc = document()
        doc["run"]["coverage"]["app"]["shai-hulud"] = "full"
        doc["run"].update(partial=True, since="origin/main")
        doc["audit"] = {"app": {"valid": False, "run_status": "incomplete",
                                "incomplete_reason": "Budget exhausted", "errors": []}}
        doc["shai_hulud"]["targets"] = [{"repo": "app", "verdict": "clean", "checked": {"packages": 5},
                                        "credential_stores": ["/private/credentials"]}]
        batches, _ = importer.build_batches(doc, "main")
        self.assertEqual(len(batches), 2)
        text = batches[0]["report"].get("description", "")
        for value in ("origin/main", "Budget exhausted", "clean", "packages", "verification"):
            self.assertIn(value, text)
        self.assertNotIn("/private/credentials", text)
        self.assertEqual(batches[0]["report"]["findings"], [])
        self.assertEqual(batches[0]["fields"]["close_old_findings"], "false")

    def test_verdicts_severity_secret_redaction_and_rejected(self):
        doc = document()
        f = doc["findings"][0]
        f.update(verdict="confirmed", verified_severity="MEDIUM",
                 verdict_detail={"evidence": "Confirmed trace", "likelihood": "high", "impact": "medium"})
        secret = dict(f, fingerprint="a" * 16, type="secret", title="RAW SECRET",
                      description="RAW SECRET", code="", verdict="needs_validation",
                      verified_severity=None, verdict_detail={"blocker": "RAW SECRET",
                                                            "validation_plan": "RAW SECRET"})
        doc["findings"] += [secret, dict(f, fingerprint="b" * 16, verdict="rejected")]
        batches, skipped = importer.build_batches(doc, "main")
        rows = batches[0]["report"]["findings"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(skipped, {"rejected": 1})
        self.assertEqual(rows[0]["severity"], "Medium")
        self.assertTrue(rows[0]["verified"])
        self.assertFalse(rows[1]["verified"])
        self.assertNotIn("RAW SECRET", json.dumps(rows))
        self.assertNotIn("SOURCE MUST NOT LEAVE", json.dumps(rows))
        self.assertEqual(rows[0]["component_version"], "1.0")
        self.assertEqual(rows[0]["vulnerability_ids"], ["CVE-2026-1234"])

    def test_batch_scope_and_no_closure_or_forced_verification(self):
        doc = document()
        doc["run"].update(partial=True, since="origin/main")
        row = dict(doc["findings"][0], fingerprint="c" * 16, scanner="osv")
        doc["findings"] += [row, dict(row, fingerprint="d" * 16)]
        batches, _ = importer.build_batches(doc, "feature/a", batch_size=1)
        self.assertEqual(len(batches), 3)
        for batch in batches:
            fields = batch["fields"]
            self.assertEqual(fields["close_old_findings"], "false")
            self.assertEqual(fields["do_not_reactivate"], "true")
            self.assertNotIn("verified", fields)
            self.assertEqual(fields["engagement_name"], "job-security-scan / feature/a")
        self.assertNotEqual(batches[0]["fields"]["test_title"], batches[-1]["fields"]["test_title"])
        self.assertEqual(batches[0]["fields"]["test_title"], batches[1]["fields"]["test_title"])

    def test_branch_required_and_source_ref_default(self):
        doc = document()
        with self.assertRaisesRegex(ValueError, "branch unavailable"):
            importer.build_batches(doc)
        doc["run"]["source_refs"] = {"app": {"branch": "main", "commit": "abc"}}
        batches, _ = importer.build_batches(doc)
        self.assertEqual(batches[0]["fields"]["commit_hash"], "abc")

    def test_accepted_fixed_and_host_are_not_uploaded(self):
        doc = document()
        doc["baseline"] = {"accepted": [dict(doc["findings"][0])]}
        doc["fixed"] = [dict(doc["findings"][0])]
        doc["findings"].append(dict(doc["findings"][0], repo="this machine"))
        batches, skipped = importer.build_batches(doc, "main")
        self.assertEqual(len(batches[0]["report"]["findings"]), 1)
        self.assertEqual(skipped, {"host": 1})

    def test_identity_survives_line_move_and_is_namespaced(self):
        doc = document()
        first = importer.convert_finding(doc["findings"][0], doc)
        moved = deepcopy(doc["findings"][0])
        moved["line"] += 10
        self.assertEqual(first["unique_id_from_tool"], importer.convert_finding(moved, doc)["unique_id_from_tool"])
        other = dict(doc, org="different")
        self.assertNotEqual(first["unique_id_from_tool"], importer.convert_finding(moved, other)["unique_id_from_tool"])

    def test_large_valid_report_and_bad_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "security-report.json"
            doc = document()
            doc["schema_version"] = 2
            doc["padding"] = " " * (6 * 1024 * 1024)
            path.write_text(json.dumps(doc))
            self.assertEqual(importer.load_report(tmp)["findings"][0]["title"], "Outdated dependency")
            self.assertEqual(importer.load_report(path)["findings"][0]["title"], "Outdated dependency")
            doc["counts"]["HIGH"] = 0
            path.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "counts do not match"):
                importer.load_report(tmp)

    def test_v3_run_folder_imports_finding_from_integrity_checked_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            report_store.save(document(), run_dir)
            index = json.loads((run_dir / "security-report.json").read_text())
            self.assertEqual(index["schema_version"], 3)
            self.assertEqual(len(index["shards"]), 1)
            self.assertTrue((run_dir / index["shards"][0]["file"]).is_file())

            loaded = importer.load_report(run_dir)
            batches, _ = importer.build_batches(loaded, "main")

            self.assertEqual(len(batches[0]["report"]["findings"]), 1)
            self.assertEqual(batches[0]["report"]["findings"][0]["title"], "Outdated dependency")


class EnrichmentTests(unittest.TestCase):
    def put(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return path

    def test_raw_trivy_and_sidecar_restore_full_description_cvss_cwe_and_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = document()
            self.put(root, "security-report.json", doc)
            self.put(root, "run-metadata.json", {"source_refs": {"app": {
                "branch": "develop", "commit": "abc123", "dirty": False, "vcs": "git"}}})
            full = "Full explanation. " * 60
            self.put(root, "app/trivy.json", {"Results": [{"Target": "package-lock.json",
                "Vulnerabilities": [{"VulnerabilityID": "CVE-2026-1234", "PkgName": "example",
                    "InstalledVersion": "1.0", "FixedVersion": "2.0", "Description": full,
                    "CweIDs": ["CWE-79"], "SeveritySource": "nvd",
                    "CVSS": {"nvd": {"V3Vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                                      "V3Score": 9.8}},
                    "References": ["https://example.com/full"], "PublishedDate": "2026-01-02T00:00:00Z"}]}]})
            loaded = importer.load_report(root)
            batches, _ = importer.build_batches(loaded)
            row = batches[0]["report"]["findings"][0]
            self.assertIn(full, row["description"])
            self.assertEqual(row.get("cwe"), 79)
            self.assertEqual(row.get("cvssv3_score"), 9.8)
            self.assertIn("https://example.com/full", row["references"])
            self.assertEqual(row.get("publish_date"), "2026-01-02")
            self.assertEqual(batches[0]["fields"]["commit_hash"], "abc123")
            self.assertEqual(row["unique_id_from_tool"],
                             importer.convert_finding(doc["findings"][0], doc)["unique_id_from_tool"])

    def test_osv_matches_package_and_version_and_retains_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = document()
            doc["findings"][0].update(scanner="osv", rule_id="GHSA-aaaa-bbbb-cccc", fixed_version="")
            self.put(root, "security-report.json", doc)
            self.put(root, "app/osv.json", {"results": [{"source": {"path": "/workspace/app/package-lock.json"},
                "packages": [{"package": {"name": "example", "version": "1.0"}, "vulnerabilities": [{
                    "id": "GHSA-aaaa-bbbb-cccc", "aliases": ["CVE-2026-1234"], "details": "Full OSV details.",
                    "references": [{"url": "https://example.com/osv"}],
                    "affected": [{"package": {"name": "other"}, "ranges": [{"events": [{"fixed": "99"}]}]},
                                 {"package": {"name": "example"}, "ranges": [{"events": [{"fixed": "2.0"}]}]}],
                    "severity": [{"type": "CVSS_V3", "score":
                                  "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}]}]}]}]})
            loaded = importer.load_report(root)
            row = importer.build_batches(loaded, "main")[0][0]["report"]["findings"][0]
            self.assertIn("CVE-2026-1234", row["vulnerability_ids"])
            self.assertEqual(row["fix_version"], "2.0")
            self.assertIn("Full OSV details.", row["description"])
            self.assertNotIn("99", row["fix_version"])
            self.assertTrue(row.get("cvssv3"))
            doc["findings"][0]["installed_version"] = "different"
            self.put(root, "security-report.json", doc)
            unmatched = importer.build_batches(importer.load_report(root), "main")[0][0]["report"]["findings"][0]
            self.assertNotIn("Full OSV details.", unmatched["description"])

    def test_semgrep_full_message_and_cwe_without_source_or_secret_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = document()
            doc["findings"][0].update(scanner="semgrep", type="sast", rule_id="python.query",
                                      file="src/app.py", package="", installed_version="", fixed_version="")
            self.put(root, "security-report.json", doc)
            self.put(root, "app/semgrep.json", {"results": [{"path": "src/app.py", "start": {"line": 8},
                "check_id": "python.query", "extra": {"message": "Complete SAST explanation.",
                "lines": "RAW SOURCE NEVER UPLOAD", "metadata": {"cwe": ["CWE-89: SQL injection"],
                "references": ["https://example.com/one", "https://example.com/two"],
                "confidence": "HIGH", "owasp": ["A03:2021"]}}}]})
            row = importer.build_batches(importer.load_report(root), "main")[0][0]["report"]["findings"][0]
            self.assertEqual(row.get("cwe"), 89)
            self.assertIn("https://example.com/two", row["references"])
            self.assertIn("A03:2021", row["description"])
            self.assertNotIn("RAW SOURCE NEVER UPLOAD", json.dumps(row))

    def test_file_level_misconfig_matches_fallback_report_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = document()
            doc["findings"][0].update(type="misconfig", rule_id="DS-0002", file="Dockerfile", line=1,
                                      package="", installed_version="", fixed_version="Set a user")
            self.put(root, "security-report.json", doc)
            self.put(root, "app/trivy.json", {"Results": [{"Target": "Dockerfile", "Misconfigurations": [{
                "ID": "DS-0002", "Description": "Full file-level explanation.", "CauseMetadata": {}}]}]})
            row = importer.build_batches(importer.load_report(root), "main")[0][0]["report"]["findings"][0]
            self.assertIn("Full file-level explanation.", row["description"])
            self.assertEqual(row["line"], 1)

    def test_enrichment_refuses_symlinks_and_repo_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = document()
            self.put(root, "security-report.json", doc)
            external = self.put(root, "outside.json", {"Results": []})
            (root / "app").mkdir()
            (root / "app/trivy.json").symlink_to(external)
            with self.assertRaisesRegex(ValueError, "symlink"):
                importer.load_report(root)
            (root / "app/trivy.json").unlink()
            doc["findings"][0]["repo"] = "../outside"
            self.put(root, "security-report.json", doc)
            with self.assertRaisesRegex(ValueError, "repository"):
                importer.load_report(root)


class TransportTests(unittest.TestCase):
    def test_refresh_accepts_native_whitespace_null_and_cvss_defaults(self):
        batch = importer.build_batches(document(), "main")[0][0]
        row = batch["report"]["findings"][0]
        row.update(description="  Explanation. \n", component_version="",
                   cvssv4="CVSS:4.0/AV:N/AC:H/AT:N/PR:L/UI:N/VC:N/VI:N/VA:L/SC:N/SI:N/SA:N/E:P/CR:X")
        stored = dict(row, id=7, test=42, description="Explanation.", component_version=None,
                      cvssv4=row["cvssv4"].replace("/CR:X", ""))
        with patch.object(importer, "api_json", return_value={"next": None, "results": [stored]}) as api:
            self.assertEqual(importer.refresh_details("http://localhost:8080", "TOKEN", 42, batch, 30), 0)
        self.assertEqual(api.call_count, 1)

    def test_refresh_ignores_server_title_capitalization(self):
        batch = importer.build_batches(document(), "main")[0][0]
        row = batch["report"]["findings"][0]
        stored = dict(row, id=7, test=42, title=row["title"].title(),
                      vulnerability_ids=[{"vulnerability_id": v} for v in row["vulnerability_ids"]])
        with patch.object(importer, "api_json", return_value={"next": None, "results": [stored]}) as api:
            self.assertEqual(importer.refresh_details("http://localhost:8080", "TOKEN", 42, batch, 30), 0)
        self.assertEqual(api.call_count, 1)

    def test_refresh_restores_native_cwe_relations_and_preserves_manual_aliases(self):
        batch = importer.build_batches(document(), "main")[0][0]
        row = batch["report"]["findings"][0]
        row.update(cwe=79, cwes=[79, 89])
        stored = dict(row, id=7, test=42, cwes=[],
                      vulnerability_ids=[{"vulnerability_id": "MANUAL-123"}])
        writes = []
        def fake_api(url, token, path, timeout, data=None, method="GET"):
            if method == "GET":
                return {"next": None, "results": [stored]}
            writes.append(data)
            stored.update(data)
            return stored
        with patch.object(importer, "api_json", side_effect=fake_api):
            importer.refresh_details("http://localhost:8080", "TOKEN", 42, batch, 30)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].get("cwes"), [{"cwe": "CWE-79"}, {"cwe": "CWE-89"}])
        self.assertIn({"vulnerability_id": "MANUAL-123"}, writes[0].get("vulnerability_ids", []))
        self.assertIn({"vulnerability_id": "CVE-2026-1234"}, writes[0].get("vulnerability_ids", []))

    def test_refresh_matches_test_and_uid_without_overwriting_review_state(self):
        batch = importer.build_batches(document(), "main")[0][0]
        row = batch["report"]["findings"][0]
        stored = dict(row, id=7, test=42, description="Old incomplete description",
                      active=False, verified=True, severity="Low", risk_accepted=True)
        writes = []
        def fake_api(url, token, path, timeout, data=None, method="GET"):
            if method == "GET":
                return {"next": None, "results": [stored]}
            writes.append((path, data))
            stored.update(data)
            return stored
        with patch.object(importer, "api_json", side_effect=fake_api):
            self.assertEqual(importer.refresh_details("http://localhost:8080", "TOKEN", 42, batch, 30), 1)
            self.assertEqual(importer.refresh_details("http://localhost:8080", "TOKEN", 42, batch, 30), 0)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], "findings/7/")
        self.assertEqual(writes[0][1]["description"], row["description"])
        for key in ("active", "verified", "severity", "risk_accepted", "is_mitigated", "test"):
            self.assertNotIn(key, writes[0][1])
        self.assertFalse(stored["active"])
        self.assertTrue(stored["verified"])

    def test_url_credentials_external_http_and_redirects_refused(self):
        for url in ("http://example.com", "https://user:pass@example.com", "file:///tmp/x",
                    "https://example.com?token=abc", "https://example.com/#fragment"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                importer.validate_url(url)
        self.assertEqual(importer.validate_url("http://[::1]:8080/"), "http://[::1]:8080")
        self.assertEqual(importer.validate_url("https://dojo.example.com/"), "https://dojo.example.com")
        self.assertIsNone(importer.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other"))

    def test_multipart_and_successful_upload(self):
        batch = importer.build_batches(document(), "main")[0][0]
        with patch.object(importer.request, "build_opener") as build:
            response = build.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b'{"test_id": 42, "product_id": 3, "engagement_id": 4}'
            result = importer.upload_batch("http://127.0.0.1:8080", "TESTTOKEN", batch, 30)
            req = build.return_value.open.call_args[0][0]
            self.assertEqual(req.full_url, "http://127.0.0.1:8080/api/v2/reimport-scan/")
            self.assertEqual(req.get_header("Authorization"), "Token TESTTOKEN")
            self.assertIn(b'filename="findings.json"', req.data)
            self.assertIn(b'name="close_old_findings"\r\n\r\nfalse', req.data)
            self.assertNotIn(b'name="verified"', req.data)
            self.assertEqual(result["test_id"], 42)

    def test_http_failure_does_not_echo_body_or_retry(self):
        batch = importer.build_batches(document(), "main")[0][0]
        with patch.object(importer.request, "build_opener") as build:
            build.return_value.open.side_effect = error.HTTPError("url", 401, "SECRET", {}, None)
            with self.assertRaisesRegex(ValueError, "HTTP 401"):
                importer.upload_batch("http://localhost:8080", "TESTTOKEN", batch, 30)
            self.assertEqual(build.return_value.open.call_count, 1)

    def test_dry_run_never_connects_and_output_is_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "security-report.json"
            path.write_text(json.dumps(document()))
            output = Path(tmp) / "export"
            with patch.object(importer, "upload_batch") as upload:
                self.assertEqual(importer.main([str(path), "--branch", "main", "--output-dir", str(output)]), 0)
                upload.assert_not_called()
            self.assertEqual((output / "0001.json").stat().st_mode & 0o777, 0o600)
            summary = json.loads((output / "summary.json").read_text())
            self.assertFalse(summary["uploaded"])
            self.assertEqual(summary["findings"], 1)
            with self.assertRaises(FileExistsError):
                importer.write_private(output / "summary.json", {})

    def test_upload_requires_explicit_url_before_reading_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "security-report.json"
            report.write_text(json.dumps(document()))
            stderr = io.StringIO()
            with patch.object(importer, "upload_batch") as upload, \
                    redirect_stderr(stderr):
                result = importer.main([
                    str(report), "--branch", "main", "--upload",
                    "--token-file", str(Path(tmp) / "missing-token"),
                ])

            self.assertEqual(result, 1)
            self.assertIn("requires an explicit --url", stderr.getvalue())
            upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
