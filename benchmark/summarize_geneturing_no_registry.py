#!/usr/bin/env python3
"""Audit and summarize completed native-orchestration runs without calling any models."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'benchmark/geneturing_no_registry_20260929'
manifest = json.loads((OUT/'manifest.json').read_text())
records = json.loads((OUT/'scored_records.json').read_text())
summary = json.loads((OUT/'summary.json').read_text())
assert len(records)==len(manifest['questions'])==50, 'All 50 attempts must finish before final audit.'
assert {x['id'] for x in records}=={x['id'] for x in manifest['questions']}
for rel,expected in manifest['source_hashes'].items():
    assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==expected, f'Source changed: {rel}'
allowed={'planner_agent','manager_agent','evaluator_agent','reporter_agent'}
actual_models=set()
fingerprints=set()
no_retrieval=[]
no_substantive_answer=[]
errors=[]
over_token_threshold=[]
for row in records:
    case=OUT/'runs'/row['id']
    if row['status']!='ok':
        errors.append({'id':row['id'],'error':row.get('error')})
    assert row.get('specialist_invocations',0)==0
    assert set(row.get('usage', {}).get('agents', {})) <= allowed
    assert row.get('ncbi_tool_calls', 0) <= manifest['limits']['ncbi_tool_calls']
    total_tokens = sum(v['input_tokens'] + v['output_tokens'] for v in row.get('usage', {}).get('agents', {}).values())
    if total_tokens > manifest['limits']['total_tokens']:
        over_token_threshold.append({'id':row['id'], 'tokens':total_tokens})
    if (case/'messages.json').exists():
        messages=json.loads((case/'messages.json').read_text())
        for msg in messages:
            if msg['type']!='ai':
                continue
            data=msg['data']
            assert data['name'] in allowed, (row['id'],data['name'])
            metadata=data.get('response_metadata',{})
            if metadata.get('model_name'):
                actual_models.add(metadata['model_name'])
            if metadata.get('system_fingerprint'):
                fingerprints.add(metadata['system_fingerprint'])
            for call in data.get('tool_calls',[]):
                assert not call['name'].startswith('transfer_to_')
                assert call['name'] not in {'next_step','retry_step'}
                assert 'genegpt' not in call['name'].lower()
    if not row.get('ncbi_tool_calls'):
        no_retrieval.append(row['id'])
    if str(row.get('answer') or '').strip().upper() in {'','NA','N/A','UNKNOWN'}:
        no_substantive_answer.append(row['id'])

rng=random.Random(42)
intervals={}
for task,values in summary['per_task'].items():
    scores=[x['benchmark_score'] for x in records if x['task']==task]
    if task == 'Gene name conversion':
        n = len(scores)
        p = statistics.mean(scores)
        z = 1.959963984540054
        denom = 1 + z*z/n
        center = (p + z*z/(2*n))/denom
        half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denom
        intervals[task] = {'method':'Wilson score', 'lower':max(0, center-half), 'upper':min(1, center+half)}
    else:
        boot=sorted(statistics.mean(rng.choices(scores,k=len(scores))) for _ in range(10000))
        intervals[task]={'method':'percentile bootstrap, 10000 samples', 'lower':boot[249], 'upper':boot[9749]}
audit={'n':50,'all_frozen_source_hashes_match':True,'zero_specialist_invocations':True,
       'actual_models':sorted(actual_models),'system_fingerprints':sorted(fingerprints),
       'incomplete_runs':errors,'runs_without_ncbi_calls':no_retrieval,
       'runs_without_substantive_answers':no_substantive_answer,
       'token_budget_semantics':'Cumulative usage checked before each call; the final call can exceed the stopping threshold. All runs retained.',
       'runs_exceeding_token_stopping_threshold':over_token_threshold,
       'per_category_95_intervals':intervals}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')

def pct(v): return f'{v*100:.1f}%'
lines=['# TissueAgent without Agent Registry: GeneTuring subset', '',
       'Only the new baseline was run. The registered-agent list was empty; recruitment and specialist dispatch were disabled.', '',
       '## Frozen design', '',
       '- 25 questions per category, sampled with seed 42 after excluding GeneGPT demonstration questions.',
       '- Native Planner → Manager → Evaluator → Reporter, with the native targeted-replanning loop retained.',
       '- Manager executes generic NCBI HTTP requests directly; no GeneGPT prompt, procedure, or specialized agent is supplied.',
       '- GPT-4o for every native role, temperature 0, request seed 0. Actual API model: '+', '.join(sorted(actual_models))+'.',
       '- Per question: at most 10 NCBI tool calls, 32 LLM calls, 96 graph steps, and 600 seconds; an 80,000-token stopping threshold is checked before each model call.',
       '- The token setting is a stopping threshold, not a strict final-usage cap: the final call can take usage above 80,000 tokens. All such runs are retained and enumerated in audit.json.',
       '- Gold answers are held outside the agent-accessible workspace. Question-level outputs and full model/tool traces are retained.', '',
       '## Results', '',
       '| Category | Questions | Completed workflows | Benchmark score | Mean graph time |',
       '|---|---:|---:|---:|---:|']
for task,values in summary['per_task'].items():
    lines.append(f"| {task} | {values['n']} | {values['completed']}/{values['n']} | {pct(values['mean_benchmark_score'])} | {values['mean_seconds']:.1f} s |")
lines.extend(['', f"Mean benchmark score across the equally sized categories: **{pct(summary['mean_benchmark_score'])}**.",
    '', 'Gene-name conversion uses the existing exact-symbol scorer. Gene-disease association uses mean gold-gene recall, not exact-set accuracy; its inherited scorer does not penalize extra genes.',
    '', f"Disease-association mean set precision: {pct(summary['per_task']['Gene disease association']['set_precision'])}; mean set F1: {pct(summary['per_task']['Gene disease association']['set_f1'])}.",
    '', f"Input tokens: {summary['input_tokens']:,}; output tokens: {summary['output_tokens']:,}. Specialist invocations: **0**.",
    f"Workflows completed: {summary['completed']}/50. Runs without a substantive answer: {len(no_substantive_answer)}. Runs without NCBI calls: {len(no_retrieval)}.",
    f"Runs whose final call exceeded the token stopping threshold: {len(over_token_threshold)}. Actual token usage above includes every such run.",
    '', 'Runtime measures graph execution and excludes interpreter/module initialization. Completion denotes delivered answer artifacts and completed native reporting, not correctness.',
    '', '## Scope of comparison', '',
    'The historical full-benchmark GeneGPT scores are not scores on this subset. The other two conditions were not rerun. A paired comparison needs their archived outputs for exactly these questions and verification of model/prompt/resource settings. The answering model matches the recorded GeneGPT model; historical outer-orchestration settings have not been established here.',
    '', 'This ablation measures native orchestration with generic retrieval. A comparison with recruited GeneGPT would test the specialist package (instructions and API procedure) made available through the registry; it would not separately establish adaptive routing superiority.',
    '', '## Artifacts', '',
    '- `manifest.json`: frozen question list, settings, and source hashes.',
    '- `summary.json`, `scored_records.json`: all attempts and task-specific metrics.',
    '- `audit.json`: role/tool audit, model IDs, integrity checks, and descriptive bootstrap intervals.',
    '- `runs/<id>/`: isolated state, evolving plan, prompts, native messages, NCBI responses, and answer artifacts.',
    '- `evaluation/gold.json`: held-out reference answers, inaccessible through worker file tools.', ''])
(OUT/'REPORT.md').write_text('\n'.join(lines))
print(json.dumps({'report':str(OUT/'REPORT.md'),'audit':audit,'summary':summary},indent=2))
