#!/usr/bin/env python3
"""Self-test: drive the deterministic parts of `speckit-auto --pr-fix` (pr-fix/stage-01 + stage-06) against a
disposable project: a bare repo plays GitHub, a dict plays `gh api`, the REAL run-events.mjs emits.
This proves the procedure is safe when followed; test_run_events.mjs guards that the prose still says it."""
import json, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path

EMIT = str(Path(__file__).resolve().parent.parent / "speckit-auto/scripts/run-events.mjs")

def sh(cwd, *a, ok=True, inp=None):
    r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, input=inp)
    if ok and r.returncode: raise RuntimeError(f"{a}: {r.stderr or r.stdout}")
    return r
def git(cwd, *a, ok=True):
    return sh(cwd, "git", "-c", "user.name=sim", "-c", "user.email=s@s", *a, ok=ok)
def out(cwd, *a): return git(cwd, *a).stdout.strip()

class Stop(Exception):
    def __init__(s, code, msg): s.code, s.msg = code, msg

class World:
    def __init__(s):
        s.t = Path(tempfile.mkdtemp(prefix="prfix-sim-"))
        s.remote = s.t / "github.git"; s.proj = s.t / "proj"; s.mate = s.t / "mate"
        git(s.t, "init", "-q", "--bare", "-b", "main", str(s.remote))
        git(s.t, "clone", "-q", str(s.remote), str(s.proj))
        (s.proj / "auth.py").write_text("def login(u, p):\n    return u == 'admin'\n")  # bug: ignores password
        (s.proj / ".gitignore").write_text(".speckit/\n")
        git(s.proj, "add", "-A"); git(s.proj, "commit", "-qm", "init"); git(s.proj, "push", "-q", "origin", "main")
        git(s.proj, "checkout", "-qb", "fix-login")
        (s.proj / "README.md").write_text("login feature\n"); git(s.proj, "add", "-A"); git(s.proj, "commit", "-qm", "wip login")
        git(s.proj, "push", "-q", "origin", "fix-login"); git(s.proj, "checkout", "-q", "main")
        git(s.t, "clone", "-q", "-b", "fix-login", str(s.remote), str(s.mate))
        s.pr = {"state": "open", "head_ref": "fix-login", "head_repo": "o/r"}   # fake `gh api` answer
    def api(s):  # what `gh api repos/o/r/pulls/42` would return (plus head SHA from the real remote)
        sha = out(s.remote, "rev-parse", "fix-login")
        return {**s.pr, "head_sha": sha, "base_sha": out(s.remote, "rev-parse", "main"), "push_ok": True}

def emit(wt, run, payload):
    r = sh(wt, "node", EMIT, "emit", "--worktree", str(wt), "--run-id", run, inp=json.dumps(payload), ok=False)
    if r.returncode: raise Stop("instrumentation", r.stderr)
def events(wt): return [json.loads(l) for l in (wt / ".speckit/events.jsonl").read_text().splitlines()]

def intake(w, url, request, supplied=None):
    # stage-01 steps 1-3
    if not url.startswith("https://github.com/") or not request.strip(): raise Stop("policy_blocked", "bad inputs")
    api = w.api()
    if api["state"] != "open": raise Stop("policy_blocked", f"PR is {api['state']}")
    git(w.proj, "fetch", "-q", str(w.remote), f"refs/heads/{api['head_ref']}:refs/tmp/prfix-head")
    if out(w.proj, "rev-parse", "refs/tmp/prfix-head") != api["head_sha"]: raise Stop("git_error", "head moved during intake")
    if supplied:
        if out(supplied, "status", "--porcelain"): raise Stop("policy_blocked", "supplied worktree is dirty")
        if git(supplied, "merge-base", "--is-ancestor", api["head_sha"], "HEAD", ok=False).returncode:
            raise Stop("policy_blocked", "supplied worktree does not contain PR head")
        if int(out(supplied, "rev-list", "--count", f"{api['head_sha']}..HEAD")): raise Stop("policy_blocked", "extra unpublished commits")
        wt, created = supplied, False
    else:
        wt, created = w.t / "wt-pr42", True
        git(w.proj, "worktree", "add", "-q", "-b", "pr-fix/42", str(wt), api["head_sha"])
    run = str(uuid.uuid4())
    # step 5: events init is a hard gate
    r = sh(wt, "node", EMIT, "init", "--repo", str(w.proj), "--worktree", str(wt), "--run-id", run, ok=False)
    if r.returncode: raise Stop("instrumentation", r.stderr)
    emit(wt, run, {"type": "stage_finished", "stage": "01-intake"})
    return dict(wt=wt, run=run, api=api, created=created, head=api["head_sha"])

def fix(st, change=True):
    wt = st["wt"]
    if change:
        (wt / "auth.py").write_text("def login(u, p):\n    return u == 'admin' and p == 'secret'\n")
        (wt / "test_auth.py").write_text("from auth import login\nassert not login('admin','x')\nassert login('admin','secret')\n")
        git(wt, "add", "auth.py", "test_auth.py"); git(wt, "commit", "-qm", "fix(#42): check password")  # only this run's paths
    if change: sh(wt, sys.executable, "test_auth.py")  # the project's own check

