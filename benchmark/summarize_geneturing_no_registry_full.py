#!/usr/bin/env python3
"""Audit the full two-category baseline and compare saved historical answers."""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

import run_geneturing_no_registry as baseline
from extend_geneturing_no_registry import DEFAULT_OUT
from run_genegpt_paired_pilot import _score

OUT = DEFAULT_OUT
HISTORICAL = baseline.REPO / 'benchmark/geneturing_full_benchmark/records.json'
ARMS = ('no_registry', 'direct', 'tissueagent')
NAMES = {'no_registry': 'TissueAgent without Agent Registry', 'direct': 'GeneGPT',
         'tissueagent': 'TissueAgent + GeneGPT'}


def metrics(pred, gold, score, disease):
    result = {'prediction': pred, 'benchmark_score': score}
    if disease:
        ps = set(pred) if isinstance(pred, list) else set()
        gs = set(gold.split(', '))
        precision = len(ps & gs) / len(ps) if ps else 0.0
        recall = len(ps & gs) / len(gs)
        result.update(precision=precision, recall=recall,
                      f1=2*precision*recall/(precision+recall) if precision+recall else 0.0)
    return result


def aggregate(rows):
    result = {}
    for task in baseline.TASKS:
        group = [r for r in rows if r['task'] == task]
        keys = ['benchmark_score'] + (['precision', 'recall', 'f1']
                                      if task == 'Gene disease association' else [])
        result[task] = {'n': len(group), 'conditions': {
            arm: {key: mean(r[arm][key] for r in group) for key in keys} for arm in ARMS}}
        result[task]['paired_score_difference_vs_no_registry'] = {
            arm: mean(r[arm]['benchmark_score'] - r['no_registry']['benchmark_score']
                      for r in group) for arm in ARMS[1:]}
    return result


