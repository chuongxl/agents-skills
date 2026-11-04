#!/usr/bin/env python3
"""OS-enforced sandbox for deep-audit local checks (Phase 10, opt-in).

The deep audit is source-only unless JOB_SECURITY_SCAN_AUDIT_EXEC=1. When it is set, a hunter or verifier
may run a target-controlled check (an existing unit test, a minimal harness, a small fixture) ONLY through
this wrapper, which enforces every control the upstream method requires or refuses to run:

  - no external network (new network namespace; optional isolated loopback with --loopback)
  - empty environment, populated only from --env NAME=VALUE plus HOME/TMPDIR inside scratch, LANG, PATH
  - the whole filesystem read-only except the agent's own scratch/ directory
    (remounted read-only, then locked by a second unprivileged user+mount namespace: uid 65534, no capabilities,
    no_new_privs - the check cannot remount anything writable)
  - CPU, memory, process, file-size, open-file and wall-clock limits, and a cumulative disk quota
    (scratch is a size-limited tmpfs during the check; its files are copied back to scratch/ afterwards)

Usage:
  python3 -I audit-sandbox.py --scratch <run>/<repo>/audit/agents/<id>/scratch [limits] [--env N=V]... \
      [--path DIR]... [--cwd DIR] [--record FILE] -- CMD [ARG...]
  python3 -I audit-sandbox.py --self-test --scratch <.../agents/<id>/scratch>

Exit codes: the command's own exit code; 97 = a sandbox control is unavailable (nothing was run - record
the printed blocker as `needs_validation`); 98 = invalid arguments. Linux only (needs unshare, setpriv,
prlimit, timeout from util-linux/coreutils and unprivileged user namespaces). Stdlib only; Python 3.8+.
"""
import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys

BLOCKED = 97
BAD_ARGS = 98
REQUIRED_TOOLS = ("unshare", "setpriv", "prlimit", "timeout", "env", "sh")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
FORBIDDEN_ENV = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|AUTH|COOKIE|SESSION|PRIVATE)", re.I)
SCRATCH_SHAPE = re.compile(r"/agents/[a-z0-9][a-z0-9_-]{0,63}/scratch$")

# Runs as (mapped) root inside the first user+mount+net namespace: make every mount read-only except scratch,
# optionally bring up loopback, then drop into a second, unprivileged namespace that cannot undo it.
INNER = r'''
set -u
S="$1"; LOOP="$2"; DISK="$3"; shift 3
mount --make-rprivate / 2>/dev/null || { echo "BLOCKED: cannot make mounts private" >&2; exit 97; }
# Keep a handle on the real scratch directory, then cover it with a size-limited tmpfs: the check writes only
# into the tmpfs (cumulative disk quota); its files are copied back to the real scratch after it exits.
mount --bind "$S" "$S" 2>/dev/null || { echo "BLOCKED: cannot bind scratch" >&2; exit 97; }
cd "$S" || { echo "BLOCKED: cannot enter scratch" >&2; exit 97; }
mount -t tmpfs -o "size=${DISK}m,mode=1777,nosuid,nodev" sandbox-scratch "$S" 2>/dev/null \
  || { echo "BLOCKED: cannot mount size-limited scratch" >&2; exit 97; }
cp -a --no-dereference ./. "$S"/ 2>/dev/null || { echo "BLOCKED: scratch contents exceed the disk quota" >&2; exit 97; }
mkdir -p "$S/home" "$S/tmp" && chmod -R a+rwX "$S" && chmod 1777 "$S/home" "$S/tmp"
for m in $(awk '{print $5}' /proc/self/mountinfo | sort -u); do
  [ "$m" = "$S" ] && continue
  mount -o remount,bind,ro "$m" 2>/dev/null || { echo "BLOCKED: cannot make $m read-only" >&2; exit 97; }
done
if [ "$LOOP" = 1 ]; then
  ip link set lo up 2>/dev/null || { echo "BLOCKED: cannot bring up isolated loopback" >&2; exit 97; }
fi
unshare -U -m --fork -- setpriv --no-new-privs --inh-caps=-all -- "$@"
rc=$?
cp -a --no-dereference "$S"/. . 2>/dev/null || echo "warning: some scratch entries could not be copied back" >&2
exit $rc
'''


