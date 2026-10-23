"""adapters.py - turn vendor/aggregator payloads into advisories of the P0 schema.

Stdlib only; Python 3.8+. Every adapter is a pure function (payload in, data out), so it is
unit-testable offline. Payloads are parsed as JSON/XML data and never executed.
"""

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import versions
from component import format_purl

SEV_MAP = {"critical": "critical", "high": "high", "important": "high", "moderate": "medium",
           "medium": "medium", "low": "low"}
GHSA_ECOSYSTEMS = {"npm": "npm", "pip": "pypi", "maven": "maven", "go": "golang", "nuget": "nuget",
                   "composer": "composer", "rubygems": "gem", "rust": "cargo", "pub": "pub",
                   "erlang": "hex", "swift": "swift"}
_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def sev(value):
    return SEV_MAP.get(str(value or "").strip().lower(), "unknown")


def _src(tier, vendor, url, fetched_at, sha, method="feed"):
    return {"tier": tier, "vendor": vendor, "url": url, "fetched_at": fetched_at, "sha256": sha, "method": method}


def _clip(text, n=400):
    text = " ".join(str(text or "").split())
    return text[:n] if len(text) >= 10 else (text + " (no details)")[:n]


def _date(value):
    m = _DATE_RE.match(str(value or ""))
    return m.group(0) if m else None


def _https(urls):
    return sorted({u for u in urls if isinstance(u, str) and u.startswith("https://") and " " not in u})


# ------------------------------------------------------------------ Node.js WG

def nodejs_wg(payload, url, fetched_at, sha):
    """nodejs/security-wg vuln/core index: {id: {cve, vulnerable, patched, severity, ...}}."""
    items = payload.items() if isinstance(payload, dict) else enumerate(payload)
    out, skipped = [], 0
    for key, e in items:
        if not isinstance(e, dict):
            skipped += 1
            continue
        cves = e.get("cve") or []
        cves = [cves] if isinstance(cves, str) else [c for c in cves if isinstance(c, str)]
        cves = [c for c in cves if _CVE_RE.fullmatch(c)]
        # patched looks like "^22.23.2 || ^24.18.1" (older entries use ">=22.5.1")
        fixed = re.findall(r"(?:\^|>=|~)?\s*v?(\d+\.\d+\.\d+)", str(e.get("patched") or ""))
        if not fixed:
            skipped += 1      # unpatched or end-of-life only: nothing to match against
            continue
        if not cves:
            cves = ["NODE-WG-%s" % key]
        affected, seen = [], set()
        for f in fixed:
            line = str(versions.major(f))
            if line not in seen:
                seen.add(line)
                affected.append({"line": line, "introduced": "0", "fixed": f})
        title = _clip(e.get("description") or e.get("overview") or "Node.js vulnerability", 140)
        out.append({
            "id": cves[0], "aliases": cves[1:], "title": title,
            "summary": _clip(e.get("overview") or e.get("description") or title),
            "severity": sev(e.get("severity")), "status": "published",
            "component": {"kind": "runtime", "ecosystem": "node", "name": "node"},
            "affected": sorted(affected, key=lambda a: int(a["line"])),
            "references": _https([e.get("ref")]),
            "source": _src("vendor", "Node.js", url, fetched_at, sha),
        })
    # the same CVE can appear in several entries (one per release); keep one advisory, union the lines
    merged = {}
    for a in out:
        if a["id"] in merged:
            have = {x["line"] for x in merged[a["id"]]["affected"]}
            merged[a["id"]]["affected"] += [x for x in a["affected"] if x["line"] not in have]
            merged[a["id"]]["affected"].sort(key=lambda x: int(x["line"]))
        else:
            merged[a["id"]] = a
    return list(merged.values()), skipped


# ------------------------------------------------------------------------ GHSA

_RANGE_RE = re.compile(r"(<=|>=|<|>|=)\s*v?([0-9][^\s,]*)")


def parse_range(text):
    """GHSA 'vulnerable_version_range' ('>= 1.0, < 2.3') -> (introduced, fixed, last_affected) or None."""
    if not text:
        return None
    introduced, fixed, last = "0", None, None
    parts = _RANGE_RE.findall(text)
    if not parts or len(parts) != len([p for p in text.split(",") if p.strip()]):
        return None
    for op, ver in parts:
        if op == ">=":
            introduced = ver
        elif op == ">":
            return None            # exclusive lower bound cannot be expressed exactly
        elif op == "<":
            fixed = ver
        elif op == "<=":
            last = ver
        elif op == "=":
            introduced, last = ver, ver
    if fixed is None and last is None:
        return None
    return introduced, fixed, last


def _ghsa_purl(eco, name):
    if eco == "maven" and ":" in name:
        g, a = name.split(":", 1)
        return format_purl("maven", a, namespace=g)
    if eco in ("npm", "golang", "composer") and "/" in name:
        ns, _, last = name.rpartition("/")
        return format_purl(eco, last, namespace=ns)
    return format_purl(eco, name)


