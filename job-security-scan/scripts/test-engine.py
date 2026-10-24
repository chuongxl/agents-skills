#!/usr/bin/env python3
"""Offline self-tests for the advisory engine: versions, adapters, merge, match, fetch, CLI.

Run: python3 -I scripts/test-engine.py
No network: HTTP is replaced by recorded payloads in tests/fixtures/payloads.
Live behaviour is checked by the CI job 'advisory-live'. Stdlib only; Python 3.8+.
"""

import contextlib
import copy
import io
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import adapters  # noqa: E402
import advisory  # noqa: E402
import engine  # noqa: E402
import inventory  # noqa: E402
import versions  # noqa: E402
from component import Component  # noqa: E402

FIX = os.path.join(SKILL_DIR, "tests", "fixtures")
PAY = os.path.join(FIX, "payloads")
MATCH = os.path.join(SKILL_DIR, "scripts", "match.py")
SEED = os.path.join(SKILL_DIR, "assets", "advisories")
EXAMPLES = os.path.join(SKILL_DIR, "assets", "advisory-examples")
SCHEMA = advisory.load_json(os.path.join(SKILL_DIR, "assets", "advisory.schema.json"))
AT, SHA = "2026-10-23T00:00:00Z", "a" * 64


def payload(name):
    with open(os.path.join(PAY, name), "rb") as fh:
        return fh.read()


def jpayload(name):
    return json.loads(payload(name).decode("utf-8"))


def node(version, exact=True):
    return Component("runtime", "node", "node", version, extra={"exact": exact})


def merged(*paths):
    return engine.merge(engine.load_advisories(list(paths)))


def valid(advs):
    return [e for a in advs for e in advisory.validate_schema(a, {"$ref": "#/$defs/advisory"}, SCHEMA)]


class VersionTests(unittest.TestCase):
    def test_compare(self):
        self.assertEqual(versions.compare("22.14.0", "22.23.4"), -1)
        self.assertEqual(versions.compare("22.23.4", "22.23.4"), 0)
        self.assertEqual(versions.compare("v1.2", "1.2.0"), 0)
        self.assertEqual(versions.compare("1.0.0-rc1", "1.0.0"), -1)
        self.assertIsNone(versions.compare("lts/*", "1.0"))

    def test_lines(self):
        self.assertTrue(versions.line_covers("22", "22.14.0"))
        self.assertFalse(versions.line_covers("22", "24.1.0"))
        self.assertTrue(versions.line_covers("10-15", "12.0.0"))
        self.assertTrue(versions.line_covers("1.22", "1.22.3"))
        self.assertFalse(versions.line_covers("1.22", "1.23.0"))
        self.assertTrue(versions.line_covers("*", "0.0.1"))


