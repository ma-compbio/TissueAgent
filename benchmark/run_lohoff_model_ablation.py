#!/usr/bin/env python3
"""Frozen, resumable TissueAgent model sweep; 5 backbones x 5 panels x 3 runs.

No historical output is exposed to the solver. Uses the architecture-ablation
execution harness with only the model and provider adapter varied.
"""
from __future__ import annotations

import argparse
import ast
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import fcntl
import importlib.util
import io
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
JUDGE = 'google/gemini-3-flash-preview'
MODEL_CONFIGS = [
    dict(id='gpt4o', model='gpt-4o', label='GPT-4o', provider='openai',
         api_model='gpt-4o-2024-11-20', credential_env='OPENAI_API_KEY',
         constructor_overrides=dict(max_tokens=16000, temperature=0.2, parallel_tool_calls=False)),
    dict(id='gpt51', model='gpt-5.1', label='GPT-5.1', provider='openai',
         api_model='gpt-5.1-2025-11-13', credential_env='OPENAI_API_KEY', reasoning_effort='high',
         constructor_overrides=dict(max_tokens=16000, parallel_tool_calls=False)),
    dict(id='gpt55', model='gpt-5.5', label='GPT-5.5', provider='openai',
         api_model='gpt-5.5-2026-04-23', credential_env='OPENAI_API_KEY', reasoning_effort='high',
         constructor_overrides=dict(max_tokens=16000, use_responses_api=True, parallel_tool_calls=False)),
    dict(id='sonnet45', model='claude-sonnet-4-5-20250929', label='Claude Sonnet 4.5',
         provider='anthropic', api_model='claude-sonnet-4-5-20250929', credential_env='ANTHROPIC_API_KEY',
         constructor_overrides=dict(max_tokens=16000, temperature=0.2)),
    dict(id='qwen3vl', model='openrouter/qwen3-vl-32b-instruct', label='Qwen3-VL-32B-Instruct',
         provider='openrouter', api_model='qwen/qwen3-vl-32b-instruct', credential_env='OPENROUTER_API_KEY',
         constructor_overrides=dict(max_tokens=16000, temperature=0.2,
             extra_body={'provider': {'only': ['alibaba'], 'allow_fallbacks': False, 'require_parameters': True}})),
]
CRITERIA = ('figure_quality', 'content_completeness', 'visual_structural_fidelity',
            'data_fidelity', 'scientific_fidelity')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pilot = load(REPO / 'benchmark/run_lohoff_architecture_pilot.py', 'model_ablation_pilot')
dump, sha, now = pilot.dump, pilot.sha, pilot.now


def make_model(cfg):
    sys.path[:0] = [str(REPO / 'src'), str(REPO)]
    import models
    models._MODELS_BY_ID[cfg['model']] = models.ModelSpec(
        id=cfg['model'], provider=cfg['provider'], api_model=cfg['api_model'],
        label=cfg['label'], reasoning_effort=cfg.get('reasoning_effort'))
    return models.build_chat_model(cfg['model'], max_retries=2, timeout=180,
                                   **cfg['constructor_overrides'])


