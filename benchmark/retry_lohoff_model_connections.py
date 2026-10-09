#!/usr/bin/env python3
"""Rerun connection-interrupted jobs without modifying the frozen study.

One additional generation worker runs alongside the original batch. Each
selected job gets exactly one fresh attempt; no artifact-quality selection.
Original failures remain intact. Scoring is deferred to the study finalizer.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

import psutil


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connection_failure(result):
    return result.get('status') == 'failed' and str(result.get('error', '')).startswith(
        ('OpenAIConnectionError:', 'APIConnectionError:', 'APITimeoutError:'))


def claude_image_failure(result):
    error = str(result.get('error', ''))
    return (result.get('status') == 'failed'
            and error.startswith('AnthropicInvalidRequestError:')
            and ('image dimensions exceed' in error or 'image exceeds' in error))


def verify_original(parent):
    manifest = json.loads((parent / 'manifest.json').read_text())
    for key, root in [('source_hashes', parent / 'source'),
                      ('input_hashes', parent), ('job_hashes', parent)]:
        for relative, expected in manifest[key].items():
            if sha(root / relative) != expected:
                raise RuntimeError('Frozen study file changed: ' + relative)
    return manifest


def prepare(parent, out, requested, repair_claude_images=False):
    original = verify_original(parent)
    by_id = {job['id']: job for job in original['jobs']}
    if out.exists():
        raise FileExistsError(out)
    selected = []
    for ident in requested:
        job = by_id[ident]
        result_path = parent / 'jobs' / ident / 'runs/full/result.json'
        result = json.loads(result_path.read_text())
        eligible = claude_image_failure(result) if repair_claude_images else connection_failure(result)
        if not eligible or (repair_claude_images and job['model'] != 'sonnet45'):
            raise ValueError('Not an eligible recovery failure: ' + ident)
        meta_path = parent / 'jobs' / ident / 'process.json'
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if alive(meta):
                raise RuntimeError('Original worker is still alive: ' + ident)
        selected.append({**job, 'original_result': str(result_path),
                         'original_result_sha256': sha(result_path),
                         'original_manifest_sha256': sha(parent / 'jobs' / ident / 'manifest.json')})
    if not selected or len({job['id'] for job in selected}) != len(selected):
        raise ValueError('Require distinct connection-failed jobs')
    out.mkdir(parents=True)
    (out / 'logs').mkdir()
    if repair_claude_images:
        shutil.copytree(parent / 'source', out / 'source',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('anthropic_images.py', 'run_lohoff_claude_image_worker.py'):
            shutil.copy2(Path(__file__).resolve().with_name(name),
                         out / 'source/benchmark' / name)
    else:
        (out / 'source').symlink_to(parent / 'source', target_is_directory=True)
    (out / 'inputs').symlink_to(parent / 'inputs', target_is_directory=True)
    for job in selected:
        batch = out / 'jobs' / job['id']
        batch.mkdir(parents=True)
        (batch / 'source').symlink_to(out / 'source', target_is_directory=True)
        (batch / 'inputs').symlink_to(parent / 'inputs' / job['panel'], target_is_directory=True)
        shutil.copy2(parent / 'jobs' / job['id'] / 'manifest.json', batch / 'manifest.json')
    manifest = dict(created=now(), parent=str(parent),
        parent_manifest_sha256=sha(parent / 'manifest.json'), jobs=selected,
        extra_concurrency=1, reruns_per_job=1, reason='User-authorized connection-failure recovery',
        policy='Fresh rerun with identical frozen code, prompt, inputs, model and analysis seed. '
               'No model-quality selection; preserve all original failures and all retries. '
               'Do not count retry as an additional independent replicate. '
               'A retry still interrupted by connectivity remains unresolved. '
               'External scoring is deferred; the original controller tables do not include retries.')
    if repair_claude_images:
        manifest.update(reason='User-authorized Claude image-limit recovery',
            repair='claude_inline_image_limits',
            worker_script='benchmark/run_lohoff_claude_image_worker.py',
            repair_source_hashes={str(p.relative_to(out / 'source')): sha(p)
                for p in (out / 'source').rglob('*') if p.is_file()},
            policy='One fresh rerun per selected Claude image-limit failure, using the frozen original '
                   'source with only the audited outgoing-image normalization repair. Same prompts, '
                   'inputs, model settings and analysis seeds. Preserve original artifacts; never '
                   'select by quality or count retries as extra replicates. Full-resolution figure '
                   'files are unchanged by transport preprocessing. Scoring is deferred; final '
                   'tables must disclose this provider-adapter repair and use the retry artifacts.')
        changed = [rel for rel, value in manifest['repair_source_hashes'].items()
                   if original['source_hashes'].get(rel) != value]
        if sorted(changed) != ['benchmark/anthropic_images.py',
                               'benchmark/run_lohoff_claude_image_worker.py']:
            raise RuntimeError('Unexpected repair source changes: ' + str(changed))
        manifest['changed_source_files'] = changed
    dump(out / 'retry_manifest.json', manifest)
    dump(out / 'status.json', dict(status='prepared', total=len(selected), finished=0, active=None, updated=now()))
    (out / 'README.md').write_text(
        '# Connection-only recovery\n\nThree user-authorized fresh reruns of connection-interrupted attempts. '
        'Original artifacts and frozen code are unchanged. This queue uses one additional worker '
        'alongside the original controller. All selected jobs are queued together.\n\n'
        'Follow `status.json` and `selection.json`. These retries are separate from the original '
        '75-job status. Before final reporting, use each retry as the designated recovery attempt '
        '(never choose by quality), retain original failure/resource records, and judge the retry '
        'figure rather than its original artifact. Connectivity-interrupted retries remain unresolved. '
        'No external scoring is launched by this recovery controller.\n')
    if repair_claude_images:
        (out / 'README.md').write_text('# Claude image-limit recovery\n\n' + manifest['policy'] +
            '\n\nThe audited overlay adds only benchmark/anthropic_images.py and '
            'benchmark/run_lohoff_claude_image_worker.py; application source is unchanged. '
            'It checks all inline images, including nested tool results and prior conversation turns; '
            'caps dimensions at 8000 px (2000 px for more than 20 images), encoded image bytes at '
            '9 MiB each, and total encoded image bytes at 24 MiB. Uses PNG encoding with proportional '
            'downsizing as needed. Small valid images are unchanged.\n\n'
            'One additional worker runs this queue. Follow status.json and selection.json; '
            'the original controller does not incorporate these retries automatically.\n')


def alive(meta):
    try:
        process = psutil.Process(meta['pid'])
        return (abs(process.create_time() - meta['create_time']) < 1
                and process.is_running() and process.status() != psutil.STATUS_ZOMBIE)
    except psutil.Error:
        return False


def run(out):
    lock = (out / 'controller.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads((out / 'retry_manifest.json').read_text())
    parent = Path(manifest['parent'])
    if sha(parent / 'manifest.json') != manifest['parent_manifest_sha256']:
        raise RuntimeError('Parent manifest changed')
    verify_original(parent)
    for rel, expected in manifest.get('repair_source_hashes', {}).items():
        if sha(out / 'source' / rel) != expected:
            raise RuntimeError('Repair source changed: ' + rel)
    for job in manifest['jobs']:
        if sha(Path(job['original_result'])) != job['original_result_sha256']:
            raise RuntimeError('Original result changed: ' + job['id'])
        if sha(out / 'jobs' / job['id'] / 'manifest.json') != job['original_manifest_sha256']:
            raise RuntimeError('Retry configuration changed: ' + job['id'])
    dump(out / 'supervisor.json', dict(pid=os.getpid(), create_time=psutil.Process().create_time(), started=now()))
    selections = []

    def status(state, active=None):
        dump(out / 'status.json', dict(status=state, total=len(manifest['jobs']),
            finished=len(selections), active=active, updated=now(), judging='deferred'))
        dump(out / 'selection.json', dict(policy=manifest['policy'], attempts=selections, updated=now()))

    script = out / 'source' / manifest.get('worker_script', 'benchmark/run_lohoff_architecture_pilot.py')
    for job in manifest['jobs']:
        batch = out / 'jobs' / job['id']
        case = batch / 'runs/full'
        result_path = case / 'result.json'
        proc = None
        if not result_path.exists():
            if (out / 'STOP.json').exists():
                status('stopped'); return
            meta_path = batch / 'process.json'
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
            elif case.exists():
                raise RuntimeError('Untracked attempt directory: ' + str(case))
            else:
                env = os.environ.copy()
                env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                           MKL_NUM_THREADS='1', PYTHONUNBUFFERED='1')
                with (out / 'logs' / (job['id'] + '.log')).open('w') as log:
                    proc = subprocess.Popen([sys.executable, str(script), 'worker', '--out', str(batch), '--arm', 'full'],
                        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                        env=env, start_new_session=True)
                meta = dict(pid=proc.pid, create_time=psutil.Process(proc.pid).create_time(), started=now())
                dump(meta_path, meta)
            while alive(meta) and not result_path.exists():
                status('running', dict(id=job['id'], pid=meta['pid']))
                time.sleep(5)
            if proc is not None:
                proc.wait()
            if not result_path.exists():
                dump(result_path, dict(status='worker_failed', error='Worker exited without result', finished=now()))
        result = json.loads(result_path.read_text())
        selections.append(dict(id=job['id'], original_result=job['original_result'],
            retry_result=str(result_path), retry_status=result['status'],
            connectivity_resolved=not connection_failure(result) and result['status'] not in {'worker_failed', 'stopped'},
            image_limit_resolved=not claude_image_failure(result) if manifest.get('repair') else None,
            figure_exists=(case / 'state/workspace/project/outputs/figures/final_figure.png').is_file()))
        status('running')
    status('generation_finished_scoring_deferred')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--jobs', nargs='+')
    parser.add_argument('--repair-claude-images', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    if args.action == 'prepare':
        if not args.parent or not args.jobs:
            parser.error('prepare requires --parent and --jobs')
        prepare(args.parent.resolve(), out, args.jobs, args.repair_claude_images)
    elif args.action == 'launch':
        with (out / 'controller.log').open('a') as log:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run', '--out', str(out)],
                stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        print(json.dumps(dict(controller_pid=proc.pid, output=str(out))))
    else:
        try:
            run(out)
        except BaseException as exc:
            dump(out / 'controller_error.json', dict(error=f'{type(exc).__name__}: {exc}', updated=now()))
            raise


if __name__ == '__main__':
    main()
