"""Adapter that calls the upstream code.

Replace the body of `run_my_agent` with the call pattern that fits your
upstream project. The gene_agent runner is the worked example for the
most common case: an upstream that uses the legacy openai==0.28 API and
writes artifacts to relative paths.

Common building blocks you can reuse:

* `agents.llm_compat.patch_openai_legacy_api(pinned_model=...)` — context
  manager that monkey-patches the modern `openai` module so legacy
  `openai.ChatCompletion.create(...)` calls keep working, and pins the
  model to the value you specify.
* `config.DATA_DIR` — base directory; per-request artifacts should land in
  `DATA_DIR / "<your_agent_id>" / <request_id>`.
"""

from __future__ import annotations

from typing import Sequence

# from agents.llm_compat import patch_openai_legacy_api
# from config import DATA_DIR


def run_my_agent(
    # TODO: declare arguments using primitive types so LangChain can build
    # a JSON schema for the tool automatically.
    arg_a: str,
    arg_b: Sequence[str] | None = None,
) -> dict:
    """Run the upstream agent and return a JSON-serialisable dict.

    Args:
        arg_a: …
        arg_b: …

    Returns:
        A dictionary keyed by something stable so downstream agents can
        consume the result without parsing free-form text.
    """
    raise NotImplementedError("Fill in run_my_agent for your external agent.")
