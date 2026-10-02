"""Adapter that runs NCBI's GeneGPT tool-use loop from inside TissueAgent.

GeneGPT (https://github.com/ncbi/GeneGPT) teaches an LLM to answer factual
genomics questions by emitting NCBI Web API URLs (E-utilities / BLAST),
executing them for real, and feeding the responses back until it produces an
answer. Upstream ships as a *benchmark runner* (``main_turbo.py`` iterates
``data/geneturing.json``) with two integration problems:

1. No single-question entry point — the answer loop lives inside ``__main__``.
2. Its model (``code-davinci-002`` / ``gpt-3.5-turbo-16k``) is retired, and it
   uses the legacy ``openai==0.27`` ``openai.ChatCompletion.create`` convention,
   which conflicts with TissueAgent's ``openai>=1`` stack.

This adapter solves both without touching the pinned submodule:

* It **reuses the upstream's own helpers** — ``get_prompt_header`` (builds the
  few-shot prompt, making the same 7 example NCBI calls) and ``call_api``
  (executes a URL against NCBI) — imported directly from ``main_turbo``.
* It reimplements only the per-question decode loop as ``answer(question)``,
  faithfully mirroring upstream lines 156-207 (LLM step -> regex-detect a
  ``[url]`` -> execute -> append result -> repeat, max 10 calls).
* It runs that loop inside :func:`agents.llm_compat.patch_openai_legacy_api`,
  which routes ``openai.ChatCompletion.create`` to a pinned current model.

Requires ``OPENAI_API_KEY`` (via TissueAgent's key registry) and live internet
access to NCBI. An optional ``NCBI_API_KEY`` raises the E-utilities rate limit.
"""

from __future__ import annotations

import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents.llm_compat import patch_openai_legacy_api
from agents.agent_registry.genegpt_agent.answer_recovery import (
    extract_terminal_answer,
    recover_gene_symbol,
)
from agents.agent_registry.genegpt_agent.alignment_recovery import (
    blast_request,
    normalize_blast_url,
    recover_alignment,
    request_id as blast_request_id,
)
from config import active_project_outputs
from logger import logger

_HERE = Path(__file__).resolve().parent
_UPSTREAM_DIR = _HERE / "upstream"

# Pinned model — retargets GeneGPT's retired default. See manifest.yaml.
# Must be a model that supports the ``stop`` parameter: GeneGPT's tool-use
# loop halts generation on ``stop=["->", ...]`` right after the model emits a
# URL, then executes it. Reasoning models (e.g. gpt-5.x) reject ``stop`` with
# a 400, so a chat-completions model such as gpt-4o is required here.
_PINNED_MODEL = "gpt-4o"

# Upstream constants (main_turbo.py): truncate long prompts, cap tool calls.
_CUT_LENGTH = 36000
_MAX_CALLS = 10
_NCBI_HTTP_TIMEOUT_SECONDS = 1200

# The default few-shot mask upstream reports as its best config: both API docs
# (Eutils + BLAST) + all four demonstrations. String order = Dc.1-2, Dm.1-4.
_DEFAULT_MASK = "111111"

# Detects the strict "[https://...]" URL GeneGPT's protocol expects (upstream
# line 181). Preferred form.
_URL_REGEX = r"\[(https?://[^\[\]]+)\]"

# Fallback: a bare NCBI URL anywhere in the text (prose/markdown/code-fence),
# stopping at whitespace or common closing delimiters. Modern chat models
# (gpt-4o) tend to write the URL inline rather than in the terse "[url]->"
# form, so without this the loop never executes a real NCBI call.
_LOOSE_URL_REGEX = (
    r"(https?://(?:eutils\.ncbi\.nlm\.nih\.gov|blast\.ncbi\.nlm\.nih\.gov)"
    r"[^\s\]\)\"'`<>]+)"
)

