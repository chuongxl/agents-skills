#!/usr/bin/env python3
"""match.py - match advisories (vendor first) against a project inventory.

Usage:
  python3 -I scripts/match.py (--repo DIR | --sbom FILE | --inventory FILE) ...
                              [--advisories PATH ...] [--cache DIR] [--env KEY=VALUE ...]
                              [--format text|json] [--output FILE] [--fail-on LEVEL]
                              [--trust-unapproved]

Inventory sources (combine freely):
  --repo DIR        runtime versions declared in the repo (ecosystems/*.json extractors) and
                    environment facts from Dockerfiles (os, libc)
  --sbom FILE       CycloneDX SBOM: packages by purl (for example trivy fs --format cyclonedx)
  --inventory FILE  {"components":[{"kind","ecosystem","name","version","purl?","exact?"}]}

Advisories: assets/advisories plus, with --cache DIR, the output of fetch-advisories.py
(bundles, CISA KEV, end-of-life data). Vendor data wins over aggregators on merge.

--env sets facts for advisory conditions, for example --env libc=glibc --env os=linux
--env feature=app-router (repeatable; a type given twice means "any of").

LLM-assisted advisories without source.approved_by are ignored unless --trust-unapproved.

Exit codes: 0 nothing at or above --fail-on (default high), 1 findings at/above it,
2 usage error or invalid input.
Stdlib only; Python 3.8+. Run with -I.
"""

import argparse
import datetime
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "lib"))

import advisory  # noqa: E402
import ecosystems  # noqa: E402
import engine  # noqa: E402
import inventory  # noqa: E402

LEVELS = ["none", "low", "medium", "high", "critical"]
ACTIONABLE = ("affected", "affected-end-of-life", "affected-if-condition-holds", "possibly-affected")


def parse_env(pairs):
    env = {}
    for p in pairs:
        if "=" not in p:
            raise ValueError("--env expects KEY=VALUE, got %r" % p)
        k, v = p.split("=", 1)
        env.setdefault(k.strip(), set()).add(v.strip())
    return env


def load_enrichment(cache):
    kev, eol = [], {}
    if not cache:
        return kev, eol
    p = os.path.join(cache, "enrichment", "kev.json")
    if os.path.exists(p):
        kev = advisory.load_json(p).get("cves", [])
    p = os.path.join(cache, "enrichment", "eol.json")
    if os.path.exists(p):
        eol = {k: set(v) for k, v in advisory.load_json(p).get("eol_cycles", {}).items()}
    return kev, eol


def run(args):
    schema = advisory.load_json(args.schema)
    paths = list(args.advisories) or [os.path.join(SKILL_DIR, "assets", "advisories")]
    if args.cache:
        paths.append(os.path.join(args.cache, "advisories"))
    paths = [p for p in paths if os.path.exists(p)]
    results = advisory.validate_paths(paths, schema)
    errors = [e for r in results for e in r["errors"]]
    if errors:
        print("ERROR: invalid advisory data - fix or remove it:\n  " + "\n  ".join(errors[:10]), file=sys.stderr)
        return 2

    raw = engine.load_advisories(paths)
    ignored = []
    if not args.trust_unapproved:
        kept = []
        for a in raw:
            if a["source"]["method"] == "llm-assisted" and not a["source"].get("approved_by"):
                ignored.append(a["id"])
            else:
                kept.append(a)
        raw = kept
    merged = engine.apply_kev(engine.merge(raw), load_enrichment(args.cache)[0])
    eol = load_enrichment(args.cache)[1]

    comps, env = [], {}
    if args.repo:
        comps += inventory.runtimes_from_repo(args.repo)
        env.update({k: {v} for k, v in inventory.facts_from_repo(args.repo).items()})
    if args.sbom:
        comps += inventory.from_cyclonedx(args.sbom)
    if args.inventory:
        comps += inventory.from_json(args.inventory)
    env.update(parse_env(args.env))
    if not comps and not args.allow_empty:
        print("ERROR: empty inventory - give --repo, --sbom or --inventory with something in it", file=sys.stderr)
        return 2

    findings, suppressed = engine.match(comps, merged, env, eol)
    report = {
        "generated_at": args.now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inventory": [{"component": c.key, "version": c.version, "location": c.location, "exact": c.extra.get("exact", True)} for c in comps],
        "environment": {k: sorted(v) for k, v in env.items()},
        "advisories_loaded": len(merged),
        "findings": findings,
        "suppressed": suppressed,
        "ignored_unapproved": sorted(set(ignored)),
    }
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, indent=2) + "\n")
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print_text(report)

    threshold = LEVELS.index(args.fail_on)
    worst = max((LEVELS.index(f["severity"]) for f in findings if f["state"] in ACTIONABLE and f["severity"] in LEVELS), default=0)
    return 1 if threshold and worst >= threshold else 0


def print_text(r):
    print("Inventory: %s" % ", ".join("%s %s" % (c["component"], c["version"] or "?") for c in r["inventory"]))
    print("Advisories loaded: %d (vendor data first)" % r["advisories_loaded"])
    if r["environment"]:
        print("Environment: %s" % ", ".join("%s=%s" % (k, "/".join(v)) for k, v in sorted(r["environment"].items())))
    if r["ignored_unapproved"]:
        print("Ignored %d unapproved LLM-assisted advisory(ies): %s" % (len(r["ignored_unapproved"]), ", ".join(r["ignored_unapproved"])))
    if not r["findings"]:
        print("No applicable advisories.")
    for f in r["findings"]:
        flags = []
        if f["exploited"]:
            flags.append("EXPLOITED (CISA KEV)")
        if f["conflicts"]:
            flags.append("SOURCE CONFLICT")
        extra = ""
        if f["state"] == "affected-if-condition-holds":
            extra = "  if " + ", ".join("%s=%s" % (c["type"], c["value"]) for c in f["unmet_conditions"])
        print("%-8s %-27s %-34s %s%s%s" % (f["severity"].upper(), f["state"], f["id"],
              "%s %s -> fix %s" % (f["component"], f["installed"], f["fixed_in"]) if f["fixed_in"] else "%s %s" % (f["component"], f["installed"]),
              extra, ("  [" + ", ".join(flags) + "]") if flags else ""))
        print("         %s  (source: %s)" % (f["title"][:100], f["source"]["vendor"]))
    if r["suppressed"]:
        print("%d advisory(ies) not applicable to this environment." % len(r["suppressed"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Match advisories against a project inventory")
    ap.add_argument("--repo")
    ap.add_argument("--sbom")
    ap.add_argument("--inventory")
    ap.add_argument("--advisories", nargs="*", default=[])
    ap.add_argument("--cache", help="output directory of fetch-advisories.py")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--output", help="also write the JSON report here")
    ap.add_argument("--fail-on", choices=LEVELS, default="high")
    ap.add_argument("--allow-empty", action="store_true", help="an empty inventory is a valid result, not an error")
    ap.add_argument("--trust-unapproved", action="store_true")
    ap.add_argument("--schema", default=os.path.join(SKILL_DIR, "assets", "advisory.schema.json"))
    ap.add_argument("--now", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if not (args.repo or args.sbom or args.inventory):
        ap.error("give at least one of --repo, --sbom, --inventory")
    try:
        parse_env(args.env)
        return run(args)
    except (advisory.AdvisoryError, engine.EngineError, ecosystems.EcosystemError, ValueError, OSError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