def blocked(msg):
    sys.stderr.write("BLOCKED: %s\n" % msg)
    return BLOCKED


def check_scratch(path):
    """scratch must be an existing real directory named agents/<agent-id>/scratch, not a symlink anywhere."""
    if not os.path.isabs(path):
        return None, "--scratch must be an absolute path"
    real = os.path.realpath(path)
    if real != os.path.normpath(path):
        return None, "--scratch must not contain symlinks"
    try:
        st = os.lstat(real)
    except OSError:
        return None, "--scratch does not exist"
    if not stat.S_ISDIR(st.st_mode):
        return None, "--scratch is not a directory"
    if not SCRATCH_SHAPE.search(real):
        return None, "--scratch must be <audit-dir>/agents/<agent-id>/scratch"
    return real, None


def build_argv(args, scratch, cmd):
    home = os.path.join(scratch, "home")
    tmp = os.path.join(scratch, "tmp")
    path_entries = [p for p in args.path] + ["/usr/local/bin", "/usr/bin", "/bin"]
    env = ["HOME=" + home, "TMPDIR=" + tmp, "LANG=C.UTF-8", "PATH=" + ":".join(path_entries)]
    for item in args.env:
        env.append(item)
    limits = ["prlimit", "--as=%d" % (args.memory_mb * 1024 * 1024), "--cpu=%d" % args.cpu_seconds,
              "--nproc=%d" % args.processes, "--fsize=%d" % (args.file_size_mb * 1024 * 1024),
              "--nofile=%d" % args.open_files, "--core=0", "--"]
    inner_cmd = limits + ["timeout", "-k", "5", str(args.wall_seconds), "env", "-i", "-C", args.cwd or scratch] \
        + env + list(cmd)
    return ["unshare", "-r", "-n", "-m", "--fork", "--", "sh", "-c", INNER, "sandbox", scratch,
            "1" if args.loopback else "0", str(args.disk_mb)] + inner_cmd


def preflight(args):
    if not sys.platform.startswith("linux"):
        return None, blocked("OS-enforced sandbox needs Linux namespaces; this is %s" % sys.platform)
    missing = [t for t in REQUIRED_TOOLS if not shutil.which(t)]
    if missing:
        return None, blocked("missing sandbox tools: %s" % ", ".join(missing))
    if args.loopback and not shutil.which("ip"):
        return None, blocked("--loopback needs the ip tool")
    scratch, err = check_scratch(args.scratch)
    if err:
        sys.stderr.write("error: %s\n" % err)
        return None, BAD_ARGS
    for item in args.env:
        name = item.split("=", 1)[0]
        if "=" not in item or not ENV_NAME.match(name):
            sys.stderr.write("error: --env must be NAME=VALUE\n")
            return None, BAD_ARGS
        if FORBIDDEN_ENV.search(name) or name in ("HOME", "TMPDIR", "PATH", "LD_PRELOAD", "LD_LIBRARY_PATH"):
            sys.stderr.write("error: --env %s is not allowed (no credentials, no loader or sandbox variables)\n"
                             % name)
            return None, BAD_ARGS
    if args.cwd and not os.path.isdir(args.cwd):
        sys.stderr.write("error: --cwd does not exist\n")
        return None, BAD_ARGS
    if args.record and os.path.realpath(args.record).startswith(scratch + os.sep):
        sys.stderr.write("error: --record must be outside scratch (it is parent-owned evidence)\n")
        return None, BAD_ARGS
    probe = subprocess.run(["unshare", "-r", "-n", "-m", "--fork", "--", "true"], capture_output=True)
    if probe.returncode != 0:
        return None, blocked("unprivileged user/network/mount namespaces are not available")
    return scratch, 0


