#!/usr/bin/env python3
"""Deterministic coverage-ledger helpers for the deep audit (Phase 10).

Hand-deriving percent-encoded coverage IDs is error-prone, so the parent agent uses this instead:

  # canonical coverage ID for one unit
  python3 -I audit-ledger.py id --surface 'src/app.js#GET /notes/:id' --boundary 'src/app.js#requireUser' \
      --subsystem 'src' --attack-class 'ATTACK-CLASSES.md#Access control' [--lifecycle ...]

  # build (or extend) a sorted, validated ledger from unit specs
  python3 -I audit-ledger.py seed units.json --out coverage-ledger.json [--merge]

units.json is a JSON array; each entry has surface, boundary, subsystem, attack_class (human labels),
canonical_refs {surface, boundary, subsystem, attack_class[, lifecycle]}, starting_paths, and optional
ordinary_attack_class_block, selected_companion_blocks, excluded_blocks, prior_status, lifecycle.
New units start `planned` in wave 1. --merge keeps every existing unit untouched and adds only new IDs;
a new spec whose ID exists with different semantic fields is a canonical identity collision (exit 1).
Exit 0 ok, 1 invalid. Stdlib only; Python 3.8+.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import audit  # noqa: E402

SEMANTIC = ("surface", "boundary", "subsystem", "attack_class", "lifecycle", "canonical_refs")


def cmd_id(args):
    refs = {"surface": args.surface, "boundary": args.boundary, "subsystem": args.subsystem,
            "attack_class": args.attack_class}
    if args.lifecycle:
        refs["lifecycle"] = args.lifecycle
    try:
        print(audit.coverage_id(refs))
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


def cmd_seed(args):
    try:
        specs = audit.load_json(args.units)
    except audit.AuditInputError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    if not isinstance(specs, list):
        print("error: units file must be a JSON array", file=sys.stderr)
        return 1
    existing = []
    if args.merge and os.path.exists(args.out):
        try:
            existing = audit.load_json(args.out)
        except audit.AuditInputError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
    by_id = dict((u.get("coverage_id"), u) for u in existing if isinstance(u, dict))
    added = 0
    for i, spec in enumerate(specs):
        try:
            unit = audit.new_unit(spec)
        except (KeyError, ValueError, TypeError) as exc:
            print("error: units[%d]: %s" % (i, exc), file=sys.stderr)
            return 1
        old = by_id.get(unit["coverage_id"])
        if old is not None:
            if any(old.get(k) != unit.get(k) for k in SEMANTIC):
                print("error: units[%d]: canonical identity collision with existing %r"
                      % (i, unit["coverage_id"]), file=sys.stderr)
                return 1
            continue
        by_id[unit["coverage_id"]] = unit
        added += 1
    ledger = [by_id[k] for k in sorted(by_id)]
    errors = audit.validate_ledger(ledger)
    if errors:
        print("error: resulting ledger is invalid:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return 1
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, args.out)
    print("ledger %s: %d unit(s), %d added" % (args.out, len(ledger), added))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Coverage-ledger helpers for the deep audit")
    sub = ap.add_subparsers(dest="cmd")
    p_id = sub.add_parser("id", help="print the canonical coverage ID")
    p_id.add_argument("--surface", required=True)
    p_id.add_argument("--boundary", required=True)
    p_id.add_argument("--subsystem", required=True)
    p_id.add_argument("--attack-class", required=True)
    p_id.add_argument("--lifecycle")
    p_seed = sub.add_parser("seed", help="build or extend a ledger from unit specs")
    p_seed.add_argument("units")
    p_seed.add_argument("--out", required=True)
    p_seed.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    if args.cmd == "id":
        return cmd_id(args)
    if args.cmd == "seed":
        return cmd_seed(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
