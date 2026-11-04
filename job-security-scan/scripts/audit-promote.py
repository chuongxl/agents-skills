#!/usr/bin/env python3
"""Trusted parent-side promotion of deep-audit evidence from scratch/ to artifacts/ (Phase 10).

Only the parent agent runs this, after a sandboxed check and all its processes have exited. Each file
named with --file (relative to the agent's scratch/) is copied to the agent's artifacts/ following the
upstream promotion procedure: path validation, no-follow descriptor-relative traversal of every component,
regular file with link count 1, per-file and cumulative byte limits enforced on fstat and again while
reading, identity re-checked after the copy, exclusive no-follow creation of every destination component.
Symlinks, FIFOs, sockets, devices, directories, hard-linked or changing files are refused; nothing is
globbed, extracted or copied recursively.

Usage:
  python3 -I audit-promote.py --agent-dir <run>/<repo>/audit/agents/<agent-id> \
      --file out/result.txt [--file ...] [--max-file-bytes 65536] [--max-total-bytes 262144]

Prints one line per promoted file with its output-relative path (agents/<id>/artifacts/...), suitable for a
ledger check's `artifact`. Exit 0 all promoted, 1 one or more refused (refused files are reported and NOT
promoted; if one was decisive evidence, keep the finding `needs_validation` with that blocker), 2 bad args.
POSIX only. Stdlib only; Python 3.8+.
"""
import argparse
import os
import re
import stat
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import audit  # noqa: E402

DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
AGENT_DIR = re.compile(r"/agents/([a-z0-9][a-z0-9_-]{0,63})$")


class Refused(Exception):
    pass


def open_root(path, create=False):
    if create and not os.path.lexists(path):
        os.mkdir(path, 0o700)
    fd = os.open(path, DIR_FLAGS)
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise Refused("%s is not a directory" % path)
    return fd


def walk(root_fd, parts, create):
    """Descend parts from root_fd without following links; returns a new directory descriptor."""
    fd = os.dup(root_fd)
    for part in parts:
        if create:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
        try:
            nxt = os.open(part, DIR_FLAGS, dir_fd=fd)
        except OSError as exc:
            os.close(fd)
            raise Refused("component %r: %s" % (part, exc.strerror))
        os.close(fd)
        if not stat.S_ISDIR(os.fstat(nxt).st_mode):
            os.close(nxt)
            raise Refused("component %r is not a directory" % part)
        fd = nxt
    return fd


def promote(scratch_fd, artifacts_fd, rel, max_file, budget):
    if not audit.safe_relative_path(rel):
        raise Refused("unsafe relative path")
    parts = rel.split("/")
    src_dir = walk(scratch_fd, parts[:-1], create=False)
    try:
        try:
            src = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=src_dir)
        except OSError as exc:
            raise Refused("cannot open: %s" % exc.strerror)
    finally:
        os.close(src_dir)
    try:
        st = os.fstat(src)
        if not stat.S_ISREG(st.st_mode):
            raise Refused("not a regular file")
        if st.st_nlink != 1:
            raise Refused("link count is %d, not 1" % st.st_nlink)
        if st.st_size > max_file or st.st_size > budget:
            raise Refused("%d bytes exceeds the per-file or cumulative limit" % st.st_size)
        chunks, total = [], 0
        while True:
            chunk = os.read(src, 65536)
            if not chunk:
                break
            total += len(chunk)
            if total > st.st_size or total > max_file or total > budget:
                raise Refused("file grew while reading")
            chunks.append(chunk)
        after = os.fstat(src)
        if ((after.st_ino, after.st_dev, after.st_mode, after.st_nlink, after.st_size)
                != (st.st_ino, st.st_dev, st.st_mode, st.st_nlink, st.st_size)) or total != st.st_size:
            raise Refused("file changed during promotion")
        data = b"".join(chunks)
    finally:
        os.close(src)
    dst_dir = walk(artifacts_fd, parts[:-1], create=True)
    try:
        try:
            dst = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dst_dir)
        except FileExistsError:
            raise Refused("destination already exists")
    finally:
        os.close(dst_dir)
    try:
        dst_st = os.fstat(dst)
        if not stat.S_ISREG(dst_st.st_mode) or dst_st.st_nlink != 1:
            raise Refused("destination is not a fresh regular file")
        view = memoryview(data)
        while view:
            n = os.write(dst, view)
            view = view[n:]
    finally:
        os.close(dst)
    return len(data)


def main():
    ap = argparse.ArgumentParser(description="Promote scratch evidence to artifacts (parent only)")
    ap.add_argument("--agent-dir", required=True)
    ap.add_argument("--file", action="append", required=True, help="scratch-relative file (repeatable)")
    ap.add_argument("--max-file-bytes", type=int, default=64 * 1024)
    ap.add_argument("--max-total-bytes", type=int, default=256 * 1024)
    args = ap.parse_args()
    agent_dir = os.path.normpath(os.path.abspath(args.agent_dir))
    m = AGENT_DIR.search(agent_dir)
    if not m or not audit.safe_agent_id(m.group(1)) or os.path.realpath(agent_dir) != agent_dir:
        sys.stderr.write("error: --agent-dir must be <audit-dir>/agents/<agent-id> with no symlinks\n")
        return 2
    try:
        scratch_fd = open_root(os.path.join(agent_dir, "scratch"))
        artifacts_fd = open_root(os.path.join(agent_dir, "artifacts"), create=True)
    except (OSError, Refused) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    budget, refused = args.max_total_bytes, 0
    try:
        for rel in args.file:
            try:
                size = promote(scratch_fd, artifacts_fd, rel, args.max_file_bytes, budget)
            except (OSError, Refused) as exc:
                refused += 1
                print("REFUSED %s: %s" % (rel, exc))
                continue
            budget -= size
            print("agents/%s/artifacts/%s" % (m.group(1), rel))
    finally:
        os.close(scratch_fd)
        os.close(artifacts_fd)
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
