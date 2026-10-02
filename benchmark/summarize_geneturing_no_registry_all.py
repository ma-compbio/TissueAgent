#!/usr/bin/env python3
"""Audit all 450 no-registry attempts and compare the historical GeneGPT answers."""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

import run_geneturing_no_registry as original
import run_geneturing_no_registry_all as run
from run_genegpt_paired_pilot import _score
from summarize_geneturing_no_registry_full import metrics

ARMS = ('no_registry', 'direct', 'tissueagent')
NAMES = {'no_registry': 'No registry', 'direct': 'GeneGPT', 'tissueagent': 'TissueAgent + GeneGPT'}
HISTORICAL = run.ROOT / 'benchmark/geneturing_full_benchmark/records.json'


def aggregate(rows):
    values = {}
    for task in run.TASKS:
        group = [r for r in rows if r['task'] == task]
        keys = ['benchmark_score'] + (['precision', 'recall', 'f1'] if task == 'Gene disease association' else [])
        values[task] = {'n': len(group), 'conditions': {
            arm: {key: mean(r[arm][key] for r in group) for key in keys} for arm in ARMS},
            'paired_score_difference_vs_no_registry': {
                arm: mean(r[arm]['benchmark_score']-r['no_registry']['benchmark_score'] for r in group)
                for arm in ARMS[1:]}}
    return values


