"""In-env driver for TxAgent (executed on a GPU host inside the ``txagent`` env).

``runner.py`` invokes this script via ``conda run`` only after it has confirmed
a CUDA GPU and the required packages are present. The script loads the
fine-tuned TxAgent model through vLLM, runs one therapeutic question, and
writes a JSON result. TxAgent's ``run_multistep_agent`` returns only the
final-answer *string*; the multi-step reasoning is printed to stdout, so we
tee stdout into the result as ``reasoning_trace``.

Contract (absolute paths):
    python _driver.py <request_json> <result_json>

Request JSON keys:
    question:        str   (required)
    temperature:     float (default 0.3)
    max_new_tokens:  int   (default 1024)
    max_token:       int   (default 90240)
    max_round:       int   (default 20)
    multiagent:      bool  (default False)
    model_name:      str   (default mims-harvard/TxAgent-T1-Llama-3.1-8B)
    rag_model_name:  str   (default mims-harvard/ToolRAG-T1-GTE-Qwen2-1.5B)
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import traceback
from typing import Any

# Upstream's run_example.py sets this to avoid an MKL threading crash.
os.environ.setdefault("MKL_THREADING_LAYER", "GNU")

_DEFAULT_MODEL = "mims-harvard/TxAgent-T1-Llama-3.1-8B"
_DEFAULT_RAG = "mims-harvard/ToolRAG-T1-GTE-Qwen2-1.5B"


def _run(request: dict[str, Any]) -> dict[str, Any]:
    from txagent import TxAgent  # imported here so failure is structured

    question = request["question"]
    model_name = request.get("model_name") or _DEFAULT_MODEL
    rag_model_name = request.get("rag_model_name") or _DEFAULT_RAG

    agent = TxAgent(model_name, rag_model_name, enable_summary=False)
    # Loads vLLM engine + ToolUniverse + ToolRAG embedding (GPU + downloads).
    agent.init_model()

    # run_multistep_agent returns only the final answer string; its reasoning
    # is printed. Tee stdout so we can surface the trace to the caller.
    trace = io.StringIO()
    with contextlib.redirect_stdout(trace):
        answer = agent.run_multistep_agent(
            question,
            temperature=float(request.get("temperature", 0.3)),
            max_new_tokens=int(request.get("max_new_tokens", 1024)),
            max_token=int(request.get("max_token", 90240)),
            call_agent=bool(request.get("multiagent", False)),
            max_round=int(request.get("max_round", 20)),
        )

    if answer is None:
        return {
            "status": "no_answer",
            "answer": None,
            "reasoning_trace": trace.getvalue()[-8000:],
            "model_used": model_name,
        }
    return {
        "status": "ok",
        "answer": answer,
        "reasoning_trace": trace.getvalue()[-8000:],
        "model_used": model_name,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python _driver.py <request_json> <result_json>", file=sys.stderr)
        return 2
    request_path, result_path = sys.argv[1], sys.argv[2]
    try:
        with open(request_path, "r", encoding="utf-8") as fh:
            request = json.load(fh)
        result = _run(request)
    except Exception as exc:  # noqa: BLE001 — parent only sees this file.
        result = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
