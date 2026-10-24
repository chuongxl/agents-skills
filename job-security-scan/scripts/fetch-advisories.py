#!/usr/bin/env python3
"""fetch-advisories.py - fetch vendor bulletins and aggregator feeds into the advisory schema.

Usage:
  python3 -I scripts/fetch-advisories.py --out DIR [--only ID ...] [--inventory FILE]
                                         [--package PURL ...] [--since-days N] [--json]
  python3 -I scripts/fetch-advisories.py --advisory URL --out FILE.json

Fetch mode writes, under DIR:
  advisories/*.json         advisory bundles (P0 schema, validated; invalid items are dropped and counted)
  enrichment/kev.json       CISA KEV cve ids
  enrichment/eol.json       end-of-life cycles per runtime
  enrichment/leads.json     new bulletin items from RSS/Atom feeds that mention a CVE (ingest with --advisory)
  manifest.json             per-source sha256, byte count, timestamp, status
Re-running with unchanged sources rewrites nothing.

--advisory URL fetches one bulletin page and writes FILE.json (a skeleton advisory, incomplete on
purpose) plus FILE.source.txt (the page text). Claude completes the JSON from the text; a human
must approve it (source.approved_by) before the matcher uses it.

Trust controls: HTTPS only, hosts must be in assets/sources.json, size limits, payloads are parsed
as data and never executed. Vendor sources are listed first in sources.json and win on merge.

Exit codes: 0 ok, 1 produced invalid output, 2 usage/IO error, 3 some sources failed.
Stdlib only; Python 3.8+. Run with -I.
"""

import argparse
import datetime
import hashlib
import html.parser
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import adapters  # noqa: E402
import advisory  # noqa: E402
import ecosystems  # noqa: E402
import inventory  # noqa: E402
import netfetch  # noqa: E402
import sources  # noqa: E402

MAX_WATCH_PACKAGES = 40
MAX_PAGE_TEXT = 200 * 1024


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump(obj):
    return json.dumps(obj, indent=2, sort_keys=False) + "\n"


def write_if_changed(path, obj):
    text = dump(obj)
    try:
        if open(path, "r", encoding="utf-8").read() == text:
            return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return True


class Ctx:
    def __init__(self, args, src, schema):
        self.args, self.src, self.schema = args, src, schema
        self.allowed = sources.allowed_hosts_of(src)
        self.now = args.now or now_utc()
        self.prev = {}
        mpath = os.path.join(args.out, "manifest.json")
        if os.path.exists(mpath):
            try:
                self.prev = advisory.load_json(mpath).get("sources", {})
            except advisory.AdvisoryError:
                self.prev = {}
        self.manifest = {}
        self.bundles = {}       # name -> list of advisories
        self.enrich = {"kev": None, "eol": {}, "leads": []}
        self.dropped = 0
        self.failures = []
        self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def headers(self, url):
        h = {}
        if netfetch.host_of(url) == "api.github.com":
            h["Accept"] = "application/vnd.github+json"
            h["X-GitHub-Api-Version"] = "2022-11-28"
            if self.token:
                h["Authorization"] = "Bearer " + self.token
        return h

    def get(self, url, max_bytes=netfetch.DEFAULT_MAX_BYTES):
        return netfetch.fetch(url, self.allowed, max_bytes, self.args.timeout, self.headers(url))

    def stamp(self, key, sha):
        """Timestamp to use: keep the previous one when the content hash is unchanged."""
        p = self.prev.get(key, {})
        return p.get("fetched_at", self.now) if p.get("sha256") == sha else self.now

    def record(self, key, url, fmt, sha, nbytes, fetched_at, **extra):
        self.manifest[key] = dict({"url": url, "format": fmt, "sha256": sha, "bytes": nbytes,
                                   "fetched_at": fetched_at, "status": "ok"}, **extra)

    def fail(self, key, url, fmt, err):
        self.failures.append((key, str(err)))
        self.manifest[key] = {"url": url, "format": fmt, "status": "error", "error": str(err)[:300]}

    def add(self, bundle, advs):
        good = []
        for a in advs:
            errs = advisory.validate_schema(a, {"$ref": "#/$defs/advisory"}, self.schema)
            if not errs:
                errs, _w = advisory.semantic_checks(a, bundle, self.allowed)
            if errs:
                self.dropped += 1
            else:
                good.append(a)
        self.bundles.setdefault(bundle, []).extend(good)