def main():
    out = run.OUT
    manifest = json.loads((out / 'manifest.json').read_text())
    summary = run.summarize(out, manifest)
    records = json.loads((out / 'scored_records.json').read_text())
    assert len(records) == len(manifest['questions']) == 450
    assert len({(r['task'], r['question']) for r in records}) == 450
    assert {r['id'] for r in records} == {q['id'] for q in manifest['questions']}
    assert all(sum(r['task'] == task for r in records) == 50 for task in run.TASKS)
    for rel, expected in manifest['source_hashes'].items():
        assert original.sha(run.ROOT / rel) == expected, rel
        assert original.sha(out / 'source_snapshot' / rel) == expected, rel
    for key, source in manifest['reused_results'].items():
        assert original.sha(out / 'runs' / key / 'result.json') == source['sha256']
        assert original.sha(Path(source['path'])) == source['sha256']
    previous = {r['id']: r for r in json.loads((run.PRIOR / 'scored_records.json').read_text())}
    for r in records:
        if r['id'] in previous:
            assert r['benchmark_score'] == previous[r['id']]['benchmark_score']
    allowed = set(manifest['native_roles'])
    models, incomplete, no_answer, no_retrieval, over_tokens = set(), [], [], [], []
    for r in records:
        assert r.get('specialist_invocations', 0) == 0
        assert set(r.get('usage', {}).get('agents', {})) <= allowed
        assert r.get('ncbi_tool_calls', 0) <= manifest['limits']['ncbi_tool_calls']
        usages = list(r.get('usage', {}).get('agents', {}).values())
        assert sum(u['llm_calls'] for u in usages) <= manifest['limits']['llm_calls']
        tokens = sum(u['input_tokens']+u['output_tokens'] for u in usages)
        if tokens > manifest['limits']['total_tokens']:
            over_tokens.append({'id': r['id'], 'tokens': tokens})
        if r['status'] != 'ok':
            incomplete.append({'id': r['id'], 'task': r['task'], 'error': r.get('error')})
        if str(r.get('answer') or '').strip().upper() in run.UNKNOWN:
            no_answer.append(r['id'])
        if not r.get('ncbi_tool_calls'):
            no_retrieval.append(r['id'])
        path = out / 'runs' / r['id'] / 'messages.json'
        if not path.exists():
            continue
        for msg in json.loads(path.read_text()):
            if msg['type'] != 'ai':
                continue
            data = msg['data']
            assert data['name'] in allowed, (r['id'], data['name'])
            model = data.get('response_metadata', {}).get('model_name')
            if model:
                models.add(model)
            for call in data.get('tool_calls', []):
                assert not call['name'].startswith('transfer_to_')
                assert call['name'] not in {'next_step', 'retry_step'}
                assert 'genegpt' not in call['name'].lower()
    historical = json.loads(HISTORICAL.read_text())
    lookup = {(r['task'], r['question']): r for r in historical}
    paired = []
    for r in records:
        old = lookup[(r['task'], r['question'])]
        assert old['gold'] == r['gold']
        disease = r['task'] == 'Gene disease association'
        row = {k: r[k] for k in ('id', 'task', 'question', 'gold')}
        row['demonstration'] = r['id'] in manifest['demonstration_question_ids']
        row['no_registry'] = metrics(r['prediction'], r['gold'], r['benchmark_score'], disease)
        for arm in ARMS[1:]:
            assert old[arm]['status'] == 'ok'
            pred, score = _score(old[arm]['raw_completion'], r['gold'], r['task'])
            assert score == old[arm]['score'], (r['id'], arm)
            row[arm] = {**metrics(pred, r['gold'], score, disease), 'model_used': old[arm]['model_used'],
                        'historical_record_index': old['index'], 'raw_artifact': old[arm]['raw_artifact']}
        paired.append(row)
    clean = [r for r in paired if not r['demonstration']]
    comparison = {'historical_source': str(HISTORICAL), 'historical_source_sha256': original.sha(HISTORICAL),
                  'all_questions': aggregate(paired), 'excluding_demonstrations': aggregate(clean),
                  'overall_mean_benchmark_score': {a: mean(r[a]['benchmark_score'] for r in paired) for a in ARMS},
                  'excluding_demonstrations_overall_score': {a: mean(r[a]['benchmark_score'] for r in clean) for a in ARMS},
                  'records': paired}
    audit = {'n': 450, 'reused': 100, 'new': 350, 'all_frozen_source_hashes_match': True,
             'all_reused_results_unchanged': True, 'prior_100_scores_unchanged': True,
             'zero_specialist_invocations': True, 'actual_models': sorted(models),
             'incomplete_runs': incomplete, 'runs_without_substantive_answers': no_answer,
             'runs_without_ncbi_calls': no_retrieval, 'runs_exceeding_token_stopping_threshold': over_tokens,
             'demonstration_question_ids': manifest['demonstration_question_ids'],
             'report_script_sha256': original.sha(Path(__file__))}
    original.dump(out / 'audit.json', audit)
    original.dump(out / 'historical_matched_comparison.json', comparison)
    lines = ['# Full GeneTuring no-registry benchmark', '',
             'All 450 questions across nine categories were evaluated: 350 new attempts plus 100 preserved attempts from the earlier two-category evaluation. Only the no-registry baseline was newly run. Both GeneGPT conditions reuse saved outputs from the completed 450-question archive.', '',
             '| Category | N | No registry | GeneGPT | TissueAgent + GeneGPT |',
             '| --- | ---: | ---: | ---: | ---: |']
    for task, group in comparison['all_questions'].items():
        values = ' | '.join(f"{group['conditions'][a]['benchmark_score']:.1%}" for a in ARMS)
        lines.append(f"| {task.replace('aligment', 'alignment')} | {group['n']} | {values} |")
    values = ' | '.join(f"{comparison['overall_mean_benchmark_score'][a]:.1%}" for a in ARMS)
    lines.extend([f'| Overall mean benchmark score | 450 | {values} |', '',
                  'Most categories use exact-match scoring after the existing normalization. Disease association uses reference-gene recall. Human genome alignment gives 1 for exact coordinates and 0.5 for the correct chromosome alone. Overall averages these category-specific scores, so it is not uniformly strict accuracy.', '',
                  '## Demonstration-excluded check', '',
                  '| Category | N | No registry | GeneGPT | TissueAgent + GeneGPT |',
                  '| --- | ---: | ---: | ---: | ---: |'])
    for task, group in comparison['excluding_demonstrations'].items():
        values = ' | '.join(f"{group['conditions'][a]['benchmark_score']:.1%}" for a in ARMS)
        lines.append(f"| {task.replace('aligment', 'alignment')} | {group['n']} | {values} |")
    lines.extend(['', f"Excluded {len(paired)-len(clean)} questions identified by the existing GeneGPT demonstration filter; all 450 remain in the primary results.", '',
                  '## Audit and protocol', '',
                  f"- Completed native workflows: {summary['completed']}/450. All 450 attempts are scored, including failures and abstentions. Specialist invocations: 0.",
                  f'- Attempts without substantive answers: {len(no_answer)}; without NCBI retrieval: {len(no_retrieval)}.',
                  '- Roles: Planner, Manager, Evaluator, Reporter. Registry empty; recruitment bypassed; Manager uses general NCBI HTTPS GET and answer-submission tools.',
                  '- GPT-4o for every role, temperature 0, seed 0. Actual API models: '+', '.join(sorted(models))+'.',
                  '- The seven-category extension changes only answer-format instructions and the abstention marker. UNKNOWN is distinct from the supported protein-coding answer No. The original 100 attempts and their scores are unchanged.',
                  '- Limits unchanged: 10 NCBI calls, 32 LLM calls, 96 graph steps, 600 seconds per question. An 80,000-token stopping threshold is checked before each model call; its last response can exceed the threshold.',
                  f"- Input/output tokens: {summary['input_tokens']:,}/{summary['output_tokens']:,}. Runs exceeding the soft token threshold: {len(over_tokens)}; all retained.",
                  '- Four isolated workers scheduled the new categories round-robin, sharing a 0.4-second minimum NCBI request interval. Gold answers remain outside worker-accessible state.', '',
                  '## Interpretation limits', '',
                  'Questions, references and scoring are matched. Historical GeneGPT execution dates, resource budgets and outer-orchestration settings were not fully matched to this baseline. The recruited benchmark explicitly forces GeneGPT; these comparisons do not isolate autonomous registry selection.', '',
                  'Each question has one attempt per condition. Budget-limited attempts are retained without additional attempts or larger budgets. Sequence alignment relies on the same generic NCBI access; no specialist BLAST procedure or tool was added.', '',
                  'Audit details and failures: `audit.json`. Per-question comparisons: `historical_matched_comparison.json`. Frozen protocol: `manifest.json`, `worker_format_changes.diff`, `source_snapshot/`. Original answers and traces: `runs/`.', ''])
    (out / 'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({'summary': summary, 'audit': audit,
                      'category_comparison': comparison['all_questions']}, indent=2))


if __name__ == '__main__':
    main()