class AdapterTests(unittest.TestCase):
    def test_nodejs_wg_real_sample(self):
        advs, skipped = adapters.nodejs_wg(jpayload("nodejs-wg.json"), "https://raw.githubusercontent.com/x", AT, SHA)
        self.assertEqual(valid(advs), [])
        ids = [a["id"] for a in advs]
        self.assertEqual(len(ids), len(set(ids)), "duplicate CVE entries must be merged")
        newest = [a for a in advs if a["id"] == "CVE-2026-58045"][0]
        self.assertEqual([(e["line"], e["fixed"]) for e in newest["affected"]],
                         [("22", "22.23.2"), ("24", "24.18.1"), ("26", "26.5.1")])
        self.assertEqual(newest["severity"], "medium")
        self.assertTrue(any(i.startswith("NODE-WG-") for i in ids), "entries without a CVE keep a stable id")

    def test_ghsa_repo_vendor_advisory(self):
        advs, _ = adapters.ghsa(jpayload("ghsa-repo-next.json"), "https://api.github.com/x", AT, SHA, "vendor", "Vercel")
        self.assertEqual(valid(advs), [])
        a = advs[0]
        self.assertEqual((a["id"], a["aliases"], a["severity"]), ("GHSA-xxxx-yyyy-zzzz", ["CVE-2026-90001"], "high"))
        self.assertEqual(a["component"]["purl"], "pkg:npm/next")
        self.assertEqual([(e["introduced"], e["fixed"]) for e in a["affected"]], [("15.0.0", "15.5.30"), ("16.0.0", "16.4.2")])
        self.assertEqual(a["cvss"]["version"], "3.1")

    def test_ghsa_global_and_range_parsing(self):
        advs, _ = adapters.ghsa(jpayload("ghsa-global-lodash.json"), "https://api.github.com/advisories", AT, SHA, "aggregator", "GHSA")
        self.assertEqual(valid(advs), [])
        self.assertEqual(advs[0]["affected"], [{"line": "*", "introduced": "0", "fixed": "4.17.21"}])
        self.assertEqual(adapters.parse_range(">= 10.0.0, < 15.5.28"), ("10.0.0", "15.5.28", None))
        self.assertIsNone(adapters.parse_range("> 1.0"))
        self.assertIsNone(adapters.parse_range("garbage"))

    def test_go_stdlib_becomes_runtime_component(self):
        advs = adapters.osv_go_runtime(jpayload("go-osv-stdlib.json"), "https://vuln.go.dev/ID/GO-2026-0001.json", AT, SHA)
        self.assertEqual(valid(advs), [])
        a = advs[0]
        self.assertEqual((a["component"]["kind"], a["component"]["name"]), ("runtime", "go"))
        self.assertEqual([(e["introduced"], e["fixed"]) for e in a["affected"]], [("0", "1.21.12"), ("1.22.0", "1.22.5")])
        f, _ = engine.match([Component("runtime", "go", "go", "1.22.3")], engine.merge(advs))
        self.assertEqual(len(f), 1)
        f, _ = engine.match([Component("runtime", "go", "go", "1.22.5")], engine.merge(advs))
        self.assertEqual(f, [])

    def test_enrichment_and_feed(self):
        self.assertEqual(adapters.kev_ids(jpayload("kev.json")), ["CVE-2021-44228", "CVE-2026-90001"])
        self.assertEqual(adapters.eol_cycles(jpayload("eol-nodejs.json"), "2026-10-23"), {"20", "18"})
        leads = adapters.feed_leads(payload("feed.xml"), "spring")
        self.assertEqual([l["cves"] for l in leads], [["CVE-2026-91000"]])
        self.assertIsNone(adapters.feed_leads(b"<not-xml", "x"))