# ------------------------------------------------------------------- handlers

def h_nodejs(ctx, key, url, vendor):
    raw, sha, _ = ctx.get(url)
    at = ctx.stamp(key, sha)
    advs, skipped = adapters.nodejs_wg(json.loads(raw.decode("utf-8")), url, at, sha)
    ctx.add("nodejs-security-wg", advs)
    ctx.record(key, url, "json", sha, len(raw), at, advisories=len(advs), skipped=skipped)


def h_ghsa_repo(ctx, key, url, vendor, name):
    raw, sha, _ = ctx.get(url + ("&" if "?" in url else "?") + "per_page=100")
    at = ctx.stamp(key, sha)
    advs, skipped = adapters.ghsa(json.loads(raw.decode("utf-8")), url, at, sha, "vendor", vendor)
    ctx.add(name, advs)
    ctx.record(key, url, "ghsa-repo", sha, len(raw), at, advisories=len(advs), skipped=skipped)


def h_go(ctx, key, url, vendor, packages):
    raw, sha, _ = ctx.get(url)
    index = json.loads(raw.decode("utf-8"))
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=ctx.args.since_days)).strftime("%Y-%m-%d")
    recent = sorted((e for e in index if str(e.get("modified", ""))[:10] >= cutoff),
                    key=lambda e: e["id"])[:ctx.args.max_records]
    base = url.rsplit("/index/", 1)[0]
    shas, advs, nbytes = [sha], [], len(raw)
    for e in recent:
        rurl = "%s/ID/%s.json" % (base, e["id"])
        rraw, rsha, _ = ctx.get(rurl)
        shas.append(rsha)
        nbytes += len(rraw)
        record = json.loads(rraw.decode("utf-8"))
        advs.extend(adapters.osv_go_runtime(record, rurl, "{AT}", rsha, packages))
    total = hashlib.sha256("".join(shas).encode()).hexdigest()
    at = ctx.stamp(key, total)
    for a in advs:
        a["source"]["fetched_at"] = at
    ctx.add("go-vulndb", advs)
    ctx.record(key, url, "osv", total, nbytes, at, advisories=len(advs), records=len(recent))


def h_ghsa_global(ctx, key, url, watch):
    shas, nbytes, advs_by_eco = [], 0, {}
    queries = []
    for purl in watch[:MAX_WATCH_PACKAGES]:
        p = adapters.parse_purl(purl)
        eco = {v: k for k, v in adapters.GHSA_ECOSYSTEMS.items()}.get(p["type"])
        if not eco:
            continue
        name = "/".join(x for x in (p["namespace"], p["name"]) if x) if p["type"] != "maven" else "%s:%s" % (p["namespace"], p["name"])
        queries.append((eco, name))
    for eco, name in sorted(set(queries)):
        qurl = "%s?ecosystem=%s&affects=%s&per_page=100&type=reviewed" % (url, eco, name.replace("@", "%40").replace("/", "%2F"))
        raw, sha, _ = ctx.get(qurl)
        shas.append(sha)
        nbytes += len(raw)
        advs_by_eco.setdefault(eco, []).append((qurl, raw, sha))
    total = hashlib.sha256("".join(shas).encode()).hexdigest()
    at = ctx.stamp(key, total)
    count = 0
    for eco, items in advs_by_eco.items():
        for qurl, raw, sha in items:
            advs, _ = adapters.ghsa(json.loads(raw.decode("utf-8")), url, at, sha, "aggregator", "GitHub Advisory Database")
            ctx.add("ghsa-" + adapters.GHSA_ECOSYSTEMS[eco], advs)
            count += len(advs)
    ctx.record(key, url, "ghsa", total, nbytes, at, advisories=count, queries=len(queries))