def live_preflight(out):
    """Synthetic vision + tool round trips; never use benchmark targets to tune."""
    from PIL import Image
    from langchain_core.messages import HumanMessage, ToolMessage
    pilot.credentials(('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY'))
    out.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(); Image.new('RGB', (32, 32), 'red').save(buf, format='PNG')
    data_url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    tool = {'type': 'function', 'function': {'name': 'record_color',
        'description': 'Record the dominant color of the supplied image.',
        'parameters': {'type': 'object', 'properties': {'color': {'type': 'string'}},
                       'required': ['color'], 'additionalProperties': False}}}
    def check(cfg):
        dest = out / f'{cfg["id"]}.json'
        if dest.exists():
            previous = json.loads(dest.read_text())
            if previous.get('passed') and previous.get('config') == cfg:
                return previous
        try:
            llm = make_model(cfg)
            human = HumanMessage(content=[{'type': 'text', 'text':
                'Call record_color exactly once with the dominant image color. After its result reply ACK.'},
                {'type': 'image_url', 'image_url': {'url': data_url}}])
            answer = llm.bind_tools([tool]).invoke([human])
            pilot.check_response_complete(answer)
            assert len(answer.tool_calls) == 1, 'No unique tool call returned'
            call = answer.tool_calls[0]
            assert call['name'] == 'record_color' and 'red' in call['args']['color'].lower(), 'Vision/tool mismatch'
            final = llm.bind_tools([tool]).invoke([human, answer, ToolMessage(
                content='Recorded red successfully. Reply ACK.', tool_call_id=call['id'])])
            pilot.check_response_complete(final)
            result = dict(passed=True, config=cfg, checked=now(), tool_call=call,
                          response_metadata=final.response_metadata,
                          usage=[answer.usage_metadata, final.usage_metadata])
        except Exception as exc:
            result = dict(passed=False, config=cfg, checked=now(), error=f'{type(exc).__name__}: {exc}')
        dump(dest, result)
        return result
    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        for future in as_completed([pool.submit(check, c) for c in MODEL_CONFIGS]):
            r = future.result(); results.append(r)
            print(json.dumps({k:r.get(k) for k in ('passed', 'error')} | {'model':r['config']['id']}), flush=True)
    from openai import OpenAI
    try:
        with OpenAI(api_key=os.environ['OPENROUTER_API_KEY'], base_url='https://openrouter.ai/api/v1',
                    timeout=120, max_retries=2) as client:
            response = client.chat.completions.create(model=JUDGE, max_tokens=1000, temperature=0,
                messages=[{'role':'user', 'content':[{'type':'text','text':'Reply JSON only: {"color": "dominant image color"}.'},
                    {'type':'image_url','image_url':{'url':data_url}}]}])
        text = response.choices[0].message.content
        assert 'red' in (text or '').lower()
        judge = dict(passed=True, model=JUDGE, checked=now(), response=response.model_dump())
    except Exception as exc:
        judge = dict(passed=False, model=JUDGE, checked=now(), error=f'{type(exc).__name__}: {exc}')
    dump(out / 'judge.json', judge)
    print(json.dumps({'judge_passed':judge['passed'], 'error':judge.get('error')}), flush=True)
    return all(r['passed'] for r in results) and judge['passed']


def notebook_prompt(panel):
    notebook = REPO / 'demo' / f'figure_recreation_lohoff-{panel}.ipynb'
    content = json.loads(notebook.read_text())
    for cell in content['cells']:
        if cell['cell_type'] != 'code':
            continue
        try:
            tree = ast.parse(''.join(cell.get('source', [])))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PROMPT' for t in node.targets):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, str):
                    return value, notebook
    # Older notebooks store the prompt inline. Their archived manifest records
    # that exact input; no generated artifact is read or staged.
    archived = REPO / 'demo/outputs' / f'figure_recreation_lohoff-{panel}' / 'run_manifest.json'
    return json.loads(archived.read_text())['prompt'], archived