SELF_TEST = r'''
import json, os, socket, sys
r = {}
r["uid"] = os.getuid()
try:
    open("/sandbox-escape-probe", "w"); r["root_writable"] = True
except OSError:
    r["root_writable"] = False
try:
    open(os.path.join(os.environ["HOME"], "..", "..", "probe"), "w"); r["outside_scratch_writable"] = True
except OSError:
    r["outside_scratch_writable"] = False
try:
    p = os.path.join(os.environ["TMPDIR"], "probe"); open(p, "w").write("x"); os.remove(p); r["scratch_writable"] = True
except OSError:
    r["scratch_writable"] = False
try:
    socket.create_connection(("1.1.1.1", 53), 2); r["network"] = True
except OSError:
    r["network"] = False
try:
    with open(os.path.join(os.environ["TMPDIR"], "fill"), "wb") as fh:
        for _ in range(4096):
            fh.write(b"x" * 65536)
    r["disk_quota"] = False
except OSError:
    r["disk_quota"] = True
finally:
    try:
        os.remove(os.path.join(os.environ["TMPDIR"], "fill"))
    except OSError:
        pass
r["env"] = sorted(os.environ)
caps = [l.split()[1] for l in open("/proc/self/status") if l.startswith("CapEff")]
r["capabilities"] = caps[0] if caps else "unknown"
print(json.dumps(r))
'''


def self_test(args, scratch):
    py = shutil.which("python3")
    argv = build_argv(args, scratch, [py, "-I", "-c", SELF_TEST])
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=args.wall_seconds + 30)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return blocked("self-test could not run inside the sandbox (exit %d)" % proc.returncode)
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    ok = (not result["root_writable"] and not result["outside_scratch_writable"] and result["scratch_writable"]
          and not result["network"] and result["capabilities"] == "0000000000000000" and result["uid"] != 0
          and result["disk_quota"]
          and set(result["env"]) <= {"HOME", "TMPDIR", "LANG", "PATH", "PWD"})
    result["sandbox_ok"] = ok
    print(json.dumps(result, sort_keys=True))
    return 0 if ok else blocked("self-test found a control that is not enforced: %s" % json.dumps(result))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--cwd", help="working directory inside the sandbox (default: scratch); read-only unless scratch")
    ap.add_argument("--env", action="append", default=[], help="NAME=VALUE (allowlisted, non-secret)")
    ap.add_argument("--path", action="append", default=[], help="extra PATH entry (e.g. a toolchain bin dir)")
    ap.add_argument("--cpu-seconds", type=int, default=30)
    ap.add_argument("--memory-mb", type=int, default=1024)
    ap.add_argument("--processes", type=int, default=64)
    ap.add_argument("--file-size-mb", type=int, default=16)
    ap.add_argument("--open-files", type=int, default=256)
    ap.add_argument("--disk-mb", type=int, default=64, help="cumulative scratch quota (size-limited tmpfs)")
    ap.add_argument("--wall-seconds", type=int, default=120)
    ap.add_argument("--loopback", action="store_true", help="bring up an isolated loopback (no external network)")
    ap.add_argument("--record", help="write a JSON record of the check here (outside scratch)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if os.environ.get("JOB_SECURITY_SCAN_AUDIT_EXEC") != "1":
        return blocked("local execution is disabled; set JOB_SECURITY_SCAN_AUDIT_EXEC=1 to allow sandboxed checks")
    scratch, rc = preflight(args)
    if rc:
        return rc
    if args.self_test:
        return self_test(args, scratch)
    if not cmd:
        sys.stderr.write("error: no command given after --\n")
        return BAD_ARGS
    # nosemgrep: dangerous-subprocess-use-tainted-env-args (running this command is the wrapper's purpose; gated by JOB_SECURITY_SCAN_AUDIT_EXEC=1)
    proc = subprocess.run(build_argv(args, scratch, cmd))
    if args.record:
        record = {
            "command": cmd,
            "cwd": args.cwd or scratch,
            "env_names": sorted(e.split("=", 1)[0] for e in args.env) + ["HOME", "LANG", "PATH", "TMPDIR"],
            "limits": {"cpu_seconds": args.cpu_seconds, "memory_mb": args.memory_mb, "processes": args.processes,
                       "disk_mb": args.disk_mb,
                       "file_size_mb": args.file_size_mb, "open_files": args.open_files,
                       "wall_seconds": args.wall_seconds},
            "network": "isolated-loopback" if args.loopback else "none",
            "filesystem": "read-only except scratch",
            "exit_code": proc.returncode,
        }
        with open(args.record, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
            fh.write("\n")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
