"""Offline checks for the no-registry execution path."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from dataclasses import replace
from queue import Queue
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
ROOT_STATE = tempfile.mkdtemp(prefix="native-orchestration-test-")
os.environ["TISSUEAGENT_STATE_ROOT"] = ROOT_STATE
os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/tissueagent-native-test-cache/mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp/tissueagent-native-test-cache")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from graph import graph as module
from graph.message_filters import filter_for_execution_phase

class Fake(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        assert not any(t.name.startswith("transfer_to_") for t in tools)
        return self

class NativeTests(unittest.TestCase):
    def test_explicit_empty_registry_required(self):
        with self.assertRaises(ValueError):
            module.create_tissueagent_graph(Queue(), lambda m: m, native_execution_tools=[], native_execution_prompt="Direct execution")

    def test_execution_evidence_without_recruiter(self):
        user = HumanMessage(content="question")
        planner = AIMessage(content="plan", name="planner_agent")
        manager = AIMessage(content="", name="manager_agent", tool_calls=[{"name":"ncbi_request", "args":{}, "id":"t"}])
        evidence = ToolMessage(content="evidence", tool_call_id="t")
        history = [user, planner, manager, evidence]
        self.assertEqual(filter_for_execution_phase(history), history)

    def test_native_route_keeps_four_roles_and_zero_specialists(self):
        plan = {"user_request":"question", "steps":[{"step_number":1,"title":"Answer question","description":"Use general tools", "reasoning":"Retrieve evidence", "expected_artifacts":["project/outputs/result.json"]}], "provenance":{"template_names":[],"justification":"No template"}}
        replies = {
            "PlannerAgent": "ROUTE: PLAN\n```json\n" + json.dumps(plan) + "\n```",
            "RecruiterAgent": "Recruiter must not execute",
            "ManagerAgent": "Answer: TESTGENE",
            "EvaluatorAgent": "ROUTE: REPORT\nEVALUATION: done",
            "ReporterAgent": "Answer: TESTGENE",
        }
        replacements = {name:replace(getattr(module,name), model_ctor=lambda response=reply:Fake(responses=[AIMessage(content=response)])) for name,reply in replies.items()}
        with patch.multiple(module, **replacements), patch.object(module,"create_manager_step_tools",side_effect=AssertionError("Specialist dispatch must not be built")):
            graph = module.create_tissueagent_graph(Queue(),lambda m:m,domain_agents=[],native_execution_tools=[],native_execution_prompt="Answer directly from general tools").compile()
            state = graph.invoke({"messages":[HumanMessage(content="question")],"replan_count":0,"replan_history":[]}, {"recursion_limit":30})
        names = [getattr(m,"name",None) for m in state["messages"] if isinstance(m,AIMessage)]
        self.assertEqual(names,["planner_agent","manager_agent","evaluator_agent","reporter_agent"])

if __name__ == "__main__":
    unittest.main()