def h_kev(ctx, key, url):
    raw, sha, _ = ctx.get(url)
    ids = adapters.kev_ids(json.loads(raw.decode("utf-8")))
    ctx.enrich["kev"] = ids
    ctx.record(key, url, "json", sha, len(raw), ctx.stamp(key, sha), cves=len(ids))


def h_eol(ctx, key, base_url, descriptors):
    products = {}
    for d in descriptors:
        rt = d.get("runtime") or {}
        if rt.get("eol_product"):
            products["runtime:" + rt["name"]] = rt["eol_product"]
    shas, nbytes, ok = [], 0, 0
    today = ctx.now[:10]
    for ckey, product in sorted(products.items()):
        url = base_url.rsplit("/", 1)[0] + "/%s.json" % product
        try:
            raw, sha, _ = ctx.get(url)
            ctx.enrich["eol"][ckey] = sorted(adapters.eol_cycles(json.loads(raw.decode("utf-8")), today))
            shas.append(sha)
            nbytes += len(raw)
            ok += 1
        except (netfetch.FetchError, ValueError) as exc:
            ctx.failures.append(("%s[%s]" % (key, product), str(exc)))
    total = hashlib.sha256("".join(shas).encode()).hexdigest()
    ctx.record(key, base_url, "json", total, nbytes, ctx.stamp(key, total), products=ok)


def h_feed(ctx, key, url, sid):
    raw, sha, _ = ctx.get(url)
    items = adapters.feed_leads(raw, sid)
    if items is None:
        raise netfetch.FetchError("not a valid RSS/Atom feed: %s" % url)
    ctx.enrich["leads"].extend(items)
    ctx.record(key, url, "rss", sha, len(raw), ctx.stamp(key, sha), items=len(items))


def h_page(ctx, key, url, fmt):
    raw, sha, _ = ctx.get(url)
    prev = ctx.prev.get(key, {})
    ctx.record(key, url, fmt, sha, len(raw), ctx.stamp(key, sha), changed=bool(prev) and prev.get("sha256") != sha)


# ----------------------------------------------------------------------- main

def watch_packages(ctx, inv_path, extra):
    purls = list(extra)
    for v in ctx.src.get("vendors", []):
        purls += [c for c in v["components"] if c.startswith("pkg:") and "*" not in c]
    if inv_path:
        comps = inventory.from_json(inv_path) if inv_path.endswith("inventory.json") else inventory.from_cyclonedx(inv_path)
        purls += [c.purl for c in comps if c.purl]
    out = []
    for p in purls:
        try:
            out.append(adapters.parse_purl(p) and p.split("@")[0])
        except Exception:
            pass
    return sorted(set(out))


