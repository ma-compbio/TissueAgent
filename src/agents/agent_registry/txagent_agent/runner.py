"""Adapter that runs TxAgent from inside TissueAgent.

TxAgent serves a fine-tuned 8B model **in-process via vLLM** and therefore
hard-requires a CUDA GPU (the authors recommend an H100/80GB) plus a multi-GB
HuggingFace weight download and the separately-installed ``tooluniverse``
package. There is no CPU fallback.

This runner is deliberately **capability-gated and honest**:

* It validates the question and resolves the run directory always.
* It then checks that the isolated ``txagent`` conda env exists and that a
  CUDA GPU is visible to that env.
* Only if both hold does it launch ``_driver.py`` (which loads vLLM + weights
  and runs the real agent).
* Otherwise it returns a structured status (``requires_gpu`` or
  ``unavailable``) — it NEVER fabricates a therapeutic recommendation. This is
  a clinical-adjacent tool; a made-up answer would be dangerous.

Create the env once (on a GPU host):

    conda create -n txagent -y python=3.10
    conda run -n txagent pip install txagent tooluniverse
    # (installs vllm<=0.8.4, sentence_transformers, gradio, torch/CUDA)
    # Set HF_TOKEN if the model repo is gated.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import active_project_outputs
from logger import logger

_HERE = Path(__file__).resolve().parent
_UPSTREAM_DIR = _HERE / "upstream"
_DRIVER = _HERE / "_driver.py"

_ISOLATED_ENV = "txagent"

# TxAgent runs long multi-round tool-use loops with a large context window;
# a single question can take many minutes even on an H100.
_TIMEOUT_S = 5400


def _upstream_present() -> bool:
    # The package lives at upstream/src/txagent/txagent.py.
    return (_UPSTREAM_DIR / "src" / "txagent" / "txagent.py").is_file()


def _env_present() -> bool:
    if shutil.which("conda") is None:
        return False
    probe = subprocess.run(
        ["conda", "run", "-n", _ISOLATED_ENV, "python", "-c",
         "import txagent, tooluniverse, vllm"],
        capture_output=True, text=True, check=False,
    )
    return probe.returncode == 0


def _gpu_available_in_env() -> bool:
    """True only if the isolated env can see at least one CUDA device."""
    if shutil.which("conda") is None:
        return False
    probe = subprocess.run(
        ["conda", "run", "-n", _ISOLATED_ENV, "python", "-c",
         "import torch,sys; sys.exit(0 if torch.cuda.is_available() "
         "and torch.cuda.device_count() > 0 else 1)"],
        capture_output=True, text=True, check=False,
    )
    return probe.returncode == 0


def run_txagent_question(
    question: str,
    temperature: float = 0.3,
    max_new_tokens: int = 1024,
    max_token: int = 90240,
    max_round: int = 20,
    multiagent: bool = False,
    request_id: Optional[str] = None,
) -> dict:
    """Answer a therapeutic / precision-medicine question with TxAgent.

    Args:
        question: The clinical/therapeutic question in natural language
            (e.g. dose adjustment for organ impairment, drug interactions).
        temperature: Sampling temperature (default 0.3).
        max_new_tokens: Max new tokens per generation step (default 1024).
        max_token: Max total context tokens (default 90240, per upstream).
        max_round: Max tool-use rounds (default 20).
        multiagent: Enable TxAgent's multi-agent calls (default False).
        request_id: Optional id for the run artifact directory.

    Returns:
        A JSON-serialisable dict. ``status`` is one of:
          - "ok": ``answer`` holds the recommendation; ``reasoning_trace`` the
            captured multi-step reasoning; ``artifact_path`` the saved JSON.
          - "no_answer": the agent ran but did not produce a final answer.
          - "requires_gpu": no CUDA GPU is available to the txagent env; the
            question was NOT answered (no fabrication).
          - "unavailable": the txagent env / upstream is not installed.
          - "error": an exception occurred (see ``error`` / ``error_type``).
        Always includes ``request_id`` and ``run_directory``.

    Raises:
        ValueError: if ``question`` is blank.
    """
    if not (question or "").strip():
        raise ValueError("question must be a non-empty therapeutic question.")

    run_identifier = request_id or datetime.now(timezone.utc).strftime(
        "run_%Y%m%d_%H%M%S"
    )
    run_dir = active_project_outputs() / "txagent" / run_identifier
    run_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "result.json"

    def _finalize(result: dict) -> dict:
        result.setdefault("request_id", run_identifier)
        result["run_directory"] = str(run_dir.resolve())
        result["question"] = question
        try:
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            result["artifact_path"] = str(result_path.resolve())
        except OSError:
            pass
        return result

    # --- Capability gates (fail honestly, never fabricate) ------------------
    if not _upstream_present():
        logger.warning("TxAgent[%s]: upstream submodule missing.", run_identifier)
        return _finalize({
            "status": "unavailable",
            "reason": (
                f"TxAgent upstream not found at {_UPSTREAM_DIR}. Run "
                "`git submodule update --init --recursive` from the repo root."
            ),
            "answer": None,
        })

    if not _env_present():
        logger.warning(
            "TxAgent[%s]: isolated env `%s` not found or missing "
            "txagent/tooluniverse/vllm.", run_identifier, _ISOLATED_ENV,
        )
        return _finalize({
            "status": "unavailable",
            "reason": (
                f"Isolated env `{_ISOLATED_ENV}` cannot import "
                "txagent/tooluniverse/vllm. Create it on a GPU host: "
                f"`conda create -n {_ISOLATED_ENV} -y python=3.10 && "
                f"conda run -n {_ISOLATED_ENV} pip install txagent tooluniverse`."
            ),
            "answer": None,
        })

    if not _gpu_available_in_env():
        logger.warning(
            "TxAgent[%s]: no CUDA GPU visible; refusing to fabricate an answer.",
            run_identifier,
        )
        return _finalize({
            "status": "requires_gpu",
            "reason": (
                "TxAgent serves an 8B model in-process via vLLM and needs a "
                "CUDA GPU (authors recommend an H100/80GB). No CUDA device is "
                "visible to the txagent env, so the question was not answered. "
                "Run this on GPU hardware to get a real recommendation."
            ),
            "answer": None,
        })

    # --- Real run on GPU hardware -------------------------------------------
    request = {
        "question": question,
        "temperature": temperature,
        "max_new_tokens": max_new_tokens,
        "max_token": max_token,
        "max_round": max_round,
        "multiagent": multiagent,
    }
    request_path = run_dir / "request.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")

    logger.info(
        "TxAgent[%s]: running (GPU detected). This loads vLLM + weights and "
        "can take several minutes.", run_identifier,
    )
    try:
        proc = subprocess.run(
            ["conda", "run", "-n", _ISOLATED_ENV, "--live-stream",
             "python", str(_DRIVER), str(request_path), str(result_path)],
            cwd=str(_UPSTREAM_DIR),
            env={**os.environ},
            capture_output=True, text=True, check=False, timeout=_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return _finalize({
            "status": "error",
            "error_type": "Timeout",
            "error": f"TxAgent exceeded the {_TIMEOUT_S}s time limit.",
            "answer": None,
        })

    if result_path.is_file():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        result = {
            "status": "error",
            "error_type": "NoResult",
            "error": "driver produced no result.json",
            "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
            "answer": None,
        }
    result["returncode"] = proc.returncode
    result["execution"] = "isolated_env_gpu"
    return _finalize(result)