def prepare(out, preflight, concurrency):
    if out.exists():
        raise FileExistsError(out)
    checks = {c['id']: json.loads((preflight/f'{c["id"]}.json').read_text()) for c in MODEL_CONFIGS}
    assert all(checks[c['id']]['passed'] and checks[c['id']]['config'] == c for c in MODEL_CONFIGS)
    assert json.loads((preflight/'judge.json').read_text())['passed']
    out.mkdir(parents=True)
    source = out / 'source'
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.git', '.env', '.env.*', 'node_modules', 'cached_skills')
    for name in ('src', 'knowledge'):
        shutil.copytree(REPO/name, source/name, ignore=ignore)
    (source/'benchmark').mkdir()
    for name in ('run_lohoff_architecture_pilot.py', 'run_lohoff_model_ablation.py',
                 'lohoff_execution_guard.py', 'reevaluate_lohoff_llm_judge.py'):
        shutil.copy2(REPO/'benchmark'/name, source/'benchmark'/name)
    shutil.copytree(preflight, out/'provider_preflight')
    rubric = load(source/'benchmark/reevaluate_lohoff_llm_judge.py', 'model_sweep_rubric')
    (out/'rubric.txt').write_text(rubric.RUBRIC+'\n')
    panel_cfgs = {}
    for panel in PANELS:
        names = ['dataset_lohoff_et_al_seqfish.h5ad', f'reference_lohoff-{panel}.png']
        if (REPO/'demo/data'/f'instructions_lohoff-{panel}.md').is_file():
            names.append(f'instructions_lohoff-{panel}.md')
        if panel == '2a':
            names += ['gastrulation_atlas_joint_umap.csv', 'seqfish_author_joint_umap.csv']
        inp = out/'inputs'/panel; inp.mkdir(parents=True)
        destinations = {}
        for name in names:
            shutil.copy2(REPO/'demo/data'/name, inp/name)
            destinations[name] = 'library/datasets' if Path(name).suffix in {'.h5ad', '.csv'} else 'project/uploads'
        original, prompt_source = notebook_prompt(panel)
        prompt = original.replace('Fig2b.jpg', f'reference_lohoff-{panel}.png')
        # The current demo prompts use bare input names. The explicit map avoids
        # assumptions about the storage location of CSVs and references.
        prompt += '\n\nExact staged input paths:\n' + '\n'.join(f'- {destinations[n]}/{n}' for n in names)
        prompt += ('\nSave the final reproduced figure as project/outputs/figures/final_figure.png, '
            'the plotted numerical data as project/outputs/tables/plotted_data.csv, and all executable '
            'code and reports under project/outputs. Work only with supplied inputs and newly generated '
            'files. Do not retrieve prior reproductions or author code. Generate figures by analyzing '
            'the supplied data, never by copying or transforming reference pixels.')
        panel_cfgs[panel] = dict(prompt=prompt, input_destinations=destinations,
            prompt_source=str(prompt_source), prompt_source_sha256=sha(prompt_source),
            input_hashes={n:sha(inp/n) for n in names})
    shutil.copy2(REPO/'demo/data/provenance_lohoff-2a.json', out/'atlas_provenance.json')
    jobs = []
    for seed in SEEDS:
        for panel in PANELS:
            for cfg in MODEL_CONFIGS:
                ident = f'{cfg["id"]}_{panel}_repeat{seed}'
                batch = out/'jobs'/ident; batch.mkdir(parents=True)
                (batch/'source').symlink_to(source, target_is_directory=True)
                (batch/'inputs').symlink_to(out/'inputs'/panel, target_is_directory=True)
                dump(batch/'manifest.json', dict(panel=panel, seed=seed, model=cfg['model'], model_config=cfg,
                    repository_root=str(REPO), **(panel_cfgs[panel] | {
                    'prompt':panel_cfgs[panel]['prompt']+f'\nUse analysis random seed {seed} for stochastic computations.'})))
                jobs.append(dict(id=ident, model=cfg['id'], panel=panel, seed=seed))
    # Prioritize the soon-to-retire Qwen route, retaining independent isolated jobs.
    random.Random(20261008).shuffle(jobs)
    jobs.sort(key=lambda j:(j['model']!='qwen3vl', j['seed']))
    manifest = dict(created=now(), models=MODEL_CONFIGS, panels=PANELS, seeds=SEEDS,
        jobs=jobs, total_jobs=len(jobs), concurrency=concurrency, evaluation_concurrency=2,
        judge=JUDGE, judge_replicates=1, model_request_seed=None,
        source_hashes={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()},
        input_hashes={str(p.relative_to(out)):sha(p) for p in (out/'inputs').rglob('*') if p.is_file()},
        job_hashes={str(p.relative_to(out)):sha(p) for p in (out/'jobs').glob('*/manifest.json')},
        policy={'all_attempts_fresh':True, 'output_selection':'Exact final_figure.png; no best-of selection',
            'failure_scoring':'Missing/unreadable/reference-copy image: zero judge scores, NA image metrics. Judge/scorer errors: NA.',
            'seed_policy':'Three independent API generations; analysis seeds 0/1/2; request seed omitted for all providers.',
            'runtime_policy':'Native graph/retry/tool limits; 16000 output tokens per response, including reasoning where applicable.',
            'judge_policy':'Fixed blinded Gemini judge outside all tested model families; one judgment per generated figure.',
            'aggregation':'Main table mean/sample SD across 15 attempts; per-panel across three. Also export repeat-level five-panel means.',
            'atlas_scope':'Panel 2a reproduces plotting from published joint coordinates, not raw-count integration.',
            'historical_comparison':'Updated 2a, current frozen code and different judge: do not pool with historical architecture-ablation runs.'})
    dump(out/'manifest.json', manifest)
    dump(out/'status.json', dict(status='prepared', total=75, completed=0, active=[], updated=now()))
    (out/'logs').mkdir(); (out/'evaluation').mkdir()
    print(json.dumps({'prepared':str(out), 'jobs':len(jobs)}), flush=True)


def verify(out):
    manifest = json.loads((out/'manifest.json').read_text())
    for key, root in (('source_hashes',out/'source'),('input_hashes',out),('job_hashes',out)):
        for rel, expected in manifest[key].items():
            if sha(root/rel) != expected:
                raise RuntimeError('Frozen study file changed: '+rel)
    return manifest


