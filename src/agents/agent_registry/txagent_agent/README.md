# TxAgent

Adapter wrapping [TxAgent](https://github.com/mims-harvard/TxAgent) (Harvard
MIMS) — a therapeutic-reasoning agent for precision medicine.

## What it does

Answers clinical/therapeutic questions (drug interactions, contraindications,
dose adjustment for organ impairment, treatment selection) via multi-step tool
use over the ToolUniverse (~200 biomedical tools), using a fine-tuned 8B model.

## Hardware requirement (read this first)

TxAgent serves its 8B model **in-process via vLLM** and **requires a CUDA
GPU** (the authors recommend an H100/80GB) plus a multi-GB HuggingFace weight
download. There is no CPU fallback.

This adapter is **capability-gated and honest**: if no CUDA GPU (or the
isolated env) is available, `run_txagent_question` returns a structured
`requires_gpu` / `unavailable` status and **does not fabricate a clinical
answer**. It only produces a real recommendation on suitable GPU hardware.

## Isolated environment (GPU host)

```bash
conda create -n txagent -y python=3.10
conda run -n txagent pip install txagent tooluniverse
#   -> pulls vllm<=0.8.4, sentence_transformers, gradio, torch/CUDA
export HF_TOKEN=...   # only if the model repo is gated
```

## Entry point

`runner.run_txagent_question(question, temperature=0.3, max_new_tokens=1024,
max_token=90240, max_round=20, multiagent=False)` → structured dict with
`status` in {ok, no_answer, requires_gpu, unavailable, error}. See `tool.py`.

Upstream pinned commit: see `manifest.yaml` (`upstream.commit`).
