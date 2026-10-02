"""Evidence recovery must remain independent of gold answers and fail closed."""

import copy
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from agents.agent_registry.genegpt_agent.answer_recovery import (
    extract_terminal_answer,
    recover_gene_symbol,
)

QUESTION = "Convert ENSG00000140199 to official gene symbol."
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def trace(symbol="SLC12A6"):
    return [
        {"url": BASE + "esearch.fcgi?db=gene&term=ENSG00000140199",
         "response_excerpt": json.dumps({"esearchresult": {"count": "1", "idlist": ["9990"]}})},
        {"url": BASE + "efetch.fcgi?db=gene&id=9990",
         "response_excerpt": f"\n1. {symbol}\nOfficial Symbol: {symbol} and Name: example\nID: 9990\n"},
    ]


def test_recovery_uses_linked_record_not_an_expected_symbol():
    evidence = trace("UNEXPECTED_SYMBOL")
    before = copy.deepcopy(evidence)
    result = recover_gene_symbol(QUESTION, evidence)
    assert result["answer"] == "UNEXPECTED_SYMBOL"
    assert result["ncbi_gene_id"] == "9990"
    assert result["evidence"][0]["trace_index"] == 1
    assert evidence == before


@pytest.mark.parametrize("mutation", ["wrong_question", "wrong_fetch_id", "wrong_host", "wrong_db",
                                      "multi_hit", "partial_search", "conflicting_symbol", "no_search"])
def test_unlinked_or_ambiguous_evidence_is_not_used(mutation):
    evidence = trace()
    question = QUESTION
    if mutation == "wrong_question":
        question = QUESTION.replace("140199", "139618")
    elif mutation == "wrong_fetch_id":
        evidence[1]["url"] = evidence[1]["url"].replace("9990", "675")
    elif mutation == "wrong_host":
        evidence[1]["url"] = evidence[1]["url"].replace("eutils.ncbi.nlm.nih.gov", "example.test")
    elif mutation == "wrong_db":
        evidence[1]["url"] = evidence[1]["url"].replace("db=gene", "db=omim")
    elif mutation in {"multi_hit", "partial_search"}:
        ids = ["9990", "675"] if mutation == "multi_hit" else ["9990"]
        evidence[0]["response_excerpt"] = json.dumps({"esearchresult": {"count": "2", "idlist": ids}})
    elif mutation == "conflicting_symbol":
        evidence.append(trace("OTHER")[1])
    elif mutation == "no_search":
        evidence = evidence[1:]
    assert recover_gene_symbol(question, evidence)["answer"] is None


def test_retrieved_record_before_search_is_not_linked():
    assert recover_gene_symbol(QUESTION, list(reversed(trace())))["answer"] is None


def test_complete_official_summary_and_truncated_summary():
    evidence = trace()
    evidence[1]["url"] = evidence[1]["url"].replace("efetch", "esummary")
    body = json.dumps({"result": {"uids": ["9990"], "9990": {
        "uid": "9990", "nomenclaturestatus": "Official", "nomenclaturesymbol": "SLC12A6"}}})
    evidence[1]["response_excerpt"] = body
    assert recover_gene_symbol(QUESTION, evidence)["answer"] == "SLC12A6"
    evidence[1]["response_excerpt"] = body[:-2]
    assert recover_gene_symbol(QUESTION, evidence)["answer"] is None
    evidence[1]["response"] = body
    assert recover_gene_symbol(QUESTION, evidence)["answer"] == "SLC12A6"


@pytest.mark.parametrize("text", ["", "What is the symbol of BRCA1?", "Answer: What is BRCA1?",
                                  "Answer: ", "[https://example.test]", "Answer: https://example.test",
                                  "Answer: SLC12A6\n\nQuestion: next"])
def test_invalid_terminal_outputs_are_not_answers(text):
    assert extract_terminal_answer(text) is None


def test_valid_terminal_answer():
    assert extract_terminal_answer("Answer: SLC12A6\n") == "SLC12A6"


def mock_runner(monkeypatch, tmp_path, completions, responses=()):
    import openai
    from agents.agent_registry.genegpt_agent import runner

    texts, bodies = iter(completions), iter(responses)
    prompts = []

    def create(**kwargs):
        prompts.append(kwargs["messages"][-1]["content"])
        return SimpleNamespace(choices=[{"message": {"content": next(texts)}, "finish_reason": "stop"}])

    @contextmanager
    def patch(**kwargs):
        monkeypatch.setattr(openai, "ChatCompletion", SimpleNamespace(create=create))
        yield

    monkeypatch.setattr(runner, "patch_openai_legacy_api", patch)
    monkeypatch.setattr(runner, "active_project_outputs", lambda: tmp_path)
    monkeypatch.setattr(runner, "_import_upstream_helpers", lambda: (lambda mask: "Examples\n", lambda url: next(bodies)))
    return runner, prompts


def test_runner_stops_on_linked_evidence_and_preserves_raw_completion(monkeypatch, tmp_path):
    evidence = trace()
    urls = ["[" + row["url"] + "]" for row in evidence]
    runner, _ = mock_runner(monkeypatch, tmp_path, urls, [r["response_excerpt"].encode() for r in evidence])
    result = runner.run_genegpt_question(QUESTION, request_id="test")
    assert result["status"] == "ok"
    assert result["answer"] == "SLC12A6"
    assert result["answer_source"] == "ncbi_evidence_extraction"
    assert result["raw_completion"] == urls[-1]
    assert result["num_calls"] == result["ncbi_calls"] == 2
    assert result["api_trace"][1]["response"] == evidence[1]["response_excerpt"]


def test_runner_retries_question_then_accepts_answer(monkeypatch, tmp_path):
    runner, prompts = mock_runner(monkeypatch, tmp_path, ["What is BRCA1?", "Answer: SLC12A6"])
    result = runner.run_genegpt_question(QUESTION, request_id="test")
    assert result["answer"] == "SLC12A6"
    assert result["num_calls"] == 2
    assert all(QUESTION in prompt for prompt in prompts)


def test_runner_reports_error_after_invalid_outputs_exhaust_budget(monkeypatch, tmp_path):
    runner, _ = mock_runner(monkeypatch, tmp_path, ["What is BRCA1?"] * 2)
    monkeypatch.setattr(runner, "_MAX_CALLS", 2)
    result = runner.run_genegpt_question(QUESTION, request_id="test")
    assert result["status"] == "error"
    assert result["error_type"] == "NoFinalAnswer"
    assert result["answer"] is None


def test_runner_url_at_limit_is_not_success(monkeypatch, tmp_path):
    evidence = trace()
    runner, _ = mock_runner(monkeypatch, tmp_path, ["[" + evidence[0]["url"] + "]"],
                            [evidence[0]["response_excerpt"].encode()])
    monkeypatch.setattr(runner, "_MAX_CALLS", 1)
    result = runner.run_genegpt_question(QUESTION, request_id="test")
    assert result["status"] == "error"
    assert result["answer"] is None