def stats(values):
    vals = [v for v in values if v is not None]
    return dict(n=len(vals), mean=statistics.mean(vals) if vals else None,
                sd=statistics.stdev(vals) if len(vals)>1 else None)


def summaries(rows, manifest):
    all_results = {}
    fields = [*CRITERIA, 'total_score', 'runtime_minutes', 'tokens_m', 'ssim',
              'phash_similarity', 'orb_matches']
    for model in manifest['models']:
        selected = [r for r in rows if r['model']==model['id']]
        result = dict(n=len(selected), figures=sum(r['figure_produced'] for r in selected),
                      completed=sum(r['run']['status']=='completed' for r in selected))
        result['metrics'] = {k:stats([r.get(k) for r in selected]) for k in fields}
        result['panels'] = {}
        for panel in PANELS:
            part = [r for r in selected if r['panel']==panel]
            result['panels'][panel] = dict(n=len(part), figures=sum(r['figure_produced'] for r in part),
                metrics={k:stats([r.get(k) for r in part]) for k in fields})
        seed_means = []
        for seed in SEEDS:
            part = [r for r in selected if r['seed']==seed and r.get('total_score') is not None]
            if len(part)==len(PANELS):
                seed_means.append(statistics.mean(r['total_score'] for r in part))
        result['total_score_repeat_means'] = stats(seed_means)
        all_results[model['id']] = result
    return all_results


def tex_cell(s, digits=2):
    if s['mean'] is None:
        return '--'
    if s['sd'] is None:
        return f"${s['mean']:.{digits}f}$"
    return f"\\shortstack{{${s['mean']:.{digits}f}$\\\\$\\pm {s['sd']:.{digits}f}$}}"