# System instruction that pins the model to the executable protocol. GeneGPT's
# original few-shot examples imply the format; stating it explicitly keeps a
# verbose chat model from replacing real URLs with a prose plan.
_SYSTEM_INSTRUCTION = (
    "You answer genomics questions by calling NCBI Web APIs. When you need "
    "data, output EXACTLY ONE API URL wrapped in square brackets and nothing "
    "else on that turn, e.g. "
    "[https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gene&"
    "retmax=5&retmode=json&sort=relevance&term=LMP10]. Do not describe the "
    "call, do not use markdown, do not add commentary — emit only the bracketed "
    "URL. You will receive the API response and may then emit the next URL. "
    "When you have enough information, reply with a line starting 'Answer:' "
    "followed by the concise final answer. A BLAST RID only identifies a queued "
    "job; retrieve that same RID with CMD=Get before answering. A waiting/error "
    "page is not an alignment. For human alignment, subject coordinates on a "
    "clone, transcript, RefSeqGene or synthetic construct are not chromosome "
    "coordinates. Report only the chromosome if no reference-coordinate mapping "
    "is available. Do not substitute coordinates from a hit's title. For species "
    "identification, do not resolve equally strong hits from different species "
    "by choosing the first hit."
)


def _find_url(text: str) -> str | None:
    """Return the first NCBI URL the model emitted, strict form preferred."""
    strict = re.findall(_URL_REGEX, text)
    if strict:
        return strict[0]
    loose = re.findall(_LOOSE_URL_REGEX, text)
    return loose[0] if loose else None


def _call_api(url: str) -> bytes:
    """Execute one upstream-compatible NCBI request with a bounded read."""
    time.sleep(1)
    url = url.replace(" ", "+")
    print(url)
    request = urllib.request.Request(url)
    with urllib.request.urlopen(
        request, timeout=_NCBI_HTTP_TIMEOUT_SECONDS
    ) as response:
        return response.read()


def _ensure_upstream_on_path() -> bool:
    if not (_UPSTREAM_DIR / "main_turbo.py").is_file():
        raise RuntimeError(
            f"GeneGPT upstream not found at {_UPSTREAM_DIR}. "
            "Run `git submodule update --init --recursive` from the repo root."
        )
    p = str(_UPSTREAM_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)
        return True
    return False


def _import_upstream_helpers():
    """Import ``get_prompt_header`` and ``call_api`` from the upstream module.

    ``main_turbo`` runs ``openai.api_key = config.API_KEY`` at import time; that
    is harmless (config ships a placeholder and we override the client inside
    the shim), and the two helpers we use do not depend on it. Import happens
    *inside* the shim so any ``openai`` module-top access resolves against the
    patched module.
    """
    added_path = _ensure_upstream_on_path()
    app_config = sys.modules.get("config")
    try:
        # Force a fresh import so the module-top side effects re-run under the patch.
        for mod in ("main_turbo", "config"):
            sys.modules.pop(mod, None)
        import main_turbo  # type: ignore[import-not-found]
        main_turbo.call_api = _call_api
    finally:
        if app_config is None:
            sys.modules.pop("config", None)
        else:
            sys.modules["config"] = app_config
        if added_path:
            sys.path.remove(str(_UPSTREAM_DIR))

    return main_turbo.get_prompt_header, _call_api


