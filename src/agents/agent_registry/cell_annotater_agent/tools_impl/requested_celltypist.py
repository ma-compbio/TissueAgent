"""Explicit original-request-bound CellTypist execution, separate from adaptive selection."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

MARKER = "CellTypist execution request:"
POLICY = "user_requested_reference_celltypist_v1"
FIELDS = {
    "method",
    "spatial_anndata_path",
    "reference_anndata_path",
    "cell_type_column",
    "output_path",
    "random_state",
    "majority_voting",
    "query_sha256",
    "reference_sha256",
}


def parse_execution_request(user_request: str) -> dict | None:
    """Parse only an explicit method plus complete fixed request from the original task."""
    if MARKER not in user_request:
        return None
    if len(user_request.split(MARKER)) != 2 or not re.search(
        r"\bprimary_method\s*=\s*['\"]celltypist['\"]", user_request, re.I
    ):
        raise ValueError("CellTypist execution requires one explicit original-user method request")
    spec, _ = json.JSONDecoder().raw_decode(user_request.split(MARKER, 1)[1].lstrip())
    validate_request(spec)
    return spec


def validate_request(spec: dict) -> None:
    """Validate the fixed request before any source is read or backend executes."""
    if not isinstance(spec, dict) or set(spec) != FIELDS:
        raise ValueError("CellTypist execution request requires the complete fixed schema")
    if spec["method"] != "celltypist" or spec["majority_voting"] is not True:
        raise ValueError("This explicit route is reference-trained CellTypist with normal voting")
    if type(spec["random_state"]) is not int or not 0 <= spec["random_state"] < 2**32:
        raise ValueError("CellTypist random_state must be an integer in [0, 2**32)")
    for key in [
        "spatial_anndata_path",
        "reference_anndata_path",
        "cell_type_column",
        "output_path",
    ]:
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError(f"Missing explicit {key}")
    for key in ["query_sha256", "reference_sha256"]:
        if not isinstance(spec[key], str) or not re.fullmatch(r"[a-f0-9]{64}", spec[key]):
            raise ValueError(f"Invalid input binding {key}")


def run_requested_celltypist_tool() -> dict[str, Any]:
    """Execute the exact CellTypist request bound by the manager; accept no model arguments."""
    from agents.cell_annotation_context import get_bound_cell_annotation_context
    from agents.workspace_paths import resolve_workspace_input, resolve_project_output
    from .annotation_review import file_sha256
    from .celltypist_annotation import celltypist_annotation_tool
    from anndata.io import read_elem
    import h5py

    try:
        context = get_bound_cell_annotation_context() or {}
        spec = context.get("celltypist_execution_request")
        validate_request(spec)
        query = resolve_workspace_input(spec["spatial_anndata_path"])
        reference = resolve_workspace_input(spec["reference_anndata_path"])
        output = resolve_project_output(spec["output_path"], suffix=".h5ad")
        if query.samefile(reference):
            raise ValueError("Query cannot be its own training reference")
        if file_sha256(query) != spec["query_sha256"]:
            raise ValueError("Query no longer matches the original request")
        if file_sha256(reference) != spec["reference_sha256"]:
            raise ValueError("Training reference no longer matches the original request")
        with h5py.File(query, "r") as q, h5py.File(reference, "r") as r:
            qobs, robs = q["obs"], r["obs"]
            qids = set(read_elem(qobs[qobs.attrs["_index"]]).astype(str))
            rids = set(read_elem(robs[robs.attrs["_index"]]).astype(str))
            if qids & rids:
                raise ValueError("Query/reference observation IDs overlap; cannot train")
            if spec["cell_type_column"] not in robs:
                raise ValueError("Requested reference label column is missing")
        request_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        contract = {
            "selection_contract_id": request_hash,
            "configuration_sha256": request_hash,
            "parameter_policy_version": POLICY,
            "selection_mode": "explicit_user_request",
            "request": spec,
            "query_reference_id_overlap": 0,
            "automatic_method_selection": False,
        }
        meta = output.with_suffix(".run_meta.json")
        if output.exists() and meta.exists():
            saved = json.loads(meta.read_text())
            if saved.get("status") == "success" and saved.get("execution_contract") == contract:
                return {
                    "status": "success",
                    "already_complete": True,
                    "annotated_object_h5ad": spec["output_path"],
                    "run_meta_json": str(meta),
                    "method": "celltypist",
                    "random_state": spec["random_state"],
                }
            raise FileExistsError("Existing output does not match the requested CellTypist run")
        return celltypist_annotation_tool(
            spatial_anndata_path=spec["spatial_anndata_path"],
            output_path=spec["output_path"],
            reference_anndata_path=spec["reference_anndata_path"],
            cell_type_column=spec["cell_type_column"],
            majority_voting=True,
            mode="best match",
            n_jobs=2,
            min_feature_overlap=50,
            random_state=spec["random_state"],
            overclustering_strategy="bounded_v1",
            selection_rationale="User explicitly requested reference-trained CellTypist with "
            "standard majority voting; no automatic method ranking or "
            "historical accuracy was used to select this run.",
            execution_contract=contract,
        )
    except Exception as exc:
        return {
            "status": "error",
            "operation": "requested_celltypist",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
