#!/usr/bin/env python3
"""Complete both GeneTuring categories using the unchanged no-registry worker."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

import run_geneturing_no_registry as baseline
from run_genegpt_paired_pilot import _is_fewshot

PRIOR = baseline.DEFAULT_OUT
DEFAULT_OUT = baseline.REPO / 'benchmark/geneturing_no_registry_full_20260929'


def prepare(out: Path) -> dict:
    prior = json.loads((PRIOR / 'manifest.json').read_text())
    data = json.loads(baseline.SOURCE.read_text())
    assert baseline.sha(baseline.SOURCE) == prior['source_sha256']
    # Verify every retained role prompt/model/graph snapshot, beyond the worker's
    # original minimal source-hash list, before making new requests.
    hashes = dict(prior['source_hashes'])
    for saved in (PRIOR / 'source_snapshot').rglob('*'):
        if not saved.is_file() or saved.name == 'hashes.json':
            continue
        rel = str(saved.relative_to(PRIOR / 'source_snapshot'))
        assert baseline.sha(baseline.REPO / rel) == baseline.sha(saved), rel
        hashes[rel] = baseline.sha(saved)
    hashes[str(Path(__file__).relative_to(baseline.REPO))] = baseline.sha(Path(__file__))
    for rel, expected in hashes.items():
        assert baseline.sha(baseline.REPO / rel) == expected, rel

    questions = list(prior['questions'])
    seen = {(q['task'], q['question']) for q in questions}
    for task in baseline.TASKS:
        for question in sorted(data[task]):
            if (task, question) not in seen:
                questions.append({'id': f'q{len(questions)+1:03d}',
                                  'task': task, 'question': question})
                seen.add((task, question))
    assert len(questions) == len(seen) == 100
    for task in baseline.TASKS:
        assert {q['question'] for q in questions if q['task'] == task} == set(data[task])
        assert len(data[task]) == 50
    old_gold = json.loads((PRIOR / 'evaluation/gold.json').read_text())
    reuse = {}
    for q in prior['questions']:
        result_path = PRIOR / 'runs' / q['id'] / 'result.json'
        result = json.loads(result_path.read_text())
        assert result['status'] == 'ok' and result['question'] == q['question']
        assert old_gold[q['id']] == data[q['task']][q['question']]
        reuse[q['id']] = {'path': str(result_path), 'sha256': baseline.sha(result_path)}
    manifest = {**prior,
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'sampling_seed': None,
                'sampling': 'All 50 questions per category; original 25/category retained without rerunning.',
                'demonstration_exclusions': {task: [] for task in baseline.TASKS},
                'demonstration_question_ids': [q['id'] for q in questions if _is_fewshot(q['question'])],
                'questions': questions, 'source_hashes': hashes,
                'prior_manifest': str(PRIOR / 'manifest.json'),
                'prior_manifest_sha256': baseline.sha(PRIOR / 'manifest.json'),
                'reused_results': reuse,
                'new_question_ids': [q['id'] for q in questions if q['id'] not in reuse]}
    if (out / 'manifest.json').exists():
        saved = json.loads((out / 'manifest.json').read_text())
        assert {k: v for k, v in saved.items() if k != 'created_utc'} == {
            k: v for k, v in manifest.items() if k != 'created_utc'}
        return saved
    baseline.dump(out / 'manifest.json', manifest)
    baseline.dump(out / 'evaluation/gold.json',
                  {q['id']: data[q['task']][q['question']] for q in questions})
    for q in questions:
        baseline.dump(out / 'questions' / (q['id'] + '.json'), q)
        if q['id'] in reuse:
            destination = out / 'runs' / q['id']
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(PRIOR / 'runs' / q['id'], target_is_directory=True)
    for rel in hashes:
        destination = out / 'source_snapshot' / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline.REPO / rel, destination)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--summarize-only', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    manifest = prepare(out)
    if args.prepare_only:
        print(json.dumps({'questions': len(manifest['questions']),
                          'reused': len(manifest['reused_results']),
                          'new': len(manifest['new_question_ids']),
                          'demonstrations': manifest['demonstration_question_ids']}))
        return
    if not args.summarize_only:
        started = time.perf_counter()
        pending = [q for q in manifest['questions']
                   if not (out / 'runs' / q['id'] / 'result.json').exists()]
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            jobs = [executor.submit(baseline.run_case, out, q) for q in pending]
            for job in as_completed(jobs):
                key = job.result()
                summary = baseline.summarize(out, manifest)
                print(json.dumps({'finished_id': key, 'finished': summary['finished'],
                                  'completed': summary['completed'],
                                  'elapsed_s': round(time.perf_counter()-started, 1)}), flush=True)
    print(json.dumps(baseline.summarize(out, manifest), indent=2), flush=True)


if __name__ == '__main__':
    main()
