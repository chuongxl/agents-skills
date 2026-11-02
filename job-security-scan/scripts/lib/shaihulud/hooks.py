"""npm lifecycle hooks: which ones run at install time and which file each one executes."""

import os
import re
from pathlib import Path

from . import MAX_SCAN_BYTES

INSTALL_HOOKS = ("preinstall", "install", "postinstall", "prepare", "prepublishOnly", "prepack")
_TARGET = re.compile(r"""(?:^|[\s'"=(])((?:\.{0,2}/)?[\w@./-]+\.(?:js|cjs|mjs|sh))\b""")


def install_hooks(manifest):
    """[(hook_name, command)] for the install-time hooks a manifest declares (case-insensitive keys)."""
    scripts = manifest.get("scripts") if isinstance(manifest, dict) else None
    if not isinstance(scripts, dict):
        return []
    wanted = dict((h.lower(), h) for h in INSTALL_HOOKS)
    out = []
    for key, cmd in scripts.items():
        if isinstance(key, str) and key.lower() in wanted and isinstance(cmd, str) and cmd.strip():
            out.append((wanted[key.lower()], cmd.strip()))
    return out


_REQUIRE = re.compile(r"""\b(?:require|import)\s*\(\s*['"](\.{1,2}/[^'"]+)['"]""")
_RESOLVE_SUFFIXES = ("", ".js", ".cjs", ".mjs", "/index.js")


def _inside(base, rel):
    path = os.path.realpath(os.path.join(base, rel))
    return path if path.startswith(base + os.sep) else None


def hook_targets(pkg_dir, command):
    """Every script file a hook command runs: *.js/.cjs/.mjs/.sh tokens and require()/import() paths
    (node -e "require('./x')"), resolved inside pkg_dir only, de-duplicated, in order."""
    base = os.path.realpath(str(pkg_dir))
    found = []
    candidates = [(m.start(), [m.group(1)]) for m in _TARGET.finditer(command)]
    candidates += [(m.start(), [m.group(1) + sfx for sfx in _RESOLVE_SUFFIXES]) for m in _REQUIRE.finditer(command)]
    for _pos, options in sorted(candidates, key=lambda c: c[0]):
        for rel in options:
            path = _inside(base, rel)
            if path and os.path.isfile(path) and not os.path.islink(path):
                if path not in found:
                    found.append(path)
                break
    return [Path(p) for p in found]


def read_text(path, limit=MAX_SCAN_BYTES):
    """File text (lossy UTF-8) or None if unreadable, binary, or larger than limit."""
    try:
        if os.path.getsize(str(path)) > limit:
            return None
        with open(str(path), "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace")
