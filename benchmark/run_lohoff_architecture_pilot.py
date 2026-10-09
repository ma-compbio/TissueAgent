#!/usr/bin/env python3
"""One-seed, eight-condition Lohoff 2E pilot using a frozen native TissueAgent graph.

prepare and preflight are offline. controller launches isolated workers, then scores
and judges their final figures. Never reads historical reproduced figures.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
ARMS = ('full', 'single_react_no_skills', 'no_evolving_plan', 'no_local_retry',
        'no_manager', 'no_evaluator_replanning', 'no_plan_registry', 'no_skill_registry')
MODEL = 'gpt-5.1'
JUDGE = 'claude-sonnet-4-5-20250929'
# Keep the native graph bounds; impose no additional generation budgets.
LIMITS = dict(graph_steps=200, execution_steps=160)
PROMPT = (
    'I have provided a spatial transcriptomics dataset in '
    'library/datasets/dataset_lohoff_et_al_seqfish.h5ad. Create a violin plot showing '
    'the t-statistic for each gene and cell type corresponding to a measure of the '
    'degree of residual transcriptional heterogeneity explained by space. Sort the '
    'plot by average t-statistic. Scale the y-axis appropriately so that the violins '
    'are completely visible. The file project/uploads/instructions_lohoff-2e.md '
    'contains the specific methodology to use for the analysis. A reference image '
    'is included in project/uploads/reference_lohoff-2e.png. Make the plot as close '
    'as possible to the reference. Save the final reproduced figure as '
    'project/outputs/figures/final_figure.png, its plotted numerical data as '
    'project/outputs/tables/plotted_data.csv, and the analysis code and a report '
    'under project/outputs. Use random seed 0 for stochastic analysis operations. '
    'Work only with supplied inputs and files created in this workspace; do not '
    'retrieve prior reproductions. Generate the figure from analysis of the dataset, '
    'never by copying or transforming the reference pixels.'
)
EXECUTION_NOTE = '''
Benchmark execution environment: use the file tools to inspect and edit files.
The execute tool accepts Python commands only: python3 script.py [arguments],
python3 -c 'code', or python3 - <<'PY' ... PY. Calls are fresh processes.
Use installed packages; package installation, networking and arbitrary shell
commands are unavailable equally in every condition. Python subprocesses can
read this workspace and installed packages, and write only inside the workspace.
Use Python for filesystem operations instead of shell ls/cp/mkdir commands.
Keep all files under project/outputs. The common final filename is
project/outputs/figures/final_figure.png. External benchmark judge scores are
unavailable during generation. You may inspect the supplied reference image.
'''


def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, default=str) + '\n'); tmp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def credentials(required=('OPENAI_API_KEY', 'ANTHROPIC_API_KEY')):
    """Read only literal credential assignments from the previously authorized source."""
    sources = [Path.home() / '.bashrc']
    if os.environ.get('TISSUEAGENT_BENCHMARK_CREDENTIAL_FILE'):
        sources.append(Path(os.environ['TISSUEAGENT_BENCHMARK_CREDENTIAL_FILE']))
    for source in sources:
        if not source.is_file():
            continue
        for line in source.read_text().splitlines():
            m = re.match(r'\s*(?:export\s+)?(OPENAI_API_KEY|ANTHROPIC_API_KEY|OPENROUTER_API_KEY)\s*=\s*(.*)', line)
            if not m or os.environ.get(m[1]):
                continue
            try:
                parts = shlex.split(m[2], comments=True)
            except ValueError:
                continue
            if len(parts) == 1 and '$' not in parts[0] and '`' not in parts[0]:
                os.environ[m[1]] = parts[0]
    if not all(os.environ.get(k) for k in required):
        raise RuntimeError('The configured generation/judging credentials are unavailable')


def python_command(command):
    """Parse Python invocations without executing shell syntax or substitutions."""
    command = command.strip()
    m = re.fullmatch(r"(?:python3?|python3\.\d+)\s+-?\s*<<\s*['\"]?(\w+)['\"]?\s*\n(.*)\n\1\s*", command, re.S)
    if m:
        return ['-c', m[2]]
    parts = shlex.split(command)
    if not parts or not re.fullmatch(r'python(?:3(?:\.\d+)?)?', parts[0]):
        raise ValueError('Use a Python command; shell operations are unavailable')
    if any(x in {';', '&&', '||', '|', '>', '>>', '<', '&'} for x in parts):
        raise ValueError('Shell operators are unavailable; use Python code')
    if len(parts) < 2 or parts[1] in {'-m', '-S', '-I', '-E'}:
        raise ValueError('Use python3 script.py or python3 -c code')
    return parts[1:]


def prepare(out, source_from=None):
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite {out}')
    source_repo = REPO
    input_dir = REPO / 'demo/data'
    if source_from is not None:
        source_from = source_from.resolve()
        previous = json.loads((source_from / 'manifest.json').read_text())
        for directory, key in (('source', 'source_hashes'), ('inputs', 'input_hashes')):
            for rel, expected in previous[key].items():
                if sha(source_from / directory / rel) != expected:
                    raise RuntimeError(f'Frozen {directory} changed: {rel}')
        source_repo = source_from / 'source'
        input_dir = source_from / 'inputs'
    out.mkdir(parents=True)
    frozen = out / 'source'
    ignore = shutil.ignore_patterns('__pycache__', '.git', '*.pyc', '.env', '.env.*',
                                    'node_modules', 'cached_skills')
    for directory in ('src', 'knowledge'):
        shutil.copytree(source_repo / directory, frozen / directory, ignore=ignore)
    (frozen / 'benchmark').mkdir()
    for name in ('run_lohoff_architecture_pilot.py', 'lohoff_execution_guard.py'):
        shutil.copy2(REPO / 'benchmark' / name, frozen / 'benchmark' / name)
    inp = out / 'inputs'; inp.mkdir()
    for name in ('dataset_lohoff_et_al_seqfish.h5ad', 'reference_lohoff-2e.png',
                 'instructions_lohoff-2e.md'):
        shutil.copy2(input_dir / name, inp / name)
    manifest = dict(created=now(), panel='Lohoff 2E', arms=list(ARMS), seed=0,
                    model=MODEL, reasoning_effort='high', sampling='provider default; seed=0',
                    judge=JUDGE, judge_replicates=1, limits=LIMITS, prompt=PROMPT,
                    source_from=str(source_from) if source_from else None,
                    budget_policy='No custom token, response-token, call-count, or generation wall-time caps; native graph, retry, and tool timeout settings apply',
                    coding_agent='native DeepAgent coding implementation',
                    execution='same restricted Python execution backend in all conditions',
                    nested_delegation='DeepAgent task delegation disabled equally; native TissueAgent specialist routing retained',
                    source_hashes={str(p.relative_to(frozen)): sha(p) for p in frozen.rglob('*') if p.is_file()},
                    input_hashes={p.name: sha(p) for p in inp.iterdir()},
                    output_selection='exact final_figure.png only; no best-of-attempt selection',
                    failure_scoring='missing/unreadable/copied-reference figure: judge=0; image metrics NA',
                    limitations=['one seed, one panel; no variability or generalization estimate',
                                 'No Evaluator/replanning is a combined ablation',
                                 'skill removal removes guidance and bundled helpers',
                                 'native unrestricted shell is replaced equally in all arms',
                                 'a one-step plan may weakly exercise shared-state coordination',
                                 'image judgments do not verify intermediate numerical correctness'])
    dump(out / 'manifest.json', manifest)
    dump(out / 'status.json', dict(status='prepared', completed=[], running=[], updated=now()))
    print(json.dumps(dict(output=str(out), status='prepared', source_files=len(manifest['source_hashes']))))


class ResponseTruncated(BaseException):
    """Stop the attempt without allowing tool-retry wrappers to hide truncation."""


class StudyStopped(BaseException):
    """Cooperative stop for a background study, without requiring OS signals."""


def check_response_complete(message, generation_info=None):
    """Detect provider truncation even when the graph would otherwise return normally."""
    metadata = {**(generation_info or {}), **(getattr(message, 'response_metadata', None) or {})}
    reason = metadata.get('finish_reason') or metadata.get('stop_reason')
    details = metadata.get('incomplete_details') or {}
    if reason in {'length', 'max_tokens', 'max_output_tokens'} or details.get('reason') == 'max_output_tokens':
        raise ResponseTruncated(f'Model response truncated: {reason or details["reason"]}')


def worker(out, arm, offline=False):
    manifest = json.loads((out / 'manifest.json').read_text())
    model_config = manifest.get('model_config')
    model_id = manifest.get('model', MODEL)
    seed = manifest.get('seed', 0)
    prompt = manifest.get('prompt', PROMPT)
    if type(seed) is not int or not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('A worker requires an integer seed and a nonempty task prompt')
    random.seed(seed)
    case = out / ('preflight' if offline else 'runs') / arm
    if case.exists():
        raise FileExistsError(case)
    case.mkdir(parents=True)
    source = out / 'source'
    os.environ.update(TISSUEAGENT_STATE_ROOT=str(case / 'state'),
                      TISSUEAGENT_CODING_AGENT='deepagent',
                      TISSUEAGENT_REASONING_EFFORT='high',
                      TISSUEAGENT_RECURSION_LIMIT=str(LIMITS['graph_steps']),
                      TISSUEAGENT_EXECUTOR_RECURSION_LIMIT=str(LIMITS['execution_steps']))
    if model_config:
        for role in ('ORCHESTRATION', 'WORKER'):
            os.environ[f'TISSUEAGENT_{role}_REASONING_EFFORT'] = model_config.get('reasoning_effort') or 'none'
    workspace = case / 'state/workspace'
    for name in ('project/outputs', 'project/uploads', 'library/datasets', 'project/skills', '.cache'):
        (workspace / name).mkdir(parents=True)
    os.environ.update(MPLCONFIGDIR=str(workspace / '.cache/mpl'),
                      XDG_CACHE_HOME=str(workspace / '.cache'),
                      NUMBA_CACHE_DIR=str(workspace / '.cache/numba'))
    for p in (out / 'inputs').iterdir():
        dest = manifest.get('input_destinations', {}).get(p.name)
        if dest is None:
            dest = 'library/datasets' if p.suffix == '.h5ad' else 'project/uploads'
        shutil.copy2(p, workspace / dest / p.name)
    sys.path[:0] = [str(source / 'src'), str(source)]
    required = (model_config['credential_env'],) if model_config else ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY')
    credentials(required)
    if model_config:
        # A non-OpenAI condition must not silently use an OpenAI-only specialist.
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY'):
            if key not in required:
                os.environ.pop(key, None)
    import knowledge
    no_skills = arm in {'no_skill_registry', 'single_react_no_skills'}
    if no_skills:
        knowledge.SKILLS_DIR = case / 'empty_skills'; knowledge.SKILLS_DIR.mkdir()
    if arm == 'no_plan_registry':
        knowledge.PLANS_DIR = case / 'empty_plans'; knowledge.PLANS_DIR.mkdir()

    import models
    if model_config:
        spec = models.ModelSpec(id=model_id, provider=model_config['provider'],
            api_model=model_config['api_model'], label=model_config['label'],
            reasoning_effort=model_config.get('reasoning_effort'))
        models._MODELS_BY_ID[model_id] = spec
        # Web search would introduce a second LLM and author-code access.
        # All models receive the same offline task and the same disabled tool.
        from agents.agent_registry.searcher_agent.tools_impl.openai_web_search_tool import OpenAIWebSearchEngine
        OpenAIWebSearchEngine.run = lambda self, *args, **kwargs: 'Web search is disabled for this benchmark; use the supplied local inputs.'
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, message_to_dict
    from langgraph.types import Command
    from langchain.agents.middleware import AgentMiddleware, hook_config
    import deepagents
    import deepagents.backends
    from deepagents.backends.protocol import ExecuteResponse

    started = time.monotonic()
    counts = dict(llm_calls=0, input_tokens=0, output_tokens=0, tool_calls=0,
                  execution_errors=0, execution_calls=0, local_failure_stops=0,
                  manager_calls=0, evaluator_calls=0, manager_retries=0,
                  cached_input_tokens=0, reasoning_tokens=0)
    lock = threading.RLock()
    calls = {}

    def event(kind, **fields):
        with lock:
            with (case / 'events.jsonl').open('a') as f:
                f.write(json.dumps(dict(time=now(), event=kind, **fields), default=str) + '\n')

    class Recorder(BaseCallbackHandler):
        raise_error = True
        def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
            if model_config and any((out.parents[1] / name).exists() for name in ('STOP.json', 'INVALIDATED.json')):
                raise StudyStopped('Background study stop requested')
            with lock:
                counts['llm_calls'] += 1
                calls[str(run_id)] = counts['llm_calls']
                dump(case / 'calls' / f'{counts["llm_calls"]:03d}_input.json',
                     [[message_to_dict(m) for m in group] for group in messages])
                dump(case / 'heartbeat.json', dict(updated=now(), counts=counts, status='model_call'))
        def on_llm_end(self, response, *, run_id, **kwargs):
            with lock:
                for group in response.generations:
                    for gen in group:
                        msg = gen.message
                        usage = getattr(msg, 'usage_metadata', None) or {}
                        counts['input_tokens'] += usage.get('input_tokens', 0)
                        counts['output_tokens'] += usage.get('output_tokens', 0)
                        counts['cached_input_tokens'] += (usage.get('input_token_details') or {}).get('cache_read', 0)
                        counts['reasoning_tokens'] += (usage.get('output_token_details') or {}).get('reasoning', 0)
                        dump(case / 'calls' / f'{calls.get(str(run_id),0):03d}_output.json', message_to_dict(msg))
                dump(case / 'heartbeat.json', dict(updated=now(), counts=counts, status='working'))
                for group in response.generations:
                    for gen in group:
                        check_response_complete(gen.message, gen.generation_info)
        def on_llm_error(self, error, *, run_id, **kwargs):
            event('model_error', error=type(error).__name__, message=str(error)[:500])

    recorder = Recorder()
    original_build = models.build_chat_model
    def build_model(model_id, **kwargs):
        kwargs.update(callbacks=[recorder], max_retries=2)
        if model_config:
            if model_id != manifest['model']:
                raise ValueError('Unexpected backbone requested: ' + model_id)
            kwargs.update(model_config.get('constructor_overrides', {}))
            event('model_configuration', model_id=model_id, role=kwargs.get('role'),
                  provider=model_config['provider'], api_model=model_config['api_model'])
        else:
            kwargs['parallel_tool_calls'] = False
        return original_build(model_id, **kwargs)
    models.build_chat_model = build_model
    models.set_selection(model_id, model_id)
    models.set_model_seed(model_config.get('request_seed') if model_config else seed)
    if model_config and model_config['provider'] == 'openrouter':
        import fcntl
        from langchain_openai import ChatOpenAI
        original_generate = ChatOpenAI._generate
        def serialized_generate(self, *args, **kwargs):
            while True:
                if any((out.parents[1]/name).exists() for name in ('STOP.json','INVALIDATED.json')):
                    raise StudyStopped('Study stopped while waiting for OpenRouter')
                with (out.parents[1]/'openrouter_request.lock').open('a') as stream:
                    fcntl.flock(stream, fcntl.LOCK_EX)
                    try:
                        return original_generate(self, *args, **kwargs)
                    except Exception as exc:
                        # Billing/concurrency outages are infrastructure, not
                        # scientific failures. Preserve the attempt and await funding.
                        if getattr(exc, 'status_code', None) != 402:
                            raise
                        event('waiting_for_openrouter_credits', error=str(exc)[:400])
                time.sleep(30)
        ChatOpenAI._generate = serialized_generate

    guard_dir = workspace / '.python_guard'; guard_dir.mkdir()
    shutil.copy2(source / 'benchmark/lohoff_execution_guard.py', guard_dir / 'sitecustomize.py')
    child_env = {k:v for k,v in os.environ.items() if k in {'PATH','LANG','LC_ALL','SYSTEMROOT'}}
    child_env.update(PYTHONPATH=str(guard_dir), PYTHONDONTWRITEBYTECODE='1',
                     LOHOFF_WORKSPACE=str(workspace),
                     LOHOFF_REPOSITORY=manifest.get('repository_root', str(out.parents[1])),
                     LOHOFF_ENVIRONMENT=str(Path(sys.executable).parent.parent),
                     MPLCONFIGDIR=str(workspace / '.cache/mpl'),
                     NUMBA_CACHE_DIR=str(workspace / '.cache/numba'),
                     XDG_CACHE_HOME=str(workspace / '.cache'),
                     TMPDIR=str(workspace / '.cache'), OPENBLAS_NUM_THREADS='1',
                     OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')

    OriginalBackend = deepagents.backends.LocalShellBackend
    class IsolatedBackend(OriginalBackend):
        def execute(self, command, *, timeout=None):
            counts['execution_calls'] += 1
            idx = counts['execution_calls']
            event('execute_start', number=idx, command=command)
            try:
                args = python_command(command)
                done = subprocess.run([sys.executable, *args], cwd=workspace, env=child_env,
                                      text=True, capture_output=True,
                                      timeout=timeout if timeout is not None else self._default_timeout)
                text = done.stdout + ('\n[stderr]\n'+done.stderr if done.stderr else '')
                code = done.returncode
            except Exception as exc:
                text = f'{type(exc).__name__}: {exc}'; code = 1
            if code:
                counts['execution_errors'] += 1
                text += f'\nExit code: {code}'
            dump(case / 'execution' / f'{idx:03d}.json', dict(command=command, output=text, exit_code=code))
            event('execute_end', number=idx, exit_code=code)
            return ExecuteResponse(output=text[-24000:], exit_code=code, truncated=len(text)>24000)
    deepagents.backends.LocalShellBackend = IsolatedBackend

    class Controls(AgentMiddleware):
        @hook_config(can_jump_to=['end'])
        def before_model(self, state, runtime):
            if arm != 'no_local_retry':
                return None
            last = state['messages'][-1]
            if getattr(last, 'type', '') == 'tool' and getattr(last, 'name', '') == 'execute':
                text = str(last.content)
                if re.search(r'Exit code:\s*[1-9]\d*', text) or text.startswith('Error:'):
                    counts['local_failure_stops'] += 1
                    event('local_failure_stop', error=text[-1500:])
                    return {'messages':[AIMessage(content='Execution failed; local retry is disabled. '
                                                  'Returning the failure to the Manager.\n'+text[-3000:])],
                            'jump_to':'end'}
            return None
        def wrap_model_call(self, request, handler):
            # Native specialist routing remains; hidden nested delegation would
            # bypass the local-retry boundary and make ReAct more than one agent.
            request = request.override(tools=[t for t in request.tools if getattr(t,'name','')!='task'])
            return handler(request)
        def wrap_tool_call(self, request, handler):
            with lock:
                counts['tool_calls'] += 1
            if request.tool_call['name']=='task':
                raise RuntimeError('Nested DeepAgent delegation is disabled in this pilot')
            return handler(request)

    original_deep = deepagents.create_deep_agent
    def create_deep(**kwargs):
        kwargs['middleware'] = [*kwargs.get('middleware', []), Controls()]
        kwargs['system_prompt'] = str(kwargs.get('system_prompt','')) + EXECUTION_NOTE
        return original_deep(**kwargs)
    deepagents.create_deep_agent = create_deep

    from queue import Queue
    from graph import graph as gm
    from server.plan_store import plan_store, serialize_plan
    from agents import agent_tools
    from agents.manager_agent import prompt as manager_prompt
    from agents.agent_defns import AgentDefns, ReActAgent
    import agents.agent_registry.coding_agent.model as coding
    import agents.agent_utils as au
    from agents.recruiter_agent.prompt import get_skill_metadata
    from agents.planner_agent.prompt import _build_template_index
    from agents.agent_registry.coding_agent.prompt import CodingAgentPrompt
    plan_store.reset()

    # Every native model/tool remains available except the declared intervention.
    # Keep all on-disk raw prompts and source in the frozen directory for review.
    original_node = gm.create_agent_node
    original_tools = gm.create_tool_node
    manager_step_tools = {}
    old_step_factory = gm.create_manager_step_tools
    def step_tools(invocations):
        result = old_step_factory(invocations)
        manager_step_tools.update({t.name:t for t in result})
        return result
    gm.create_manager_step_tools = step_tools

    initial_doc = [None]
    if arm == 'no_evolving_plan':
        # Private scheduler state is never rendered as an evolving shared artifact.
        private_doc = [copy.deepcopy(plan_store.read())]
        original_write = plan_store.write
        def private_read():
            return copy.deepcopy(private_doc[0])
        def private_write(doc):
            clean = copy.deepcopy(doc)
            for step in clean.steps:
                step.actual_outputs=[]
            private_doc[0] = clean
            if initial_doc[0] is None and clean.steps and all(s.assigned_agent for s in clean.steps):
                initial_doc[0] = copy.deepcopy(clean)
                original_write(initial_doc[0])
                event('initial_plan_frozen')
            dump(case / 'private_scheduler.json', serialize_plan(clean))
            return clean.to_markdown()
        plan_store.read = private_read; plan_store.write = private_write
        old_format = manager_prompt._format_plan
        manager_prompt._format_plan = lambda doc: old_format(initial_doc[0] or doc)
        gm.filter_for_manager = lambda _id: lambda messages: messages

    def node_factory(agent_node_id, agent_model, prompt, tool_node_id, exit_node=None,
                     state_update_fn=None, message_filter_fn=None, budget_guard=None):
        if agent_node_id == 'evaluator_agent' and arm == 'no_evaluator_replanning':
            def bypass(state):
                event('evaluator_bypassed')
                return Command(goto='reporter_agent', update={'messages':[AIMessage(
                    content='Internal evaluation and global replanning are disabled; report the available outputs.',
                    name='evaluator_bypass')]})
            return bypass
        if agent_node_id == 'manager_agent' and arm == 'no_manager':
            def dispatch(state):
                messages=[]
                while True:
                    doc=plan_store.read()
                    target=next((s for s in doc.steps if s.id==doc.current_step_id),None)
                    if target is None:
                        break
                    instruction=target.description or target.title
                    event('fixed_dispatch', step=target.id, assigned_agent=target.assigned_agent)
                    result=manager_step_tools['next_step'].invoke(dict(task_instructions=instruction,
                                                        expected_artifacts=list(target.expected_artifacts)))
                    messages.append(AIMessage(content=f'Step {target.id}: {result}',name='fixed_dispatcher'))
                return Command(goto='evaluator_agent',update={'messages':messages or [AIMessage(
                    content='No steps available to dispatch.',name='fixed_dispatcher')]})
            return dispatch
        base=original_node(agent_node_id,agent_model,prompt,tool_node_id,exit_node,
                           state_update_fn,message_filter_fn,budget_guard)
        def invoke(state):
            event('role_enter', role=agent_node_id)
            if agent_node_id=='manager_agent':counts['manager_calls']+=1
            if agent_node_id=='evaluator_agent':counts['evaluator_calls']+=1
            if arm=='no_local_retry' and agent_node_id not in {
                'planner_agent','recruiter_agent','manager_agent','evaluator_agent','reporter_agent'}:
                last=state['messages'][-1]
                if getattr(last,'type','')=='tool' and str(last.content).startswith('Error'):
                    counts['local_failure_stops']+=1
                    return Command(goto='__end__',update={'messages':[AIMessage(
                        content='Local retry disabled; returning tool failure: '+str(last.content),name=agent_node_id)]})
            return base(state)
        return invoke
    gm.create_agent_node=node_factory

    def tool_factory(tools):
        base=original_tools(tools)
        def invoke(state):
            tool_calls=state['messages'][-1].tool_calls
            counts['tool_calls']+=len(tool_calls)
            counts['manager_retries']+=sum(t['name']=='retry_step' for t in tool_calls)
            for call in tool_calls:event('native_tool',name=call['name'],args=call['args'])
            return base(state)
        return invoke
    gm.create_tool_node=tool_factory

    if no_skills:
        assert get_skill_metadata()=={}
        gm.RecruiterAgent=copy.copy(gm.RecruiterAgent)
        old_recruiter_prompt=gm.RecruiterAgent.prompt
        gm.RecruiterAgent.prompt=lambda registry: old_recruiter_prompt(registry)+(
            '\nSkill Registry access is disabled for this run. Assign skills=[] to every step. '
            'Agents must derive execution details from the supplied task and methods; '
            'a template naming a skill does not make that skill available.')
        gm.RecruiterAgent.tools=[t for t in gm.RecruiterAgent.tools if t.name!='read_skill']
    if arm=='no_plan_registry':
        assert _build_template_index()==''
        gm.PlannerAgent=copy.copy(gm.PlannerAgent)
        gm.PlannerAgent.tools=[t for t in gm.PlannerAgent.tools if t.name!='read_template']
    if arm=='no_evolving_plan':
        original_write_tool=agent_tools.write_tool.func
        def write_without_plan(*args,**kwargs):
            if 'plan.md' in str(args)+str(kwargs):
                return 'Error: the initial plan is immutable in this condition; communicate revisions in messages.'
            return original_write_tool(*args,**kwargs)
        agent_tools.write_tool.func=write_without_plan

    # Freeze a graph even during preflight, detecting missing constructors/imports.
    queue=Queue()
    if arm=='single_react_no_skills':
        from agents.planner_agent.tools_impl.read_template_tool import read_template_tool
        combined = CodingAgentPrompt(sandbox_enabled=False).replace('{{skill_prompt}}',coding._SHELL_EXECUTION_NOTE)
        combined += ('\nYou are one ReAct agent. Perform planning, execution, verification, correction, '
                     'and reporting yourself without delegation. No skills are available. '
                     'Plan-template registry:\n'+_build_template_index())
        combined += ('\nPlan the complete analysis before execution; you may retrieve an appropriate '
                     'template or plan de novo. A template mentioning a skill does not grant access '
                     'to it. Inspect supplied methods and data, execute the analysis, track intermediate '
                     'files, diagnose and repair failures, check expected artifacts and scientific '
                     'consistency, revise your approach if needed, and report available results with '
                     'limitations and reproducible code. Assess critical scientific or execution '
                     'failures separately from minor presentation issues. Do not emit orchestration '
                     'routing headers or delegate: perform these responsibilities in this conversation.')
        # Union of native specialist analysis tools, with duplicate names collapsed.
        analysis_tools={t.name:t for a in AgentDefns if isinstance(a,ReActAgent) for t in a.tools}
        analysis_tools[read_template_tool.name]=read_template_tool
        graph=create_deep(model=models.build_chat_model(model_id,role='worker'),
                          tools=list(analysis_tools.values()), system_prompt=au.substitute_shared_prompts(combined),
                          backend=IsolatedBackend(root_dir=str(workspace),virtual_mode=True,inherit_env=False))
    else:
        graph=gm.create_tissueagent_graph(queue,lambda m:m,
                    allow_targeted_replanning=arm!='no_evaluator_replanning').compile()
    config=dict(arm=arm,model=model_id,seed=seed,panel=manifest.get('panel'),no_skills=no_skills,
                registered_skills=list(get_skill_metadata()),
                template_index=_build_template_index(),
                domain_agents=[a.id for a in AgentDefns],limits=LIMITS,
                model_spec=str(models.get_model_spec(model_id)), model_config=model_config)
    dump(case / 'condition.json',config)
    if offline:
        # Exercise the actual callbacks beyond the former caps without API calls.
        from langchain_core.outputs import ChatGeneration, LLMResult
        counts.update(llm_calls=101, input_tokens=400000, tool_calls=251)
        recorder.on_chat_model_start({}, [[HumanMessage('offline budget check')]], run_id='offline')
        assert counts['llm_calls'] == 102
        Controls().wrap_tool_call(type('Request', (), {'tool_call': {'name': 'read_file'}})(), lambda _: None)
        assert counts['tool_calls'] == 252
        truncated = AIMessage(content='', response_metadata={'finish_reason': 'length'},
                              usage_metadata={'input_tokens': 2, 'output_tokens': 8192, 'total_tokens': 8194})
        try:
            recorder.on_llm_end(LLMResult(generations=[[ChatGeneration(message=truncated)]]), run_id='offline')
        except ResponseTruncated:
            pass
        else:
            raise AssertionError('Truncated responses must not be marked completed')
        assert counts['output_tokens'] == 8192
        if not model_config:
            payload = models.build_chat_model(model_id)._get_request_payload([HumanMessage('offline payload check')])
            assert 'max_completion_tokens' not in payload and 'max_tokens' not in payload
            assert payload['seed'] == seed
        counts.update({name: 0 for name in counts})
        shutil.rmtree(case / 'calls')
        (case / 'heartbeat.json').unlink()
        calls.clear()
        failed=ToolMessage(content='Traceback: execution failed\nExit code: 1',name='execute',tool_call_id='test')
        action=Controls().before_model({'messages':[failed]},None)
        assert bool(action and action.get('jump_to')=='end') == (arm=='no_local_retry')
        counts['local_failure_stops']=0
        ok=ToolMessage(content='Complete\nExit code: 0',name='execute',tool_call_id='test')
        assert Controls().before_model({'messages':[ok]},None) is None
        if arm=='no_evaluator_replanning':
            assert node_factory('evaluator_agent',None,'','')(dict(messages=[])).goto=='reporter_agent'
        if arm=='no_manager':
            assert node_factory('manager_agent',None,'','')(dict(messages=[])).goto=='evaluator_agent'
        if arm=='no_evolving_plan':
            from server.plan_store import PlanDocument, PlanStep
            doc=PlanDocument(user_request='offline check',steps=[PlanStep(
                id=1,title='Initial task',assigned_agent='coding_agent')])
            plan_store.write(doc)
            frozen_text=plan_store.path.read_text()
            doc.steps[0].title='Revised task';doc.steps[0].actual_outputs=['hidden.csv']
            plan_store.write(doc)
            assert plan_store.path.read_text()==frozen_text
            assert plan_store.read().steps[0].actual_outputs==[]
            assert 'Initial task' in manager_prompt._format_plan(plan_store.read())
            assert 'Revised task' not in manager_prompt._format_plan(plan_store.read())
        # Execute the actual child policy: ordinary scientific Python works, leakage fails.
        allowed=subprocess.run([sys.executable,'-c','import numpy; print(numpy.arange(3).sum())'],
                               env=child_env,cwd=workspace,capture_output=True,text=True)
        forbidden=subprocess.run([sys.executable,'-c',f'open({str(out / "manifest.json")!r}).read()'],
                                 env=child_env,cwd=workspace,capture_output=True,text=True)
        assert allowed.returncode==0,allowed.stderr
        assert forbidden.returncode!=0 and 'Benchmark isolation' in forbidden.stderr
        assert counts['llm_calls']==0
        dump(case/'result.json',dict(status='offline_preflight_passed',policy_enforced=True,counts=counts))
        return
    status='completed'; error=None; state=None
    try:
        state=graph.invoke({'messages':[HumanMessage(prompt)]},config={'recursion_limit':LIMITS['graph_steps']})
    except StudyStopped as exc:
        status='stopped';error=str(exc)
    except ResponseTruncated as exc:
        status='response_truncated';error=str(exc)
    except Exception as exc:
        status='failed';error=f'{type(exc).__name__}: {exc}'
        (case/'traceback.txt').write_text(traceback.format_exc())
    if state is not None:
        dump(case/'final_messages.json',[message_to_dict(m) for m in state.get('messages',[])])
    dump(case/'final_plan.json',serialize_plan(plan_store.read()))
    dump(case/'result.json',dict(arm=arm,status=status,error=error,counts=counts,
                                elapsed_seconds=time.monotonic()-started,finished=now()))


def score_all(out):
    from PIL import Image, ImageChops
    import anthropic
    credentials()
    client=anthropic.Anthropic(timeout=180,max_retries=2)
    rows=[]; ordering=list(ARMS); random.Random(0).shuffle(ordering)
    dump(out/'evaluation/blind_order.json',{f'output_{i+1:02d}':a for i,a in enumerate(ordering)})
    scorer=out/'source/knowledge/skills/figure-reproduce/scripts/compare_figures.py'
    reference=out/'inputs/reference_lohoff-2e.png'
    rubric=('Evaluate this reproduced scientific figure against the reference. Image 1 is the '
            'published reference; image 2 is the generated output. The system identity is hidden. '
            'Do not infer the system identity. Score each dimension from 0 to 10: visual_quality '
            '(legibility/rendering), visual_style_match (plot type/layout/colors), instruction_fidelity '
            '(requested plot elements/labels), data_fidelity (visible distributions/order/axis ranges), '
            'scientific_fidelity (same qualitative biological interpretation). Image-only judgments '
            'cannot verify the underlying calculations. Return JSON only: {"scores":{dimension:number},'
            '"rationale":{dimension:string},"limitations":string}.\nTask:\n'+PROMPT+
            '\nMethods:\n'+(out/'inputs/instructions_lohoff-2e.md').read_text())
    def img(path):
        return {'type':'image','source':{'type':'base64','media_type':'image/png',
                                        'data':base64.b64encode(path.read_bytes()).decode()}}
    for idx,arm in enumerate(ordering):
        case=out/'runs'/arm
        result=json.loads((case/'result.json').read_text())
        fig=case/'state/workspace/project/outputs/figures/final_figure.png'
        dest=out/'evaluation'/f'output_{idx+1:02d}';dest.mkdir(parents=True,exist_ok=True)
        row=dict(arm=arm,run=result,figure_produced=False,ssim=None,phash_similarity=None,
                 orb_matches=None,llm_judge=0,judge_status='no_figure')
        try:
            with Image.open(fig) as im: im.verify()
            if sha(fig)==sha(reference):raise ValueError('Output is a byte-identical copy of reference')
            with Image.open(fig) as a, Image.open(reference) as b:
                if a.size==b.size and ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None:
                    raise ValueError('Output pixels are identical to reference')
            row['figure_produced']=True
        except (OSError,ValueError) as exc:
            row['figure_issue']=str(exc); rows.append(row);continue
        r=subprocess.run([sys.executable,str(scorer),str(reference),str(fig),'--json',
                          '--out',str(dest/'comparison.png')],capture_output=True,text=True,timeout=180)
        (dest/'scorer_stdout.txt').write_text(r.stdout);(dest/'scorer_stderr.txt').write_text(r.stderr)
        try:
            metrics=json.loads(r.stdout)
            dump(dest/'metrics.json',metrics)
            row.update(ssim=metrics['ssim'],phash_similarity=1-metrics['phash_hamming']/64,
                       orb_matches=metrics['orb_good_matches'])
        except (ValueError,KeyError):row['metric_error']='Scorer output was unavailable; inspect saved logs'
        try:
            response=client.messages.create(model=JUDGE,max_tokens=2000,extra_body={'temperature':0},
                    messages=[{'role':'user','content':[{'type':'text','text':rubric},img(reference),img(fig)]}])
            dump(dest/'judge_raw.json',response.model_dump())
            txt=''.join(b.text for b in response.content if getattr(b,'type','')=='text')
            match=re.search(r'\{.*\}',txt,re.S); judged=json.loads(match[0])
            names=['visual_quality','visual_style_match','instruction_fidelity','data_fidelity','scientific_fidelity']
            vals=[judged['scores'][n] for n in names]
            if not all(isinstance(v,(int,float)) and 0<=v<=10 for v in vals):raise ValueError('Invalid judge scores')
            row.update(llm_judge=sum(vals)/5,judge_status='scored',judge_dimensions=judged['scores'])
            dump(dest/'judge.json',judged)
        except Exception as exc:
            row.update(llm_judge=None,judge_status='failed',judge_error=f'{type(exc).__name__}: {exc}')
        rows.append(row);dump(out/'results.json',rows)
    rows.sort(key=lambda r:ARMS.index(r['arm']));dump(out/'results.json',rows)
    lines=['# Lohoff 2E architecture pilot — seed 0','',
           'One attempt per condition; GPT-5.1 generation and independent Claude judging. '
           'This pilot does not estimate variability or verify intermediate numerical correctness.','',
           '| Condition | Figure | SSIM | pHash similarity | ORB matches | LLM judge /10 | Minutes |',
           '|---|---:|---:|---:|---:|---:|---:|']
    def fmt(v):return 'NA' if v is None else f'{v:.3f}'
    for r in rows:
        lines.append(f'| {r["arm"]} | {int(r["figure_produced"])} | {fmt(r["ssim"])} | '
                     f'{fmt(r["phash_similarity"])} | {r["orb_matches"]} | {fmt(r["llm_judge"])} | '
                     f'{r["run"]["elapsed_seconds"]/60:.1f} |')
    lines+=['','Failed attempts remain included. Missing images receive judge=0 and image metrics NA. '
            'Judge API failures receive NA, not zero. Full traces, generated scripts, and per-arm condition manifests are retained.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


def controller(out, preflight=False):
    credentials()
    manifest=json.loads((out/'manifest.json').read_text())
    for rel,expected in manifest['source_hashes'].items():
        if sha(out/'source'/rel)!=expected:raise RuntimeError('Frozen source changed: '+rel)
    for rel,expected in manifest['input_hashes'].items():
        if sha(out/'inputs'/rel)!=expected:raise RuntimeError('Frozen input changed: '+rel)
    script=out/'source/benchmark/run_lohoff_architecture_pilot.py'
    completed=[]
    for arm in ARMS:
        if not preflight and not (out/'preflight'/arm/'result.json').exists():
            raise RuntimeError('All offline preflights must pass before generation')
        case=out/('preflight' if preflight else 'runs')/arm
        logs=out/'logs';logs.mkdir(exist_ok=True)
        dump(out/'status.json',dict(status='preflight' if preflight else 'running',
                                    running=[arm],completed=completed,updated=now()))
        cmd=[sys.executable,str(script),'worker','--out',str(out),'--arm',arm]
        if preflight:cmd+=['--offline']
        with (logs/(arm+('_preflight' if preflight else '')+'.log')).open('w') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            worker_started=time.monotonic()
            deadline=worker_started+180 if preflight else None
            while proc.poll() is None and (deadline is None or time.monotonic()<deadline):
                dump(out/'status.json',dict(status='preflight' if preflight else 'running',
                       running=[arm],worker_pid=proc.pid,completed=completed,updated=now()))
                time.sleep(1 if preflight else 10)
            if proc.poll() is None:
                import signal
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        if not (case/'result.json').exists():
            if preflight:raise RuntimeError(f'Offline preflight failed: {arm}; inspect {logs}')
            heartbeat=json.loads((case/'heartbeat.json').read_text()) if (case/'heartbeat.json').exists() else {}
            dump(case/'result.json',dict(arm=arm,status='worker_failed',exit_code=proc.returncode,
                                        counts=heartbeat.get('counts',{}),elapsed_seconds=time.monotonic()-worker_started,finished=now()))
        completed.append(arm)
    if preflight:
        dump(out/'status.json',dict(status='preflight_passed',completed=[],running=[],updated=now()))
        return
    dump(out/'status.json',dict(status='scoring',completed=completed,running=[],updated=now()))
    score_all(out)
    dump(out/'status.json',dict(status='complete',completed=completed,running=[],updated=now()))


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','preflight','controller','background','worker','score'])
    p.add_argument('--out',type=Path,required=True);p.add_argument('--arm',choices=ARMS);p.add_argument('--offline',action='store_true')
    p.add_argument('--source-from',type=Path,help='Reuse a previous run\'s verified frozen src, knowledge, and inputs with the current harness')
    a=p.parse_args();out=a.out.resolve()
    if a.action=='prepare':prepare(out,a.source_from)
    elif a.action=='worker':worker(out,a.arm,a.offline)
    elif a.action=='score':score_all(out)
    elif a.action=='background':
        try:
            controller(out,preflight=True)
            controller(out)
        except BaseException as exc:
            dump(out/'status.json',dict(status='blocked',error=f'{type(exc).__name__}: {exc}',updated=now()))
            raise
    else:controller(out,preflight=a.action=='preflight')


if __name__=='__main__':main()