class MatchTests(unittest.TestCase):
    def test_node_oct_2026_line_22(self):
        m = merged(SEED)
        f, _ = engine.match([node("22.14.0")], m)
        ids = {x["id"] for x in f}
        for cve in ("CVE-2026-105482", "CVE-2026-106069", "CVE-2026-111497", "CVE-2026-105481",
                    "CVE-2026-106072", "CVE-2026-106074", "CVE-2026-106073"):
            self.assertIn(cve, ids)
        self.assertNotIn("CVE-2026-105483", ids)   # lines 26 and 24 only
        self.assertNotIn("CVE-2026-106070", ids)   # line 26 only
        self.assertEqual(engine.match([node("22.23.4")], m)[0], [])

    def test_other_lines(self):
        m = merged(SEED)
        ids24 = {x["id"] for x in engine.match([node("24.22.0")], m)[0]}
        self.assertIn("CVE-2026-105483", ids24)
        self.assertEqual(engine.match([node("24.22.1")], m)[0], [])
        ids26 = {x["id"] for x in engine.match([node("26.12.0")], m)[0]}
        self.assertIn("CVE-2026-106070", ids26)

    def test_end_of_life_line_is_flagged_with_eol_data(self):
        m = merged(SEED)
        f, _ = engine.match([node("20.11.0")], m)
        self.assertEqual(f, [], "unlisted line without EOL data is not guessed")
        f, _ = engine.match([node("20.11.0")], m, eol={"runtime:node": {"20"}})
        self.assertTrue(f and all(x["state"] == "affected-end-of-life" for x in f))

    def test_unpinned_runtime_is_possibly_affected(self):
        f, _ = engine.match([node("22", exact=False)], merged(SEED))
        self.assertTrue(f and all(x["state"] == "possibly-affected" for x in f))

    def test_vendor_only_advisory_absent_from_aggregator_is_flagged(self):
        vendor, _ = adapters.ghsa(jpayload("ghsa-repo-next.json"), "https://api.github.com/x", AT, SHA, "vendor", "Vercel")
        osv_like, _ = adapters.ghsa(jpayload("ghsa-global-lodash.json"), "https://api.github.com/advisories", AT, SHA, "aggregator", "GHSA")
        m = engine.merge(vendor + osv_like)
        f, _ = engine.match([Component("package", "npm", "next", "15.5.0", "pkg:npm/next@15.5.0")], m)
        self.assertEqual([x["id"] for x in f], ["GHSA-xxxx-yyyy-zzzz"])
        self.assertEqual(f[0]["source"]["tier"], "vendor")
        self.assertEqual(engine.match([Component("package", "npm", "next", "15.5.30", "pkg:npm/next@15.5.30")], m)[0], [])

    def test_vendor_wins_and_conflict_is_flagged(self):
        vendor, _ = adapters.ghsa(jpayload("ghsa-repo-next.json"), "https://api.github.com/x", AT, SHA, "vendor", "Vercel")
        agg = copy.deepcopy(vendor)
        a = agg[0]
        a["id"], a["aliases"] = "GHSA-aaaa-bbbb-cccc", ["CVE-2026-90001"]
        a["source"].update(tier="aggregator", vendor="GHSA")
        a["affected"] = [{"line": "*", "introduced": "15.0.0", "fixed": "15.5.28"}]
        m = engine.merge(vendor + agg)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0]["source"]["tier"], "vendor")
        self.assertEqual(m[0]["affected"][0]["fixed"], "15.5.30")
        self.assertEqual(len(m[0]["merged_from"]), 2)
        # the 15.x ranges disagree (15.5.30 vs 15.5.28): flagged, vendor value kept
        self.assertEqual([(c["introduced"], c["winner_fixed"], c["other_fixed"]) for c in m[0]["conflicts"]],
                         [("15.0.0", "15.5.30", "15.5.28")])
        agg[0]["affected"] = copy.deepcopy(vendor[0]["affected"])
        self.assertEqual(engine.merge(vendor + agg)[0]["conflicts"], [])

    def test_pending_is_replaced_by_published(self):
        pend = advisory.load_json(os.path.join(EXAMPLES, "pending-preannouncement.json"))["advisories"][0]
        pub, _ = adapters.ghsa(jpayload("ghsa-repo-next.json"), "https://api.github.com/x", AT, SHA, "vendor", "Vercel")
        pend = dict(pend, aliases=["CVE-2026-90001"])
        m = engine.merge([pend] + pub)
        self.assertEqual([a["status"] for a in m], ["published"])
        m = engine.merge([pend])
        f, _ = engine.match([Component("package", "npm", "next", "16.0.0", "pkg:npm/next@16.0.0")], m)
        self.assertEqual(f[0]["state"], "pending")

    def test_glibc_conditional_advisory(self):
        m = merged(EXAMPLES)
        c = Component("package", "npm", "next", "16.0.0", "pkg:npm/next@16.0.0")
        def run(comp, env):
            f, s = engine.match([comp], m, env=env)
            return [x for x in f if x["id"] == "CVE-2026-96889"], [x for x in s if x["id"] == "CVE-2026-96889"]
        f, _ = run(c, {})
        self.assertEqual(f[0]["state"], "affected-if-condition-holds")
        self.assertEqual({(u["type"], u["value"]) for u in f[0]["unmet_conditions"]}, {("os", "linux"), ("libc", "glibc")})
        f, s = run(c, {"os": {"linux"}, "libc": {"musl"}})
        self.assertEqual((f, len(s)), ([], 1))
        f, _ = run(c, {"os": {"linux"}, "libc": {"glibc"}})
        self.assertEqual(f[0]["state"], "affected")
        c2 = Component("package", "npm", "next", "16.4.1", "pkg:npm/next@16.4.1")
        self.assertEqual(run(c2, {"os": {"linux"}, "libc": {"glibc"}})[0], [])

    def test_kev_raises_severity_one_step(self):
        advs, _ = adapters.ghsa(jpayload("ghsa-repo-next.json"), "https://api.github.com/x", AT, SHA, "vendor", "Vercel")
        m = engine.apply_kev(engine.merge(advs), adapters.kev_ids(jpayload("kev.json")))
        self.assertEqual((m[0]["severity"], m[0]["exploited"], m[0]["kev_raised_from"]), ("critical", True, "high"))
        engine.apply_kev(m, ["CVE-2026-90001"])
        self.assertEqual(m[0]["severity"], "critical")   # not raised twice

    def test_withdrawn_is_ignored(self):
        advs, _ = adapters.ghsa(jpayload("ghsa-repo-next.json"), "https://api.github.com/x", AT, SHA, "vendor", "Vercel")
        advs[0]["status"] = "withdrawn"
        self.assertEqual(engine.merge(advs), [])


