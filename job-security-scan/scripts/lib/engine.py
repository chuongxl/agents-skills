"""engine.py - merge advisories (vendor first) and match them against an inventory.

Stdlib only; Python 3.8+.

Resolution order for one component:
  vendor bulletin  >  aggregator (OSV / GHSA)  >  secondary alert
Advisories that share an id or alias for the same component are one vulnerability: the
highest-tier source supplies the affected ranges, the others are recorded as merged_from,
and disagreements on the fixed version are flagged as conflicts for human review.
"""

import os

import advisory as adv_lib
import versions
from component import Component

TIER_RANK = {"vendor": 0, "aggregator": 1, "secondary": 2, "enrichment": 3, "lifecycle": 4}
SEVERITY_ORDER = ["unknown", "low", "medium", "high", "critical"]


class EngineError(Exception):
    pass


# --------------------------------------------------------------------- loading

def load_advisories(paths):
    """Load every advisory bundle under the paths (files or directories)."""
    out = []
    for f in adv_lib.iter_advisory_files(paths):
        data = adv_lib.load_json(f)
        if not isinstance(data, dict) or not isinstance(data.get("advisories"), list):
            raise EngineError("%s: not an advisory bundle" % f)
        for a in data["advisories"]:
            a = dict(a)
            a["_origin"] = f
            out.append(a)
    return out


def component_key(c):
    """Key of an advisory component dict, same format as Component.key."""
    return Component(c["kind"], c["ecosystem"], c["name"], purl=c.get("purl")).key


# ----------------------------------------------------------------------- merge

class _UnionFind:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def _rank(a):
    return (0 if a["status"] == "published" else 1,
            TIER_RANK.get(a["source"]["tier"], 9),
            a["id"])


def merge(advisories):
    """Merge duplicates (same component, shared id/alias). Returns merged advisories."""
    live = [a for a in advisories if a.get("status") != "withdrawn"]
    uf = _UnionFind()
    for i, a in enumerate(live):
        ck = component_key(a["component"])
        node = ("adv", i)
        uf.find(node)
        for ident in [a["id"]] + list(a.get("aliases", [])):
            uf.union(node, ("id", ck, ident))

    groups = {}
    for i, a in enumerate(live):
        groups.setdefault(uf.find(("adv", i)), []).append(a)

    merged = []
    for members in groups.values():
        has_published = any(m["status"] == "published" for m in members)
        # a published advisory supersedes any pending pre-announcement of the same issue
        pool = [m for m in members if m["status"] == "published"] if has_published else members
        pool = sorted(pool, key=_rank)
        primary = dict(pool[0])
        ids = {primary["id"]}
        aliases = set(primary.get("aliases", []))
        for m in members:
            aliases.add(m["id"])
            aliases.update(m.get("aliases", []))
        aliases -= ids
        primary["aliases"] = sorted(aliases)
        primary["merged_from"] = [
            {"id": m["id"], "tier": m["source"]["tier"], "vendor": m["source"]["vendor"],
             "status": m["status"]} for m in sorted(members, key=_rank)]
        primary["conflicts"] = _conflicts(primary, pool[1:])
        # severity: keep the highest any source reports (never silently downgrade)
        sev = max((m["severity"] for m in members), key=SEVERITY_ORDER.index)
        if SEVERITY_ORDER.index(sev) > SEVERITY_ORDER.index(primary["severity"]):
            primary["severity"] = sev
        merged.append(primary)
    return sorted(merged, key=lambda a: (component_key(a["component"]), a["id"]))


def _conflicts(primary, others):
    found = []
    mine = {(e["line"], e["introduced"]): e for e in primary["affected"]}
    for o in others:
        for e in o["affected"]:
            m = mine.get((e["line"], e["introduced"]))
            if m and m.get("fixed") and e.get("fixed") and versions.compare(m["fixed"], e["fixed"]) not in (0, None):
                found.append({"line": e["line"], "introduced": e["introduced"], "winner": primary["source"]["vendor"], "winner_fixed": m["fixed"],
                              "other": o["source"]["vendor"], "other_fixed": e["fixed"]})
    return found


def apply_kev(advisories, kev_ids):
    """Mark advisories listed in CISA KEV as exploited and raise severity one step."""
    kev = set(kev_ids)
    for a in advisories:
        ids = {a["id"]} | set(a.get("aliases", []))
        if ids & kev:
            a["exploited"] = True
            if not a.get("kev_raised"):
                i = SEVERITY_ORDER.index(a["severity"])
                a["kev_raised_from"] = a["severity"]
                a["severity"] = "high" if a["severity"] == "unknown" else SEVERITY_ORDER[min(i + 1, 4)]
                a["kev_raised"] = True
    return advisories


# ----------------------------------------------------------------------- match

def evaluate_conditions(conditions, env):
    """Return ('holds'|'fails'|'unknown', unmet_list). env maps type -> value or set of values."""
    unknown = []
    for c in conditions or []:
        have = env.get(c["type"])
        if have is None:
            unknown.append(c)
            continue
        values = have if isinstance(have, (set, list, tuple)) else {have}
        if c["value"] not in values:
            return "fails", [c]
    return ("unknown", unknown) if unknown else ("holds", [])


def match(components, advisories, env=None, eol=None):
    """Match inventory components against merged advisories. Returns (findings, suppressed)."""
    env = env or {}
    eol = eol or {}
    by_key = {}
    for a in advisories:
        by_key.setdefault(component_key(a["component"]), []).append(a)

    findings, suppressed = [], []
    for comp in components:
        for a in by_key.get(comp.key, []):
            base = {
                "id": a["id"], "aliases": a.get("aliases", []), "title": a["title"],
                "severity": a["severity"], "exploited": bool(a.get("exploited")),
                "component": comp.key, "installed": comp.version, "location": comp.location,
                "source": {"tier": a["source"]["tier"], "vendor": a["source"]["vendor"], "url": a["source"]["url"]},
                "conflicts": a.get("conflicts", []), "merged_from": a.get("merged_from", []),
                "kev_raised_from": a.get("kev_raised_from"),
            }
            if a["status"] == "pending":
                findings.append(dict(base, state="pending", fixed_in=None, line=None))
                continue
            if not comp.version:
                findings.append(dict(base, state="unknown-version", fixed_in=None, line=None))
                continue
            status, entry = versions.evaluate(comp.version, a["affected"], eol.get(comp.key))
            if status in ("fixed", "unlisted"):
                continue
            if status == "unknown":
                findings.append(dict(base, state="unknown-version", fixed_in=None, line=None))
                continue
            cond_state, unmet = evaluate_conditions(a.get("conditions"), env)
            if cond_state == "fails":
                suppressed.append(dict(base, reason="condition not met: %s=%s" % (unmet[0]["type"], unmet[0]["value"])))
                continue
            if status == "eol-affected":
                state, fixed, line = "affected-end-of-life", None, None
            else:
                state, fixed, line = "affected", entry.get("fixed"), entry["line"]
            if cond_state == "unknown":
                state = "affected-if-condition-holds"
            elif comp.extra.get("exact") is False:
                state = "possibly-affected"
            findings.append(dict(base, state=state, fixed_in=fixed, line=line,
                                 unmet_conditions=unmet if cond_state == "unknown" else []))
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
    findings.sort(key=lambda f: (order[f["severity"]], f["component"], f["id"]))
    return findings, suppressed
