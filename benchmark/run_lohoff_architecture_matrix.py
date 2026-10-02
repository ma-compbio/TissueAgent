#!/usr/bin/env python3
"""Concurrent, isolated Lohoff 2a–2e architecture benchmark; seeds 0/1/2."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
PANELS = ('2a', '2b', '2c', '2d', '2e')
SEEDS = (0, 1, 2)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_jobs(arms):
    jobs = [dict(id=f'{panel}_seed{seed}_{arm}', panel=panel, seed=seed, arm=arm,
                 batch=f'{panel}_seed{seed}')
            for panel in PANELS for seed in SEEDS for arm in arms]
    random.Random(0).shuffle(jobs)
    # The explicitly requested single-agent repeat starts in the first wave.
    first = next(j for j in jobs if j['id'] == '2e_seed0_single_react_no_skills')
    return [first, *[j for j in jobs if j != first]]


def panel_prompt(panel, seed, original):
    dataset = 'dataset_lohoff_et_al_seqfish.h5ad'
    reference = f'reference_lohoff-{panel}.png'
    prompt = original.replace('Fig2b.jpg', reference)
    prompt = prompt.replace(dataset, 'library/datasets/' + dataset)
    prompt = prompt.replace(reference, 'project/uploads/' + reference)
    methods = f'instructions_lohoff-{panel}.md'
    prompt = prompt.replace(methods, 'project/uploads/' + methods)
    if panel == '2d':
        prompt += (f' The dataset is library/datasets/{dataset}. '
                   f'The reference is project/uploads/{reference}.')
    return prompt + (
        ' Save the final reproduced figure as project/outputs/figures/final_figure.png, '
        'its plotted numerical data as project/outputs/tables/plotted_data.csv, and '
        f'the analysis code and a report under project/outputs. Use random seed {seed} '
        'for stochastic analysis operations. Work only with supplied inputs and files '
        'created in this workspace; do not retrieve prior reproductions. Generate the '
        'figure from analysis of the dataset, never by copying or transforming the reference pixels.'
    )


def prepare(out, previous, concurrency):
    if out.exists():
        raise FileExistsError(out)
    old = json.loads((previous / 'manifest.json').read_text())
    pilot = load_module(previous / 'source/benchmark/run_lohoff_architecture_pilot.py', 'old_pilot')
    for folder, key in [('source', 'source_hashes'), ('inputs', 'input_hashes')]:
        for rel, digest in old[key].items():
            if pilot.sha(previous / folder / rel) != digest:
                raise RuntimeError(f'Previous frozen file changed: {folder}/{rel}')
    out.mkdir(parents=True)
    shutil.copytree(previous / 'source', out / 'source',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('run_lohoff_architecture_pilot.py', 'run_lohoff_architecture_matrix.py',
                 'reevaluate_lohoff_llm_judge.py'):
        shutil.copy2(REPO / 'benchmark' / name, out / 'source/benchmark' / name)
    pilot = load_module(out / 'source/benchmark/run_lohoff_architecture_pilot.py', 'matrix_pilot')
    rubric = load_module(out / 'source/benchmark/reevaluate_lohoff_llm_judge.py', 'matrix_rubric')
    jobs = make_jobs(pilot.ARMS)
    (out / 'rubric.txt').write_text(rubric.RUBRIC + '\n')
    prompt_sources = {}
    for panel in PANELS:
        archived = REPO / f'demo/outputs/figure_recreation_lohoff-{panel}/run_manifest.json'
        original = json.loads(archived.read_text())['prompt']
        prompt_sources[panel] = dict(path=str(archived), sha256=pilot.sha(archived),
                                     original_prompt=original)
        inp = out / 'inputs' / panel
        inp.mkdir(parents=True)
        names = ['dataset_lohoff_et_al_seqfish.h5ad', f'reference_lohoff-{panel}.png']
        if panel in ('2d', '2e'):
            names.append(f'instructions_lohoff-{panel}.md')
        for name in names:
            shutil.copy2(REPO / 'demo/data' / name, inp / name)
        for seed in SEEDS:
            batch = out / 'jobs' / f'{panel}_seed{seed}'
            batch.mkdir(parents=True)
            (batch / 'source').symlink_to(out / 'source', target_is_directory=True)
            (batch / 'inputs').symlink_to(inp, target_is_directory=True)
            record = dict(panel=panel, seed=seed, arms=list(pilot.ARMS),
                          repository_root=str(REPO), model=pilot.MODEL,
                          prompt=panel_prompt(panel, seed, original),
                          input_hashes={name: pilot.sha(inp / name) for name in names})
            pilot.dump(batch / 'manifest.json', record)
    source_hashes = {str(p.relative_to(out / 'source')): pilot.sha(p)
                     for p in (out / 'source').rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    protected = {str(p.relative_to(out)): pilot.sha(p)
                 for p in (out / 'inputs').rglob('*') if p.is_file()}
    protected.update({str(p.relative_to(out)): pilot.sha(p)
                      for p in (out / 'jobs').glob('*/manifest.json')})
    manifest = dict(created=pilot.now(), panels=list(PANELS), seeds=list(SEEDS),
        arms=list(pilot.ARMS), total_jobs=len(jobs), concurrency=concurrency,
        evaluation_concurrency=2, model=pilot.MODEL, reasoning_effort='high',
        judge=pilot.JUDGE, judge_replicates=1, rubric='rubric.txt',
        previous_pilot=str(previous), repository_root=str(REPO), all_attempts_fresh=True,
        limits=pilot.LIMITS, custom_generation_budgets=None,
        source_hashes=source_hashes, protected_hashes=protected,
        prompt_sources=prompt_sources, jobs=jobs,
        output_selection='Exact final_figure.png; all attempts retained, no best-of selection',
        failure_scoring='Missing/invalid/reference-copy figure: 0/5 on all criteria, image metrics NA; judge API errors NA',
        aggregation='Equal-weight five-criterion mean; panel mean/sample SD over 3 seeds; overall mean and sample SD of 3 five-panel seed means',
        limitations=['Panel 2a lacks atlas source population; original task forbids inventing it',
                     'Same Python-only backend, no nested delegation, and native graph/retry bounds as the pilot',
                     'Parallel runtimes include resource contention and are not directly comparable to serial pilot runtimes',
                     'Image-only judging cannot verify numerical correctness; one judge response per produced figure'])
    pilot.dump(out / 'manifest.json', manifest)
    pilot.dump(out / 'status.json', dict(status='prepared', total=len(jobs), completed=0,
                                        generation_completed=0, active=[], updated=pilot.now()))
    (out / 'README.md').write_text(
        '# Lohoff architecture benchmark: panels 2a–2e, seeds 0/1/2\n\n'
        f'120 fresh attempts: eight conditions, five panels, three seeds. {concurrency} '
        'generation jobs run concurrently in separate processes and workspaces; two independent '
        'evaluation workers score finished figures while generation continues. The single-agent '
        'panel-2e seed-0 repeat is in the first wave.\n\n'
        'Generation uses GPT-5.1/high and the matched request/analysis seed. No additional token, '
        'output-token, call-count or overall runtime cap is imposed. Native graph/retry and tool '
        'timeout settings remain. Frozen application and registry code come from the completed '
        'pilot; harness changes only parameterize panel/seed/isolation and parallel scheduling.\n\n'
        'Each job receives only its panel inputs, reference, and methods (where supplied), with '
        'the same eight independent ablations as the pilot. Inputs are copied into a fresh workspace. '
        'The reference is an input for visual matching; copying its pixels is forbidden. Panel2a '
        'lacks the atlas population in the supplied data; the original prompt documents that limitation.\n\n'
        'Evaluation: SSIM, pHash similarity, ORB matches, and one blind Claude Sonnet4.5 judgment '
        'using the exact user-provided five-criterion0–5 rubric. Means include zero for missing figures; '
        'image metrics exclude missing images and disclose the denominator. API/scorer failures are NA. '
        'No generation attempt is silently retried or selected for a better score.\n\n'
        'Live progress: status.json. Individual traces: jobs/<panel>_seed<seed>/runs/<condition>/. '
        'Per-job evaluation: evaluation/<anonymous_id>/. Results: results.json; aggregate report: REPORT.md. '
        'The overall SD is across three seed means, each averaging the five panels; per-panel SD is '
        'across three seeds. Parallel runtimes are descriptive and include shared-machine contention.\n')
    print(json.dumps(dict(output=str(out), jobs=len(jobs), concurrency=concurrency)), flush=True)


def verify(out, pilot, manifest):
    for rel, digest in manifest['source_hashes'].items():
        if pilot.sha(out / 'source' / rel) != digest:
            raise RuntimeError('Frozen source changed: ' + rel)
    for rel, digest in manifest['protected_hashes'].items():
        if pilot.sha(out / rel) != digest:
            raise RuntimeError('Frozen task/input changed: ' + rel)


def mean_sd(values):
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                sd=statistics.stdev(values) if len(values) > 1 else None)


def next_phase_jobs(jobs, pending, evaluated, seed_order, arms):
    """Finish the first seed across all panels before dispatching later seeds."""
    if set(seed_order) != set(SEEDS) or len(seed_order) != len(SEEDS):
        raise ValueError('seed_priority must contain each study seed exactly once')
    phase = next((seed for seed in seed_order
                  if any(j['seed'] == seed and j['id'] not in evaluated for j in jobs)), None)
    ready = sorted((j for j in pending if j['seed'] == phase),
                   key=lambda j: (arms.index(j['arm']), PANELS.index(j['panel'])))
    return phase, ready


def existing_job_state(out, job, blind_id, prior_active):
    """Classify preserved work before dispatch; an existing worker is never relaunched."""
    case = out / 'jobs' / job['batch'] / 'runs' / job['arm']
    saved = out / 'evaluation' / blind_id / 'result.json'
    if saved.exists():
        row = json.loads(saved.read_text())
        if row['id'] != job['id'] or not (case / 'result.json').exists():
            raise ValueError('Saved evaluation does not match its generation: ' + job['id'])
        return 'evaluated'
    if (case / 'result.json').exists():
        return 'generated'
    if case.exists() or job['id'] in prior_active:
        return 'active'
    return 'pending'


def aggregate(rows, arms):
    result = {}
    for arm in arms:
        subset = [r for r in rows if r['arm'] == arm]
        per_panel = {}
        for panel in PANELS:
            selected = [r for r in subset if r['panel'] == panel]
            per_panel[panel] = {key: mean_sd([r[key] for r in selected if r.get(key) is not None])
                               for key in ('llm_judge', 'ssim', 'runtime_minutes')}
        seed_means = []
        for seed in SEEDS:
            selected = [r for r in subset if r['seed'] == seed and r.get('llm_judge') is not None]
            if {r['panel'] for r in selected} == set(PANELS):
                seed_means.append(statistics.mean(r['llm_judge'] for r in selected))
        result[arm] = dict(completed=len(subset), figures=sum(r['figure_produced'] for r in subset),
            llm_judge_available=mean_sd([r['llm_judge'] for r in subset if r.get('llm_judge') is not None]),
            llm_judge_seed_means=mean_sd(seed_means), per_panel=per_panel,
            ssim=mean_sd([r['ssim'] for r in subset if r.get('ssim') is not None]),
            runtime_minutes=mean_sd([r['runtime_minutes'] for r in subset]),
            total_generation_tokens=sum(r['total_tokens'] for r in subset))
    return result


def report(out, rows, pilot, rubric):
    rows = sorted(rows, key=lambda r: (r['panel'], r['seed'], pilot.ARMS.index(r['arm'])))
    summary = aggregate(rows, pilot.ARMS)
    pilot.dump(out / 'results.json', rows)
    pilot.dump(out / 'summary.json', summary)
    lines = ['# Lohoff 2a–2e architecture benchmark, seeds 0/1/2', '',
             f'{len(rows)}/120 jobs evaluated. Each condition has 15 planned attempts.', '',
             '| Condition | Evaluated | Figures | LLM mean /5 | SD across seed means | SSIM (available figures) | Mean minutes |',
             '|---|---:|---:|---:|---:|---:|---:|']
    def fmt(value):
        return 'NA' if value is None else f'{value:.3f}'
    for arm, s in summary.items():
        lines.append(f'| {rubric.LABELS[arm]} | {s["completed"]}/15 | {s["figures"]} | '
                     f'{fmt(s["llm_judge_available"]["mean"])} | {fmt(s["llm_judge_seed_means"]["sd"])} | '
                     f'{fmt(s["ssim"]["mean"])} (n={s["ssim"]["n"]}) | {fmt(s["runtime_minutes"]["mean"])} |')
    lines += ['', 'Missing figures receive judge=0. Judge API/scorer errors are NA. Overall SD is '
              'across complete five-panel means for each seed; partial results are provisional. '
              'Runtimes include parallel resource contention. Image judgments do not establish '
              'numerical correctness. Panel2a has a documented missing-atlas limitation.', '',
              '## Per-panel LLM means ± sample SD across seeds', '',
              '| Condition | 2a | 2b | 2c | 2d | 2e |', '|---|---:|---:|---:|---:|---:|']
    for arm, s in summary.items():
        cells = []
        for panel in PANELS:
            stats = s['per_panel'][panel]['llm_judge']
            cells.append(f'{fmt(stats["mean"])} ± {fmt(stats["sd"])} (n={stats["n"]})')
        lines.append('| ' + rubric.LABELS[arm] + ' | ' + ' | '.join(cells) + ' |')
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n')


def controller(out, resume=False, wait_for_lock=False):
    lockfile = (out / 'controller.lock').open('a')
    pilot = load_module(out / 'source/benchmark/run_lohoff_architecture_pilot.py', 'pilot')
    while True:
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if not wait_for_lock:
                raise
            pilot.dump(out / 'replacement_status.json', dict(status='waiting_for_existing_controller',
                pid=os.getpid(), updated=pilot.now()))
            time.sleep(5)
    pilot.dump(out / 'replacement_status.json', dict(status='controller_lock_acquired',
        pid=os.getpid(), updated=pilot.now()))
    rubric = load_module(out / 'source/benchmark/reevaluate_lohoff_llm_judge.py', 'rubric')
    manifest = json.loads((out / 'manifest.json').read_text())
    verify(out, pilot, manifest)
    if resume:
        previous_supervisor = json.loads((out / 'supervisor.json').read_text())
        pilot.dump(out / 'supervisor.json', {**previous_supervisor,
            'pid': os.getpid(), 'script': str(Path(__file__).resolve()),
            'mode': 'resume_with_live_seed_priority', 'previous_pid': previous_supervisor['pid']})
    jobs = manifest['jobs']
    script = out / 'source/benchmark/run_lohoff_architecture_pilot.py'
    old_status = json.loads((out / 'status.json').read_text())
    prior_active = {j['id']: j for j in old_status.get('active', [])}
    if not resume:
        for job in jobs:
            if (out / 'jobs' / job['batch'] / 'runs' / job['arm']).exists():
                raise RuntimeError('Study already started; use resume to preserve existing attempts')
    pilot.credentials()
    active = {}
    mutex = threading.Lock()
    generated = []
    rows = []
    logs = out / 'logs'
    logs.mkdir(exist_ok=True)

    def launch(job, offline=False):
        batch = out / 'jobs' / job['batch']
        cmd = [sys.executable, str(script), 'worker', '--out', str(batch), '--arm', job['arm']]
        if offline:
            cmd.append('--offline')
        env = os.environ.copy()
        env.update(PYTHONHASHSEED=str(job['seed']), OPENBLAS_NUM_THREADS='1',
                   OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMBA_NUM_THREADS='1')
        started = time.monotonic()
        log_path = logs / (job['id'] + ('_preflight' if offline else '') + '.log')
        with log_path.open('w') as log:
            proc = subprocess.Popen(cmd, cwd=manifest['repository_root'],
                                    env=env, stdout=log, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL)
            with mutex:
                active[job['id']] = dict(**job, pid=proc.pid, stage='preflight' if offline else 'generation',
                                        started=pilot.now())
            returncode = proc.wait()  # No added generation time limit.
        with mutex:
            active.pop(job['id'], None)
        case = batch / ('preflight' if offline else 'runs') / job['arm']
        path = case / 'result.json'
        if offline:
            if returncode or not path.exists() or json.loads(path.read_text())['status'] != 'offline_preflight_passed':
                raise RuntimeError(f'Offline preflight failed: {job["id"]}; see {log_path}')
            condition = json.loads((case / 'condition.json').read_text())
            assert condition['seed'] == job['seed'] and condition['panel'] == job['panel']
            return job
        if not path.exists():
            heartbeat = case / 'heartbeat.json'
            counts = json.loads(heartbeat.read_text())['counts'] if heartbeat.exists() else {}
            pilot.dump(path, dict(arm=job['arm'], status='worker_failed', exit_code=returncode,
                                 elapsed_seconds=time.monotonic()-started, counts=counts, finished=pilot.now()))
        return job

    def status(stage, evaluation_pending=0):
        with mutex:
            current = list(active.values())
        pilot.dump(out / 'status.json', dict(status=stage, total=len(jobs),
            generation_completed=len(generated), completed=len(rows), active=current,
            evaluation_pending=evaluation_pending, scheduler_pid=os.getpid(),
            priority_seed=phase_seed, updated=pilot.now()))

    phase_seed = None

    def adopt(job):
        """Observe an already running worker; never launch a duplicate attempt."""
        prior = prior_active.get(job['id'], {})
        with mutex:
            active[job['id']] = dict(**job, pid=prior.get('pid'), stage='generation',
                started=prior.get('started'), adopted=True)
        result = out / 'jobs' / job['batch'] / 'runs' / job['arm'] / 'result.json'
        while not result.exists():
            time.sleep(2)
        with mutex:
            active.pop(job['id'], None)
        return job

    # Eight independent offline controls cover all panels and all three seeds.
    checks = []
    for i, arm in enumerate(pilot.ARMS):
        panel, seed = (('2e', 0) if arm == 'single_react_no_skills' else (PANELS[i % 5], SEEDS[i % 3]))
        checks.append(next(j for j in jobs if (j['panel'], j['seed'], j['arm']) == (panel, seed, arm)))
    # Ensure panel 2b is covered too (single-agent overrides its cyclic slot).
    if not any(j['panel'] == '2b' for j in checks):
        checks.append(next(j for j in jobs if j['panel'] == '2b' and j['seed'] == 0))
    if resume:
        if json.loads((out / 'preflight_summary.json').read_text())['status'] != 'passed':
            raise RuntimeError('Resume requires the existing passed preflights')
    else:
        with ThreadPoolExecutor(max_workers=manifest['concurrency']) as pool:
            pending = {pool.submit(launch, job, True) for job in checks}
            while pending:
                status('preflight')
                done, pending = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
                for future in done:
                    future.result()
        pilot.dump(out / 'preflight_summary.json', dict(status='passed', jobs=checks, completed=pilot.now()))
    blind_jobs = list(jobs)
    random.Random(42).shuffle(blind_jobs)
    blind_ids = {j['id']: f'output_{i+1:03d}' for i, j in enumerate(blind_jobs)}
    expected_blind = {v: k for k, v in blind_ids.items()}
    blind_path = out / 'evaluation/blind_order.json'
    if resume:
        assert json.loads(blind_path.read_text()) == expected_blind
    else:
        pilot.dump(blind_path, expected_blind)

    def evaluate(job):
        import anthropic
        from PIL import Image, ImageChops
        batch = out / 'jobs' / job['batch']
        case = batch / 'runs' / job['arm']
        run = json.loads((case / 'result.json').read_text())
        cfg = json.loads((batch / 'manifest.json').read_text())
        figure = case / 'state/workspace/project/outputs/figures/final_figure.png'
        reference = batch / 'inputs' / f'reference_lohoff-{job["panel"]}.png'
        dest = out / 'evaluation' / blind_ids[job['id']]
        dest.mkdir(exist_ok=resume)
        if (dest / 'result.json').exists():
            existing = json.loads((dest / 'result.json').read_text())
            assert existing['id'] == job['id']
            return existing
        row = dict(**job, generation_status=run['status'], figure_produced=False,
            runtime_minutes=run['elapsed_seconds']/60,
            total_tokens=sum(run['counts'].get(k, 0) for k in ('input_tokens', 'output_tokens')),
            counts=run['counts'], ssim=None, phash_similarity=None, orb_matches=None,
            llm_judge=0, judge_status='missing_figure_penalty',
            criterion_scores={key: 0 for key in rubric.CRITERIA})
        try:
            with Image.open(figure) as im:
                im.verify()
            with Image.open(figure) as a, Image.open(reference) as b:
                if a.size == b.size and ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is None:
                    raise ValueError('Output is a pixel-identical copy of the reference')
            row['figure_produced'] = True
            row['figure_sha256'] = pilot.sha(figure)
        except (OSError, ValueError) as exc:
            row['figure_issue'] = str(exc)
            pilot.dump(dest / 'result.json', row)
            return row
        try:
            if (dest / 'metrics.json').exists():
                metrics = json.loads((dest / 'metrics.json').read_text())
            else:
                proc = subprocess.run([sys.executable, str(out / 'source/knowledge/skills/figure-reproduce/scripts/compare_figures.py'),
                    str(reference), str(figure), '--json', '--out', str(dest / 'comparison.png')],
                    capture_output=True, text=True, timeout=180)
                (dest / 'scorer_stdout.txt').write_text(proc.stdout)
                (dest / 'scorer_stderr.txt').write_text(proc.stderr)
                proc.check_returncode()
                metrics = json.loads(proc.stdout)
                pilot.dump(dest / 'metrics.json', metrics)
            row.update(ssim=metrics['ssim'], phash_similarity=1-metrics['phash_hamming']/64,
                       orb_matches=metrics['orb_good_matches'])
        except Exception as exc:
            row['metric_error'] = f'{type(exc).__name__}: {exc}'
        methods = batch / 'inputs' / f'instructions_lohoff-{job["panel"]}.md'
        prompt = ('Image 1 is the published reference; image 2 is the generated figure. '
            'The generating system identity is hidden. Do not infer it.\n\n' + rubric.RUBRIC +
            '\n\nAssign one integer score to each criterion independently. '
            'Base rationales on visible evidence and explicitly note uncertainty. '
            'Image-only judgments cannot verify the underlying calculations. '
            'Return JSON only, with exactly these score and rationale keys: ' + ', '.join(rubric.CRITERIA) +
            '. Schema: {"scores":{criterion:integer},"rationale":{criterion:string},"limitations":string}.'
            '\n\nTask:\n' + cfg['prompt'] + '\nMethods:\n' + (methods.read_text() if methods.exists() else 'No additional methods supplied.'))
        (dest / 'judge_prompt.txt').write_text(prompt + '\n')
        def image_block(path):
            return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                    'data': base64.b64encode(path.read_bytes()).decode()}}
        try:
            if (dest / 'judge_raw.json').exists():
                raw = json.loads((dest / 'judge_raw.json').read_text())
            else:
                with anthropic.Anthropic(timeout=180, max_retries=2) as client:
                    response = client.messages.create(model=manifest['judge'], max_tokens=2000,
                        extra_body={'temperature': 0}, messages=[{'role': 'user', 'content': [
                            {'type': 'text', 'text': prompt}, image_block(reference), image_block(figure)]}])
                raw = response.model_dump()
                pilot.dump(dest / 'judge_raw.json', raw)
            judged, mean = rubric.parse_judgment(raw)
            pilot.dump(dest / 'judge.json', judged)
            row.update(llm_judge=mean, criterion_scores=judged['scores'], judge_status='scored',
                       judge_usage=raw['usage'])
        except Exception as exc:
            row.update(llm_judge=None, criterion_scores=None, judge_status='failed',
                       judge_error=f'{type(exc).__name__}: {exc}')
        pilot.dump(dest / 'result.json', row)
        return row

    with ThreadPoolExecutor(max_workers=manifest['concurrency']) as generation_pool, \
            ThreadPoolExecutor(max_workers=manifest['evaluation_concurrency']) as evaluation_pool:
        gen = {}
        evaluations = {}
        pending_jobs = []
        adopting = []
        for job in jobs:
            saved = out / 'evaluation' / blind_ids[job['id']] / 'result.json'
            existing = existing_job_state(out, job, blind_ids[job['id']], prior_active)
            if existing == 'evaluated':
                row = json.loads(saved.read_text())
                rows.append(row)
                generated.append(job['id'])
            elif existing == 'generated':
                generated.append(job['id'])
                evaluations[evaluation_pool.submit(evaluate, job)] = job
            elif existing == 'active':
                adopting.append(job['id'])
                gen[generation_pool.submit(adopt, job)] = job
            else:
                pending_jobs.append(job)
        if len(adopting) > manifest['concurrency']:
            raise RuntimeError('More existing workers than configured concurrency; inspect before resuming')
        pilot.dump(out / 'handover_audit.json', dict(time=pilot.now(), scheduler_pid=os.getpid(),
            reused_evaluations=len(rows), completed_generation=len(generated),
            adopted_jobs=adopting, pending_jobs=len(pending_jobs)))
        report(out, rows, pilot, rubric)
        while pending_jobs or gen or evaluations:
            control_path = out / 'scheduler_control.json'
            control = json.loads(control_path.read_text()) if control_path.exists() else {}
            seed_order = control.get('seed_priority', [0, 1, 2])
            phase_seed, ready = next_phase_jobs(jobs, pending_jobs,
                                                {r['id'] for r in rows}, seed_order, pilot.ARMS)
            for job in ready[:max(0, manifest['concurrency']-len(gen))]:
                pending_jobs.remove(job)
                gen[generation_pool.submit(launch, job)] = job
            status('running' if gen else 'scoring', len(evaluations))
            if not gen and not evaluations and pending_jobs:
                raise RuntimeError('Pending jobs cannot advance; inspect seed-phase accounting')
            done, _ = wait(set(gen) | set(evaluations), timeout=5, return_when=FIRST_COMPLETED)
            for future in done:
                if future in gen:
                    job = future.result()
                    generated.append(job['id'])
                    gen.pop(future)
                    evaluations[evaluation_pool.submit(evaluate, job)] = job
                else:
                    rows.append(future.result())
                    evaluations.pop(future)
                    report(out, rows, pilot, rubric)
    verify(out, pilot, manifest)
    report(out, rows, pilot, rubric)
    status('complete_with_evaluation_errors' if any(r.get('metric_error') or r['judge_status'] == 'failed' for r in rows) else 'complete')
    pilot.dump(out / 'completion_audit.json', dict(finished=pilot.now(), jobs=len(rows),
        figures=sum(r['figure_produced'] for r in rows), frozen_hashes_verified=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'background', 'resume'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-from', type=Path)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--wait-for-lock', action='store_true',
                        help='Wait for the existing controller to exit, then adopt its active workers')
    args = parser.parse_args()
    out = args.out.resolve()
    if args.action == 'prepare':
        prepare(out, args.source_from.resolve(), args.concurrency)
    else:
        try:
            controller(out, resume=args.action == 'resume', wait_for_lock=args.wait_for_lock)
        except BaseException as exc:
            (out / 'controller_error.txt').write_text(traceback.format_exc())
            pilot = load_module(out / 'source/benchmark/run_lohoff_architecture_pilot.py', 'failed_pilot')
            pilot.dump(out / 'status.json', dict(status='controller_failed', error=f'{type(exc).__name__}: {exc}', updated=pilot.now()))
            raise


if __name__ == '__main__':
    main()
