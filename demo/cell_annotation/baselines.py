"""Direct, non-agentic CellTypist and GPTCellType benchmark runners."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse

from .benchmarks import DATA_DIR, REPO_ROOT, load_manifest


EXPECTED_VERSIONS = {"celltypist": "1.7.1", "omicverse": "2.2.3"}
GPTCELLTYPE_NATIVE_MAX_MARKER_GENES = 10


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_prepared(prepared: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(prepared, dict):
        return prepared
    path = Path(prepared)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _require_version(distribution: str) -> str:
    try:
        installed = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"{distribution} is not installed. Run the locked benchmark environment setup; "
            "the notebook will not install packages automatically."
        ) from exc
    expected = EXPECTED_VERSIONS[distribution]
    if installed != expected:
        raise RuntimeError(f"{distribution}=={expected} is required; found {installed}.")
    return installed


def _prepare_log1p(dataset: ad.AnnData) -> tuple[ad.AnnData, dict[str, Any]]:
    """Create canonical log1p-per-10K expression without double-transforming input."""
    working = dataset.copy()
    matrix = working.X
    values = matrix.data if sparse.issparse(matrix) else np.asarray(matrix).ravel()
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Baseline input contains negative or non-finite expression values.")
    indices = np.linspace(0, max(0, len(values) - 1), min(len(values), 1_000_000), dtype=int)
    sampled = np.asarray(values[indices], dtype=np.float64) if len(values) else values
    integer_like_fraction = (
        float(np.mean(np.isclose(sampled, np.rint(sampled), atol=1e-6, rtol=0)))
        if len(sampled)
        else 0.0
    )
    explicit_log1p = "log1p" in working.uns

    if integer_like_fraction >= 0.99 and not explicit_log1p:
        source_state = "raw_count_like"
        inferred_target_sum = None
    else:
        linear = working.X.copy()
        if sparse.issparse(linear):
            linear.data = np.expm1(linear.data)
        else:
            linear = np.expm1(np.asarray(linear))
        totals = np.asarray(linear.sum(axis=1)).ravel()
        positive_totals = totals[totals > 0]
        if not len(positive_totals):
            raise ValueError("Baseline input contains no positive-expression observations.")
        quantiles = np.quantile(positive_totals, [0.05, 0.5, 0.95])
        relative_spread = float((quantiles[2] - quantiles[0]) / quantiles[1])
        if not explicit_log1p and relative_spread > 0.01:
            raise ValueError(
                "Continuous nonnegative expression lacks explicit log1p metadata and does not "
                "have a stable inferred normalization total."
            )
        working.X = linear
        source_state = "explicit_log1p" if explicit_log1p else "inferred_log1p_normalized"
        inferred_target_sum = float(quantiles[1])

    sc.pp.normalize_total(working, target_sum=10_000)
    sc.pp.log1p(working)
    audit = {
        "source_state": source_state,
        "sampled_integer_like_fraction": integer_like_fraction,
        "explicit_log1p_metadata": explicit_log1p,
        "inferred_input_target_sum": inferred_target_sum,
        "output_transform": "normalize_total_10000_log1p",
    }
    return working, audit


def _normalize_log1p(dataset: ad.AnnData) -> ad.AnnData:
    """Backward-compatible wrapper for callers that only need the prepared object."""
    return _prepare_log1p(dataset)[0]


def _prediction_output(prepared: dict[str, Any], method: str) -> Path:
    run_dir = REPO_ROOT / prepared["run_dir"]
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / f"{method}_predictions.tsv"


def run_celltypist(
    prepared: dict[str, Any] | str | Path,
    majority_voting: bool = True,
    n_jobs: int = 1,
) -> dict[str, Any]:
    """Execute CellTypist directly using the dataset's declared model strategy."""
    version = _require_version("celltypist")
    import celltypist
    from celltypist import models

    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["celltypist"]
    query = ad.read_h5ad(REPO_ROOT / prepared["query_h5ad"])
    normalized_query, query_preprocessing = _prepare_log1p(query)

    if config["mode"] == "builtin":
        model_name = config["model"]
        celltypist_cache = DATA_DIR / "cache" / "celltypist"
        model_dir = celltypist_cache / "data" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        models.celltypist_path = str(celltypist_cache)
        models.data_path = str(celltypist_cache / "data")
        models.models_path = str(model_dir)
        model_path = model_dir / model_name
        if not model_path.exists():
            models.download_models(force_update=False, model=model_name)
        if not model_path.exists():
            raise FileNotFoundError(f"CellTypist did not produce requested model: {model_path}")
        model_sha256 = _sha256(model_path)
        expected_model_sha256 = config.get("model_sha256")
        if expected_model_sha256 and model_sha256 != expected_model_sha256:
            raise ValueError(f"CellTypist model SHA-256 changed: {model_path}")
        model = models.Model.load(str(model_path))
        model_description = model_name
    elif config["mode"] == "train_reference":
        reference = ad.read_h5ad(REPO_ROOT / prepared["reference_h5ad"])
        label_column = config["label_column"]
        if label_column not in reference.obs:
            raise KeyError(f"CellTypist training reference lacks .obs['{label_column}'].")
        if reference.obs[label_column].isna().any():
            raise ValueError(f"CellTypist training labels contain missing values: {label_column}")
        normalized_reference, reference_preprocessing = _prepare_log1p(reference)
        model = celltypist.train(
            normalized_reference,
            labels=label_column,
            n_jobs=n_jobs,
            use_SGD=normalized_reference.n_obs > 100_000,
            feature_selection=True,
        )
        model_description = f"trained_from:{prepared['reference_h5ad']}:{label_column}"
        model_sha256 = None
    else:
        raise ValueError(f"Unsupported CellTypist mode '{config['mode']}'.")

    model_features = pd.Index(np.asarray(model.features).astype(str))
    canonical_by_casefold = {feature.casefold(): feature for feature in model_features}
    original_query_names = pd.Index(normalized_query.var_names.astype(str))
    aligned_query_names = pd.Index(
        [canonical_by_casefold.get(name.casefold(), name) for name in original_query_names]
    )
    normalized_query.var["celltypist_original_gene_name"] = original_query_names
    normalized_query.var_names = aligned_query_names
    if not normalized_query.var_names.is_unique:
        raise ValueError(
            "CellTypist model-derived gene case alignment created duplicate query genes."
        )
    matched_features = normalized_query.var_names.intersection(model_features)
    if len(matched_features) < 10:
        raise ValueError(
            f"Only {len(matched_features)} query genes match the CellTypist model; "
            "at least 10 are required for a valid baseline run."
        )

    removed_input_graph = {
        "obsm": sorted(str(key) for key in normalized_query.obsm),
        "obsp": sorted(str(key) for key in normalized_query.obsp),
        "neighbors_uns": "neighbors" in normalized_query.uns,
    }
    if majority_voting:
        normalized_query.obsm.clear()
        normalized_query.obsp.clear()
        normalized_query.uns.pop("neighbors", None)
    predictions = celltypist.annotate(
        normalized_query,
        model=model,
        majority_voting=majority_voting,
    )
    label_frame = predictions.predicted_labels
    preferred_column = (
        "majority_voting"
        if majority_voting and "majority_voting" in label_frame
        else "predicted_labels"
    )
    raw_labels = label_frame[preferred_column].astype(str).reindex(query.obs_names)
    probability = predictions.probability_matrix.reindex(query.obs_names)
    confidence = probability.max(axis=1)
    if raw_labels.isna().any():
        missing_count = int(raw_labels.isna().sum())
        raise RuntimeError(f"CellTypist returned {missing_count} missing predictions.")

    output = _prediction_output(prepared, "celltypist")
    frame = pd.DataFrame(
        {
            "cell_id": query.obs_names,
            "raw_prediction": raw_labels.to_numpy(),
            "confidence": confidence.to_numpy(dtype=float),
            "method": "celltypist",
        }
    ).set_index("cell_id")
    frame.to_csv(output, sep="\t")
    metadata = {
        "status": "success",
        "method": "celltypist",
        "version": version,
        "model": model_description,
        "model_sha256": model_sha256,
        "n_model_features_matched": len(matched_features),
        "n_query_gene_names_case_aligned": int((original_query_names != aligned_query_names).sum()),
        "majority_voting": majority_voting,
        "majority_voting_graph": (
            "celltypist_transcriptomic_over_clustering" if majority_voting else None
        ),
        "removed_input_graph": removed_input_graph,
        "query_preprocessing": query_preprocessing,
        "reference_preprocessing": (
            reference_preprocessing if config["mode"] == "train_reference" else None
        ),
        "n_predictions": len(frame),
        "output_path": str(output.relative_to(REPO_ROOT)),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _marker_dictionary(
    dataset: ad.AnnData,
    group_key: str,
    top_n: int = 20,
) -> dict[str, list[str]]:
    result = dataset.uns["rank_genes_groups"]
    names = result["names"]
    groups = list(names.dtype.names or [])
    if not groups:
        raise ValueError("rank_genes_groups did not return named cluster fields.")
    return {
        str(group): [str(gene) for gene in names[group][:top_n] if str(gene) not in {"", "nan"}]
        for group in groups
    }


def _rank_gptcelltype_markers(
    working: ad.AnnData,
    group_key: str,
    *,
    top_marker_genes: int,
    max_cells_per_cluster: int | None,
    max_cells_total: int | None,
    random_seed: int,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    assignments = working.obs[group_key].astype(str)
    cluster_counts = assignments.value_counts().sort_index()
    selected_positions = np.arange(working.n_obs, dtype=np.int64)
    effective_cluster_cap: int | None = None
    strategy = "all_cells_full_gene_wilcoxon"
    if max_cells_total is not None and max_cells_per_cluster is None:
        raise ValueError("max_cells_total requires max_cells_per_cluster.")
    if max_cells_per_cluster is not None:
        if max_cells_per_cluster < 1:
            raise ValueError("max_cells_per_cluster must be positive when configured.")
        if max_cells_total is not None and max_cells_total < len(cluster_counts):
            raise ValueError("max_cells_total must allow at least one cell per cluster.")
        effective_cluster_cap = max_cells_per_cluster
        if max_cells_total is not None:
            effective_cluster_cap = min(
                effective_cluster_cap,
                max_cells_total // len(cluster_counts),
            )
        rng = np.random.default_rng(random_seed)
        cluster_values = assignments.to_numpy()
        selected = []
        for cluster in cluster_counts.index:
            positions = np.flatnonzero(cluster_values == cluster)
            if len(positions) > effective_cluster_cap:
                positions = rng.choice(
                    positions,
                    size=effective_cluster_cap,
                    replace=False,
                )
            selected.append(positions)
        selected_positions = np.sort(np.concatenate(selected).astype(np.int64, copy=False))
        strategy = "cluster_balanced_sample_full_gene_wilcoxon"

    marker_view = (
        working if len(selected_positions) == working.n_obs else working[selected_positions].copy()
    )
    sc.tl.rank_genes_groups(
        marker_view,
        group_key,
        method="wilcoxon",
        n_genes=top_marker_genes,
        use_raw=False,
    )
    markers = _marker_dictionary(marker_view, group_key, top_n=top_marker_genes)
    selected_assignments = marker_view.obs[group_key].astype(str)
    selected_counts = selected_assignments.value_counts().sort_index()
    digest = hashlib.sha256()
    for cell_id in marker_view.obs_names.astype(str):
        digest.update(cell_id.encode("utf-8"))
        digest.update(b"\0")
    audit = {
        "marker_ranking_strategy": strategy,
        "marker_ranking_method": "wilcoxon",
        "marker_ranking_gene_scope": "all_query_genes",
        "marker_ranking_source_cells": working.n_obs,
        "marker_ranking_cells": marker_view.n_obs,
        "marker_ranking_source_cluster_counts": {
            str(cluster): int(count) for cluster, count in cluster_counts.items()
        },
        "marker_ranking_selected_cluster_counts": {
            str(cluster): int(count) for cluster, count in selected_counts.items()
        },
        "marker_ranking_requested_max_cells_per_cluster": max_cells_per_cluster,
        "marker_ranking_effective_max_cells_per_cluster": effective_cluster_cap,
        "marker_ranking_max_cells_total": max_cells_total,
        "marker_ranking_random_seed": random_seed,
        "marker_ranking_selected_cell_ids_sha256": digest.hexdigest(),
        "all_cells_used_for_clustering_and_final_predictions": True,
        "marker_sampling_uses_query_annotations_or_spatial_metadata": False,
    }
    return markers, audit


def _gptcelltype_marker_audit(
    markers: dict[str, list[str]],
    cluster_assignments: pd.Series,
    *,
    requested_top_marker_genes: int,
) -> dict[str, Any]:
    if requested_top_marker_genes < 1:
        raise ValueError("top_marker_genes must be positive.")
    assignments = cluster_assignments.astype(str)
    cluster_counts = assignments.value_counts(sort=False)
    assignment_clusters = set(cluster_counts.index.astype(str))
    marker_clusters = set(markers)
    if assignment_clusters != marker_clusters:
        raise RuntimeError(
            "GPTCellType marker and cluster assignments disagree: "
            f"markers_only={sorted(marker_clusters - assignment_clusters)}, "
            f"assignments_only={sorted(assignment_clusters - marker_clusters)}."
        )
    effective_top_marker_genes = min(
        requested_top_marker_genes,
        GPTCELLTYPE_NATIVE_MAX_MARKER_GENES,
    )
    return {
        "requested_top_marker_genes": requested_top_marker_genes,
        "native_provider_max_marker_genes": GPTCELLTYPE_NATIVE_MAX_MARKER_GENES,
        "effective_provider_top_marker_genes": effective_top_marker_genes,
        "effective_provider_marker_genes_by_cluster": {
            cluster: min(len(genes), effective_top_marker_genes)
            for cluster, genes in markers.items()
        },
        "cluster_sizes": {cluster: int(cluster_counts.loc[cluster]) for cluster in markers},
    }


def prepare_gptcelltype_markers(
    prepared: dict[str, Any] | str | Path,
    resolution: float = 1.0,
    top_marker_genes: int = 20,
    max_marker_cells_per_cluster: int | None = None,
    max_marker_cells_total: int | None = None,
    marker_sampling_random_seed: int | None = None,
) -> dict[str, Any]:
    """Prepare the exact transcriptomic clusters and marker lists without calling an LLM."""
    version = _require_version("omicverse")
    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["gptcelltype"]
    query = ad.read_h5ad(REPO_ROOT / prepared["query_h5ad"])
    working, query_preprocessing = _prepare_log1p(query)
    if working.n_obs < 3 or working.n_vars < 3:
        raise ValueError("GPTCellType requires at least three cells and three genes.")

    n_top_genes = min(2_000, working.n_vars)
    clustering = working
    if n_top_genes < working.n_vars:
        sc.pp.highly_variable_genes(working, n_top_genes=n_top_genes, flavor="seurat")
        clustering = working[:, working.var["highly_variable"]].copy()
    n_pcs = min(50, clustering.n_obs - 1, clustering.n_vars - 1)
    sc.pp.pca(clustering, n_comps=n_pcs)
    sc.pp.neighbors(
        clustering,
        n_neighbors=min(15, clustering.n_obs - 1),
        n_pcs=n_pcs,
    )
    sc.tl.leiden(
        clustering,
        key_added="gptcelltype_cluster",
        resolution=resolution,
        random_state=42,
    )
    working.obs["gptcelltype_cluster"] = clustering.obs["gptcelltype_cluster"].copy()
    max_marker_cells_per_cluster = (
        max_marker_cells_per_cluster
        if max_marker_cells_per_cluster is not None
        else config.get("max_marker_cells_per_cluster")
    )
    max_marker_cells_total = (
        max_marker_cells_total
        if max_marker_cells_total is not None
        else config.get("max_marker_cells_total")
    )
    marker_sampling_random_seed = (
        marker_sampling_random_seed
        if marker_sampling_random_seed is not None
        else int(config.get("marker_sampling_random_seed", 42))
    )
    markers, marker_ranking_audit = _rank_gptcelltype_markers(
        working,
        "gptcelltype_cluster",
        top_marker_genes=top_marker_genes,
        max_cells_per_cluster=max_marker_cells_per_cluster,
        max_cells_total=max_marker_cells_total,
        random_seed=marker_sampling_random_seed,
    )
    cluster_assignments = working.obs["gptcelltype_cluster"].astype(str)
    marker_audit = _gptcelltype_marker_audit(
        markers,
        cluster_assignments,
        requested_top_marker_genes=top_marker_genes,
    )

    output = _prediction_output(prepared, "gptcelltype")
    markers_path = output.with_suffix(".markers.json")
    clusters_path = output.with_suffix(".cluster_assignments.tsv")
    if output.exists() or markers_path.exists() or clusters_path.exists():
        raise FileExistsError("GPTCellType marker or prediction artifacts already exist.")
    markers_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": {},
                "species": config["species_name"],
                "tissue": config["tissue_name"],
                **marker_ranking_audit,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        {"cluster": cluster_assignments},
        index=working.obs_names,
    ).to_csv(clusters_path, sep="\t")
    metadata = {
        "status": "markers_ready",
        "method": "gptcelltype",
        "version": version,
        "configured_model": config["model"],
        "n_clusters": len(markers),
        "resolution": resolution,
        **marker_ranking_audit,
        **marker_audit,
        "query_preprocessing": query_preprocessing,
        "markers_path": str(markers_path.relative_to(REPO_ROOT)),
        "cluster_assignments_path": str(clusters_path.relative_to(REPO_ROOT)),
        "data_sent_to_provider": "none",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def complete_gptcelltype_from_cluster_labels(
    prepared: dict[str, Any] | str | Path,
    cluster_labels: dict[str, str],
    *,
    label_provider: str,
) -> dict[str, Any]:
    """Map independently generated marker-only labels back to every query observation."""
    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["gptcelltype"]
    output = _prediction_output(prepared, "gptcelltype")
    markers_path = output.with_suffix(".markers.json")
    assignments_path = output.with_suffix(".cluster_assignments.tsv")
    payload = json.loads(markers_path.read_text(encoding="utf-8"))
    markers = payload["markers"]
    missing = sorted(set(markers).difference(cluster_labels))
    extra = sorted(set(cluster_labels).difference(markers))
    if missing or extra:
        raise ValueError(f"Cluster labels mismatch: missing={missing}, extra={extra}.")
    cleaned = {str(key): str(value).strip() for key, value in cluster_labels.items()}
    if any(not value for value in cleaned.values()):
        raise ValueError("GPTCellType cluster labels must be non-empty.")
    assignments = pd.read_csv(assignments_path, sep="\t", index_col=0)
    assignments.index = assignments.index.astype(str)
    cluster_assignments = assignments["cluster"].astype(str)
    requested_top_marker_genes = int(
        payload.get(
            "requested_top_marker_genes",
            max((len(genes) for genes in markers.values()), default=1),
        )
    )
    marker_audit = _gptcelltype_marker_audit(
        markers,
        cluster_assignments,
        requested_top_marker_genes=requested_top_marker_genes,
    )
    raw_predictions = cluster_assignments.map(cleaned)
    if raw_predictions.isna().any():
        raise RuntimeError("One or more GPTCellType clusters lack a label.")

    pd.DataFrame(
        {
            "raw_prediction": raw_predictions,
            "confidence": np.nan,
            "method": "gptcelltype",
        },
        index=assignments.index,
    ).to_csv(output, sep="\t")
    clusters_path = output.with_suffix(".clusters.json")
    clusters_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": cleaned,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    version = _require_version("omicverse")
    metadata = {
        "status": "success",
        "method": "gptcelltype",
        "version": version,
        "configured_model": config["model"],
        "label_provider": label_provider,
        "remote_configured_model_executed": False,
        "n_clusters": len(markers),
        "n_predictions": len(assignments),
        **marker_audit,
        "output_path": str(output.relative_to(REPO_ROOT)),
        "clusters_path": str(clusters_path.relative_to(REPO_ROOT)),
        "cluster_assignments_path": str(assignments_path.relative_to(REPO_ROOT)),
        "data_sent_to_provider": "cluster marker gene names only",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _run_gptcelltype_batch(
    ov: Any,
    markers: dict[str, list[str]],
    config: dict[str, Any],
    *,
    max_api_attempts: int,
    timeout_seconds: int,
    provider_top_marker_genes: int = GPTCELLTYPE_NATIVE_MAX_MARKER_GENES,
    prompt_records: list[dict[str, Any]] | None = None,
    api_batch_index: int | None = None,
) -> tuple[dict[str, str], int]:
    """Call OmicVerse GPTCellType with bounded retries and formatting normalization."""
    import openai

    if not 1 <= provider_top_marker_genes <= GPTCELLTYPE_NATIVE_MAX_MARKER_GENES:
        raise ValueError(
            "provider_top_marker_genes must be between 1 and "
            f"{GPTCELLTYPE_NATIVE_MAX_MARKER_GENES}."
        )
    real_openai = openai.OpenAI
    api_calls = 0

    class BoundedCompletions:
        def __init__(self, completions: Any) -> None:
            self._completions = completions

        def create(self, *args: Any, **kwargs: Any) -> Any:
            nonlocal api_calls
            if api_calls >= max_api_attempts:
                raise RuntimeError(
                    "GPTCellType did not return exactly one label per cluster after "
                    f"{max_api_attempts} API attempts."
                )
            api_calls += 1
            kwargs.setdefault("timeout", timeout_seconds)
            prompt = kwargs.get("messages", [{}])[-1].get("content", "")
            if prompt_records is not None:
                prompt_records.append(
                    {
                        "api_call_index": api_calls,
                        "api_batch_index": api_batch_index,
                        "model": kwargs.get("model"),
                        "cluster_ids": list(markers),
                        "effective_marker_genes_by_cluster": {
                            cluster: min(len(genes), provider_top_marker_genes)
                            for cluster, genes in markers.items()
                        },
                        "exact_user_prompt": prompt,
                        "exact_user_prompt_sha256": hashlib.sha256(
                            prompt.encode("utf-8")
                        ).hexdigest(),
                    }
                )
            response = self._completions.create(*args, **kwargs)
            content = response.choices[0].message.content or ""
            expected_lines = max(0, len(prompt.splitlines()) - 1)
            nonempty_lines = [line.strip() for line in content.splitlines() if line.strip()]
            if len(nonempty_lines) == expected_lines:
                cleaned = [
                    re.sub(r"^(?:[-*\u2022]|\d+[.)-])\s*", "", line).strip()
                    for line in nonempty_lines
                ]
                response.choices[0].message.content = "\n".join(cleaned)
            return response

    class BoundedOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            if not kwargs.get("api_key"):
                kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
            client = real_openai(*args, **kwargs)
            self.chat = type("BoundedChat", (), {})()
            self.chat.completions = BoundedCompletions(client.chat.completions)

    openai.OpenAI = BoundedOpenAI
    try:
        labels = ov.single.gptcelltype(
            markers,
            tissuename=config["tissue_name"],
            speciename=config["species_name"],
            model=config["model"],
            provider="openai",
            topgenenumber=provider_top_marker_genes,
        )
    finally:
        openai.OpenAI = real_openai
    if not isinstance(labels, dict):
        raise RuntimeError("GPTCellType returned a prompt instead of a cluster-label dictionary.")
    return {str(key): str(value) for key, value in labels.items()}, api_calls


def run_gptcelltype(
    prepared: dict[str, Any] | str | Path,
    resolution: float = 1.0,
    top_marker_genes: int = 20,
    api_batch_size: int = 25,
    max_api_attempts_per_batch: int = 3,
    api_timeout_seconds: int = 120,
    max_marker_cells_per_cluster: int | None = None,
    max_marker_cells_total: int | None = None,
    marker_sampling_random_seed: int | None = None,
) -> dict[str, Any]:
    """Execute GPTCellType directly; only cluster marker names are sent to OpenAI."""
    version = _require_version("omicverse")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not visible to this process.")
    import omicverse as ov

    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["gptcelltype"]
    query = ad.read_h5ad(REPO_ROOT / prepared["query_h5ad"])
    working, query_preprocessing = _prepare_log1p(query)
    if working.n_obs < 3 or working.n_vars < 3:
        raise ValueError("GPTCellType requires at least three cells and three genes.")

    n_top_genes = min(2_000, working.n_vars)
    clustering = working
    if n_top_genes < working.n_vars:
        sc.pp.highly_variable_genes(working, n_top_genes=n_top_genes, flavor="seurat")
        clustering = working[:, working.var["highly_variable"]].copy()
    n_pcs = min(50, clustering.n_obs - 1, clustering.n_vars - 1)
    sc.pp.pca(clustering, n_comps=n_pcs)
    sc.pp.neighbors(
        clustering,
        n_neighbors=min(15, clustering.n_obs - 1),
        n_pcs=n_pcs,
    )
    sc.tl.leiden(
        clustering,
        key_added="gptcelltype_cluster",
        resolution=resolution,
        random_state=42,
    )
    working.obs["gptcelltype_cluster"] = clustering.obs["gptcelltype_cluster"].copy()
    max_marker_cells_per_cluster = (
        max_marker_cells_per_cluster
        if max_marker_cells_per_cluster is not None
        else config.get("max_marker_cells_per_cluster")
    )
    max_marker_cells_total = (
        max_marker_cells_total
        if max_marker_cells_total is not None
        else config.get("max_marker_cells_total")
    )
    marker_sampling_random_seed = (
        marker_sampling_random_seed
        if marker_sampling_random_seed is not None
        else int(config.get("marker_sampling_random_seed", 42))
    )
    markers, marker_ranking_audit = _rank_gptcelltype_markers(
        working,
        "gptcelltype_cluster",
        top_marker_genes=top_marker_genes,
        max_cells_per_cluster=max_marker_cells_per_cluster,
        max_cells_total=max_marker_cells_total,
        random_seed=marker_sampling_random_seed,
    )
    cluster_assignments = working.obs["gptcelltype_cluster"].astype(str)
    marker_audit = _gptcelltype_marker_audit(
        markers,
        cluster_assignments,
        requested_top_marker_genes=top_marker_genes,
    )
    effective_provider_top_marker_genes = marker_audit["effective_provider_top_marker_genes"]
    if api_batch_size < 1 or api_batch_size > 29:
        raise ValueError("api_batch_size must be between 1 and 29.")
    if max_api_attempts_per_batch < 1:
        raise ValueError("max_api_attempts_per_batch must be positive.")

    output = _prediction_output(prepared, "gptcelltype")
    markers_path = output.with_suffix(".markers.json")
    assignments_path = output.with_suffix(".cluster_assignments.tsv")
    prompts_path = output.with_suffix(".prompts.json")
    markers_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": {},
                **marker_ranking_audit,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        {"cluster": cluster_assignments},
        index=working.obs_names,
    ).to_csv(assignments_path, sep="\t")
    marker_items = list(markers.items())
    cluster_labels: dict[str, str] = {}
    prompt_records: list[dict[str, Any]] = []
    api_calls = 0
    api_batches = 0
    try:
        for start in range(0, len(marker_items), api_batch_size):
            batch = dict(marker_items[start : start + api_batch_size])
            batch_labels, batch_calls = _run_gptcelltype_batch(
                ov,
                batch,
                config,
                max_api_attempts=max_api_attempts_per_batch,
                timeout_seconds=api_timeout_seconds,
                provider_top_marker_genes=effective_provider_top_marker_genes,
                prompt_records=prompt_records,
                api_batch_index=api_batches + 1,
            )
            cluster_labels.update(batch_labels)
            api_calls += batch_calls
            api_batches += 1
    except Exception as error:
        prompts_path.write_text(
            json.dumps(
                {
                    "status": "error",
                    "prompt_hash_algorithm": "sha256_utf8",
                    "records": prompt_records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        failure = {
            "status": "error",
            "method": "gptcelltype",
            "version": version,
            "model": config["model"],
            "stage": "remote_cluster_annotation",
            "error_type": type(error).__name__,
            "message": str(error),
            "n_clusters": len(markers),
            "api_batch_size": api_batch_size,
            "api_batches_completed": api_batches,
            "api_calls_completed": api_calls,
            **marker_ranking_audit,
            **marker_audit,
            "markers_path": str(markers_path.relative_to(REPO_ROOT)),
            "cluster_assignments_path": str(assignments_path.relative_to(REPO_ROOT)),
            "prompts_path": str(prompts_path.relative_to(REPO_ROOT)),
            "data_sent_to_provider": "cluster marker gene names only",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        output.with_suffix(".run.json").write_text(
            json.dumps(failure, indent=2),
            encoding="utf-8",
        )
        raise
    prompts_path.write_text(
        json.dumps(
            {
                "status": "success",
                "prompt_hash_algorithm": "sha256_utf8",
                "records": prompt_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    missing_clusters = sorted(set(markers).difference(cluster_labels))
    if missing_clusters:
        raise RuntimeError("GPTCellType omitted clusters: " + ", ".join(missing_clusters))
    raw_predictions = cluster_assignments.map(cluster_labels)
    if raw_predictions.isna().any():
        missing_count = int(raw_predictions.isna().sum())
        raise RuntimeError(f"GPTCellType returned {missing_count} missing predictions.")

    frame = pd.DataFrame(
        {
            "cell_id": working.obs_names,
            "raw_prediction": raw_predictions.to_numpy(),
            "confidence": np.nan,
            "method": "gptcelltype",
        }
    ).set_index("cell_id")
    frame.to_csv(output, sep="\t")
    clusters_path = output.with_suffix(".clusters.json")
    clusters_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": cluster_labels,
                **marker_ranking_audit,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    metadata = {
        "status": "success",
        "method": "gptcelltype",
        "version": version,
        "model": config["model"],
        "n_clusters": len(markers),
        "resolution": resolution,
        **marker_ranking_audit,
        **marker_audit,
        "api_batch_size": api_batch_size,
        "api_batches": api_batches,
        "api_calls": api_calls,
        "max_api_attempts_per_batch": max_api_attempts_per_batch,
        "api_timeout_seconds": api_timeout_seconds,
        "n_predictions": len(frame),
        "query_preprocessing": query_preprocessing,
        "output_path": str(output.relative_to(REPO_ROOT)),
        "clusters_path": str(clusters_path.relative_to(REPO_ROOT)),
        "cluster_assignments_path": str(assignments_path.relative_to(REPO_ROOT)),
        "prompts_path": str(prompts_path.relative_to(REPO_ROOT)),
        "data_sent_to_provider": "cluster marker gene names only",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