def finish(w, st):
    wt, run = st["wt"], st["run"]
    cur = w.api()                                     # re-query before push
    if cur["state"] != "open" or cur["head_ref"] != st["api"]["head_ref"]: raise Stop("git_error", "PR identity changed")
    git(wt, "fetch", "-q", str(w.remote), "refs/heads/fix-login:refs/tmp/prfix-final")
    if out(wt, "rev-parse", "refs/tmp/prfix-final") != cur["head_sha"]: raise Stop("git_error", "fetched sha != api head")
    if git(wt, "merge-base", "--is-ancestor", "refs/tmp/prfix-final", "HEAD", ok=False).returncode:
        raise Stop("git_error", "remote head is not an ancestor of local HEAD")
    if hasattr(w, "race"): w.race()                   # a teammate pushes after our check, before our push
    p = git(wt, "push", "-q", str(w.remote), "HEAD:refs/heads/fix-login", ok=False)   # ordinary, non-force
    if p.returncode: raise Stop("git_error", "push rejected: " + p.stderr.strip().splitlines()[-1])
    if out(w.remote, "rev-parse", "fix-login") != out(wt, "rev-parse", "HEAD"): raise Stop("git_error", "post-push verify failed")
    if out(wt, "rev-parse", "HEAD") != st["head"]:
        emit(wt, run, {"type": "pr_updated", "pr_url": "https://github.com/o/r/pull/42"})
    emit(wt, run, {"type": "stage_finished", "stage": "06-finish"}); emit(wt, run, {"type": "run_completed"})

def run_case(name, setup=None, change=True, supplied=None, expect="ok", expect_types=None, check=None):
    w = World(); st = None; res = "ok"
    try:
        if setup: setup(w)
        sup = None
        if supplied:  # a function that dirties or advances the supplied worktree
            sup = w.t / "supplied"; git(w.proj, "worktree", "add", "-q", "-b", "mine", str(sup), out(w.remote, "rev-parse", "fix-login"))
            supplied(sup)
        st = intake(w, "https://github.com/o/r/pull/42", "Fix: login ignores the password", sup)
        fix(st, change); finish(w, st)
    except Stop as e:
        res = e.code
        if st:
            try: emit(st["wt"], st["run"], {"type": "run_failed", "reason": {"code": e.code if e.code in ("git_error", "policy_blocked") else "crashed", "message": e.msg[:200]}})
            except Stop: pass
        print(f"   stop: {e.code}: {e.msg[:90]}")
    good = (res == expect)
    if st and expect_types is not None:
        types = [e["type"] for e in events(st["wt"])]
        good &= (types == expect_types); print("   events:", types)
    if check: good &= bool(check(w, st))
    print(("PASS" if good else "FAIL"), name); shutil.rmtree(w.t, ignore_errors=True)
    return good

base = ["run_started", "stage_started", "stage_finished"]
ok_all = []
ok_all.append(run_case("A happy path: fix lands on the PR head, pr_updated emitted",
    expect_types=base + ["pr_updated", "stage_finished", "run_completed"],
    check=lambda w, st: out(w.remote, "rev-parse", "fix-login") == out(st["wt"], "rev-parse", "HEAD") != st["head"]))
def race(w):
    git(w.mate, "pull", "-q"); (w.mate / "x.txt").write_text("x"); git(w.mate, "add", "-A"); git(w.mate, "commit", "-qm", "mate"); git(w.mate, "push", "-q", "origin", "fix-login")
def s_race(w): w.race = lambda: race(w)
ok_all.append(run_case("B teammate pushes mid-run: push rejected, teammate commit kept, run_failed, no completion",
    setup=s_race, expect="git_error",
    check=lambda w, st: out(w.remote, "log", "-1", "--format=%s", "fix-login") == "mate"
        and "run_completed" not in [e["type"] for e in events(st["wt"])] and events(st["wt"])[-1]["type"] == "run_failed"))
def closed(w): w.pr["state"] = "closed"
ok_all.append(run_case("C closed PR: stop before any worktree exists", setup=closed, expect="policy_blocked",
    check=lambda w, st: not (w.t / "wt-pr42").exists()))
ok_all.append(run_case("D dirty supplied worktree: stopped, edit preserved", supplied=lambda s: (s / "scratch.txt").write_text("mine"), expect="policy_blocked",
    check=lambda w, st: (w.t / "supplied/scratch.txt").read_text() == "mine"))
def extra(s): (s / "local.txt").write_text("l"); git(s, "add", "-A"); git(s, "commit", "-qm", "local only")
ok_all.append(run_case("E supplied worktree ahead of PR head: stopped, not pushed", supplied=extra, expect="policy_blocked",
    check=lambda w, st: out(w.remote, "log", "-1", "--format=%s", "fix-login") == "wip login"))
ok_all.append(run_case("F no-change run: push verified, neither pr_opened nor pr_updated",
    change=False, expect_types=base + ["stage_finished", "run_completed"]))
print("\nALL PASS" if all(ok_all) else "\nSOME FAILED"); sys.exit(0 if all(ok_all) else 1)