def main():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    summary = baseline.summarize(OUT, manifest)
    records = json.loads((OUT / 'scored_records.json').read_text())
    assert len(records) == len(manifest['questions']) == 100
    assert len({(r['task'], r['question']) for r in records}) == 100
    assert {r['id'] for r in records} == {r['id'] for r in manifest['questions']}
    for rel, expected in manifest['source_hashes'].items():
        assert baseline.sha(baseline.REPO / rel) == expected, rel
        assert baseline.sha(OUT / 'source_snapshot' / rel) == expected, rel
    for key, source in manifest['reused_results'].items():
        assert baseline.sha(OUT / 'runs' / key / 'result.json') == source['sha256']
        assert baseline.sha(Path(source['path'])) == source['sha256']
    allowed = set(manifest['native_roles'])
    models = set()
    over_tokens, incomplete, no_answer, no_retrieval = [], [], [], []
    for r in records:
        assert r.get('specialist_invocations', 0) == 0
        assert set(r.get('usage', {}).get('agents', {})) <= allowed
        assert r.get('ncbi_tool_calls', 0) <= manifest['limits']['ncbi_tool_calls']
        usages = list(r.get('usage', {}).get('agents', {}).values())
        assert sum(u['llm_calls'] for u in usages) <= manifest['limits']['llm_calls']
        tokens = sum(u['input_tokens'] + u['output_tokens'] for u in usages)
        if tokens > manifest['limits']['total_tokens']:
            over_tokens.append({'id': r['id'], 'tokens': tokens})
        if r['status'] != 'ok':
            incomplete.append({'id': r['id'], 'error': r.get('error')})
        if str(r.get('answer') or '').strip().upper() in {'', 'NA', 'N/A', 'UNKNOWN'}:
            no_answer.append(r['id'])
        if not r.get('ncbi_tool_calls'):
            no_retrieval.append(r['id'])
        path = OUT / 'runs' / r['id'] / 'messages.json'
        if not path.exists():
            continue
        for msg in json.loads(path.read_text()):
            if msg['type'] != 'ai':
                continue
            data = msg['data']
            assert data['name'] in allowed
            if data.get('response_metadata', {}).get('model_name'):
                models.add(data['response_metadata']['model_name'])
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
            row[arm] = {**metrics(pred, r['gold'], score, disease),
                        'model_used': old[arm]['model_used'],
                        'historical_record_index': old['index'],
                        'raw_artifact': old[arm]['raw_artifact']}
        paired.append(row)
    comparison = {'historical_source': str(HISTORICAL),
                  'historical_source_sha256': baseline.sha(HISTORICAL),
                  'all_questions': aggregate(paired),
                  'excluding_demonstrations': aggregate([r for r in paired if not r['demonstration']]),
                  'overall_mean_benchmark_score': {
                      arm: mean(r[arm]['benchmark_score'] for r in paired) for arm in ARMS},
                  'records': paired}
    audit = {'n': len(records), 'reused': 50, 'new': 50,
             'all_frozen_source_hashes_match': True, 'all_reused_results_unchanged': True,
             'zero_specialist_invocations': True, 'actual_models': sorted(models),
             'incomplete_runs': incomplete, 'runs_without_substantive_answers': no_answer,
             'runs_without_ncbi_calls': no_retrieval,
             'runs_exceeding_token_stopping_threshold': over_tokens,
             'demonstration_question_ids': manifest['demonstration_question_ids'],
             'report_script_sha256': baseline.sha(Path(__file__))}
    baseline.dump(OUT / 'audit.json', audit)
    baseline.dump(OUT / 'historical_matched_comparison.json', comparison)
    lines = ['# Full two-category GeneTuring benchmark', '',
             'All 50 gene-name-conversion and 50 gene-disease-association questions were evaluated.',
             'Only the no-registry baseline was run: 50 earlier results were retained unchanged and 50 additional questions were executed. Direct and recruited GeneGPT answers were reused from the completed 450-question archive.', '',
             '## Same-question comparison', '',
             '| Category | N | No registry | GeneGPT | TissueAgent + GeneGPT |',
             '| --- | ---: | ---: | ---: | ---: |']
    for task, group in comparison['all_questions'].items():
        values = ' | '.join(f"{group['conditions'][a]['benchmark_score']:.1%}" for a in ARMS)
        lines.append(f"| {task} | {group['n']} | {values} |")
    overall = ' | '.join(f"{comparison['overall_mean_benchmark_score'][a]:.1%}" for a in ARMS)
    lines.extend([f'| Mean benchmark score | 100 | {overall} |', '',
                  'Conversion uses exact-symbol accuracy. Disease association uses mean reference-gene recall; extra genes are not penalized by that benchmark score. The overall value averages different metrics.', '',
                  '| Disease-association metric | No registry | GeneGPT | TissueAgent + GeneGPT |',
                  '| --- | ---: | ---: | ---: |'])
    disease = comparison['all_questions']['Gene disease association']['conditions']
    for metric in ('precision', 'recall', 'f1'):
        values = ' | '.join(f'{disease[a][metric]:.1%}' for a in ARMS)
        lines.append(f'| Mean reference-set {metric} | {values} |')
    clean = comparison['excluding_demonstrations']['Gene disease association']
    values = ', '.join(f"{NAMES[a]} {clean['conditions'][a]['benchmark_score']:.1%}" for a in ARMS)
    lines.extend(['', f"Excluding the GeneGPT demonstration question (Meesmann corneal dystrophy), disease recall on the remaining {clean['n']} questions is: {values}.", '',
                  '## Execution audit', '',
                  f"- Completed native workflows: {summary['completed']}/100. Specialist calls: 0.",
                  '- Native roles: Planner, Manager, Evaluator, Reporter. Registry empty; Recruiter bypassed. Manager directly uses generic NCBI retrieval.',
                  '- GPT-4o, temperature 0, request seed 0; actual API models: ' + ', '.join(sorted(models)) + '.',
                  '- Original prompts, models, graph, worker, scorer and limits verified against preserved source hashes before and after extension.',
                  '- Per question: 10 NCBI tool calls, 32 LLM calls, 96 graph steps, 600 seconds. The 80,000-token stopping threshold is checked before each model call and may be exceeded by its final response.',
                  f"- Input/output tokens across all 100 attempts: {summary['input_tokens']:,}/{summary['output_tokens']:,}. Runs exceeding the token threshold: {len(over_tokens)}; all retained.",
                  f'- Runs without a substantive answer: {len(no_answer)}; without NCBI calls: {len(no_retrieval)}.',
                  '- All 100 attempts are scored, including any saved answers from workflows that stopped before final reporting. No budget-limited attempt is dropped or rerun.',
                  '- Incomplete workflows: ' + ('; '.join(
                      f"{item['id']}: {item['error']}" for item in incomplete) if incomplete else 'none') + '.',
                  '- Full per-question traces, source snapshots, held-out gold, reused-result hashes and demonstration flag are retained.', '',
                  '## Interpretation limits', '',
                  'Questions, reference answers and scoring are matched. These are historical comparisons: execution dates, resource budgets and outer-orchestration settings were not experimentally matched. Both historical answering arms record gpt-4o; new native roles also use gpt-4o.', '',
                  'The recruited benchmark explicitly requests GeneGPT. This comparison measures the specialist package against native orchestration with generic retrieval; it does not isolate autonomous registry selection or establish that every architectural component helps every task.', '',
                  'Each condition has one recorded run per question. These results cover two complete categories, not all GeneTuring tasks.', '',
                  'Artifacts: `summary.json`, `audit.json`, `scored_records.json`, `historical_matched_comparison.json`, `manifest.json`, `runs/`, `source_snapshot/`.', ''])
    (OUT / 'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({'audit': audit, 'summary': summary,
                      'all_questions': comparison['all_questions'],
                      'excluding_demonstrations': comparison['excluding_demonstrations']}, indent=2))


if __name__ == '__main__':
    main()