class InventoryTests(unittest.TestCase):
    def test_runtime_from_repo_and_ranges_dropped(self):
        comps = inventory.runtimes_from_repo(os.path.join(FIX, "node-22-14-demo"))
        self.assertEqual([(c.key, c.version) for c in comps], [("runtime:node", "22.14.0")])   # engines ">=22" ignored
        self.assertTrue(comps[0].extra["exact"])

    def test_facts_from_dockerfile(self):
        self.assertEqual(inventory.facts_from_repo(os.path.join(FIX, "node-22-14-demo")), {"os": "linux", "libc": "glibc"})
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, "Dockerfile"), "w") as fh:
            fh.write("FROM node:22-alpine\n")
        self.assertEqual(inventory.facts_from_repo(d)["libc"], "musl")

    def test_cyclonedx_packages(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "sbom.json")
        json.dump({"components": [{"name": "next", "purl": "pkg:npm/next@16.0.0"},
                                  {"name": "x", "purl": "pkg:npm/%40nestjs/core@10.0.0"}, {"name": "nopurl"}]}, open(p, "w"))
        comps = inventory.from_cyclonedx(p)
        self.assertEqual([(c.key, c.version) for c in comps], [("pkg:npm/next", "16.0.0"), ("pkg:npm/%40nestjs/core", "10.0.0")])


