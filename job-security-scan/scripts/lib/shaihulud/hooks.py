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


def hook_target(pkg_dir, command):
    """The script file a hook command runs, resolved inside pkg_dir only; None if none/outside."""
    m = _TARGET.search(command)
    if not m:
        return None
    base = os.path.realpath(str(pkg_dir))
    path = os.path.realpath(os.path.join(base, m.group(1)))
    if path != base and not path.startswith(base + os.sep):
        return None
    p = Path(path)
    return p if p.is_file() and not p.is_symlink() else None


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
