"""versions.py - version comparison and advisory range evaluation.

Stdlib only; Python 3.8+.

Versions are compared as dotted numbers; a pre-release suffix (-rc.1, -beta) sorts before
the release. Versions that cannot be parsed return None from compare(), and the matcher
reports them as 'unknown' instead of guessing.
"""

import re

_VER_RE = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(?:[-+_.]?([A-Za-z][\w.+-]*))?$")


def parse(version):
    """Return (numbers tuple, prerelease string or '') or None."""
    if not isinstance(version, str):
        return None
    m = _VER_RE.match(version.strip())
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split(".")), (m.group(2) or "")


def compare(a, b):
    """-1, 0, 1, or None when either version cannot be parsed."""
    pa, pb = parse(a), parse(b)
    if pa is None or pb is None:
        return None
    na, nb = pa[0], pb[0]
    n = max(len(na), len(nb))
    na, nb = na + (0,) * (n - len(na)), nb + (0,) * (n - len(nb))
    if na != nb:
        return -1 if na < nb else 1
    ra, rb = pa[1], pb[1]
    if ra == rb:
        return 0
    if not ra:
        return 1   # release > pre-release
    if not rb:
        return -1
    return -1 if ra < rb else 1


def major(version):
    p = parse(version)
    return p[0][0] if p else None


def line_covers(line, version):
    """Does a release-line label ('22', '10-15', '1.22', '*') include this version?"""
    if line == "*":
        return True
    p = parse(version)
    if p is None:
        return False
    if re.fullmatch(r"\d+-\d+", line):
        lo, hi = (int(x) for x in line.split("-"))
        return lo <= p[0][0] <= hi
    parts = re.fullmatch(r"\d+(?:\.\d+)*", line)
    if not parts:
        return False
    want = tuple(int(x) for x in line.split("."))
    return p[0][:len(want)] == want


def line_floor(line):
    """Lowest major a line label refers to, or None for '*' and odd labels."""
    m = re.match(r"^(\d+)", line)
    return int(m.group(1)) if m else None


def evaluate(version, affected, eol_cycles=None):
    """Evaluate a version against an advisory's affected[] entries.

    Returns (status, entry):
      'affected'     in a listed line and inside [introduced, fixed)
      'fixed'        in a listed line but at/after the fix (or outside the range)
      'unlisted'     no entry covers the version's release line
      'eol-affected' unlisted line that is below every listed line and known end-of-life
      'unknown'      the version or a bound could not be compared
    """
    covering = [e for e in affected if line_covers(e["line"], version)]
    if not covering:
        floors = [f for f in (line_floor(e["line"]) for e in affected) if f is not None]
        mv = major(version)
        if mv is not None and floors and mv < min(floors) and eol_cycles and str(mv) in eol_cycles:
            return "eol-affected", None
        return "unlisted", None
    unknown = False
    for e in covering:
        lo = compare(version, e["introduced"]) if e["introduced"] != "0" else 1
        if lo is None:
            unknown = True
            continue
        if lo < 0:
            continue
        if e.get("fixed") is not None:
            c = compare(version, e["fixed"])
            if c is None:
                unknown = True
                continue
            if c >= 0:
                continue
        if e.get("last_affected") is not None:
            c = compare(version, e["last_affected"])
            if c is None:
                unknown = True
                continue
            if c > 0:
                continue
        return "affected", e
    return ("unknown", None) if unknown else ("fixed", None)
