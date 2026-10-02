#!/usr/bin/env python3
"""Rejudge saved Lohoff figures with the user-specified five-criterion 0–5 rubric."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
from pathlib import Path
import re
import shutil


CRITERIA = (
    'figure_quality', 'content_completeness', 'visual_structural_fidelity',
    'data_fidelity', 'scientific_fidelity',
)
RUBRIC = '''Please evaluate the generated figure relative to the reference using the following scale:
0: Failed · 1: Poor · 2: Fair · 3: Good · 4: Excellent · 5: Exceptional
Evaluation Criteria
Figure quality: Is the figure readable and clear? Overall visual quality, image resolution,
text readability, and clarity of labels, legends, and axes.
Content completeness: Does the figure include all scientifically important content
from the reference, such as panels, samples, conditions, cell types, annotations,
legends, and statistical summaries?
Visual and structural fidelity: Does the figure use visual representations comparable
to the reference, including plot types, panel organization, coordinate systems,
graphical encodings, and color mappings?
Data fidelity: Does the figure preserve the trends, directions, rankings, spatial
distributions, group differences, and numerical scales or ranges shown in the
reference?
Scientific fidelity: Does the figure convey the same biological or scientific conclusion
as the reference, such that a domain expert would reach essentially the same take-
home message?'''
LABELS = {
    'full': 'Full TissueAgent',
    'single_react_no_skills': 'Single-agent ReAct, no skills',
    'no_evolving_plan': 'No evolving plan',
    'no_local_retry': 'No local retry',
    'no_manager': 'No Manager supervision/retry',
    'no_evaluator_replanning': 'No Evaluator/replanning',
    'no_plan_registry': 'No Plan Registry',
    'no_skill_registry': 'No Skill Registry',
}


def parse_judgment(raw):
    """Reject incomplete responses, old rubrics, and invalid ordinal scores."""
    if raw.get('stop_reason') != 'end_turn':
        raise ValueError(f'Incomplete judge response: {raw.get("stop_reason")}')
    text = ''.join(b['text'] for b in raw['content'] if b.get('type') == 'text').strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    judged = json.loads(text)
    scores = judged['scores']
    if set(scores) != set(CRITERIA):
        raise ValueError('Judge must score exactly the five requested criteria')
    if any(type(scores[k]) is not int or not 0 <= scores[k] <= 5 for k in CRITERIA):
        raise ValueError('Every criterion must have an integer score from 0 to 5')
    if any(not isinstance(judged['rationale'].get(k), str) or not judged['rationale'][k].strip()
           for k in CRITERIA):
        raise ValueError('Every criterion must have a rationale')
    if not isinstance(judged.get('limitations'), str):
        raise ValueError('Judge must describe limitations')
    return judged, sum(scores.values()) / len(CRITERIA)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run, out = args.run.resolve(), args.out.resolve()
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite an evaluation: {out}')

    spec = importlib.util.spec_from_file_location(
        'frozen_lohoff_pilot', run / 'source/benchmark/run_lohoff_architecture_pilot.py')
    pilot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pilot)
    original = json.loads((run / 'results.json').read_text())
    prior = {r['arm']: r for r in original}
    order = json.loads((run / 'evaluation/blind_order.json').read_text())
    assert set(order.values()) == set(prior) == set(pilot.ARMS)
    reference = run / 'inputs/reference_lohoff-2e.png'
    figures = {arm: run / 'runs' / arm / 'state/workspace/project/outputs/figures/final_figure.png'
               for arm in pilot.ARMS}
    from PIL import Image, ImageChops
    for arm, figure in figures.items():
        assert figure.exists() == prior[arm]['figure_produced'], arm
        if figure.exists():
            with Image.open(figure) as im:
                im.verify()
            with Image.open(figure) as a, Image.open(reference) as b:
                assert a.size != b.size or ImageChops.difference(
                    a.convert('RGB'), b.convert('RGB')).getbbox() is not None, arm

    out.mkdir(parents=True)
    shutil.copy2(__file__, out / 'reevaluate_lohoff_llm_judge.py')
    (out / 'rubric.txt').write_text(RUBRIC + '\n')
    prompt = (
        'Image 1 is the published reference; image 2 is the generated figure. '
        'The generating system identity is hidden. Do not infer it.\n\n' + RUBRIC +
        '\n\nAssign one integer score to each criterion independently. '
        'Base rationales on visible evidence and explicitly note uncertainty. '
        'Image-only judgments cannot verify the underlying calculations. '
        'Return JSON only, with exactly these score and rationale keys: ' + ', '.join(CRITERIA) +
        '. Schema: {"scores":{criterion:integer},"rationale":{criterion:string},"limitations":string}.'
        '\n\nTask:\n' + pilot.PROMPT + '\nMethods:\n' +
        (run / 'inputs/instructions_lohoff-2e.md').read_text()
    )
    (out / 'judge_prompt.txt').write_text(prompt + '\n')
    protected = [run / 'results.json', run / 'REPORT.md', run / 'manifest.json',
                 run / 'inputs/instructions_lohoff-2e.md', reference,
                 *[p for p in (run / 'evaluation').rglob('*') if p.is_file()],
                 *[p for p in figures.values() if p.exists()]]
    before = {str(p.relative_to(run)): pilot.sha(p) for p in protected}
    pilot.dump(out / 'manifest.json', {
        'created': pilot.now(), 'source_run': str(run), 'judge': pilot.JUDGE,
        'temperature': 0, 'judge_replicates': 1, 'criteria': list(CRITERIA),
        'scale': {0: 'Failed', 1: 'Poor', 2: 'Fair', 3: 'Good', 4: 'Excellent', 5: 'Exceptional'},
        'aggregation': 'Equal-weight arithmetic mean of five integer scores; range 0–5',
        'missing_output_policy': 'All five scores and aggregate are zero; no judge API call',
        'api_failure_policy': 'NA, never a zero score',
        'blind_order': order, 'protected_file_hashes': before,
        'script_sha256': pilot.sha(out / 'reevaluate_lohoff_llm_judge.py'),
        'prompt_sha256': pilot.sha(out / 'judge_prompt.txt'),
        'context': 'Same generation task and methods as the previous evaluation; previous scores withheld',
    })
    pilot.credentials()

    def image_block(path):
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                'data': base64.b64encode(path.read_bytes()).decode()}}

    def evaluate(blind, arm):
        import anthropic
        dest = out / blind
        dest.mkdir()
        old = prior[arm]
        row = dict(arm=arm, blind_id=blind, figure_produced=old['figure_produced'],
                   ssim=old['ssim'], phash_similarity=old['phash_similarity'],
                   orb_matches=old['orb_matches'], runtime_minutes=old['run']['elapsed_seconds']/60,
                   previous_llm_judge_0_to_10=old['llm_judge'],
                   criterion_scores=None, llm_judge_0_to_5=None, judge_status='pending')
        if not old['figure_produced']:
            row.update(criterion_scores={k: 0 for k in CRITERIA}, llm_judge_0_to_5=0,
                       judge_status='missing_figure_penalty')
        else:
            try:
                with anthropic.Anthropic(timeout=180, max_retries=2) as client:
                    response = client.messages.create(
                        model=pilot.JUDGE, max_tokens=2000, extra_body={'temperature': 0},
                        messages=[{'role': 'user', 'content': [
                            {'type': 'text', 'text': prompt}, image_block(reference),
                            image_block(figures[arm])]}])
                raw = response.model_dump()
                pilot.dump(dest / 'judge_raw.json', raw)
                judged, mean = parse_judgment(raw)
                pilot.dump(dest / 'judge.json', judged)
                row.update(criterion_scores=judged['scores'], llm_judge_0_to_5=mean,
                           judge_status='scored', judge_usage=raw['usage'])
            except Exception as exc:
                row.update(judge_status='failed', judge_error=f'{type(exc).__name__}: {exc}')
        pilot.dump(dest / 'result.json', row)
        return row

    rows = []
    pilot.dump(out / 'status.json', {'status': 'running', 'completed': [], 'updated': pilot.now()})
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(evaluate, blind, arm) for blind, arm in order.items()]
        for job in as_completed(jobs):
            row = job.result()
            rows.append(row)
            rows.sort(key=lambda r: pilot.ARMS.index(r['arm']))
            pilot.dump(out / 'results.json', rows)
            pilot.dump(out / 'status.json', {'status': 'running',
                'completed': [r['arm'] for r in rows], 'updated': pilot.now()})
            print(json.dumps({k: row[k] for k in ('arm', 'judge_status', 'llm_judge_0_to_5')}), flush=True)

    mismatches = [rel for rel, digest in before.items() if pilot.sha(run / rel) != digest]
    pilot.dump(out / 'integrity_audit.json', {'checked': pilot.now(),
        'protected_files': len(before), 'changed_files': mismatches})
    if mismatches:
        raise RuntimeError(f'Protected inputs or prior results changed: {mismatches}')
    lines = ['# Lohoff 2E: five-criterion LLM reevaluation (0–5)', '',
             'The same seven saved figures were freshly judged by Claude Sonnet 4.5 using the '
             'user-specified rubric, one blinded judgment per figure. Previous scores were withheld. '
             'The aggregate is the equal-weight mean of five integer scores; no previous score was rescaled.', '',
             '0: Failed · 1: Poor · 2: Fair · 3: Good · 4: Excellent · 5: Exceptional', '',
             '| Condition | Figure quality | Content completeness | Visual/structural fidelity | Data fidelity | Scientific fidelity | Mean /5 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        scores = row['criterion_scores']
        cells = [str(scores[k]) for k in CRITERIA] if scores else ['NA'] * len(CRITERIA)
        mean = 'NA' if row['llm_judge_0_to_5'] is None else f'{row["llm_judge_0_to_5"]:.1f}'
        if row['judge_status'] == 'missing_figure_penalty':
            mean += '*'
        lines.append('| ' + LABELS[row['arm']] + ' | ' + ' | '.join(cells + [mean]) + ' |')
    lines += ['', '*Missing output receives zero on every criterion by the existing failure rule; '
              'it was not submitted to the judge. API or parsing failures receive NA.', '',
              'Generation outputs, original 0–10 evaluations, image-similarity metrics and runtimes '
              'are preserved. One panel, one generation seed and one judge response per figure '
              'do not estimate variability; image-only scores do not verify underlying calculations.', '',
              'Exact rubric: [rubric.txt](rubric.txt). Exact prompt: [judge_prompt.txt](judge_prompt.txt). '
              'Scores: [results.json](results.json). Raw responses and rationales: `output_*/`.']
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    failures = [r['arm'] for r in rows if r['judge_status'] == 'failed']
    pilot.dump(out / 'status.json', {'status': 'complete' if not failures else 'complete_with_failures',
        'completed': [r['arm'] for r in rows], 'failures': failures, 'updated': pilot.now()})
    if failures:
        raise RuntimeError(f'Judgment failed for {failures}; inspect saved errors and raw responses')


if __name__ == '__main__':
    main()
