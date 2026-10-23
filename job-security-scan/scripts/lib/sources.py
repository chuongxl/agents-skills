"""sources.py - the trusted-source registry (assets/sources.json).

Stdlib only; compatible with Python 3.8+.

The registry lists which vendor bulletins and aggregators the advisory engine may
read, which components each vendor owns, and which hosts are allowed at all.
"""

import json
import re
import socket
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from advisory import AdvisoryError, load_json

FORMATS = ("html", "rss", "json", "osv", "ghsa", "text")
AGGREGATOR_TIERS = ("aggregator", "enrichment", "lifecycle")
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_PATTERN_RE = re.compile(r"^(runtime:[a-z][a-z0-9.+-]*|pkg:[a-z][a-z0-9.+-]*/\S+)$")
USER_AGENT = "job-security-scan-validate/0.1 (+https://github.com/chuongxl/agents-skills)"


def load_sources(path):
    return load_json(path)


def _host(url):
    return (urlparse(url).hostname or "").lower()


def _check_source_entry(entry, where, allowed, errors):
    if not isinstance(entry, dict):
        errors.append("%s: source entry must be an object" % where)
        return
    url = entry.get("url", "")
    if not isinstance(url, str) or not url.startswith("https://"):
        errors.append("%s: url must start with https:// (got %r)" % (where, url))
    elif _host(url) not in allowed:
        errors.append("%s: host '%s' is not in allowed_hosts" % (where, _host(url)))
    if entry.get("format") not in FORMATS:
        errors.append("%s: format must be one of %s (got %r)" % (where, ", ".join(FORMATS), entry.get("format")))


def _check_group(items, group, allowed, errors, need_components, seen_ids):
    if not isinstance(items, list) or not items:
        errors.append("%s: must be a non-empty list" % group)
        return
    for i, item in enumerate(items):
        where = "%s[%d]" % (group, i)
        if not isinstance(item, dict):
            errors.append("%s: must be an object" % where)
            continue
        sid = item.get("id", "")
        if not isinstance(sid, str) or not _ID_RE.match(sid):
            errors.append("%s: id must be lowercase kebab-case (got %r)" % (where, sid))
        elif sid in seen_ids:
            errors.append("%s: duplicate id '%s'" % (where, sid))
        seen_ids.add(sid)
        if not item.get("name"):
            errors.append("%s: missing name" % where)
        if need_components:
            comps = item.get("components")
            if not isinstance(comps, list) or not comps:
                errors.append("%s: needs a non-empty components list" % where)
            else:
                for pat in comps:
                    if not isinstance(pat, str) or not _PATTERN_RE.match(pat):
                        errors.append("%s: component pattern %r must be 'runtime:<name>' or 'pkg:<type>/...'" % (where, pat))
        if group == "aggregators" and item.get("tier") not in AGGREGATOR_TIERS:
            errors.append("%s: tier must be one of %s (got %r)" % (where, ", ".join(AGGREGATOR_TIERS), item.get("tier")))
        srcs = item.get("sources")
        if not isinstance(srcs, list) or not srcs:
            errors.append("%s: needs a non-empty sources list" % where)
        else:
            for j, s in enumerate(srcs):
                _check_source_entry(s, "%s.sources[%d]" % (where, j), allowed, errors)


def validate_sources(data):
    """Return a list of error strings for a parsed sources.json."""
    errors = []
    if not isinstance(data, dict):
        return ["sources.json: top level must be an object"]
    if data.get("schema_version") != 1:
        errors.append("schema_version: must be 1")
    allowed = data.get("allowed_hosts")
    if not isinstance(allowed, list) or not allowed:
        errors.append("allowed_hosts: must be a non-empty list")
        allowed = []
    else:
        for h in allowed:
            if not isinstance(h, str) or h != h.lower() or "/" in h or ":" in h:
                errors.append("allowed_hosts: %r must be a bare lowercase hostname" % (h,))
        if len(set(allowed)) != len(allowed):
            errors.append("allowed_hosts: contains duplicates")
    allowed_set = set(allowed)
    seen = set()
    _check_group(data.get("vendors"), "vendors", allowed_set, errors, True, seen)
    _check_group(data.get("aggregators"), "aggregators", allowed_set, errors, False, seen)
    if "secondary" in data:
        _check_group(data.get("secondary"), "secondary", allowed_set, errors, False, seen)
    return errors


def allowed_hosts_of(data):
    return set(data.get("allowed_hosts", []))


def all_urls(data):
    """Yield (group, id, url) for every source URL in the registry."""
    for group in ("vendors", "aggregators", "secondary"):
        for item in data.get(group, []):
            for s in item.get("sources", []):
                yield group, item.get("id", "?"), s.get("url", "")


# -------------------------------------------------------------- live checking

class _AllowlistRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to allowlisted hosts and only over https."""

    def __init__(self, allowed):
        self.allowed = allowed

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise urllib.error.URLError("redirect to non-https URL refused: %s" % newurl)
        if _host(newurl) not in self.allowed:
            raise urllib.error.URLError("redirect to non-allowlisted host refused: %s" % _host(newurl))
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


def check_url(url, allowed, timeout=20):
    """HEAD (falling back to GET) one URL. Returns dict(url, ok, status, note)."""
    opener = urllib.request.build_opener(_AllowlistRedirect(allowed))
    last = {"url": url, "ok": False, "status": None, "note": ""}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with opener.open(req, timeout=timeout) as resp:
                status = resp.status
                return {"url": url, "ok": 200 <= status < 300, "status": status,
                        "note": "final url: %s" % resp.geturl() if resp.geturl() != url else ""}
        except urllib.error.HTTPError as exc:
            last = {"url": url, "ok": False, "status": exc.code, "note": "HTTP %d" % exc.code}
            if exc.code in (400, 403, 405, 501) and method == "HEAD":
                continue  # some servers reject HEAD; retry with GET
            return last
        except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            return {"url": url, "ok": False, "status": None, "note": "%s" % (reason,)}
    return last


def check_sources(data, timeout=20, workers=6):
    """Live-check every URL in the registry. Returns a list of result dicts."""
    allowed = allowed_hosts_of(data)
    entries = list(all_urls(data))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(lambda e: check_url(e[2], allowed, timeout), entries))
    for (group, sid, _url), out in zip(entries, outcomes):
        out["group"], out["id"] = group, sid
    return outcomes