def run_genegpt_question(
    question: str,
    mask: str = _DEFAULT_MASK,
    request_id: Optional[str] = None,
) -> dict:
    """Answer a factual genomics question with GeneGPT's NCBI tool-use loop.

    Args:
        question: A factual genomics question, e.g. "What is the official gene
            symbol of LMP10?", "Which gene is SNP rs1217074595 associated
            with?", "What are genes related to Meesmann corneal dystrophy?",
            or "Align this DNA sequence to the human genome: ATTC...".
        mask: Six 0/1 chars toggling the few-shot prompt components
            (Dc.1-2 API docs, Dm.1-4 demonstrations). Default "111111" (the
            upstream's best-reported config).
        request_id: Optional id for the run artifact directory.

    Returns:
        A JSON-serialisable dict:
          - status: "ok" | "error"
          - answer: the extracted final answer (present on success)
          - raw_completion: the model's final untrimmed text
          - api_trace: URL, full response, and display excerpt for each NCBI call
          - num_calls: number of model completions (legacy field name)
          - answer_source, answer_evidence: final-answer provenance
          - model_used, run_directory, artifact_path
        On error: status "error" with error/error_type.

    Raises:
        ValueError: if ``question`` is blank or ``mask`` is malformed.
        RuntimeError: if the upstream submodule is missing or no OpenAI key
            is available (raised by the legacy shim).
    """
    if not (question or "").strip():
        raise ValueError("question must be a non-empty genomics question.")
    if len(mask) != 6 or any(c not in "01" for c in mask):
        raise ValueError("mask must be six 0/1 characters, e.g. '111111'.")

    run_identifier = request_id or datetime.now(timezone.utc).strftime(
        "run_%Y%m%d_%H%M%S"
    )
    run_dir = active_project_outputs() / "genegpt" / run_identifier
    run_dir.mkdir(parents=True, exist_ok=True)

    mask_bits = [bool(int(x)) for x in mask]
    api_trace: list[dict] = []
    llm_trace: list[dict] = []
    num_calls = 0

    logger.info(
        "GeneGPT[%s]: answering %r (model=%s). Builds the few-shot prompt "
        "(several NCBI calls) then loops tool use against NCBI.",
        run_identifier, question[:80], _PINNED_MODEL,
    )

    try:
        import openai  # modern SDK; ChatCompletion is patched inside the shim

        with patch_openai_legacy_api(pinned_model=_PINNED_MODEL):
            get_prompt_header, call_api = _import_upstream_helpers()

            # Few-shot header (upstream makes 7 example NCBI calls here).
            prompt = get_prompt_header(mask_bits)
            q_prompt = prompt + f"Question: {question}\n"

            final_text = ""
            answer = None
            answer_source = None
            answer_evidence = None
            stop_reason = "call_limit"
            blast_polled_at = {}
            while num_calls < _MAX_CALLS:
                # Keep the current question explicit even after truncation.
                current_task = f"\n\nCurrent question: {question}\nContinue this question only.\n"
                model_prompt = q_prompt[-max(1, _CUT_LENGTH - len(current_task)):] + current_task

                completion = openai.ChatCompletion.create(  # -> pinned model
                    model="ignored-shim-overrides",
                    messages=[
                        {"role": "system", "content": _SYSTEM_INSTRUCTION},
                        {"role": "user", "content": model_prompt},
                    ],
                    temperature=0.0,
                    stop=["->", "\n\nQuestion"],
                )
                # The legacy shim exposes the choice with dict-style access
                # (choices[0]["message"]["content"]) — the exact idiom upstream
                # GeneGPT uses. Attribute access (.message) would fall through
                # to the raw modern object, which is not subscriptable.
                text = completion.choices[0]["message"]["content"]
                num_calls += 1
                final_text = text
                llm_trace.append({"completion": text, "finish_reason": completion.choices[0]["finish_reason"]})

                url = _find_url(text)
                if url:
                    requested_url = url
                    try:
                        url = normalize_blast_url(url, api_trace)
                    except ValueError as exc:
                        stop_reason = "invalid_blast_request"
                        q_prompt += f"\nRequest not executed: {exc}\n"
                        continue
                    blast_query = blast_request(url)
                    if blast_query and blast_query.get("CMD") == ["Get"]:
                        rid = blast_query["RID"][0]
                        # Keep repeated polling of the same job at least a minute apart.
                        delay = max(0, 60 - (time.monotonic() - blast_polled_at.get(rid, float("-inf"))))
                        if delay:
                            time.sleep(delay)
                        blast_polled_at[rid] = time.monotonic()
                    call = call_api(url)

                    call_bytes = call if isinstance(call, (bytes, str)) else str(call)
                    response = (
                        call_bytes.decode("utf-8", "replace")
                        if isinstance(call_bytes, bytes) else str(call_bytes)
                    )
                    api_trace.append({"url": url, "requested_url": requested_url,
                                      "response": response, "response_excerpt": response[:2000]})
                    prompt_response = response[:20000]
                    if blast_query and blast_query.get("CMD") == ["Put"]:
                        rid = blast_request_id(response)
                        if rid is None:
                            raise RuntimeError("BLAST submission returned no valid RID.")
                        # Archive the full submission response, but keep the
                        # model-facing message free of irrelevant HTML.
                        prompt_response = f"BLAST submitted. RID={rid}. Retrieve results with CMD=Get using this RID."
                        blast_polled_at[rid] = time.monotonic()
                    recovered = recover_gene_symbol(question, api_trace)
                    if recovered["reason"] == "unsupported_question":
                        recovered = recover_alignment(question, api_trace)
                    if recovered["answer"] is not None:
                        answer = recovered["answer"]
                        answer_source = "ncbi_evidence_extraction"
                        answer_evidence = recovered
                        stop_reason = "evidence_answer"
                        break
                    if blast_query and blast_query.get("CMD") == ["Get"] and "BLASTN" not in response:
                        prompt_response = f"No completed BLAST text report was returned for RID={blast_query['RID'][0]}. Check its status; do not infer an alignment from this page.\n" + response[:1000]
                    q_prompt = f"{q_prompt}[{url}]->[{prompt_response}]\n"
                else:
                    answer = extract_terminal_answer(text)
                    if answer and blast_request_id(answer.strip("[]")) and any(blast_request(t["url"]) for t in api_trace):
                        answer = None  # A BLAST request identifier is not a scientific answer.
                    if answer is not None:
                        answer_source = "model_final_answer"
                        stop_reason = "final_answer"
                        break
                    # A new example/question is not an answer. Retry within
                    # the same cap, retaining the question and existing evidence.
                    stop_reason = "invalid_terminal_completion"
                    q_prompt += "\nReturn Answer: <final answer> for the current question, or one NCBI URL. Do not generate a new question.\n"

                if num_calls >= _MAX_CALLS:
                    logger.warning(
                        "GeneGPT[%s]: hit the %d-call cap without a clean answer.",
                        run_identifier, _MAX_CALLS,
                    )
                    break

        result: dict = {
            "status": "ok" if answer is not None else "error",
            "answer": answer,
            "answer_source": answer_source,
            "answer_evidence": answer_evidence,
            "stop_reason": stop_reason,
            "raw_completion": final_text,
            "api_trace": api_trace,
            "llm_trace": llm_trace,
            "num_calls": num_calls,
            "ncbi_calls": len(api_trace),
            "model_used": _PINNED_MODEL,
            "mask": mask,
        }
        if answer is None:
            result.update(error_type="NoFinalAnswer", error="No valid final answer within the model-call limit.")
    except Exception as exc:  # noqa: BLE001 — report, don't crash the graph
        logger.error("GeneGPT[%s]: failed (%s): %s",
                     run_identifier, type(exc).__name__, exc)
        result = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "api_trace": api_trace,
            "num_calls": num_calls,
        }

    # Persist the full result (incl. trace) as an artifact.
    import json
    result["request_id"] = run_identifier
    result["run_directory"] = str(run_dir.resolve())
    result["question"] = question
    artifact = run_dir / "result.json"
    try:
        artifact.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["artifact_path"] = str(artifact.resolve())
    except OSError:
        pass

    if result.get("status") == "ok":
        logger.info("GeneGPT[%s]: answered in %d call(s): %s",
                    run_identifier, num_calls, str(result.get("answer"))[:120])
    return result
