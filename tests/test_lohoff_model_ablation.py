"""Scientific accounting and input controls for the model comparison."""
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('model_sweep_test',ROOT/'benchmark/run_lohoff_model_ablation.py')
sweep=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


def test_failed_generation_is_zero_but_missing_judgment_is_not_zero():
    rows=[]
    for seed,score,figure in [(0,20,True),(1,0,False),(2,None,True)]:
        rows.append(dict(id=str(seed),model='gpt4o',panel='2a',seed=seed,
                         total_score=score,figure_produced=figure,run={'status':'completed' if figure else 'failed'}))
    s=sweep.summaries(rows,{'models':sweep.MODEL_CONFIGS})['gpt4o']
    assert s['n']==3 and s['figures']==2
    assert s['panels']['2a']['metrics']['total_score']['n']==2
    assert s['panels']['2a']['metrics']['total_score']['mean']==10
    assert s['total_score_repeat_means']['n']==0


def test_repeat_means_require_all_five_panels():
    rows=[dict(id=f'{p}-{s}',model='gpt4o',panel=p,seed=s,total_score=s+10,
               figure_produced=True,run={'status':'completed'}) for s in range(3) for p in sweep.PANELS]
    result=sweep.summaries(rows,{'models':sweep.MODEL_CONFIGS})['gpt4o']
    assert result['total_score_repeat_means']=={'n':3,'mean':11,'sd':1}
    rows.pop()
    assert sweep.summaries(rows,{'models':sweep.MODEL_CONFIGS})['gpt4o']['total_score_repeat_means']['n']==2


def test_updated_atlas_prompt_is_used():
    prompt,path=sweep.notebook_prompt('2a')
    assert path.name=='figure_recreation_lohoff-2a.ipynb'
    assert 'gastrulation_atlas_joint_umap.csv' in prompt
    assert 'seqfish_author_joint_umap.csv' in prompt
    assert 'not a rerun of raw-count integration' in prompt


def test_judge_rejects_incomplete_or_out_of_range_scores():
    import json
    j={'scores':{k:3 for k in sweep.CRITERIA},'rationale':{k:'Visible evidence' for k in sweep.CRITERIA},'limitations':'Image only'}
    assert sweep.parse_judge(json.dumps(j))==j
    j['scores']['figure_quality']=6
    with pytest.raises(AssertionError):sweep.parse_judge(json.dumps(j))
    j['scores'].pop('figure_quality')
    with pytest.raises(AssertionError):sweep.parse_judge(json.dumps(j))


def test_unrun_conditions_are_not_reported_as_failed_scores(tmp_path):
    sweep.export_tables(tmp_path,[],{'models':sweep.MODEL_CONFIGS})
    import json
    summary=json.loads((tmp_path/'summary.json').read_text())
    assert all(s['metrics']['total_score']['mean'] is None for s in summary.values())
    assert '0/75 attempts evaluated' in (tmp_path/'REPORT.md').read_text()


def test_optional_openai_search_does_not_require_key_until_used(monkeypatch):
    module=sweep.load(ROOT/'src/agents/agent_registry/searcher_agent/tools_impl/openai_web_search_tool.py','lazy_search_test')
    from unittest.mock import Mock
    constructor=Mock(side_effect=RuntimeError('No test credentials'))
    monkeypatch.setattr(module,'OpenAI',constructor)
    engine=module.OpenAIWebSearchEngine()
    constructor.assert_not_called()
    assert 'No test credentials' in engine.run('test query')
    constructor.assert_called_once()


def test_recruiter_retains_own_tool_results_only_for_current_plan():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    f=sweep.load(ROOT/'src/graph/message_filters.py','recruiter_filter_test')
    human=HumanMessage('Task')
    old=AIMessage('old assignments',name='recruiter_agent')
    plan=AIMessage('revised plan',name='planner_agent')
    call=AIMessage('',name='recruiter_agent',tool_calls=[{'id':'new','name':'glob','args':{}}])
    result=ToolMessage('found files',tool_call_id='new')
    unrelated=ToolMessage('unrelated',tool_call_id='other')
    assert f.filter_for_recruiter([human,old,plan,call,result,unrelated])==[human,plan,call,result]
    assert f._last_index_of_final([old,plan,call],'recruiter_agent')==0


def test_manager_has_user_anchor_after_tool_round_trip():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    f=sweep.load(ROOT/'src/graph/message_filters.py','manager_anchor_test')
    call=AIMessage('',name='manager_agent',tool_calls=[{'id':'x','name':'next_step','args':{}}])
    reply=ToolMessage('done',tool_call_id='x')
    result=f.filter_for_manager('manager_agent')([call,reply])
    assert isinstance(result[0],HumanMessage)
    assert result[1:]==[call,reply]
