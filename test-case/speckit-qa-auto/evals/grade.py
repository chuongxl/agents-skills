#!/usr/bin/env python3
"""Grade one speckit-qa-auto eval run against its mechanical assertions.

Usage:

    python3 test-case/speckit-qa-auto/evals/grade.py <eval-id> <run-folder> [--out grading.json]

`<run-folder>` is the `docs/qa/<issue>/` the run produced.

Only assertions a script can decide are graded here. The rest are printed as a checklist for the
human reviewer, because a check that guesses is worse than one that abstains: a fabricated pass on
a fidelity or judgement assertion is exactly the failure these evals exist to catch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "speckit-qa-auto" / "scripts" / "validate-run-state.py"
EVALS = json.loads((Path(__file__).resolve().parent / "evals.json").read_text(encoding="utf-8"))


class Run:
    """Everything a check needs, read once."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.run_json = self._json("run.json")
        self.design = self._text("test-design.md")
        self.features = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(folder.glob("*.feature"))
        }
        self.feature_text = "\n".join(self.features.values())

    def _json(self, name: str) -> dict:
        path = self.folder / name
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _text(self, name: str) -> str:
        path = self.folder / name
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    @property
    def review_text(self) -> str:
        review = self.run_json.get("review", {})
        return json.dumps(review, ensure_ascii=False).lower() + "\n" + self.design.lower()

    def severities(self) -> list[str]:
        findings = self.run_json.get("review", {}).get("findings", [])
        out = []
        for finding in findings:
            if isinstance(finding, dict):
                value = finding.get("severity")
                if isinstance(value, str):
                    out.append(value.lower())
        return out

    def validator_ok(self) -> tuple[bool, str]:
        target = self.folder / "run.json"
        if not target.is_file():
            return False, "run.json is missing"
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(target)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        return result.returncode == 0, (result.stderr or result.stdout).strip()[:400]


def has_all(haystack: str, *needles: str) -> bool:
    low = haystack.lower()
    return all(needle.lower() in low for needle in needles)


def has_any(haystack: str, *needles: str) -> bool:
    low = haystack.lower()
    return any(needle.lower() in low for needle in needles)


def check_1(r: Run) -> list[tuple[int, bool, str]]:
    review = r.run_json.get("review", {})
    sev = r.severities()
    routed = review.get("status") == "changes-requested" and r.run_json.get("resume_target") == "design"
    return [
        (0, has_all(r.review_text, "invoice") and has_any(r.review_text, "modify", "attached", "amend"),
         "searched review findings + test-design.md for invoice / modify / attached"),
        (1, any(s in {"critical", "important"} for s in sev),
         f"severities recorded: {sev or 'none'}"),
        (2, routed,
         f"review.status={review.get('status')!r}, resume_target={r.run_json.get('resume_target')!r}"),
        (3, not has_any(r.review_text, "no criterion is uncovered", "all criteria are covered",
                        "fully covers", "no gap"),
         "searched for completeness claims"),
    ]


def check_2(r: Run) -> list[tuple[int, bool, str]]:
    review = r.run_json.get("review", {})
    findings = review.get("findings", []) or []
    return [
        (0, has_any(r.review_text, "settle") and has_any(r.review_text, "re-rate", "rerate", "re-assign", "reassign"),
         "searched review findings + test-design.md for settle + re-rate / re-assign"),
        (1, bool(findings) or review.get("status") == "changes-requested",
         f"{len(findings)} finding(s), review.status={review.get('status')!r}"),
        (2, not has_any(r.review_text, "no criterion is uncovered", "all criteria are covered",
                        "fully covers", "no gap"),
         "searched for completeness claims"),
    ]


def check_3(r: Run) -> list[tuple[int, bool, str]]:
    impact = r.run_json.get("impact", {})
    candidates = impact.get("candidates", []) or []
    approved = impact.get("approved_scenarios", []) or []
    dropped = impact.get("dropped_scenarios", []) or []
    ok, detail = r.validator_ok()
    artifacts = (r.design + r.feature_text).lower()
    return [
        (0, has_any(r.feature_text, "refresh"),
         f"feature files: {', '.join(r.features) or 'none'}"),
        (1, bool(not candidates or approved or dropped),
         f"{len(candidates)} candidates, {len(approved)} approved, {len(dropped)} dropped"),
        (2, all(isinstance(x, dict) and str(x.get("reason", "")).strip() for x in dropped),
         f"{len(dropped)} drop(s) inspected"),
        (3, ok, detail or "validator ok"),
        (4, not has_any(artifacts, "affected: true", "risk: high", "needs regression: true"),
         "searched design + features for verdict phrasing"),
    ]


