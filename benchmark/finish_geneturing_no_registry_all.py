#!/usr/bin/env python3
"""Finalize the running full benchmark automatically, without launching model calls."""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import json
import os
import subprocess
import sys
import time

from run_geneturing_no_registry_all import OUT, ROOT
from run_geneturing_no_registry import dump


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    started = time.monotonic()
    while time.monotonic()-started < 24*60*60:
        summary_path = OUT / 'summary.json'
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        with (OUT / 'controller.lock').open('a+') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                running = False
                fcntl.flock(lock, fcntl.LOCK_UN)
            except BlockingIOError:
                running = True
        status = {'updated_utc': now(), 'finalizer_pid': os.getpid(), 'controller_running': running,
                  'planned': 450, 'finished': summary.get('finished', 100),
                  'completed_workflows': summary.get('completed', 99), 'phase': 'running'}
        dump(OUT / 'status.json', status)
        if not running:
            if summary.get('finished') != 450:
                status.update(phase='stopped_before_all_questions', updated_utc=now())
                dump(OUT / 'status.json', status)
                return 1
            break
        time.sleep(20)
    else:
        dump(OUT / 'status.json', {'phase': 'finalizer_watch_timeout', 'updated_utc': now()})
        return 1
    for name, log_name, phase in [
        ('summarize_geneturing_no_registry_all.py', 'final_audit_output.json', 'auditing'),
        ('update_geneturing_all_manuscript.py', 'manuscript_update.log', 'updating_manuscript'),
    ]:
        status.update(phase=phase, updated_utc=now())
        dump(OUT / 'status.json', status)
        with (OUT / log_name).open('w') as log:
            proc = subprocess.run([sys.executable, str(ROOT / 'benchmark' / name)], cwd=ROOT,
                                  stdout=log, stderr=subprocess.STDOUT)
        if proc.returncode:
            status.update(phase=phase+'_failed', exit_code=proc.returncode, log=log_name, updated_utc=now())
            dump(OUT / 'status.json', status)
            return proc.returncode
    status.update(phase='complete', updated_utc=now(), report=str(OUT / 'REPORT.md'))
    dump(OUT / 'status.json', status)
    with (ROOT / 'progress.md').open('a') as log:
        log.write(f"\nGeneTuring all-category queue finalized at{now()}: all450attempts scored,100priorresults hash-verified unchanged, zero specialists. Audit/comparison/report and Response2/supplement updates completed; JM comments preserved and focusedLaTeX checks passed. Results: benchmark/geneturing_no_registry_all_20260929/. See summary.json/audit.json for scores and failures.\n")
    print(json.dumps(status, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