def export_tables(out, rows, manifest):
    summary = summaries(rows, manifest)
    dump(out/'results.json', sorted(rows,key=lambda r:r['id']))
    dump(out/'summary.json', summary)
    tabledir = out/'tables'; tabledir.mkdir(exist_ok=True)
    csv_fields = ['id','model','panel','seed','figure_produced','judge_status',*CRITERIA,
                  'total_score','runtime_minutes','tokens_m','ssim','phash_similarity','orb_matches']
    with (tabledir/'run_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=csv_fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    def fmt(s):
        if s['mean'] is None:return 'NA'
        return f"{s['mean']:.3f}" + (f" ± {s['sd']:.3f}" if s['sd'] is not None else '')
    lines=['# Lohoff TissueAgent model ablation','',f'{len(rows)}/75 attempts evaluated. Results remain provisional until all attempts and judgments are accounted for.','',
        '| Model | Evaluated | Figures | Quality | Completeness | Visual fidelity | Data fidelity | Scientific fidelity | Total /25 | Minutes | Tokens M/run |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    fields=[*CRITERIA,'total_score','runtime_minutes','tokens_m']
    for cfg in manifest['models']:
        s=summary[cfg['id']]
        lines.append('| '+ ' | '.join([cfg['label'],f"{s['n']}/15",f"{s['figures']}/{s['n']}",*[fmt(s['metrics'][k]) for k in fields]])+' |')
    lines += ['', 'Scores use the fixed blinded Gemini judge and the architecture-ablation 0–5 rubric. Missing/invalid figures score zero; evaluation errors remain NA. Means/SDs in the main table are across attempts; per-panel statistics are across three independent generations. Figure production is separate from graph completion and scientific correctness. Timings include concurrent resource contention. Updated 2a uses published processed atlas/seqFISH coordinates. These results must not be pooled with historical architecture runs.', '',
        '| Model | 2a total /25 | 2b total /25 | 2c total /25 | 2d total /25 | 2e total /25 |', '|---|---:|---:|---:|---:|---:|']
    for cfg in manifest['models']:
        s=summary[cfg['id']]
        lines.append('| '+cfg['label']+' | '+' | '.join(fmt(s['panels'][p]['metrics']['total_score']) for p in PANELS)+' |')
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    def start(columns, title):
        weights = [0.75,0.9,1.25,1,1,1,1.2,0.9,1] if columns == 10 else [1]*(columns-1)
        spec = ''.join(r'>{\hsize='+str(w)+r'\hsize\linewidth=\hsize\centering\arraybackslash}X' for w in weights)
        return [r'\clearpage',r'\begin{table}[p]',r'\centering\scriptsize',r'\setlength{\tabcolsep}{2pt}',
            r'\renewcommand{\arraystretch}{1.15}',r'\begin{tabularx}{\textwidth}{@{}p{0.19\textwidth}'+
            spec+'@{}}',r'\toprule',title+r' \\',r'\midrule']
    def end(lines, caption, label):
        lines += [r'\bottomrule',r'\end{tabularx}',r'\caption{'+caption+'}',r'\label{'+label+'}',r'\end{table}']
        return '\n'.join(lines)+'\n'
    heads=['Model',r'\shortstack{Figures\\($n/15$)}',r'\shortstack{Figure\\quality}',r'\shortstack{Content\\completeness}',
        r'\shortstack{Visual\\fidelity}',r'\shortstack{Data\\fidelity}',r'\shortstack{Scientific\\fidelity}',
        r'\shortstack{Total\\(0--25)}',r'\shortstack{Runtime\\(min)}',r'\shortstack{Tokens\\(M/run)}']
    main=start(10,' & '.join(heads))
    for cfg in manifest['models']:
        s=summary[cfg['id']]
        main.append(' & '.join([cfg['label'],f"{s['figures']}/15",*[tex_cell(s['metrics'][k],3 if k=='tokens_m' else 2) for k in fields]])+r' \\')
    caption=(f"TissueAgent backbone comparison on Lohoff Fig. 2A--E ({len(rows)}/75 evaluated attempts). "
        r"Five models, five panels and three independent generations per panel. Values are mean $\pm$ sample SD across attempts. "
        r"Each judge dimension ranges from 0 to 5; their sum ranges from 0 to 25. Missing or invalid figures receive zero; judge API failures are unavailable. "
        r"Runtime and tokens include failed attempts and exclude external judging. The fixed blinded judge is Gemini 3 Flash Preview. "
        r"All TissueAgent roles use the selected backbone. Panel 2A uses the updated published atlas and seqFISH joint coordinates; it evaluates plotting reconstruction. "
        r"Unfinished and unavailable entries are shown as dashes; denominator details are in the accompanying CSV and manifest.")
    (tabledir/'aggregate.tex').write_text(end(main,caption,'tab:lohoff_model_ablation'))
    for group,name in [(PANELS[:3],'panels_abc'),(PANELS[3:],'panels_de')]:
        body=start(8,' & '.join([heads[0],r'\shortstack{Figures\\($n/3$)}',*heads[2:8]]))
        for panel in group:
            body += [r'\multicolumn{8}{@{}l}{\textbf{Panel '+panel.upper()+r'}} \\',r'\midrule']
            for cfg in manifest['models']:
                s=summary[cfg['id']]['panels'][panel]
                body.append(' & '.join([cfg['label'],f"{s['figures']}/3",*[tex_cell(s['metrics'][k]) for k in fields[:6]]])+r' \\')
            body.append(r'\midrule')
        (tabledir/f'{name}.tex').write_text(end(body,
            r'Panel-level backbone comparison. Values are mean $\pm$ sample SD across three independent generations. The same fixed judge and failure policy apply as in Table~\ref{tab:lohoff_model_ablation}.',
            'tab:lohoff_model_'+name))
    body=start(5,'Model / panel & Figures & SSIM & pHash similarity & ORB matches')
    for panel in PANELS:
        body += [r'\multicolumn{5}{@{}l}{\textbf{Panel '+panel.upper()+r'}} \\',r'\midrule']
        for cfg in manifest['models']:
            s=summary[cfg['id']]['panels'][panel]
            body.append(' & '.join([cfg['label'],f"{s['figures']}/3",*[tex_cell(s['metrics'][k],3) for k in ['ssim','phash_similarity','orb_matches']]])+r' \\')
    (tabledir/'image_metrics.tex').write_text(end(body,
        r'Image-similarity metrics, mean $\pm$ sample SD over available valid images. Missing images are excluded with denominators retained in the CSV. These metrics do not establish numerical or biological correctness.',
        'tab:lohoff_model_image_metrics'))
    wrapper=[r'\documentclass[10pt]{article}',r'\usepackage[margin=0.7in]{geometry}',
             r'\usepackage{booktabs,tabularx,array}',r'\begin{document}']
    wrapper += [r'\input{'+n+'.tex}' for n in ('aggregate','panels_abc','panels_de','image_metrics')]
    wrapper += [r'\end{document}']
    (tabledir/'all_tables.tex').write_text('\n'.join(wrapper)+'\n')


def parse_judge(content):
    import re
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip())
    j=json.loads(text)
    assert set(j['scores'])==set(CRITERIA)
    assert all(type(j['scores'][k]) is int and 0<=j['scores'][k]<=5 for k in CRITERIA)
    assert all(isinstance(j['rationale'].get(k),str) and j['rationale'][k].strip() for k in CRITERIA)
    assert isinstance(j.get('limitations'),str)
    return j


def evaluate(out, job, manifest):
    from PIL import Image, ImageChops
    from openai import OpenAI
    batch=out/'jobs'/job['id'];case=batch/'runs/full'
    anonymous='output_'+sha(batch/'manifest.json')[:16]
    dest=out/'evaluation'/anonymous;dest.mkdir(exist_ok=True)
    if (dest/'result.json').exists():
        return json.loads((dest/'result.json').read_text())
    run=json.loads((case/'result.json').read_text())
    fig=case/'state/workspace/project/outputs/figures/final_figure.png'
    reference=out/'inputs'/job['panel']/f'reference_lohoff-{job["panel"]}.png'
    counts=run.get('counts',{})
    row={**job,'run':run,'anonymous_id':anonymous,'figure_produced':False,
         'runtime_minutes':run.get('elapsed_seconds',0)/60,
         'tokens_m':(counts.get('input_tokens',0)+counts.get('output_tokens',0))/1e6,
         'ssim':None,'phash_similarity':None,'orb_matches':None,
         'judge_status':'no_figure',**{k:0 for k in CRITERIA},'total_score':0}
    try:
        with Image.open(fig) as im:im.verify()
        with Image.open(fig) as a,Image.open(reference) as b:
            if a.size==b.size and ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None:
                raise ValueError('Output pixels identical to reference')
        row['figure_produced']=True
    except (OSError,ValueError) as exc:
        row['figure_issue']=str(exc);dump(dest/'result.json',row);return row
    scorer=out/'source/knowledge/skills/figure-reproduce/scripts/compare_figures.py'
    scored=subprocess.run([sys.executable,str(scorer),str(reference),str(fig),'--json','--out',str(dest/'comparison.png')],
        capture_output=True,text=True,timeout=240)
    (dest/'scorer_stdout.txt').write_text(scored.stdout);(dest/'scorer_stderr.txt').write_text(scored.stderr)
    try:
        metrics=json.loads(scored.stdout);dump(dest/'image_metrics.json',metrics)
        row.update(ssim=metrics['ssim'],phash_similarity=1-metrics['phash_hamming']/64,
                   orb_matches=metrics['orb_good_matches'])
    except Exception as exc:row['metric_error']=f'{type(exc).__name__}: {exc}'
    cfg=json.loads((batch/'manifest.json').read_text())
    methods=out/'inputs'/job['panel']/f'instructions_lohoff-{job["panel"]}.md'
    prompt=('Image 1 is the published reference and image 2 is the generated figure. '
        'The generator identity is hidden; do not infer it.\n'+(out/'rubric.txt').read_text()+
        '\nReturn JSON only: {"scores": {criterion: integer}, "rationale": {criterion: string}, "limitations": string}. '
        'Use exactly these criterion keys: '+', '.join(CRITERIA)+'. Explain visible evidence and uncertainty. '
        'Images cannot verify underlying calculations.\nTask:\n'+cfg['prompt']+
        '\nMethods:\n'+(methods.read_text() if methods.exists() else 'No additional Methods supplied.'))
    (dest/'judge_prompt.txt').write_text(prompt)
    def image_block(path):
        return {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()}}
    for attempt in range(3):
        try:
            while not router_funded():
                dump(dest/'waiting_for_credits.json',{'status':'waiting_for_openrouter_credits','updated':now()})
                if any((out/name).exists() for name in ('STOP.json','INVALIDATED.json')):
                    raise RuntimeError('Study stopped while waiting for judging credits')
                time.sleep(30)
            router_lock=(out/'openrouter_request.lock').open('a')
            fcntl.flock(router_lock,fcntl.LOCK_EX)
            with OpenAI(api_key=os.environ['OPENROUTER_API_KEY'],base_url='https://openrouter.ai/api/v1',
                        timeout=180,max_retries=2) as client:
                response=client.chat.completions.create(model=manifest['judge'],max_tokens=4000,temperature=0,
                    messages=[{'role':'user','content':[{'type':'text','text':prompt},image_block(reference),image_block(fig)]}])
            dump(dest/f'judge_raw_{attempt+1}.json',response.model_dump())
            router_lock.close()
            if response.choices[0].finish_reason!='stop':raise ValueError('Incomplete judge response')
            judged=parse_judge(response.choices[0].message.content or '')
            dump(dest/'judge.json',judged)
            row.update(judged['scores']);row.update(total_score=sum(judged['scores'].values()),judge_status='scored',
                                                   judge_model=response.model,judge_usage=response.usage.model_dump())
            break
        except Exception as exc:
            if 'router_lock' in locals():router_lock.close()
            dump(dest/f'judge_error_{attempt+1}.json',{'error':f'{type(exc).__name__}: {exc}','time':now()})
            row.update({k:None for k in CRITERIA});row.update(total_score=None,judge_status='failed',judge_error=f'{type(exc).__name__}: {exc}')
            if attempt<2:time.sleep(5)
    dump(dest/'result.json',row)
    return row


