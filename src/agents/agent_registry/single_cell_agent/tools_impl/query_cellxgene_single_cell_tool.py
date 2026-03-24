"""Live-query and aggregate CELLxGENE Census datasets by tissue, disease, and other criteria."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Dict, Any
from collections import defaultdict
from typing import Union
import pandas as pd
import cellxgene_census as cg


# ---------------------------
# Query schema and utilities
# ---------------------------


@dataclass
class CensusQuery:
    """Criteria for live filtering of CELLxGENE Census obs.

    Provide labels (NOT ontology IDs) for tissue/disease/etc. that match the obs columns.
    Handle ontology expansion/synonyms before calling this.
    """

    species: str = "homo_sapiens"  # "homo_sapiens" | "mus_musculus"
    tissue_general: Optional[List[str]] = None
    tissue: Optional[List[str]] = None
    disease: Optional[List[str]] = None
    development_stage: Optional[List[str]] = None
    sex: Optional[List[str]] = None
    assay: Optional[List[str]] = None
    is_primary_data: Optional[bool] = True  # Prefer primary by default
    columns_extra: Optional[List[str]] = (
        None  # e.g., ["cell_type"] if you plan to post-aggregate cell types
    )
    # Output controls
    include_cell_type_counts: bool = False
    top_k_cell_types: int = 15  # Only used if include_cell_type_counts=True

    def needed_columns(self) -> List[str]:
        """Return the list of Census obs columns required by this query."""
        base = [
            "dataset_id",
            "donor_id",
            "tissue_general",
            "tissue",
            "disease",
            "development_stage",
            "sex",
            "assay",
            "is_primary_data",
        ]
        if self.include_cell_type_counts:
            base.append("cell_type")
        if self.columns_extra:
            for c in self.columns_extra:
                if c not in base:
                    base.append(c)
        return base


def _normalize_species(species: str) -> str:
    """Map common species aliases to canonical Census organism names."""
    s = species.strip().lower().replace(" ", "_")
    if s in {"human", "homo", "h sapiens", "h_sapiens", "homo sapiens"}:
        return "homo_sapiens"
    if s in {"mouse", "mice", "mmusculus", "m_musculus", "mus musculus"}:
        return "mus_musculus"
    # assume user passed canonical
    return s


def _or_equals(col: str, values: Iterable[str]) -> str:
    """Build a SOMA value_filter OR clause like ``(col == "v1" or col == "v2")``."""
    safe_vals = [str(v).replace('"', '\\"') for v in values if v is not None]
    if not safe_vals:
        return ""
    parts = [f'{col} == "{v}"' for v in safe_vals]
    return "(" + " or ".join(parts) + ")"


def _build_value_filter(q: CensusQuery) -> str:
    """Assemble a SOMA value_filter string from all non-None query criteria."""
    clauses = []

    if q.tissue_general:
        clauses.append(_or_equals("tissue_general", q.tissue_general))
    if q.tissue:
        clauses.append(_or_equals("tissue", q.tissue))
    if q.disease:
        clauses.append(_or_equals("disease", q.disease))
    if q.development_stage:
        clauses.append(_or_equals("development_stage", q.development_stage))
    if q.sex:
        clauses.append(_or_equals("sex", q.sex))
    if q.assay:
        clauses.append(_or_equals("assay", q.assay))
    if q.is_primary_data is not None:
        clauses.append(f"is_primary_data == {bool(q.is_primary_data)}")

    # Filter string for SOMA: join non-empty clauses with AND
    clauses = [c for c in clauses if c]
    return " and ".join(clauses) if clauses else ""


# ---------------------------
# Main live query function
# ---------------------------


def query_cellxgene_census_live(
    query: CensusQuery,
    census_version: str = "latest",
    enrich_metadata: bool = False,
    max_results: Optional[int] = None,
) -> pd.DataFrame:
    """Live query against CELLxGENE Census SOMA obs using value_filter, streaming aggregation.

    Returns a DataFrame with one row per dataset_id and columns:
      ['dataset_id', 'n_cells', 'n_donors', 'assays', 'tissues_general', 'tissues',
       'diseases', 'development_stages', 'sexes', 'is_primary_data',
       'cell_type_topK' (optional), 'census_version', ... + optional dataset metadata]

    Args:
        query: CensusQuery with your criteria.
        census_version: 'latest' or a pinned version.
        enrich_metadata: join dataset title/collection info from get_datasets().
        max_results: if provided, truncates to top-N by n_cells.
    """
    org = _normalize_species(query.species)
    value_filter = _build_value_filter(query)
    cols = query.needed_columns()

    # Aggregation holders
    n_cells = defaultdict(int)
    donors = defaultdict(set)
    assays = defaultdict(set)
    tissues_general = defaultdict(set)
    tissues = defaultdict(set)
    diseases = defaultdict(set)
    devstages = defaultdict(set)
    sexes = defaultdict(set)
    primary_flags = defaultdict(list)
    celltype_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    with cg.open_soma(census_version=census_version) as census:
        if org not in census["census_data"]:
            raise ValueError(f"Organism '{org}' not found in this census version.")
        obs = census["census_data"][org].obs

        reader = obs.read(
            value_filter=value_filter if value_filter else None,
            column_names=cols,
        )

        # Stream over arrow Tables to stay memory-friendly

        for tbl in reader:
            df = tbl.to_pandas(types_mapper=None)
            # Update aggregations
            for ds_id, sub in df.groupby("dataset_id", dropna=True):
                n = len(sub)
                if n == 0:  # shouldn't happen, but be safe
                    continue
                n_cells[ds_id] += n
                donors[ds_id].update(x for x in sub["donor_id"].dropna().unique())
                assays[ds_id].update(x for x in sub["assay"].dropna().unique())
                tissues_general[ds_id].update(x for x in sub["tissue_general"].dropna().unique())
                tissues[ds_id].update(x for x in sub["tissue"].dropna().unique())
                diseases[ds_id].update(x for x in sub["disease"].dropna().unique())
                devstages[ds_id].update(x for x in sub["development_stage"].dropna().unique())
                sexes[ds_id].update(x for x in sub["sex"].dropna().unique())
                primary_flags[ds_id].extend(sub["is_primary_data"].dropna().astype(bool).tolist())

                if query.include_cell_type_counts and "cell_type" in sub.columns:
                    ct_counts = sub["cell_type"].value_counts(dropna=True).to_dict()
                    for ct, c in ct_counts.items():
                        celltype_counts[ds_id][ct] += int(c)

    # Materialize per-dataset rows
    rows: List[Dict[str, Any]] = []
    for ds_id in n_cells.keys():
        row = {
            "dataset_id": ds_id,
            "n_cells": n_cells[ds_id],
            "n_donors": len(donors[ds_id]) if donors[ds_id] else 0,
            "assays": sorted(list(assays[ds_id])) if assays[ds_id] else [],
            "tissues_general": sorted(list(tissues_general[ds_id]))
            if tissues_general[ds_id]
            else [],
            "tissues": sorted(list(tissues[ds_id])) if tissues[ds_id] else [],
            "diseases": sorted(list(diseases[ds_id])) if diseases[ds_id] else [],
            "development_stages": sorted(list(devstages[ds_id])) if devstages[ds_id] else [],
            "sexes": sorted(list(sexes[ds_id])) if sexes[ds_id] else [],
            "is_primary_data": _mode_bool(primary_flags[ds_id]),
            "census_version": census_version,
        }
        if query.include_cell_type_counts:
            # keep top-K as list of tuples
            topK = sorted(celltype_counts[ds_id].items(), key=lambda kv: kv[1], reverse=True)[
                : query.top_k_cell_types
            ]
            row["cell_type_topK"] = topK
        rows.append(row)

    if not rows:
        return pd.DataFrame(
            columns=[
                "dataset_id",
                "n_cells",
                "n_donors",
                "assays",
                "tissues_general",
                "tissues",
                "diseases",
                "development_stages",
                "sexes",
                "is_primary_data",
                "census_version",
                *(["cell_type_topK"] if query.include_cell_type_counts else []),
            ]
        )

    out = pd.DataFrame(rows).sort_values("n_cells", ascending=False, ignore_index=True)
    # Drop zero-cell datasets (if any slipped through)
    out = out[out["n_cells"] > 0].sort_values("n_cells", ascending=False, ignore_index=True)

    # Optional: limit to top-N by size before enrichment
    if max_results is not None and max_results > 0:
        out = out.head(max_results).reset_index(drop=True)

    # Enrich with dataset/collection metadata
    if enrich_metadata:
        try:
            meta = cg.get_datasets(census_version=census_version)  # returns a DataFrame
            # Keep a few useful columns if present
            keep_cols = [
                "dataset_id",
                "dataset_title",
                "dataset_asset_h5ad_uri",
                "collection_id",
                "collection_name",
                "collection_doi",
                "collection_is_published",
                "dataset_published_at",
                "collection_url",
                "dataset_url",
                "explorer_url",
                "reference_organism",
            ]
            meta = meta[[c for c in keep_cols if c in meta.columns]].drop_duplicates("dataset_id")
            out = out.merge(meta, on="dataset_id", how="left")
        except Exception as e:
            # Non-fatal if metadata fetch fails
            out["metadata_error"] = str(e)

    return out


def _mode_bool(vals: List[bool]) -> Optional[bool]:
    """Return the majority boolean value, or None on empty or tie."""
    if not vals:
        return None
    # Assume field is constant per dataset; fallback to majority vote
    trues = sum(1 for v in vals if v)
    falses = len(vals) - trues
    if trues == falses:
        return None
    return trues > falses


def _coerce_str_or_list(x: Optional[Union[str, Iterable[str]]]) -> Optional[List[str]]:
    """Accept None, a single string, or an iterable of strings; normalize to list[str] or None."""
    if x is None:
        return None
    if isinstance(x, str):
        x = x.strip()
        return [x] if x else None
    # Filter out Nones/empties, keep order
    out = [str(v).strip() for v in x if v is not None and str(v).strip() != ""]
    return out or None


def run_query_cellxgene_census_live(
    species: str = "homo_sapiens",
    tissue_general: Optional[Union[str, List[str]]] = None,
    tissue: Optional[Union[str, List[str]]] = None,
    disease: Optional[Union[str, List[str]]] = None,
    development_stage: Optional[Union[str, List[str]]] = None,
    sex: Optional[Union[str, List[str]]] = None,
    assay: Optional[Union[str, List[str]]] = (
        # Common scRNA-seq assays (feel free to tweak)
        [
            "10x 3' v3",
            "10x 3' v2",
            "10x 5' v1",
            "10x 5' v2",
            "10x 5' transcription profiling",
            "10x 3' transcription profiling",
            "Smart-seq3",
            "Smart-seq2",
            "Smart-seq",
            "Drop-seq",
            "CEL-Seq2",
            "inDrops",
            "Seq-Well",
            "Microwell-seq",
            "Fluidigm C1",
        ]
    ),
    is_primary_data: Optional[bool] = True,
    include_cell_type_counts: bool = False,
    top_k_cell_types: int = 15,
    census_version: str = "latest",
    enrich_metadata: bool = True,
    max_results: Optional[int] = 20,
) -> str:
    """Live-filter CELLxGENE Census by species/tissue/disease/etc. and aggregate per dataset.

    Returns JSON (list of dataset dicts).
    """
    q = CensusQuery(
        species=species,
        tissue_general=_coerce_str_or_list(tissue_general),
        tissue=_coerce_str_or_list(tissue),
        disease=_coerce_str_or_list(disease),
        development_stage=_coerce_str_or_list(development_stage),
        sex=_coerce_str_or_list(sex),
        assay=_coerce_str_or_list(assay),
        is_primary_data=is_primary_data,
        include_cell_type_counts=include_cell_type_counts,
        top_k_cell_types=int(top_k_cell_types),
    )

    limit = None if (max_results is None) else int(max_results)
    if limit is not None and limit <= 0:
        limit = None

    df = query_cellxgene_census_live(
        query=q,
        census_version=census_version,
        enrich_metadata=enrich_metadata,
        max_results=limit,
    )

    if df is None or df.empty:
        return "No datasets matched the query parameters."
    else:
        return df.to_json(orient="records")