def check_4(r: Run) -> list[tuple[int, bool, str]]:
    coverage = r.run_json.get("coverage", {})
    design = r.design.lower()
    return [
        (0, has_any(design, "skip", "review"),
         "searched test-design.md for a SKIP / REVIEW label"),
        (1, "existing-tests-mom-12401.feature" in design,
         "searched test-design.md for the related export filename"),
        (2, "mom-3042" in design,
         "searched test-design.md for the manual test key"),
        (5, coverage.get("dedup") == "ran",
         f"coverage.dedup = {coverage.get('dedup')!r}"),
    ]


def check_5(r: Run) -> list[tuple[int, bool, str]]:
    conversion = r.run_json.get("conversion", {})
    converted = conversion.get("converted", []) or []
    modes = [c.get("mode") for c in converted if isinstance(c, dict)]
    keys = [c.get("manual_test") for c in converted if isinstance(c, dict)]
    deviations = [c.get("deviations") or [] for c in converted if isinstance(c, dict)]
    return [
        (0, "@test_" not in r.feature_text.lower(),
         f"feature files: {', '.join(r.features) or 'none'}"),
        (1, bool(modes) and all(m == "link" for m in modes),
         f"modes = {modes or 'none recorded'}"),
        (2, "MOM-3110" in keys,
         f"manual_test keys = {keys or 'none recorded'}"),
        (4, any(d for d in deviations),
         f"deviation counts = {[len(d) for d in deviations] or 'none recorded'}"),
    ]


def check_6(r: Run) -> list[tuple[int, bool, str]]:
    automation = r.run_json.get("automation", {})
    deferred = automation.get("deferred") or {}
    ok, detail = r.validator_ok()
    reason = str(deferred.get("reason", "")).strip()
    resume_when = str(deferred.get("resume_when", "")).strip()
    return [
        (0, automation.get("status") == "deferred",
         f"automation.status = {automation.get('status')!r}"),
        (1, bool(reason) and bool(resume_when),
         f"reason={reason!r}, resume_when={resume_when!r}"),
        (3, not (r.folder / "automation-result.json").is_file(),
         "checked the run folder"),
        (4, ok, detail or "validator ok"),
    ]


CHECKS = {1: check_1, 2: check_2, 3: check_3, 4: check_4, 5: check_5, 6: check_6}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval_id", type=int, choices=sorted(CHECKS))
    parser.add_argument("run_folder", type=Path, help="the docs/qa/<issue>/ the run produced")
    parser.add_argument("--out", type=Path, default=None, help="write grading.json here")
    args = parser.parse_args()

    if not args.run_folder.is_dir():
        print(f"run folder not found: {args.run_folder}", file=sys.stderr)
        return 2

    spec = next(e for e in EVALS["evals"] if e["id"] == args.eval_id)
    assertions = spec["assertions"]
    graded = CHECKS[args.eval_id](Run(args.run_folder))

    expectations = [
        {"text": assertions[idx], "passed": passed, "evidence": evidence}
        for idx, passed, evidence in graded
    ]
    graded_idx = {idx for idx, _, _ in graded}
    human = [text for i, text in enumerate(assertions) if i not in graded_idx]

    result = {
        "eval_id": args.eval_id,
        "eval_name": spec["name"],
        "expectations": expectations,
        "human_checks": human,
        "passed": sum(1 for e in expectations if e["passed"]),
        "total": len(expectations),
    }

    print(f"{spec['name']}  —  {result['passed']}/{result['total']} machine checks passed")
    for item in expectations:
        print(f"  {'ok  ' if item['passed'] else 'FAIL'} - {item['text']}")
        if not item["passed"]:
            print(f"         {item['evidence']}")
    if human:
        print("\n  needs a human reviewer:")
        for text in human:
            print(f"    · {text}")

    out = args.out or (args.run_folder / "grading.json")
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