_router_credit_cache = {'checked':0.,'funded':False}
_router_credit_lock = threading.Lock()


def router_funded():
    """Read account credits without generating requests or exposing credentials."""
    import httpx
    with _router_credit_lock:
        if time.monotonic()-_router_credit_cache['checked']<30:
            return _router_credit_cache['funded']
        try:
            response=httpx.get('https://openrouter.ai/api/v1/credits',timeout=20,
                headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']})
            response.raise_for_status();d=response.json()['data']
            funded=float(d.get('total_credits',0))-float(d.get('total_usage',0))>0.02
        except Exception:
            funded=False
        _router_credit_cache.update(checked=time.monotonic(),funded=funded)
        return funded


def offline_preflight(out):
    manifest=verify(out)
    script=out/'source/benchmark/run_lohoff_architecture_pilot.py'
    jobs=[next(j for j in manifest['jobs'] if j['model']==c['id'] and j['panel']=='2a' and j['seed']==0) for c in manifest['models']]
    def check(job):
        batch=out/'jobs'/job['id'];result=batch/'preflight/full/result.json'
        if result.exists():return json.loads(result.read_text())['status']=='offline_preflight_passed'
        with (out/'logs'/f'{job["model"]}_offline.log').open('w') as log:
            proc=subprocess.run([sys.executable,str(script),'worker','--out',str(batch),'--arm','full','--offline'],
                                stdout=log,stderr=subprocess.STDOUT,timeout=240)
        return proc.returncode==0 and result.exists()
    with ThreadPoolExecutor(max_workers=2) as pool:
        success=list(pool.map(check,jobs))
    dump(out/'offline_preflight.json',{'passed':all(success),'models':dict(zip([j['model'] for j in jobs],success)),'checked':now()})
    return all(success)


def controller(out):
    import psutil
    lock=(out/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=verify(out)
    pilot.credentials(('OPENAI_API_KEY','ANTHROPIC_API_KEY','OPENROUTER_API_KEY'))
    if not offline_preflight(out):raise RuntimeError('Offline graph preflight failed; inspect logs')
    dump(out/'supervisor.json',{'pid':os.getpid(),'created':now(),'script':str(Path(__file__).resolve())})
    rows=[];active={};mutex=threading.RLock()
    script=out/'source/benchmark/run_lohoff_architecture_pilot.py'
    def launch(job):
        batch=out/'jobs'/job['id'];case=batch/'runs/full';result=case/'result.json'
        if result.exists():return job
        if any((out/name).exists() for name in ('STOP.json','INVALIDATED.json')):
            return None
        meta_path=batch/'process.json';proc=None
        started=time.time()
        if meta_path.exists():
            meta=json.loads(meta_path.read_text());started=meta['started_epoch']
            try:
                existing=psutil.Process(meta['pid'])
                alive=abs(existing.create_time()-meta['create_time'])<1 and existing.is_running()
            except psutil.Error:alive=False
            if alive:
                with mutex:active[job['id']]={**job,'pid':meta['pid'],'adopted':True}
                while not result.exists() and existing.is_running() and existing.status()!=psutil.STATUS_ZOMBIE:time.sleep(3)
            elif not case.exists():raise RuntimeError('Inconsistent preserved process metadata: '+job['id'])
        elif case.exists():
            raise RuntimeError('Existing attempt has no process/result record; inspect before resuming: '+job['id'])
        else:
            env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUNBUFFERED='1')
            with (out/'logs'/f'{job["id"]}.log').open('w') as log:
                proc=subprocess.Popen([sys.executable,str(script),'worker','--out',str(batch),'--arm','full'],
                    stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
                meta=dict(pid=proc.pid,create_time=psutil.Process(proc.pid).create_time(),started_epoch=started)
                dump(meta_path,meta)
                with mutex:active[job['id']]={**job,'pid':proc.pid}
                proc.wait()
        if not result.exists():
            heartbeat=case/'heartbeat.json';counts=json.loads(heartbeat.read_text()).get('counts',{}) if heartbeat.exists() else {}
            dump(result,dict(arm='full',status='worker_failed',exit_code=proc.returncode if proc else None,
                counts=counts,elapsed_seconds=time.time()-started,finished=now()))
        with mutex:active.pop(job['id'],None)
        return job
    def status(state):
        with mutex:
            dump(out/'status.json',dict(status=state,total=75,evaluated=len(rows),
                generated=sum((out/'jobs'/j['id']/'runs/full/result.json').exists() for j in manifest['jobs']),
                figures=sum(r['figure_produced'] for r in rows),active=list(active.values()),updated=now()))
    export_tables(out,rows,manifest)
    from concurrent.futures import wait,FIRST_COMPLETED
    with ThreadPoolExecutor(max_workers=manifest['concurrency']) as generation,ThreadPoolExecutor(max_workers=2) as evaluation:
        pending={};scoring={};queued=list(manifest['jobs'])
        while pending or scoring or queued:
            stopped=any((out/name).exists() for name in ('STOP.json','INVALIDATED.json'))
            if stopped:queued=[]
            funded=router_funded()
            ready=[j for j in queued if j['model']!='qwen3vl' or funded]
            for job in ready[:max(0,manifest['concurrency']-len(pending))]:
                queued.remove(job);pending[generation.submit(launch,job)]=job
            status('running' if pending else 'waiting_for_openrouter_credits' if queued and not funded else 'scoring')
            if not pending and not scoring:
                time.sleep(5);continue
            done,_=wait(set(pending)|set(scoring),timeout=5,return_when=FIRST_COMPLETED)
            for future in done:
                if future in pending:
                    job=future.result();pending.pop(future)
                    if job is not None:
                        scoring[evaluation.submit(evaluate,out,job,manifest)]=job
                else:
                    job=scoring.pop(future)
                    try:row=future.result()
                    except Exception as exc:
                        dump(out/'evaluation'/f'{job["id"]}_fatal.json',{'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()})
                        continue
                    rows.append(row);export_tables(out,rows,manifest)
    verify(out)
    state='complete' if len(rows)==75 and all(r['judge_status']!='failed' and not r.get('metric_error') for r in rows) else 'evaluation_incomplete'
    if any((out/name).exists() for name in ('STOP.json','INVALIDATED.json')):state='stopped'
    status(state)
    dump(out/'completion_audit.json',{'status':state,'finished':now(),'evaluated':len(rows),'frozen_hashes_verified':True})
    if shutil.which('pdflatex'):
        for _ in range(2):
            compiled=subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','all_tables.tex'],
                cwd=out/'tables',capture_output=True,text=True,timeout=90)
        (out/'tables/build_stdout.txt').write_text(compiled.stdout+'\n'+compiled.stderr)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['live-preflight','prepare','offline-preflight','run','launch','report'])
    p.add_argument('--out',type=Path,required=True);p.add_argument('--preflight',type=Path)
    p.add_argument('--concurrency',type=int,default=3)
    a=p.parse_args();out=a.out.resolve()
    if a.action=='live-preflight':raise SystemExit(0 if live_preflight(out) else 1)
    if a.action=='prepare':prepare(out,a.preflight.resolve(),a.concurrency);return
    if a.action=='offline-preflight':raise SystemExit(0 if offline_preflight(out) else 1)
    if a.action=='report':
        manifest=verify(out)
        rows=[json.loads(p.read_text()) for p in (out/'evaluation').glob('output_*/result.json')]
        export_tables(out,rows,manifest);return
    if a.action=='launch':
        script=out/'source/benchmark/run_lohoff_model_ablation.py'
        with (out/'controller.log').open('a') as log:
            proc=subprocess.Popen([sys.executable,str(script),'run','--out',str(out)],
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True,stdin=subprocess.DEVNULL)
        print(json.dumps({'controller_pid':proc.pid,'output':str(out)}));return
    try:controller(out)
    except BaseException as exc:
        dump(out/'controller_error.json',{'time':now(),'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()})
        raise


if __name__=='__main__':main()
