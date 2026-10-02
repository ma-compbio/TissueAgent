"""Matched-design, task, and missing-output aggregation checks for the paid matrix."""
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'benchmark' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


matrix = load('run_lohoff_architecture_matrix')
pilot = load('run_lohoff_architecture_pilot')


def test_120_jobs_are_unique_and_paired_with_single_agent_repeat_first():
    jobs = matrix.make_jobs(pilot.ARMS)
    assert len(jobs) == len({j['id'] for j in jobs}) == 120
    assert jobs[0]['id'] == '2e_seed0_single_react_no_skills'
    assert Counter(j['arm'] for j in jobs) == {arm: 15 for arm in pilot.ARMS}
    assert set(Counter((j['panel'], j['seed']) for j in jobs).values()) == {8}
    assert {(j['panel'], j['seed']) for j in jobs} == {
        (panel, seed) for panel in matrix.PANELS for seed in (0, 1, 2)}


@pytest.mark.parametrize('panel', matrix.PANELS)
def test_tasks_resolve_to_their_own_staged_panel_and_seed(panel):
    archive = ROOT / f'demo/outputs/figure_recreation_lohoff-{panel}/run_manifest.json'
    original = json.loads(archive.read_text())['prompt']
    prompt = matrix.panel_prompt(panel, 2, original)
    assert 'library/datasets/dataset_lohoff_et_al_seqfish.h5ad' in prompt
    assert f'project/uploads/reference_lohoff-{panel}.png' in prompt
    assert 'Use random seed 2 for stochastic analysis operations.' in prompt
    assert 'Fig2b.jpg' not in prompt
    if panel in ('2d', '2e'):
        assert f'project/uploads/instructions_lohoff-{panel}.md' in prompt


def test_panel_e_seed_zero_keeps_the_exact_validated_pilot_task():
    original = json.loads((ROOT / 'demo/outputs/figure_recreation_lohoff-2e/run_manifest.json').read_text())['prompt']
    assert matrix.panel_prompt('2e', 0, original) == pilot.PROMPT


def test_missing_figure_zero_contributes_to_mean_but_not_ssim():
    rows = [dict(arm='full', panel=panel, seed=seed, figure_produced=True,
                 llm_judge=value, ssim=0.55, runtime_minutes=10, total_tokens=100)
            for panel in matrix.PANELS for seed, value in enumerate((1, 3, 5))]
    rows[0].update(figure_produced=False, llm_judge=0, ssim=None)
    result = matrix.aggregate(rows, ['full'])['full']
    assert result['figures'] == result['ssim']['n'] == 14
    assert result['ssim']['mean'] == pytest.approx(0.55)
    assert result['llm_judge_available']['mean'] == pytest.approx(44 / 15)
    assert result['llm_judge_seed_means']['mean'] == pytest.approx(44 / 15)
    assert result['llm_judge_seed_means']['n'] == 3
    assert result['llm_judge_seed_means']['sd'] == pytest.approx(2.1007935008784973)
    rows[0]['llm_judge'] = None
    result = matrix.aggregate(rows, ['full'])['full']
    assert result['llm_judge_seed_means']['n'] == 2
    assert result['llm_judge_available']['n'] == 14


def test_seed_zero_all_panels_finish_before_seed_one_dispatch():
    jobs = matrix.make_jobs(pilot.ARMS)
    phase, ready = matrix.next_phase_jobs(jobs, jobs, set(), [0, 1, 2], pilot.ARMS)
    assert phase == 0
    assert len(ready) == 40
    assert {j['seed'] for j in ready} == {0}
    assert {j['panel'] for j in ready} == set(matrix.PANELS)
    # Even when all seed-0 jobs have started, later seeds wait for their evaluation.
    seed_zero = {j['id'] for j in jobs if j['seed'] == 0}
    remaining = [j for j in jobs if j['seed'] != 0]
    phase, ready = matrix.next_phase_jobs(jobs, remaining, seed_zero - {next(iter(seed_zero))},
                                         [0, 1, 2], pilot.ARMS)
    assert phase == 0 and ready == []
    phase, ready = matrix.next_phase_jobs(jobs, remaining, seed_zero, [0, 1, 2], pilot.ARMS)
    assert phase == 1 and len(ready) == 40
    assert all(j['seed'] == 1 for j in ready)


def test_resume_classifies_active_completed_and_unstarted_without_overwriting(tmp_path):
    job = matrix.make_jobs(pilot.ARMS)[0]
    blind = 'output_001'
    state = lambda: matrix.existing_job_state(tmp_path, job, blind, {})
    assert state() == 'pending'
    assert matrix.existing_job_state(tmp_path, job, blind, {job['id']: {'pid': 42}}) == 'active'
    case = tmp_path / 'jobs' / job['batch'] / 'runs' / job['arm']
    case.mkdir(parents=True)
    assert state() == 'active'
    generation = '{"status":"completed"}'
    (case / 'result.json').write_text(generation)
    assert state() == 'generated'
    saved = tmp_path / 'evaluation' / blind / 'result.json'
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps({'id': job['id'], 'llm_judge': 0}))
    assert state() == 'evaluated'
    assert (case / 'result.json').read_text() == generation
    saved.write_text(json.dumps({'id': 'wrong_job'}))
    with pytest.raises(ValueError):
        state()
