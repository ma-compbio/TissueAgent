#!/usr/bin/env python3
"""Run the seven remaining GeneTuring categories, retaining the original 100 attempts."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import shutil
from statistics import mean
import subprocess
import sys
import time

import run_geneturing_no_registry as baseline
from run_genegpt_paired_pilot import _is_fewshot, _score

ROOT = baseline.REPO
PRIOR = ROOT / 'benchmark/geneturing_no_registry_full_20260929'
OUT = ROOT / 'benchmark/geneturing_no_registry_all_20260929'
WORKER = ROOT / 'benchmark/run_geneturing_no_registry_all_worker.py'
TASKS = tuple(json.loads(baseline.SOURCE.read_text()))
UNKNOWN = {'', 'UNKNOWN', 'N/A', 'NA'}


def prepare(out: Path) -> dict:
    prior = json.loads((PRIOR / 'manifest.json').read_text())
    data = json.loads(baseline.SOURCE.read_text())
    assert baseline.sha(baseline.SOURCE) == prior['source_sha256']
    hashes = dict(prior['source_hashes'])
    for rel, expected in hashes.items():
        assert baseline.sha(ROOT / rel) == expected, rel
    for path in (Path(__file__), WORKER):
        hashes[str(path.relative_to(ROOT))] = baseline.sha(path)
    questions = list(prior['questions'])
    seen = {(q['task'], q['question']) for q in questions}
    for task in TASKS:
        for question in sorted(data[task]):
            if (task, question) in seen:
                continue
            questions.append({'id': f'q{len(questions)+1:03d}', 'task': task, 'question': question})
            seen.add((task, question))
    assert len(questions) == len(seen) == 450
    assert all(len(data[t]) == 50 for t in TASKS)
    assert seen == {(t, q) for t in TASKS for q in data[t]}
    old_gold = json.loads((PRIOR / 'evaluation/gold.json').read_text())
    reuse = {}
    for q in prior['questions']:
        path = PRIOR / 'runs' / q['id'] / 'result.json'
        r = json.loads(path.read_text())
        assert r['question'] == q['question'] and old_gold[q['id']] == data[q['task']][q['question']]
        reuse[q['id']] = {'path': str(path), 'sha256': baseline.sha(path), 'status': r['status']}
    manifest = {**prior, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'sampling': 'All 450 questions across nine categories; 100 prior attempts retained unchanged.',
                'questions': questions, 'source_hashes': hashes, 'reused_results': reuse,
                'prior_manifest': str(PRIOR / 'manifest.json'),
                'prior_manifest_sha256': baseline.sha(PRIOR / 'manifest.json'),
                'new_question_ids': [q['id'] for q in questions if q['id'] not in reuse],
                'demonstration_exclusions': {t: [] for t in TASKS},
                'demonstration_question_ids': [q['id'] for q in questions if _is_fewshot(q['question'])],
                'protocol_amendment': 'For the seven new categories only, expand output-format instructions and submit_answer documentation. UNKNOWN denotes abstention, distinct from a supported No for protein-coding questions. Models, role graph, tools, limits and original scorer unchanged.',
                'worker_diff': 'worker_format_changes.diff',
                'scheduling': 'Four isolated workers; new questions round-robin across categories; shared NCBI minimum request interval 0.4 seconds.',
                'scoring': {t: ('reference-gene recall' if t == 'Gene disease association' else
                               'exact coordinates=1, correct chromosome=0.5, otherwise=0' if t == 'Human genome DNA aligment' else
                               'existing category-specific normalization and exact match') for t in TASKS},
                'absent_answer_scoring': 'Absent or explicit UNKNOWN/N/A/NA answers score zero. Supported protein-coding No answers still map to the upstream negative class; abstention never earns negative credit.'}
    if (out / 'manifest.json').exists():
        saved = json.loads((out / 'manifest.json').read_text())
        assert {k: v for k, v in saved.items() if k != 'created_utc'} == {
            k: v for k, v in manifest.items() if k != 'created_utc'}
        return saved
    baseline.dump(out / 'manifest.json', manifest)
    baseline.dump(out / 'evaluation/gold.json', {q['id']: data[q['task']][q['question']] for q in questions})
    for q in questions:
        baseline.dump(out / 'questions' / (q['id'] + '.json'), q)
        if q['id'] in reuse:
            destination = out / 'runs' / q['id']
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(PRIOR / 'runs' / q['id'], target_is_directory=True)
    for rel in hashes:
        target = out / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    return manifest


def score_answer(row: dict, gold, task: str):
    answer = str(row.get('answer') or '').strip()
    raw = str(row.get('raw_completion') or '').strip()
    if answer.upper() in UNKNOWN or not raw:
        return None, 0.0
    # NA is an upstream negative label for protein-coding; the new worker asks
    # for Yes/No and UNKNOWN, so a missing answer never earns negative credit.
    return _score(raw, gold, task)


def summarize(out: Path, manifest: dict) -> dict:
    gold = json.loads((out / 'evaluation/gold.json').read_text())
    rows = []
    for q in manifest['questions']:
        path = out / 'runs' / q['id'] / 'result.json'
        if not path.exists():
            continue
        row = json.loads(path.read_text())
        assert (row['id'], row['task'], row['question']) == (q['id'], q['task'], q['question'])
        pred, score = score_answer(row, gold[q['id']], q['task'])
        row.update(gold=gold[q['id']], prediction=pred, benchmark_score=score)
        if q['task'] == 'Gene disease association':
            ps = set(pred) if isinstance(pred, list) else set()
            gs = set(gold[q['id']].split(', '))
            p = len(ps & gs)/len(ps) if ps else 0.0
            r = len(ps & gs)/len(gs)
            row.update(set_precision=p, set_recall=r, set_f1=2*p*r/(p+r) if p+r else 0.0)
        rows.append(row)
    summary = {'planned': 450, 'finished': len(rows), 'completed': sum(r['status'] == 'ok' for r in rows),
               'specialist_invocations': sum(r.get('specialist_invocations', 0) for r in rows),
               'mean_benchmark_score': mean(r['benchmark_score'] for r in rows) if rows else None,
               'input_tokens': sum(u['input_tokens'] for r in rows for u in r.get('usage', {}).get('agents', {}).values()),
               'output_tokens': sum(u['output_tokens'] for r in rows for u in r.get('usage', {}).get('agents', {}).values()),
               'total_run_seconds': sum(r.get('elapsed_s', 0) for r in rows), 'per_task': {}}
    for task in TASKS:
        group = [r for r in rows if r['task'] == task]
        summary['per_task'][task] = {'n': len(group), 'completed': sum(r['status'] == 'ok' for r in group),
                                     'mean_benchmark_score': mean(r['benchmark_score'] for r in group) if group else None,
                                     'mean_seconds': mean(r.get('elapsed_s', 0) for r in group) if group else None}
        if task == 'Gene disease association' and group:
            summary['per_task'][task].update({k: mean(r[k] for r in group) for k in ('set_precision', 'set_recall', 'set_f1')})
    baseline.dump(out / 'scored_records.json', rows)
    baseline.dump(out / 'summary.json', summary)
    return summary


def run_case(out: Path, q: dict):
    case = out / 'runs' / q['id']
    case.mkdir(parents=True, exist_ok=True)
    if (case / 'result.json').exists():
        return q['id']
    started = time.perf_counter()
    with (case / 'worker.log').open('w') as log:
        try:
            proc = subprocess.run([sys.executable, str(WORKER), '--worker', str(out / 'questions' / (q['id']+'.json')),
                                   '--case', str(case), '--rate-file', str(out / 'ncbi_rate.txt')],
                                  cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=baseline.TIMEOUT)
            error = f'worker exited {proc.returncode}' if proc.returncode else 'worker returned no artifact'
        except subprocess.TimeoutExpired:
            error = 'worker timeout'
        if not (case / 'result.json').exists():
            baseline.dump(case / 'result.json', {**q, 'status': 'incomplete', 'error': error, 'answer': None,
                                                'raw_completion': '', 'elapsed_s': time.perf_counter()-started,
                                                'specialist_invocations': 0})
    return q['id']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--summarize-only', action='store_true')
    args = parser.parse_args()
    manifest = prepare(OUT)
    if args.prepare_only:
        print(json.dumps({'planned': 450, 'reused': 100, 'new': 350,
                          'demonstrations': manifest['demonstration_question_ids']}))
        return
    if args.summarize_only:
        print(json.dumps(summarize(OUT, manifest), indent=2))
        return
    with (OUT / 'controller.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = {task: [q for q in manifest['questions'] if q['task'] == task and
                         not (OUT / 'runs' / q['id'] / 'result.json').exists()] for task in TASKS}
        ordered = [pending[t][i] for i in range(50) for t in TASKS if i < len(pending[t])]
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as executor:
            jobs = [executor.submit(run_case, OUT, q) for q in ordered]
            for job in as_completed(jobs):
                key = job.result()
                summary = summarize(OUT, manifest)
                print(json.dumps({'finished_id': key, 'finished': summary['finished'], 'completed': summary['completed'],
                                  'elapsed_s': round(time.perf_counter()-started, 1)}), flush=True)
        print(json.dumps(summarize(OUT, manifest), indent=2), flush=True)


if __name__ == '__main__':
    main()
