#!/usr/bin/env python3
"""Update only Response 2 and its supplementary registry table after the full audit."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess

from run_geneturing_no_registry_all import OUT, ROOT, TASKS


def pct(value):
    return f'{value*100:.1f}\\%'


def jm(text):
    notes = []
    for match in re.finditer(r'\\jian\{', text):
        depth, end = 1, match.end()
        while depth:
            if text[end] == '{' and text[end-1] != '\\':
                depth += 1
            elif text[end] == '}' and text[end-1] != '\\':
                depth -= 1
            end += 1
        prefix = text[text.rfind('\n', 0, match.start())+1:match.start()]
        notes.append(('%' in prefix, text[match.start():end]))
    return notes


def table_bounds(text, label):
    index = text.index('\\label{'+label+'}')
    start = text.rfind(r'\begin{table}', 0, index)
    end = text.index(r'\end{table}', index) + len(r'\end{table}')
    return start, end


def main():
    s = json.loads((OUT / 'summary.json').read_text())
    c = json.loads((OUT / 'historical_matched_comparison.json').read_text())
    a = json.loads((OUT / 'audit.json').read_text())
    assert s['finished'] == a['n'] == 450 and a['all_frozen_source_hashes_match']
    overall = c['overall_mean_benchmark_score']
    disease = c['all_questions']['Gene disease association']['conditions']
    counts = {'higher': 0, 'equal': 0, 'lower': 0}
    for task in TASKS:
        group = c['all_questions'][task]['conditions']
        delta = group['no_registry']['benchmark_score']-group['tissueagent']['benchmark_score']
        counts['equal' if abs(delta)<1e-12 else 'higher' if delta>0 else 'lower'] += 1
    response = ROOT / 'docs/manuscript/response.tex'
    supp = ROOT / 'docs/manuscript/supp-tab-fig.tex'
    before, before_supp = response.read_text(), supp.read_text()
    start = before.index(r'\noindent 2. The paper can benefit')
    end = before.index(r'\end{reviewresponse}', start) + len(r'\end{reviewresponse}')
    section = before[start:end]
    ts, te = table_bounds(before_supp, 'tab:geneturing_registry_full')
    expected = json.loads((OUT / 'manuscript_expected_scope.json').read_text())
    assert hashlib.sha256(section.encode()).hexdigest() == expected['response2_sha256'], 'Response 2 changed during the run; preserve user edits and review manually.'
    assert hashlib.sha256(before_supp[ts:te].encode()).hexdigest() == expected['registry_table_sha256'], 'Registry table changed during the run; preserve user edits and review manually.'
    old = next(line for line in section.splitlines() if line.startswith(r'\textit{Draft status:'))
    section = section.replace(old, r'\textit{Draft status: the no-registry baseline and same-question historical GeneGPT comparison are complete for all 450 GeneTuring questions across nine categories. Execution dates, resource budgets, and historical outer-orchestration settings were not fully matched; the other controlled architecture ablations remain pending.}')
    old = next(line for line in section.splitlines() if line.startswith(r'\item \textit{External-specialist access:}'))
    section = section.replace(old, r'\item \textit{External-specialist access:} all 450 GeneTuring questions across nine complete categories (50 questions per category). The new \methodname condition without Agent Registry access is compared with saved direct and recruited GeneGPT answers on the same questions (\textbf{Table~\ref{tab:geneturing_registry_all}}).')
    bs = section.index('For the Agent Registry comparison,')
    be = section.index('For the remaining architecture ablations', bs)
    block = r'''For the Agent Registry comparison, we evaluated all 450 GeneTuring questions spanning nine categories, with 50 questions per category: gene aliases, gene-name conversion, gene--disease association, gene location, SNP location, SNP--gene association, protein-coding status, human genome DNA alignment, and multi-species DNA alignment.
We retained the 100 attempts from the initial two-category evaluation and ran the remaining 350 questions. For the additional categories, we expanded only the answer-format instructions and distinguished an unsupported answer (UNKNOWN) from a supported No answer to a protein-coding question.
The native model, role graph, general NCBI tools, and per-question resource limits remained unchanged. Planner, Manager, Evaluator, and Reporter used GPT-4o with temperature 0 and request seed 0; recruitment was bypassed and the Manager executed NCBI requests directly.
Every question used isolated state with reference answers withheld. The registry was empty and traces confirmed zero specialist invocations.
The direct and recruited GeneGPT conditions were not rerun; their archived outputs from the completed 450-question benchmark were rescored against the same questions and references.

'''
    block += (
        f"The no-registry baseline completed {s['completed']}/450 workflows. All 450 attempts, including incomplete workflows and abstentions, were retained in scoring.\n"
        f"Its overall mean benchmark score was {pct(overall['no_registry'])}, compared with {pct(overall['direct'])} for direct GeneGPT and {pct(overall['tissueagent'])} for \\methodname{{}}+GeneGPT (\\textbf{{Table~\\ref{{tab:geneturing_registry_all}}}}).\n"
        f"Relative to recruited GeneGPT, the no-registry score was higher in {counts['higher']} categories, equal in {counts['equal']}, and lower in {counts['lower']}; the category-level results provide the relevant task-specific comparison.\n"
        "Most categories use exact-match scoring after the existing normalization. Disease association uses reference-gene recall, and human genome alignment gives half credit for the correct chromosome without exact coordinates; the overall score therefore combines category-specific metrics.\n"
        f"For disease association, no-registry recall, reference-set precision, and F1 were {pct(disease['no_registry']['recall'])}, {pct(disease['no_registry']['precision'])}, and {pct(disease['no_registry']['f1'])}, respectively.\n"
        f"We also report a sensitivity analysis excluding the {len(a['demonstration_question_ids'])} questions identified by the existing GeneGPT demonstration filter.\n"
        f"Across all 450 attempts, the no-registry condition used {s['input_tokens']:,} input tokens and {s['output_tokens']:,} output tokens; costs and completion counts include unsuccessful attempts.\n\n"
    )
    block += r'''This comparison assesses the specialist package, including its instructions and API-use procedure, against native orchestration with general retrieval. Direct GeneGPT provides a reference for the specialist's standalone performance; a separate direct GPT baseline is not required for this targeted question.
The comparison is descriptive: historical execution dates, resource budgets, and outer-orchestration settings were not fully matched, so performance differences cannot be attributed solely to the Agent Registry.
The recruited benchmark explicitly instructs \methodname to invoke GeneGPT. These results therefore do not isolate autonomous recruitment or establish that adaptive selection is better than a fixed assignment; that claim requires an unprompted routing comparison with the same specialists available in both conditions.

'''
    section = section[:bs] + block + section[be:]
    section = section.replace('The completed GeneTuring baseline used one run per question in the two full categories;', 'The completed GeneTuring baseline used one run per question across all nine categories;')
    section = section.replace('; this focused evaluation does not establish performance across all GeneTuring categories.', '; repeated evaluations would be needed to assess stochastic variation.')
    section = section.replace('No Agent Registry (two GeneTuring categories)', 'No Agent Registry (full GeneTuring)')
    section = section.replace('on all 50 gene-name-conversion and 50 gene-disease-association questions', 'on all 450 questions across nine categories')
    section = section.replace('The three conditions for the two complete GeneTuring categories', 'The three full GeneTuring conditions')
    section = section.replace('tab:geneturing_registry_full', 'tab:geneturing_registry_all')
    after = before[:start] + section + before[end:]
    old_table = before_supp[ts:te]
    rows = []
    for task in TASKS:
        values = c['all_questions'][task]['conditions']
        scores = ' & '.join(pct(values[arm]['benchmark_score']) for arm in ('direct', 'tissueagent', 'no_registry'))
        rows.append(task.replace('aligment', 'alignment')+' & 50 & '+scores+r' \\')
    scores = ' & '.join(r'\textbf{'+pct(overall[arm])+'}' for arm in ('direct', 'tissueagent', 'no_registry'))
    body_start = old_table.index('Gene name conversion &')
    body_end = old_table.index(r'\bottomrule', body_start)
    table = old_table[:body_start] + '\n'.join(rows) + '\n\\midrule\n' + r'\textbf{Mean benchmark score} & \textbf{450} & ' + scores + r' \\' + '\n' + old_table[body_end:]
    caption_start = table.index(r'\caption{')
    caption = r'''\caption{Full GeneTuring comparison of direct GeneGPT, \methodname-recruited GeneGPT, and \methodname without Agent Registry access (450 questions; 50 per category).
Only the no-registry condition was newly executed: 100 prior attempts were retained unchanged and 350 additional questions were evaluated. The additional categories required only expanded answer-format instructions and an explicit UNKNOWN abstention marker. Models, native roles, general NCBI tools, and per-question limits were unchanged.
Direct and recruited GeneGPT outputs were reused from the completed benchmark and scored on the same questions and references.
Most tasks use normalized exact match; disease association uses mean reference-gene recall, which does not penalize extra genes, and human genome alignment gives half credit for the correct chromosome alone. The overall value averages these category-specific scores.
'''
    caption += (
        f"The no-registry condition completed {s['completed']}/450 workflows, with zero specialist calls; all 450 attempts, including failures and abstentions, were scored.\n"
        f"No-registry disease-association reference-set precision/F1 were {pct(disease['no_registry']['precision'])}/{pct(disease['no_registry']['f1'])}.\n"
        f"Excluding {len(a['demonstration_question_ids'])} demonstration questions, overall scores were {pct(c['excluding_demonstrations_overall_score']['direct'])} for direct GeneGPT, {pct(c['excluding_demonstrations_overall_score']['tissueagent'])} for recruited GeneGPT, and {pct(c['excluding_demonstrations_overall_score']['no_registry'])} without the registry.\n"
    )
    caption += r'''The no-registry roles used GPT-4o, temperature 0, and request seed 0. Historical dates, resource budgets, and outer-orchestration settings were not fully matched, so these are descriptive comparisons. Explicitly forced GeneGPT recruitment does not test autonomous specialist selection.}
\label{tab:geneturing_registry_all}
\label{tab:geneturing_registry_full}
\label{tab:geneturing_registry_subset}
\end{threeparttable}
\end{table}'''
    table = table[:caption_start] + caption
    after_supp = before_supp[:ts] + table + before_supp[te:]
    assert jm(before) == jm(after) and jm(before_supp) == jm(after_supp)
    backup = OUT / 'manuscript_before_all_results'
    backup.mkdir(exist_ok=False)
    (backup / 'response.tex').write_text(before)
    (backup / 'supp-tab-fig.tex').write_text(before_supp)
    response.write_text(after)
    supp.write_text(after_supp)
    verification = {'updated_utc': datetime.now(timezone.utc).isoformat(), 'all_jm_comments_preserved': True,
                    'response_changes_confined_to_reviewer1_response2': True,
                    'supplement_changes_confined_to_registry_table': True}
    # Build a focused proof using the prior successful proof's preamble.
    preamble = (OUT / 'manuscript_proof_preamble.tex').read_text()
    a1, b1 = table_bounds(after_supp, 'tab:geneturing_results')
    proof = OUT / 'manuscript_proof'
    proof.mkdir(exist_ok=True)
    (proof / 'results-check.tex').write_text(preamble+section+'\n\\clearpage\n'+after_supp[a1:b1]+'\n\\clearpage\n'+table+'\n\\end{document}\n')
    with (proof / 'build.log').open('w') as log:
        proc = subprocess.run(['/Library/TeX/texbin/latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error',
                               '-outdir='+str(proof), str(proof / 'results-check.tex')],
                              cwd=ROOT / 'docs/manuscript', stdout=log, stderr=subprocess.STDOUT)
    latex_log = (proof / 'results-check.log').read_text()
    issues = [line for line in latex_log.splitlines() if any(t in line for t in
              ['Undefined control', 'undefined references', 'LaTeX Warning: Reference', 'Overfull', '! LaTeX Error'])]
    verification.update(focused_latex_exit_code=proc.returncode, latex_issues=issues)
    (OUT / 'manuscript_verification.json').write_text(json.dumps(verification, indent=2)+'\n')
    assert proc.returncode == 0 and not issues, issues
    print(json.dumps(verification, indent=2))


if __name__ == '__main__':
    main()
