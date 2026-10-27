"""Bulk-generate many days of Make Money (or any kind) videos in one run, sequentially.

Runs outside the web server, using the exact same functions the app uses (jobs.run with
auto_render=True), so every video ends up in the normal Video Creator gallery: downloadable,
deletable, same as one made by clicking Generate + Render in the browser.

One video renders at a time (same as the app itself), so this is slow by nature -- expect it to
run for hours for a large --days count. It is safe to stop (Ctrl+C) and re-run: already-completed
dates are skipped, so it resumes where it left off.

Usage (from backend, with the venv active):
    python ..\\scripts\\bulk_generate.py --kind make-money --days 365 --delete-existing

    --kind             history | indian-law | make-money   (default: make-money)
    --days             how many days to generate, starting from --start-date  (default: 365)
    --start-date       YYYY-MM-DD, default: today (Asia/Kolkata)
    --voice            ta-IN-PallaviNeural | ta-IN-ValluvarNeural  (default: Pallavi)
    --owner            user id to generate under; auto-detected from existing jobs if omitted
    --delete-existing  delete this owner's existing jobs of this kind before starting
    --dry-run          only print the plan (owner, date range, how many existing jobs would be
                        deleted) and exit -- makes no changes
"""
import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.video_creator import jobs  # noqa: E402


def detect_owner():
    with jobs.connect() as db:
        rows = db.execute('SELECT DISTINCT owner FROM jobs').fetchall()
    owners = [r[0] for r in rows]
    if len(owners) == 1:
        return owners[0]
    if not owners:
        raise SystemExit('No existing jobs found to detect the owner from. Create one video in the '
                          'browser first, or pass --owner <user-id> explicitly.')
    raise SystemExit(f'Multiple owners found ({owners}); pass --owner <user-id> explicitly.')


def existing_dates(owner, kind):
    """Dates that already have a completed job of this kind, keyed by date -> job id."""
    with jobs.connect() as db:
        rows = db.execute('SELECT body FROM jobs WHERE owner=?', (str(owner),)).fetchall()
    out = {}
    import json
    for (body,) in rows:
        job = json.loads(body)
        if job.get('kind', 'history') == kind and job.get('status') == 'complete':
            out[job['date']] = job['id']
    return out


def delete_all(owner, kind):
    with jobs.connect() as db:
        rows = db.execute('SELECT id, body FROM jobs WHERE owner=?', (str(owner),)).fetchall()
    import json
    count = 0
    for job_id, body in rows:
        job = json.loads(body)
        if job.get('kind', 'history') == kind:
            if jobs.delete(job_id, owner):
                count += 1
    return count


def run_one(owner, day, voice, kind):
    job = {'id': str(uuid4()), 'owner': str(owner), 'date': day.isoformat(), 'voice': voice,
           'auto_render': True, 'kind': kind,
           'model': __import__('app.config.settings', fromlist=['settings']).settings.HISTORY_MODEL if kind == 'history' else 'curated-tamil-v1',
           'status': 'new', 'points': [], 'message': '', 'rate': '+0%', 'pitch': '+0Hz', 'volume': '+0%', 'display': 'tamil'}
    # jobs.run() always releases jobs.gate in its finally block (it's normally called by jobs.launch(),
    # which acquires it first) -- so we must hold the lock before calling run() directly, or the
    # release call raises. This also keeps us serialized with the web UI: if someone is generating a
    # video in the browser at the same time, we simply wait for that lock instead of racing it.
    while not jobs.gate.acquire(timeout=5):
        pass
    jobs.run(job, 'script')
    return job


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kind', choices=list(jobs.KINDS), default='make-money')
    p.add_argument('--days', type=int, default=365)
    p.add_argument('--start-date', type=date.fromisoformat, default=date.today())
    p.add_argument('--voice', choices=['ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural'], default='ta-IN-PallaviNeural')
    p.add_argument('--owner', default=None)
    p.add_argument('--delete-existing', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    owner = args.owner or detect_owner()
    dates = [args.start_date + timedelta(days=i) for i in range(args.days)]
    already_done = existing_dates(owner, args.kind)
    would_delete = sum(1 for _ in already_done) if args.delete_existing else 0

    print(f'Owner: {owner}')
    print(f'Kind: {args.kind}')
    print(f'Date range: {dates[0]} .. {dates[-1]} ({len(dates)} days)')
    print(f'Existing completed {args.kind} jobs for this owner: {len(already_done)}'
          + (' (will be deleted first)' if args.delete_existing else ' (dates already done will be skipped)'))
    if args.dry_run:
        print('Dry run only -- no changes made.')
        return

    if args.delete_existing:
        removed = delete_all(owner, args.kind)
        print(f'Deleted {removed} existing {args.kind} job(s).')
        already_done = {}

    ok, failed = 0, []
    started = time.time()
    for i, day in enumerate(dates, 1):
        if day.isoformat() in already_done:
            print(f'[{i}/{len(dates)}] {day} -- already complete, skipping')
            ok += 1
            continue
        print(f'[{i}/{len(dates)}] {day} -- generating...', flush=True)
        try:
            job = run_one(owner, day, args.voice, args.kind)
        except Exception as exc:  # keep going even if one day fails
            print(f'  FAILED (exception): {exc}')
            failed.append(day.isoformat())
            continue
        if job['status'] == 'complete':
            ok += 1
            print(f'  done ({job.get("duration", "?")}s)')
        else:
            failed.append(day.isoformat())
            print(f'  FAILED: {job.get("message")}')

    elapsed = time.time() - started
    print(f'\nFinished: {ok} succeeded, {len(failed)} failed, in {elapsed/60:.1f} minutes.')
    if failed:
        print('Failed dates (re-run this script to retry -- already-completed dates are skipped):')
        for d in failed:
            print(' ', d)


if __name__ == '__main__':
    main()
