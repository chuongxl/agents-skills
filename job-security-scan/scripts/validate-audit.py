#!/usr/bin/env python3
"""Validate deep-audit output (Phase 9).

Usage:
  python3 -I validate-audit.py findings <run>/<repo>/audit/findings.json
  python3 -I validate-audit.py ledger   <run>/<repo>/audit/coverage-ledger.json
  python3 -I validate-audit.py run      <run>/<repo>/audit        # both files, plus run-metadata.json

Exit 0 valid, 1 invalid, 2 unreadable. Validator success proves format and ledger consistency only, not
that a finding is true. Stdlib only; Python 3.8+.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import audit  # noqa: E402

METADATA_REQUIRED = ("run_id", "repo", "target", "source_ref", "profile", "scope_paths", "budget",
                     "execution_policy", "run_status")
RUN_STATUSES = ("awaiting_agent", "in_progress", "complete", "incomplete")


def check_metadata(path):
    try:
        meta = audit.load_json(path)
    except audit.AuditInputError as exc:
        print("INVALID %s\n  %s" % (path, exc))
        return 2
    errors = ["missing required field %r" % k for k in METADATA_REQUIRED if k not in meta] if isinstance(meta, dict) \
        else ["expected object"]
    if isinstance(meta, dict):
        if meta.get("profile") not in ("quick", "standard", "deep"):
            errors.append("profile: expected quick|standard|deep")
        if meta.get("run_status") not in RUN_STATUSES:
            errors.append("run_status: expected one of %s" % ", ".join(RUN_STATUSES))
        if meta.get("run_status") == "incomplete" and not audit.visible_text(meta.get("incomplete_reason")):
            errors.append("incomplete_reason: required when run_status is incomplete")
        if meta.get("execution_policy") not in ("source-only", "sandboxed-source-and-local-only"):
            errors.append("execution_policy: expected source-only or sandboxed-source-and-local-only")
    if errors:
        print("INVALID %s (%d error(s))" % (path, len(errors)))
        for e in errors:
            print("  " + e)
        return 1
    print("OK %s: run_status=%s profile=%s" % (path, meta["run_status"], meta["profile"]))
    return 0


def main(argv):
    if len(argv) != 3 or argv[1] not in ("findings", "ledger", "run"):
        sys.stderr.write(__doc__)
        return 2
    kind, target = argv[1], argv[2]
    if kind != "run":
        return audit.main_validate(kind, target)
    worst = 0
    for name, check in (("run-metadata.json", check_metadata),
                        ("coverage-ledger.json", lambda p: audit.main_validate("ledger", p)),
                        ("findings.json", lambda p: audit.main_validate("findings", p))):
        path = os.path.join(target, name)
        if not os.path.exists(path):
            print("MISSING %s" % path)
            worst = max(worst, 1)
            continue
        worst = max(worst, check(path))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))
