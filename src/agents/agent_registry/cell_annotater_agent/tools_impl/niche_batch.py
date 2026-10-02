"""Small, validated batches with durable checkpoints for native niche labeling."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

POLICY = "niche_label_batches_v1"


def checkpoint_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    pending.replace(path)


def model_identity(model) -> dict:
    """Fingerprint public inference settings without serializing credentials."""
    for _ in range(3):
        if hasattr(model, "bound"):
            model = model.bound
        else:
            break
    return {
        key: getattr(model, key, None)
        for key in ("model_name", "model", "temperature", "seed", "reasoning_effort", "reasoning")
        if isinstance(getattr(model, key, None), (str, int, float, dict, type(None)))
    }


def _payload(queries: dict[str, str]) -> dict:
    # Native prompts repeat the identical section overview and rules for every cluster.
    # Move that exact shared suffix to a single place; retain all measured evidence.
    separator = (
        "Other clusters in this section (IDs are computational, not known anatomical regions):"
    )
    parts = [query.split(separator, 1) for query in queries.values()]
    if parts and all(len(p) == 2 for p in parts) and len({p[1] for p in parts}) == 1:
        return {
            "shared_section_context_and_rules": separator + parts[0][1],
            "niches": {key: query.split(separator, 1)[0] for key, query in queries.items()},
        }
    return {"niches": queries}


def label_niche_batches(
    queries: dict[str, str],
    allowed_labels: list[str],
    unmatched_label: str,
    model,
    checkpoint_path: Path,
    *,
    batch_size: int = 8,
    run_id: str = "default",
) -> dict[str, dict]:
    """Resume exact completed batches; reject incomplete IDs and unsupported labels."""
    if not 1 <= batch_size <= 16:
        raise ValueError("label_batch_size must be between 1 and 16.")
    binding = {
        "policy": POLICY,
        "queries": queries,
        "allowed_labels": allowed_labels,
        "unmatched_label": unmatched_label,
        "batch_size": batch_size,
        "model": model_identity(model),
        "run_id": run_id,
    }
    digest = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    state = {"policy": POLICY, "request_sha256": digest, "results": {}, "completed_batches": 0}
    if checkpoint_path.exists():
        state = json.loads(checkpoint_path.read_text())
        if state.get("request_sha256") != digest:
            raise ValueError(
                "Niche checkpoint belongs to different evidence/settings; use a new output directory."
            )
    results = state["results"]
    if not set(results).issubset(queries):
        raise ValueError("Niche checkpoint contains unrequested cluster IDs.")
    vocabulary = {label.casefold(): label for label in allowed_labels + [unmatched_label]}
    for key, value in results.items():
        if value.get("niche_id") != key or value.get("label") not in vocabulary.values():
            raise ValueError("Invalid saved niche labeling checkpoint.")
    missing = [key for key in queries if key not in results]
    for start in range(0, len(missing), batch_size):
        ids = missing[start : start + batch_size]
        selected = {key: queries[key] for key in ids}
        system = SystemMessage(
            "Label anatomical tissue niches from measured evidence. Assess each niche independently "
            "in its shared section context; different niches may have the same label. Return only "
            'JSON {"annotations":[{"niche_id":"...","label":"...","justification":"..."}]}. '
            "Return exactly one record per requested ID and only permitted labels. "
            "Use Unmatched for insufficient evidence. Do not merge small or rare niches to save work."
        )
        response = model.invoke(
            [system, HumanMessage(json.dumps(_payload(selected), ensure_ascii=False))]
        )
        from .niche_annotation import _extract_json_object, _message_content_to_text

        parsed = _extract_json_object(_message_content_to_text(response.content))
        records = parsed.get("annotations") if isinstance(parsed, dict) else None
        if not isinstance(records, list) or len(records) != len(ids):
            raise ValueError(
                "Niche batch response has missing or extra annotations; completed batches retained."
            )
        accepted = {}
        for record in records:
            key = str(record.get("niche_id", ""))
            label = vocabulary.get(str(record.get("label", "")).strip().casefold())
            reason = str(record.get("justification", "")).strip()
            if key not in selected or key in accepted or label is None or not reason:
                raise ValueError(
                    "Niche batch has duplicate/unknown IDs, invalid labels or no justification."
                )
            accepted[key] = {"niche_id": key, "label": label, "justification": reason}
        results.update(accepted)
        state["completed_batches"] += 1
        checkpoint_json(checkpoint_path, state)
    return results