def run_fetch(args):
    try:
        src = sources.load_sources(args.sources)
        schema = advisory.load_json(args.schema)
        descriptors = ecosystems.load_descriptors()
    except (advisory.AdvisoryError, ecosystems.EcosystemError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    errs = sources.validate_sources(src)
    if errs:
        print("ERROR: sources.json invalid:\n  " + "\n  ".join(errs), file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    ctx = Ctx(args, src, schema)
    watch = watch_packages(ctx, args.inventory, args.package)
    go_modules = [p.replace("pkg:golang/", "") for p in watch if p.startswith("pkg:golang/")]

    plan = []
    for group in ("vendors", "aggregators", "secondary"):
        for item in src.get(group, []):
            if args.only and item["id"] not in args.only:
                continue
            for n, s in enumerate(item["sources"]):
                plan.append((group, item, n, s))

    for group, item, n, s in plan:
        sid, url, fmt = item["id"], s["url"], s["format"]
        key = "%s/%s/%d" % (group, sid, n)
        try:
            if group == "vendors" and sid == "nodejs" and fmt == "json":
                h_nodejs(ctx, key, url, item["name"])
            elif fmt == "ghsa-repo":
                h_ghsa_repo(ctx, key, url, item["name"], "%s-ghsa-repo" % sid)
            elif group == "vendors" and sid == "go" and fmt == "osv":
                h_go(ctx, key, url, item["name"], go_modules)
            elif fmt == "rss":
                h_feed(ctx, key, url, sid)
            elif sid == "cisa-kev":
                h_kev(ctx, key, url)
            elif sid == "endoflife":
                h_eol(ctx, key, url, descriptors)
            elif sid == "ghsa" and fmt == "ghsa":
                h_ghsa_global(ctx, key, url, watch)
            elif fmt in ("html", "text"):
                h_page(ctx, key, url, fmt)
            else:
                ctx.manifest[key] = {"url": url, "format": fmt, "status": "skipped",
                                     "note": "not fetched here (queried by osv-scanner or no adapter)"}
        except (netfetch.FetchError, ValueError, KeyError, TypeError) as exc:
            ctx.fail(key, url, fmt, "%s: %s" % (type(exc).__name__, exc))

    # write outputs (only what changed); remove bundles that are now empty
    changed = []
    adv_dir = os.path.join(args.out, "advisories")
    live = set()
    for name, advs in sorted(ctx.bundles.items()):
        if not advs:
            continue
        advs = sorted(advs, key=lambda a: (a["component"]["name"], a["id"]))
        live.add(name + ".json")
        if write_if_changed(os.path.join(adv_dir, name + ".json"), {"schema_version": 1, "advisories": advs}):
            changed.append(name + ".json")
    failed_keys = {k for k, _ in ctx.failures}
    if os.path.isdir(adv_dir) and not failed_keys:
        for f in os.listdir(adv_dir):
            if f.endswith(".json") and f not in live:
                os.remove(os.path.join(adv_dir, f))
                changed.append("-" + f)
    edir = os.path.join(args.out, "enrichment")
    if ctx.enrich["kev"] is not None and write_if_changed(os.path.join(edir, "kev.json"), {"cves": ctx.enrich["kev"]}):
        changed.append("kev.json")
    if ctx.enrich["eol"] and write_if_changed(os.path.join(edir, "eol.json"), {"eol_cycles": ctx.enrich["eol"]}):
        changed.append("eol.json")
    leads = sorted(ctx.enrich["leads"], key=lambda l: (l["source"], l["link"], l["title"]))
    if leads and write_if_changed(os.path.join(edir, "leads.json"), {"leads": leads}):
        changed.append("leads.json")
    # keep previous manifest entries of sources not fetched this run (--only)
    merged = dict(ctx.prev) if args.only else {}
    merged.update(ctx.manifest)
    if write_if_changed(os.path.join(args.out, "manifest.json"), {"schema_version": 1, "sources": dict(sorted(merged.items()))}):
        changed.append("manifest.json")

    # final validation of what is on disk
    results = advisory.validate_paths([adv_dir], schema, ctx.allowed) if os.path.isdir(adv_dir) and os.listdir(adv_dir) else []
    bad = [e for r in results for e in r["errors"]]
    n_adv = sum(len(r["ids"]) for r in results)

    if args.json:
        print(json.dumps({"changed": changed, "advisories": n_adv, "dropped": ctx.dropped,
                          "failures": ctx.failures, "validation_errors": bad}, indent=2))
    else:
        for key, m in sorted(ctx.manifest.items()):
            extra = {k: v for k, v in m.items() if k in ("advisories", "cves", "items", "products", "records", "changed", "note", "skipped")}
            print("%-5s %-34s %s %s" % ("OK" if m["status"] == "ok" else m["status"].upper()[:5], key, m["url"],
                                       ("%s" % extra) if extra else m.get("error", "")))
        for e in bad:
            print("ERROR  " + e)
        print("%d advisories in %d bundle(s), %d dropped as invalid, %d source failure(s); changed: %s" % (
            n_adv, len(results), ctx.dropped, len(ctx.failures), ", ".join(changed) or "nothing"))
    if bad:
        return 1
    return 3 if ctx.failures else 0


# ------------------------------------------------------------ --advisory mode

class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag in ("p", "br", "li", "tr", "h1", "h2", "h3", "h4", "div"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip() + " ")


def page_text(raw):
    p = _Text()
    p.feed(raw.decode("utf-8", errors="replace"))
    lines = [" ".join(l.split()) for l in "".join(p.parts).split("\n")]
    return "\n".join(l for l in lines if l)[:MAX_PAGE_TEXT]


def run_advisory(args):
    try:
        src = sources.load_sources(args.sources)
    except advisory.AdvisoryError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    allowed = sources.allowed_hosts_of(src)
    host = netfetch.host_of(args.advisory)
    vendor = None
    for group in ("vendors", "aggregators", "secondary"):
        for item in src.get(group, []):
            if any(netfetch.host_of(s["url"]) == host for s in item["sources"]):
                vendor = (group, item)
    if vendor is None:
        print("ERROR: host '%s' is not a source in sources.json; add the vendor there first" % host, file=sys.stderr)
        return 2
    try:
        raw, sha, final = netfetch.fetch(args.advisory, allowed, 5 * 1024 * 1024, args.timeout)
    except netfetch.FetchError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if not args.out.endswith(".json"):
        print("ERROR: --out must be a .json file", file=sys.stderr)
        return 2
    group, item = vendor
    tier = "vendor" if group == "vendors" else ("secondary" if group == "secondary" else "aggregator")
    skeleton = {"schema_version": 1, "advisories": [{
        "id": "TODO-CVE-OR-VENDOR-ID", "title": "TODO", "summary": "TODO",
        "severity": "unknown", "status": "published",
        "component": {"kind": "TODO: package|runtime|image|os", "ecosystem": "TODO", "name": "TODO"},
        "affected": [],
        "references": [final],
        "source": {"tier": tier, "vendor": item["name"], "url": final, "fetched_at": args.now or now_utc(),
                   "sha256": sha, "method": "llm-assisted"}}]}
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(dump(skeleton))
    txt = args.out[:-5] + ".source.txt"
    with open(txt, "w", encoding="utf-8") as fh:
        fh.write(page_text(raw) + "\n")
    print("Wrote %s (skeleton, incomplete on purpose) and %s (page text)." % (args.out, txt))
    print("Next: fill every TODO from the page text, one advisory per CVE and release line, then run")
    print("  python3 -I scripts/validate-advisories.py %s" % args.out)
    print("A human must set source.approved_by before the matcher uses it.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch vendor and aggregator advisories")
    ap.add_argument("--out", required=True, help="cache directory (fetch) or .json file (--advisory)")
    ap.add_argument("--advisory", metavar="URL", help="ingest one bulletin page (human approval required)")
    ap.add_argument("--only", nargs="*", default=[], help="fetch only these source ids")
    ap.add_argument("--inventory", help="CycloneDX SBOM or inventory.json: also query GHSA for these packages")
    ap.add_argument("--package", action="append", default=[], help="extra purl to query (repeatable)")
    ap.add_argument("--since-days", type=int, default=60, help="Go vulndb: records modified in the last N days")
    ap.add_argument("--max-records", type=int, default=300)
    ap.add_argument("--sources", default=os.path.join(SKILL_DIR, "assets", "sources.json"))
    ap.add_argument("--schema", default=os.path.join(SKILL_DIR, "assets", "advisory.schema.json"))
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--now", help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    return run_advisory(args) if args.advisory else run_fetch(args)


if __name__ == "__main__":
    sys.exit(main())