def load_fetch_module():
    spec = importlib.util.spec_from_file_location("fetch_advisories", os.path.join(SKILL_DIR, "scripts", "fetch-advisories.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FetchTests(unittest.TestCase):
    """fetch-advisories.py with HTTP replaced by recorded payloads."""

    def setUp(self):
        self.fetch = load_fetch_module()
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out)
        self.nf = self.fetch.netfetch
        self.orig = self.nf.fetch
        import hashlib

        def fake(url, allowed, max_bytes=0, timeout=0, headers=None, retries=0):
            if "security-wg" in url:
                data = payload("nodejs-wg.json")
            elif "security-advisories" in url:
                data = payload("ghsa-repo-next.json")
            elif "known_exploited" in url:
                data = payload("kev.json")
            elif "endoflife.date" in url:
                data = payload("eol-nodejs.json")
            else:
                raise self.nf.FetchError("offline test: %s" % url)
            return data, hashlib.sha256(data).hexdigest(), url
        self.nf.fetch = fake
        self.addCleanup(setattr, self.nf, "fetch", self.orig)

    def run_fetch(self, *extra, now="2026-10-23T00:00:00Z"):
        with contextlib.redirect_stdout(io.StringIO()):
            return self._run_fetch(extra, now)

    def _run_fetch(self, extra, now):
        return self.fetch.main(["--out", self.out, "--now", now, "--only", "nodejs", "nextjs", "cisa-kev", "endoflife"] + list(extra))

    def test_fetch_validates_and_is_idempotent(self):
        rc = self.run_fetch()
        self.assertEqual(rc, 3)   # html/rss sources of those vendors are unreachable offline
        names = sorted(os.listdir(os.path.join(self.out, "advisories")))
        self.assertEqual(names, ["nextjs-ghsa-repo.json", "nodejs-security-wg.json"])
        r = advisory.validate_paths([os.path.join(self.out, "advisories")], SCHEMA)
        self.assertEqual([e for x in r for e in x["errors"]], [])
        self.assertEqual(advisory.load_json(os.path.join(self.out, "enrichment", "kev.json"))["cves"], ["CVE-2021-44228", "CVE-2026-90001"])
        def snapshot():
            snap = {}
            for dp, _d, fs in os.walk(self.out):
                for f in fs:
                    p = os.path.join(dp, f)
                    with open(p) as fh:
                        snap[p] = fh.read()
            return snap
        before = snapshot()
        self.run_fetch(now="2026-10-24T09:00:00Z")   # later clock, same content
        after = snapshot()
        self.assertEqual(before, after, "unchanged sources must produce no diff")

    def test_fetch_failure_does_not_delete_previous_data(self):
        self.run_fetch()
        self.nf.fetch = lambda *a, **k: (_ for _ in ()).throw(self.nf.FetchError("down"))
        self.run_fetch()
        self.assertTrue(os.path.exists(os.path.join(self.out, "advisories", "nodejs-security-wg.json")))

    def test_match_uses_fetched_cache_with_kev(self):
        self.run_fetch()
        r = subprocess.run([sys.executable, "-I", MATCH, "--inventory", self.inv(), "--cache", self.out, "--format", "json",
                            "--advisories", EXAMPLES], capture_output=True, text=True)
        rep = json.loads(r.stdout)
        ids = {f["id"]: f for f in rep["findings"]}
        self.assertTrue(ids["GHSA-xxxx-yyyy-zzzz"]["exploited"])
        self.assertEqual(ids["GHSA-xxxx-yyyy-zzzz"]["severity"], "critical")

    def inv(self):
        p = os.path.join(self.out, "inv.json")
        json.dump({"components": [{"kind": "package", "ecosystem": "npm", "name": "next", "version": "15.5.0", "purl": "pkg:npm/next"}]}, open(p, "w"))
        return p

    def test_advisory_skeleton_is_incomplete_and_unapproved(self):
        page = b"<html><head><style>x{}</style></head><body><h1>Security release</h1><p>CVE-2026-1 fixed in 1.2.3</p><script>evil()</script></body></html>"
        import hashlib
        self.nf.fetch = lambda url, allowed, *a, **k: (page, hashlib.sha256(page).hexdigest(), url)
        out = os.path.join(self.out, "new.json")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = self.fetch.main(["--advisory", "https://nodejs.org/en/blog/vulnerability/x", "--out", out, "--now", AT])
        self.assertEqual(rc, 0)
        with open(out[:-5] + ".source.txt") as fh:
            txt = fh.read()
        self.assertIn("CVE-2026-1 fixed in 1.2.3", txt)
        self.assertNotIn("evil()", txt)
        r = advisory.validate_file(out, SCHEMA)
        self.assertTrue(r["errors"], "skeleton must not validate until completed")
        with contextlib.redirect_stderr(io.StringIO()):
            rc = self.fetch.main(["--advisory", "https://not-a-source.example.com/x", "--out", out])
        self.assertEqual(rc, 2)


class NetfetchTests(unittest.TestCase):
    def test_authorization_not_forwarded_to_another_host(self):
        import urllib.request
        import netfetch
        h = netfetch._NoAuthAcrossHosts({"a.example", "b.example"})
        req = urllib.request.Request("https://a.example/x", headers={"Authorization": "Bearer t"})
        def has_auth(r):
            return "Authorization" in {k.title() for k in list(r.headers) + list(r.unredirected_hdrs)}
        self.assertFalse(has_auth(h.redirect_request(req, None, 302, "", {}, "https://b.example/y")))
        self.assertTrue(has_auth(h.redirect_request(req, None, 302, "", {}, "https://a.example/z")))


class MatchCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", MATCH] + list(args), capture_output=True, text=True)

    def test_repo_node_22_14_fails_and_reports(self):
        r = self.run_cli("--repo", os.path.join(FIX, "node-22-14-demo"), "--format", "json")
        self.assertEqual(r.returncode, 1)
        rep = json.loads(r.stdout)
        self.assertIn("CVE-2026-111497", {f["id"] for f in rep["findings"]})
        self.assertEqual(rep["environment"], {"libc": ["glibc"], "os": ["linux"]})

    def test_fail_on_none_and_patched_version(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        open(os.path.join(d, ".nvmrc"), "w").write("22.23.4\n")
        open(os.path.join(d, "package.json"), "w").write("{}")
        r = self.run_cli("--repo", d)
        self.assertEqual(r.returncode, 0)
        self.assertIn("No applicable advisories", r.stdout)
        r = self.run_cli("--repo", os.path.join(FIX, "node-22-14-demo"), "--fail-on", "none")
        self.assertEqual(r.returncode, 0)

    def test_unapproved_llm_assisted_is_ignored(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        data = advisory.load_json(os.path.join(SEED, "nodejs-2026-10.json"))
        for a in data["advisories"]:
            a["source"].pop("approved_by", None)
            a["source"]["method"] = "llm-assisted"
        json.dump(data, open(os.path.join(d, "x.json"), "w"))
        r = self.run_cli("--repo", os.path.join(FIX, "node-22-14-demo"), "--advisories", d)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Ignored 15 unapproved", r.stdout)
        r = self.run_cli("--repo", os.path.join(FIX, "node-22-14-demo"), "--advisories", d, "--trust-unapproved")
        self.assertEqual(r.returncode, 1)

    def test_fixtures_are_not_scanned_from_a_parent_dir(self):
        """The daily job scans the whole repo; test fixtures must not be inventoried."""
        self.assertEqual(inventory.runtimes_from_repo(os.path.dirname(os.path.dirname(FIX))), [])

    def test_allow_empty_inventory(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        self.assertEqual(self.run_cli("--repo", d).returncode, 2)
        r = self.run_cli("--repo", d, "--allow-empty", "--fail-on", "none")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_usage_and_invalid_data(self):
        self.assertEqual(self.run_cli().returncode, 2)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        open(os.path.join(d, "bad.json"), "w").write('{"schema_version": 1, "advisories": [{"id": "x"}]}')
        r = self.run_cli("--repo", os.path.join(FIX, "node-22-14-demo"), "--advisories", d)
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid advisory data", r.stderr)


class ScanIntegrationTests(unittest.TestCase):
    def test_run_scan_advisories_and_report(self):
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work)
        cfg = os.path.join(work, "repository.md")
        with open(cfg, "w") as fh:
            fh.write('---\nteam: t\norg: o\nmonorepo-root: "%s"\nci-runner: x\nfail-on-severity: HIGH\n'
                     'output-dir: "%s"\nrepos:\n  - name: node-22-14-demo\n    active: true\n    has-dockerfile: false\n---\n'
                     % (FIX, os.path.join(work, "out")))
        env = dict(os.environ, ADVISORY_OFFLINE="1")
        r = subprocess.run(["bash", os.path.join(SKILL_DIR, "scripts", "run-scan.sh"), "--config", cfg, "--scanner", "advisories"],
                           capture_output=True, text=True, env=env, cwd=work)
        self.assertIn("critical/high", r.stdout)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        rep = advisory.load_json(os.path.join(work, "out", "node-22-14-demo", "advisories.json"))
        self.assertIn("CVE-2026-111497", {f["id"] for f in rep["findings"]})
        with open(os.path.join(work, "out", "security-report.html")) as fh:
            html = fh.read()
        self.assertIn("CVE-2026-111497", html)


if __name__ == "__main__":
    unittest.main(verbosity=1)
