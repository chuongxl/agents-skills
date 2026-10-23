"""component.py - component model and package-URL (purl) helpers.

Stdlib only; compatible with Python 3.8+.

A component is anything an advisory can apply to: a library package, a language
runtime, a container image or an OS package. Packages carry a purl
(https://github.com/package-url/purl-spec); runtimes use the pseudo key
"runtime:<name>" because they have no registry purl.
"""

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import quote, unquote

KINDS = ("package", "runtime", "image", "os")

_TYPE_RE = re.compile(r"^[a-z][a-z0-9.+-]*$")


class PurlError(ValueError):
    """Raised when a purl string is malformed."""


@dataclass
class Component:
    kind: str
    ecosystem: str
    name: str
    version: Optional[str] = None
    purl: Optional[str] = None
    location: Optional[str] = None  # file (and line) where the component was found
    extra: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError("unknown component kind: %r" % (self.kind,))

    @property
    def key(self):
        """Version-less identity used to match advisories and vendor patterns."""
        if self.kind == "runtime":
            return "runtime:%s" % self.name
        if self.purl:
            return purl_key(self.purl)
        return "%s:%s/%s" % (self.kind, self.ecosystem, self.name)


def _normalize_name(ptype, name):
    # PyPI names are case-insensitive and treat _ and . like -; the purl spec
    # normalizes them. Other types are kept exactly as written (several are
    # case-sensitive, e.g. maven).
    if ptype == "pypi":
        return re.sub(r"[-_.]+", "-", name).lower()
    return name


def parse_purl(purl):
    """Parse a purl into a dict: type, namespace, name, version, qualifiers, subpath."""
    if not isinstance(purl, str) or not purl.startswith("pkg:"):
        raise PurlError("purl must start with 'pkg:': %r" % (purl,))
    rest = purl[4:].lstrip("/")

    subpath = None
    if "#" in rest:
        rest, subpath = rest.split("#", 1)
        subpath = unquote(subpath).strip("/") or None

    qualifiers = {}
    if "?" in rest:
        rest, qs = rest.split("?", 1)
        for pair in qs.split("&"):
            if not pair:
                continue
            if "=" not in pair:
                raise PurlError("bad qualifier %r in %r" % (pair, purl))
            k, v = pair.split("=", 1)
            qualifiers[k.lower()] = unquote(v)

    version = None
    if "@" in rest:
        rest, version = rest.rsplit("@", 1)
        version = unquote(version)
        if version == "":
            raise PurlError("empty version in %r" % (purl,))

    parts = rest.split("/")
    ptype = parts[0].lower()
    if not _TYPE_RE.match(ptype):
        raise PurlError("bad purl type %r in %r" % (ptype, purl))
    segments = [unquote(p) for p in parts[1:] if p != ""]
    if not segments:
        raise PurlError("purl has no name: %r" % (purl,))

    name = _normalize_name(ptype, segments[-1])
    namespace = "/".join(segments[:-1]) or None
    return {
        "type": ptype,
        "namespace": namespace,
        "name": name,
        "version": version,
        "qualifiers": qualifiers,
        "subpath": subpath,
    }


def format_purl(ptype, name, namespace=None, version=None, qualifiers=None, subpath=None):
    """Build a canonical purl string (percent-encoding reserved characters)."""
    ptype = ptype.lower()
    if not _TYPE_RE.match(ptype):
        raise PurlError("bad purl type %r" % (ptype,))
    if not name:
        raise PurlError("purl name is required")
    out = "pkg:" + ptype + "/"
    if namespace:
        out += "/".join(quote(seg, safe="") for seg in namespace.split("/")) + "/"
    out += quote(_normalize_name(ptype, name), safe="")
    if version:
        out += "@" + quote(version, safe="")
    if qualifiers:
        out += "?" + "&".join(
            "%s=%s" % (k, quote(str(v), safe="")) for k, v in sorted(qualifiers.items())
        )
    if subpath:
        out += "#" + "/".join(quote(seg, safe="") for seg in subpath.split("/"))
    return out


def purl_key(purl):
    """Version-less, qualifier-less identity of a purl: 'pkg:type/namespace/name'."""
    p = parse_purl(purl)
    return format_purl(p["type"], p["name"], namespace=p["namespace"])


def canonical_purl(purl):
    """Parse then re-format; two spellings of the same package give the same string."""
    p = parse_purl(purl)
    return format_purl(
        p["type"], p["name"], namespace=p["namespace"], version=p["version"],
        qualifiers=p["qualifiers"], subpath=p["subpath"],
    )


def matches_pattern(component, pattern):
    """True when a component matches a vendor-registry pattern.

    Patterns are either 'runtime:<name>' or a purl prefix with optional '*' glob,
    e.g. 'pkg:npm/next', 'pkg:maven/org.springframework.boot/*', 'pkg:pypi/django'.
    Matching is on the version-less key, case-sensitive except for the type.
    """
    key = component.key if isinstance(component, Component) else str(component)
    if pattern.startswith("runtime:"):
        return key == pattern
    if not pattern.startswith("pkg:"):
        return False
    return fnmatch.fnmatchcase(key, pattern)