def ghsa(payload, url, fetched_at, sha, tier, vendor):
    """GitHub advisory objects (global /advisories or repo /security-advisories)."""
    out, skipped = [], 0
    for e in payload if isinstance(payload, list) else []:
        gid = e.get("ghsa_id")
        if not gid:
            skipped += 1
            continue
        per_pkg = {}
        for v in e.get("vulnerabilities") or []:
            pkg = (v.get("package") or {})
            eco = GHSA_ECOSYSTEMS.get(str(pkg.get("ecosystem") or "").lower())
            name = pkg.get("name")
            r = parse_range(v.get("vulnerable_version_range"))
            if not eco or not name or r is None:
                continue
            introduced, fixed, last = r
            patched = v.get("first_patched_version")
            patched = patched.get("identifier") if isinstance(patched, dict) else patched
            if fixed is None and patched and last is not None:
                fixed, last = None, last
            entry = {"line": "*", "introduced": introduced}
            if fixed:
                entry["fixed"] = fixed
            if last and not fixed:
                entry["last_affected"] = last
            per_pkg.setdefault((eco, name), []).append(entry)
        cve = e.get("cve_id")
        status = "withdrawn" if e.get("withdrawn_at") else "published"
        cvss = e.get("cvss") or {}
        for (eco, name), entries in sorted(per_pkg.items()):
            a = {
                "id": gid if len(per_pkg) == 1 else "%s:%s" % (gid, name.replace("/", "_")),
                "aliases": [cve] if cve and _CVE_RE.fullmatch(cve) else [],
                "title": _clip(e.get("summary") or gid, 140),
                "summary": _clip(e.get("summary") or e.get("description") or gid),
                "severity": sev(e.get("severity")), "status": status,
                "component": {"kind": "package", "ecosystem": eco, "name": name, "purl": _ghsa_purl(eco, name)},
                "affected": entries,
                "references": _https([e.get("html_url")]),
                "source": _src(tier, vendor, url, fetched_at, sha),
            }
            if len(per_pkg) > 1:
                a["aliases"] = sorted(set(a["aliases"]) | {gid})
            if isinstance(cvss.get("score"), (int, float)) and cvss.get("vector_string"):
                a["cvss"] = {"score": cvss["score"], "vector": cvss["vector_string"],
                             "version": "4.0" if str(cvss["vector_string"]).startswith("CVSS:4") else "3.1"}
            d = _date(e.get("published_at"))
            if d:
                a["published"] = d
            out.append(a)
        if not per_pkg:
            skipped += 1
    return out, skipped


# -------------------------------------------------------------------- OSV (Go)

def _norm_go(v):
    return re.sub(r"-0$", "", v or "")


def osv_go_runtime(record, url, fetched_at, sha, packages=()):
    """Go vulndb OSV record -> advisories for the Go runtime (stdlib/toolchain) and given modules."""
    out = []
    ranges_by_comp = {}
    for aff in record.get("affected") or []:
        pkg = aff.get("package") or {}
        name = pkg.get("name", "")
        if name in ("stdlib", "toolchain"):
            comp_key = ("runtime", "go", "go", None)
        elif name in packages:
            comp_key = ("package", "golang", name, _ghsa_purl("golang", name))
        else:
            continue
        for rng in aff.get("ranges") or []:
            if rng.get("type") != "SEMVER":
                continue
            introduced = None
            for ev in rng.get("events") or []:
                if "introduced" in ev:
                    introduced = _norm_go(ev["introduced"])
                elif "fixed" in ev and introduced is not None:
                    ranges_by_comp.setdefault(comp_key, []).append(
                        {"line": "*", "introduced": introduced, "fixed": _norm_go(ev["fixed"])})
                    introduced = None
                elif "last_affected" in ev and introduced is not None:
                    ranges_by_comp.setdefault(comp_key, []).append(
                        {"line": "*", "introduced": introduced, "last_affected": _norm_go(ev["last_affected"])})
                    introduced = None
    for (kind, eco, name, purl), entries in sorted(ranges_by_comp.items(), key=lambda kv: kv[0][2]):
        comp = {"kind": kind, "ecosystem": eco, "name": name}
        if purl:
            comp["purl"] = purl
        rid = record["id"] if len(ranges_by_comp) == 1 else "%s:%s" % (record["id"], name.replace("/", "_"))
        a = {
            "id": rid,
            "aliases": sorted(set(record.get("aliases") or []) | ({record["id"]} if rid != record["id"] else set())),
            "title": _clip(record.get("summary") or record["id"], 140),
            "summary": _clip(record.get("details") or record.get("summary") or record["id"]),
            "severity": sev((record.get("database_specific") or {}).get("severity")),
            "status": "withdrawn" if record.get("withdrawn") else "published",
            "component": comp, "affected": entries,
            "references": _https([r.get("url") for r in record.get("references") or []])[:5],
            "source": _src("vendor", "Go", url, fetched_at, sha),
        }
        d = _date(record.get("published"))
        if d:
            a["published"] = d
        out.append(a)
    return out


# ------------------------------------------------------------ enrichment feeds

def kev_ids(payload):
    return sorted({v["cveID"] for v in (payload.get("vulnerabilities") or []) if _CVE_RE.fullmatch(v.get("cveID", ""))})


def eol_cycles(payload, today):
    """endoflife.date product JSON -> set of cycle labels already end-of-life on `today` (YYYY-MM-DD)."""
    out = set()
    for c in payload if isinstance(payload, list) else []:
        eol = c.get("eol")
        if eol is True or (isinstance(eol, str) and _DATE_RE.match(eol) and eol[:10] <= today):
            out.add(str(c.get("cycle")))
    return out


# ------------------------------------------------------------------- RSS leads

def feed_leads(xml_bytes, source_id, limit=30):
    """RSS 2.0 / Atom items that mention a CVE -> leads for human ingestion with --advisory."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    items = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        def txt(name):
            for ch in el:
                if ch.tag.rsplit("}", 1)[-1] == name:
                    return (ch.text or "").strip() or ch.attrib.get("href", "")
            return ""
        title = txt("title")
        link = txt("link")
        body = " ".join([title, txt("description"), txt("summary"), txt("content")])
        cves = sorted(set(_CVE_RE.findall(body)))
        if cves or re.search(r"security|vulnerab", title, re.I):
            items.append({"source": source_id, "title": title[:200], "link": link if link.startswith("https://") else "",
                          "date": txt("pubDate") or txt("updated") or txt("published"), "cves": cves})
    return items[:limit]
