#!/usr/bin/env python3
"""
git_sync_agent.py - keeps a local project folder and its GitHub repo in sync.

Every INTERVAL seconds it:
  1. Waits until local changes have been quiet for one full cycle
     (so it never commits a file an editor/agent is halfway through writing)
  2. Commits local changes   (git add + commit)
  3. Pulls remote changes    (git pull --rebase)
  4. Pushes to GitHub        (git push)

Usage (Windows CMD / PowerShell):
  python git_sync_agent.py "C:\\path\\to\\project"
  python git_sync_agent.py "C:\\path\\to\\project" --interval 30
  python git_sync_agent.py "C:\\path\\to\\project" --once        # single run
  python git_sync_agent.py "C:\\path\\to\\project" --no-pull     # push only

Stop with Ctrl+C. Log is written to sync_agent.log inside the project folder.
Needs: Python 3.8+, git in PATH, and you already signed in to GitHub
(GitHub Desktop / Git Credential Manager credentials are reused).
"""
import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

# Files that must never be auto-committed, even if not in .gitignore
NEVER_ADD = [
    ".env", "*.pem", "*.key", "*.pfx", "sync_agent.log",
    "*.db", "*.db.*", "*.bak*", "*.sqlite*",          # databases / backups
    "*.rar", "*.zip", "*.7z", "*.tar*",               # archives
    "*.mp4", "*.mp3", "*.wav", "*.mov", "*.jfif",     # media
    "node_modules/", "__pycache__/", "venv/", ".venv/",
]
MAX_FILE_MB = 50  # GitHub rejects files over 100 MB; stay well below


def log(msg, logfile):
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def git(repo, *args):
    r = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def status(repo):
    return git(repo, "status", "--porcelain")[1]


def commit_local(repo, logfile):
    excludes = [f":(exclude){p}" for p in NEVER_ADD]
    code, out = git(repo, "add", "-A", "--", ".", *excludes)
    # git exits non-zero just because an ignored path was named; that is harmless
    if code != 0 and "ignored by one of your .gitignore" not in out:
        log(f"git add failed: {out[:500]}", logfile)
        return False
    # unstage anything too big for GitHub
    names = git(repo, "diff", "--cached", "--name-only")[1].splitlines()
    for n in names:
        p = repo / n
        if p.is_file() and p.stat().st_size > MAX_FILE_MB * 1024 * 1024:
            git(repo, "reset", "-q", "--", n)
            log(f"skipped (over {MAX_FILE_MB} MB): {n}", logfile)
    # anything staged?
    if git(repo, "diff", "--cached", "--quiet")[0] == 0:
        return False
    msg = f"auto-sync {dt.datetime.now():%Y-%m-%d %H:%M}"
    code, out = git(repo, "commit", "-m", msg)
    log(f"commit: {'ok' if code == 0 else 'FAILED ' + out}", logfile)
    return code == 0


def pull_remote(repo, logfile):
    code, out = git(repo, "pull", "--rebase", "--autostash")
    if code != 0:
        git(repo, "rebase", "--abort")
        log(f"PULL CONFLICT - rebase aborted, NOT pushing. Fix manually in GitHub Desktop.\n{out}", logfile)
        return False
    if "Already up to date" not in out:
        log("pulled new changes from GitHub", logfile)
    return True


def push_remote(repo, logfile):
    code, out = git(repo, "push")
    if code != 0 and "no upstream" in out.lower():
        code, out = git(repo, "push", "-u", "origin", "HEAD")
    if code != 0:
        log(f"PUSH FAILED: {out}", logfile)
        return False
    if "Everything up-to-date" not in out:
        log("pushed to GitHub", logfile)
    return True


def cycle(repo, logfile, pull, commit_now):
    if commit_now:
        commit_local(repo, logfile)
    if pull and not pull_remote(repo, logfile):
        return
    # push only if we are ahead of remote
    code, out = git(repo, "rev-list", "--count", "@{u}..HEAD")
    if code != 0 or (out.strip().isdigit() and int(out.strip()) > 0):
        push_remote(repo, logfile)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".", help="project folder")
    ap.add_argument("--interval", type=int, default=60, help="seconds between checks (default 60)")
    ap.add_argument("--once", action="store_true", help="run one sync and exit")
    ap.add_argument("--no-pull", action="store_true", help="push only, never pull")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    logfile = repo / "sync_agent.log"

    if git(repo, "rev-parse", "--is-inside-work-tree")[0] != 0:
        sys.exit(f"{repo} is not a git repository (or git is not in PATH).")

    log(f"Sync agent started for {repo} (every {a.interval}s). Ctrl+C to stop.", logfile)

    if a.once:
        cycle(repo, logfile, not a.no_pull, commit_now=True)
        return

    last = None
    try:
        while True:
            cur = status(repo)
            # commit only when changes exist AND stayed identical since last check
            commit_now = bool(cur) and cur == last
            cycle(repo, logfile, not a.no_pull, commit_now)
            last = status(repo)
            time.sleep(a.interval)
    except KeyboardInterrupt:
        log("Stopped by user.", logfile)


if __name__ == "__main__":
    main()
