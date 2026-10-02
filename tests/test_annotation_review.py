"""Review boundaries, minority protection and artifact preservation; no network."""

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "unit-test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import anndata as ad
import numpy as np
import pandas as pd
import config
from agents.agent_registry.cell_annotater_agent.tools_impl import annotation_review as review
from agents.agent_registry.cell_annotater_agent.tools_impl import harmony_transfer
from agents.agent_registry.cell_annotater_agent.tools_impl.reference_labels import (
    biological_label_mask,
)


class ReviewTests(unittest.TestCase):
    """Exercise scientific edit guards and the artifact contract."""

    def setUp(self):
        """Create an isolated native primary artifact with a distinct minority."""
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        (self.project / "outputs").mkdir(parents=True)
        (self.project / "uploads").mkdir()
        self.patches = [
            patch.object(config, "DATA_DIR", self.root),
            patch.object(config, "ACTIVE_PROJECT_DIR", self.project),
        ]
        for p in self.patches:
            p.start()
        rng = np.random.default_rng(2)
        x = rng.uniform(0.01, 0.1, (120, 12)).astype(np.float32)
        x[:80, :3] += 2
        x[60:80, 3:6] += 3
        x[80:, 6:9] += 3
        obs = pd.DataFrame(index=[f"cell{i}" for i in range(120)])
        obs[review.PRIMARY] = ["primary A"] * 60 + ["minority B"] * 20 + ["primary C"] * 40
        obs[review.CONFIDENCE] = 0.99
        obs["cell_annotation_method"] = "harmony"
        obs["cell_annotation_status"] = "transferred"
        obs["hidden_ground_truth"] = "NEVER_SEND_SECRET"
        self.data = ad.AnnData(x, obs=obs, var=pd.DataFrame(index=[f"GENE{i}" for i in range(12)]))
        self.data.uns["tissueagent_cell_annotation"] = {"annotation_method": "harmony"}
        self.data.uns["unrelated"] = "NEVER_SEND_SECRET"
        self.path = self.project / "uploads" / "primary.h5ad"
        self.data.write_h5ad(self.path)

    def tearDown(self):
        """Restore workspace configuration."""
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def inspect(self):
        """Inspect a known partition while exercising real marker extraction."""
        clusters = np.array(["0"] * 80 + ["1"] * 40, dtype=object)
        with patch.object(
            review,
            "_cluster_review_working_copy",
            return_value=(
                clusters,
                np.zeros(120, dtype=bool),
                {"random_state": 42},
            ),
        ):
            r = review.inspect_annotation_evidence_tool(
                "uploads/primary.h5ad", "review/evidence", "human", "test tissue"
            )
        self.assertEqual(r["status"], "success", r)
        evidence = json.loads((self.root / r["evidence_path"]).read_text())
        return r, evidence

    def test_placeholder_policy_does_not_discard_rare_biology(self):
        """Filter placeholder identities rather than rare biological classes."""
        labels = pd.Series(["unknown", " Unknown ", None, "cell", "fibroblast", "rare cell"])
        self.assertEqual(
            biological_label_mask(labels).tolist(), [False, False, False, False, True, True]
        )

    def test_evidence_excludes_truth_preserves_input_and_detects_minority(self):
        """Only expression and native primary predictions enter review evidence."""
        before = review.file_sha256(self.path)
        _, evidence = self.inspect()
        self.assertNotIn("NEVER_SEND_SECRET", json.dumps(evidence))
        self.assertEqual(before, review.file_sha256(self.path))
        group = next(g for g in evidence["groups"] if g["primary_label"] == "minority B")
        self.assertTrue(group["distinct_minority"])
        self.assertGreaterEqual(len(group["within_cluster_markers"]), 2)
        self.assertEqual(evidence["ontology"]["status"], "not_assessable")
        self.assertEqual(evidence["quality_control"]["doublet"]["status"], "not_assessable")
        self.assertEqual(
            evidence["quality_control"]["ambient_rna"]["status"], "not_assessable"
        )

    def test_real_clustering_small_expression_matrix(self):
        """Smoke-test the real numerical clustering path."""
        result = review.inspect_annotation_evidence_tool(
            "uploads/primary.h5ad", "real/evidence", "human", "test tissue"
        )
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(result["n_cells"], 120)
        evidence = json.loads(review.resolve_workspace_input(result["evidence_path"]).read_text())
        self.assertEqual(evidence["clustering"]["leiden_n_iterations"], 2)
        self.assertEqual(evidence["clustering"]["leiden_flavor"], "igraph")
        self.assertFalse(evidence["clustering"]["leiden_directed"])

    def test_decision_validation_rejects_hallucinated_markers_and_minority_erasure(self):
        """Changes require measured evidence specific to any distinct minority."""
        _, evidence = self.inspect()
        group = next(g for g in evidence["groups"] if g["distinct_minority"])
        decision = {
            group["group_id"]: {
                "action": "revise",
                "label": "new label",
                "cell_type_ontology_id": None,
                "cell_state": None,
                "reason": "evidence",
                "support_markers": ["INVENTED", "GENE0"],
            }
        }
        with self.assertRaises(ValueError):
            review._validate_decisions(decision, [group])
        markers = [
            m["gene"]
            for m in group["markers"]
            if m["gene"] not in {v["gene"] for v in group["within_cluster_markers"]}
        ][:2]
        decision[group["group_id"]]["support_markers"] = markers
        review._validate_decisions(decision, [group])
        self.assertEqual(decision[group["group_id"]]["action"], "keep")
        self.assertIn(
            "within-cluster marker evidence", decision[group["group_id"]]["reason"]
        )
        small = copy.deepcopy(group)
        small["change_eligible"] = False
        decision[group["group_id"]].update(
            action="revise",
            label="new label",
            cell_type_ontology_id=None,
            cell_state=None,
            reason="evidence",
        )
        decision[group["group_id"]]["support_markers"] = [
            m["gene"] for m in group["within_cluster_markers"][:2]
        ]
        review._validate_decisions(decision, [small])
        self.assertEqual(decision[group["group_id"]]["action"], "keep")
        self.assertIn("small or marker-poor", decision[group["group_id"]]["reason"])

    def test_keep_discards_unsupported_citations_without_authorizing_an_edit(self):
        """A safe no-op must not publish the model's invented marker evidence."""
        _, evidence = self.inspect()
        group = evidence["groups"][0]
        decision = {
            "action": "keep",
            "label": group["primary_label"],
            "cell_type_ontology_id": group["primary_cell_type_ontology_id"],
            "cell_state": None,
            "support_markers": ["INVENTED_GENE"],
            "reason": "INVENTED_GENE proves this label.",
        }
        review._validate_decisions({group["group_id"]: decision}, [group])
        self.assertEqual(decision["label"], group["primary_label"])
        self.assertEqual(decision["support_markers"], [])
        self.assertNotIn("INVENTED_GENE", decision["reason"])
        self.assertIn("discarded unsupported", decision["reason"])

    def test_revise_omits_unverified_ontology_id_without_bound_graph(self):
        """Keep a supported type edit but never publish an unverified LLM CL ID."""
        _, evidence = self.inspect()
        group = next(g for g in evidence["groups"] if not g["distinct_minority"])
        markers = [m["gene"] for m in group["markers"][:2]]
        decision = {
            group["group_id"]: {
                "action": "revise",
                "label": "new measured identity",
                "cell_type_ontology_id": "CL:0000001",
                "cell_state": None,
                "support_markers": markers,
                "reason": "two measured markers support the revision",
            }
        }
        review._validate_decisions(decision, [group], ontology_graph=None)
        normalized = decision[group["group_id"]]
        self.assertIsNone(normalized["cell_type_ontology_id"])
        self.assertEqual(normalized["label"], "new measured identity")
        self.assertIn("Unverified Cell Ontology ID omitted", normalized["reason"])

    def test_ontology_broadening_and_cell_state_are_separate_validated_edits(self):
        """Permit verified ancestors and marker-supported state without replacing type."""
        _, evidence = self.inspect()
        group = next(g for g in evidence["groups"] if g["primary_label"] == "primary A")
        markers = [m["gene"] for m in group["markers"][:2]]
        graph = {
            "version": "test",
            "aliases": {},
            "terms": {
                "CL:0000001": {"name": "fine cell", "parents": ["CL:0000000"]},
                "CL:0000000": {"name": "broad cell", "parents": []},
            },
        }
        group["primary_cell_type_ontology_id"] = "CL:0000001"
        group["hierarchy_status"] = "assessable"
        group["allowed_broader_terms"] = [{"id": "CL:0000000", "name": "broad cell"}]
        broaden = {
            group["group_id"]: {
                "action": "broaden",
                "label": "Broad Cell",
                "cell_type_ontology_id": "CL:0000000",
                "cell_state": None,
                "support_markers": markers,
                "reason": "measured evidence supports only the parent",
            }
        }
        review._validate_decisions(broaden, [group], graph)
        self.assertEqual(broaden[group["group_id"]]["label"], "broad cell")
        state = {
            group["group_id"]: {
                "action": "keep",
                "label": group["primary_label"],
                "cell_type_ontology_id": "CL:0000001",
                "cell_state": "cycling",
                "support_markers": markers,
                "reason": "two measured markers support the state",
            }
        }
        review._validate_decisions(state, [group], graph)
        self.assertEqual(state[group["group_id"]]["label"], "primary A")

    def test_reference_ontology_mapping_requires_one_id_per_label(self):
        """Carry unique reference CL IDs while explicitly reporting ambiguous labels."""
        reference = ad.AnnData(
            np.ones((4, 2), dtype=np.float32),
            obs=pd.DataFrame(
                {
                    "cell_type": ["A", "A", "B", "B"],
                    "cell_type_ontology_term_id": [
                        "CL:0000001",
                        "CL:0000001",
                        "CL:0000002",
                        "CL:0000003",
                    ],
                },
                index=["r1", "r2", "r3", "r4"],
            ),
            var=pd.DataFrame(index=["g1", "g2"]),
        )
        reference.write_h5ad(self.project / "uploads/reference.h5ad")
        self.data.uns["tissueagent_cell_annotation"] = {
            "annotation_method": "harmony",
            "reference_anndata_path": "project/uploads/reference.h5ad",
            "reference_cell_type_column": "cell_type",
        }
        mapping, metadata = review._reference_ontology_ids(self.data)
        self.assertEqual(mapping, {"A": "CL:0000001"})
        self.assertEqual(metadata["ambiguous_labels"], ["B"])

    def test_versioned_ontology_parser_and_non_destructive_doublet_flags(self):
        """Parse ancestry and retain one QC result for every input row."""
        ontology = self.project / "uploads/test.obo"
        ontology.write_text(
            """format-version: 1.2
data-version: test-release

[Term]
id: CL:0000000
name: broad cell

[Term]
id: CL:0000001
name: fine cell
is_a: CL:0000000 ! broad cell
"""
        )
        graph = review._parse_cell_ontology(ontology)
        self.assertEqual(graph["version"], "test-release")
        self.assertEqual(review._ontology_ancestors(graph, "CL:0000001"), ["CL:0000000"])

        raw = ad.AnnData(
            np.ones((100, 500), dtype=np.int32),
            obs=pd.DataFrame(index=[f"q{i}" for i in range(100)]),
            var=pd.DataFrame(index=[f"g{i}" for i in range(500)]),
        )

        class FakeDetector:
            def __init__(self, matrix, random_state):
                self.threshold_ = 0.25

            def scrub_doublets(self, verbose):
                return np.linspace(0, 1, 100), np.arange(100) >= 95

        fake_module = MagicMock(Scrublet=FakeDetector)
        with patch.object(review.importlib, "import_module", return_value=fake_module):
            summary, assignments = review._doublet_qc(raw, "raw_count_like", 43)
        self.assertEqual(summary["status"], "assessed")
        self.assertEqual(summary["random_state"], 43)
        self.assertEqual(summary["n_predicted_doublets"], 5)
        self.assertEqual(len(assignments["doublet_scores"]), raw.n_obs)
        self.assertEqual(raw.n_obs, 100)

    def test_changed_primary_fails_before_model_call(self):
        """Reject a stale primary identity before making paid requests."""
        r, _ = self.inspect()
        self.data.obs[review.PRIMARY] = "modified"
        self.data.write_h5ad(self.path)
        with patch.object(review, "model_ctor_for_role") as ctor:
            result = review.refine_cell_annotations_tool(
                r["evidence_path"], r["evidence_sha256"], "final.h5ad"
            )
        self.assertEqual(result["status"], "error")
        ctor.assert_not_called()

    def test_invalid_model_output_is_bounded_and_leaves_only_failure_audit(self):
        """Two invalid responses must not publish a successful annotation."""
        result, _ = self.inspect()
        model = MagicMock()
        model.invoke.return_value.content = "{}"
        with patch.object(review, "model_ctor_for_role", return_value=lambda: model):
            failed = review.refine_cell_annotations_tool(
                result["evidence_path"], result["evidence_sha256"], "failed.h5ad"
            )
        self.assertEqual(failed["status"], "error", failed)
        self.assertEqual(model.invoke.call_count, 2)
        self.assertFalse((self.project / "outputs/failed.h5ad").exists())
        self.assertFalse((self.project / "outputs/failed.run_meta.json").exists())
        audit = json.loads((self.project / "outputs/failed.review.json").read_text())
        self.assertEqual(audit["status"], "error")
        self.assertEqual(len(audit["model_calls"][0]["attempts"]), 2)

    def test_review_resumes_after_completed_screening_batch(self):
        """Persist completed batches and skip them after a transient refinement failure."""
        result, _ = self.inspect()

        def fail_after_screen(model, system, payload, audit, validate):
            if "clusters" in payload:
                output = {
                    item["cluster_id"]: {"review": True, "reason": "review evidence"}
                    for item in payload["clusters"]
                }
                validate(output)
                audit.append({"payload": payload, "response": output})
                return output
            raise ConnectionError("temporary provider failure")

        with (
            patch.object(review, "model_ctor_for_role", return_value=lambda: object()),
            patch.object(review, "_ask_json", side_effect=fail_after_screen),
        ):
            failed = review.refine_cell_annotations_tool(
                result["evidence_path"], result["evidence_sha256"], "resume/final.h5ad"
            )
        self.assertEqual(failed["status"], "error", failed)
        checkpoint_path = self.project / "outputs/resume/final.review.checkpoint.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        self.assertEqual(set(checkpoint["screened_cluster_ids"]), {"0", "1"})

        def resume_without_screening(model, system, payload, audit, validate):
            self.assertNotIn("clusters", payload, "completed screening must not be repeated")
            output = {
                item["group_id"]: {
                    "action": "keep",
                    "label": item["primary_label"],
                    "cell_type_ontology_id": item["primary_cell_type_ontology_id"],
                    "cell_state": None,
                    "support_markers": [],
                    "reason": "retain supported primary identity",
                }
                for item in payload["groups"]
            }
            validate(output)
            audit.append({"payload": payload, "response": output})
            return output

        with (
            patch.object(review, "model_ctor_for_role", return_value=lambda: object()),
            patch.object(review, "_ask_json", side_effect=resume_without_screening),
        ):
            resumed = review.refine_cell_annotations_tool(
                result["evidence_path"], result["evidence_sha256"], "resume/final.h5ad"
            )
        self.assertEqual(resumed["status"], "success", resumed)
        self.assertFalse(checkpoint_path.exists())

    def test_cross_domain_diagnostics_discount_shift_without_changing_labels(self):
        """Report embedding shift and calibrate confidence without relabeling cells."""
        rng = np.random.default_rng(9)
        reference = rng.normal(size=(120, 4)).astype(np.float32)
        query = (rng.normal(size=(80, 4)) + 8).astype(np.float32)
        labels = np.array(["A"] * 60 + ["B"] * 60)
        probabilities = np.tile(np.array([[0.95, 0.05]]), (80, 1))
        raw_labels = np.array(["A"] * 80)
        diagnostics = harmony_transfer._cross_domain_transfer_diagnostics(
            reference,
            query,
            labels,
            probabilities,
            np.array(["A", "B"]),
        )
        self.assertEqual(diagnostics["risk_level"], "high")
        self.assertLess(diagnostics["support_confidence_factor"], 1.0)
        self.assertGreater(diagnostics["query_to_reference_distance_ratio"], 2.0)
        self.assertEqual(raw_labels.tolist(), ["A"] * 80)

    def test_tampered_evidence_is_rejected_before_model_call(self):
        """A changed marker artifact cannot reuse its original binding hash."""
        result, _ = self.inspect()
        path = review.resolve_workspace_input(result["evidence_path"])
        path.write_text(path.read_text() + " ")
        with patch.object(review, "model_ctor_for_role") as ctor:
            failed = review.refine_cell_annotations_tool(
                result["evidence_path"], result["evidence_sha256"], "tampered.h5ad"
            )
        self.assertEqual(failed["status"], "error", failed)
        ctor.assert_not_called()

    def test_review_updates_only_target_group_preserves_confidence_and_audit(self):
        """Publishing edits must preserve untouched groups, expression, and primary labels."""
        r, evidence = self.inspect()
        target = next(g for g in evidence["groups"] if g["primary_label"] == "primary A")

        def fake_ask(model, system, payload, audit, validate):
            self.assertNotIn("NEVER_SEND_SECRET", json.dumps(payload))
            if "clusters" in payload:
                out = {
                    c["cluster_id"]: {"review": c["cluster_id"] == "0", "reason": "review evidence"}
                    for c in payload["clusters"]
                }
            else:
                out = {
                    g["group_id"]: {
                        "action": "keep",
                        "label": g["primary_label"],
                        "cell_type_ontology_id": g["primary_cell_type_ontology_id"],
                        "cell_state": None,
                        "reason": "retain minority",
                        "support_markers": [],
                    }
                    for g in payload["groups"]
                }
                out[target["group_id"]] = {
                    "action": "revise",
                    "label": "corrected A",
                    "cell_type_ontology_id": None,
                    "cell_state": None,
                    "reason": "measured expression",
                    "support_markers": [m["gene"] for m in target["markers"][:2]],
                }
            validate(out)
            audit.append({"payload": payload, "response": out})
            return out

        with (
            patch.object(review, "model_ctor_for_role", return_value=lambda: object()),
            patch.object(review, "_ask_json", side_effect=fake_ask),
        ):
            result = review.refine_cell_annotations_tool(
                r["evidence_path"], r["evidence_sha256"], "review/final.h5ad"
            )
        self.assertEqual(result["status"], "success", result)
        out = ad.read_h5ad(self.root / result["annotated_object_h5ad"])
        self.assertEqual(out.obs_names.tolist(), self.data.obs_names.tolist())
        np.testing.assert_array_equal(out.X, self.data.X)
        self.assertEqual(
            out.obs["cell_annotation_primary_label"].tolist(),
            self.data.obs[review.PRIMARY].tolist(),
        )
        self.assertTrue(out.obs.iloc[:60][review.CONFIDENCE].isna().all())
        self.assertTrue((out.obs.iloc[60:80][review.PRIMARY] == "minority B").all())
        self.assertIn(review.ONTOLOGY_ID, out.obs)
        self.assertIn(review.CELL_STATE, out.obs)
        self.assertTrue(out.obs[review.CELL_STATE].isna().all())
        self.assertTrue(out.obs["cell_annotation_qc_doublet_score"].isna().all())
        self.assertEqual(result["n_changed"], 60)
        original_hash = review.file_sha256(self.root / result["annotated_object_h5ad"])
        repeat = review.refine_cell_annotations_tool(
            r["evidence_path"], r["evidence_sha256"], "review/final.h5ad"
        )
        self.assertEqual(repeat["status"], "error")
        self.assertEqual(
            original_hash, review.file_sha256(self.root / result["annotated_object_h5ad"])
        )

    def test_retrieval_retains_context_filters_placeholders_and_rejects_cache_drift(self):
        """Mock Census I/O while exercising real subset sampling and provenance."""
        from agents.agent_registry.single_cell_agent.tools_impl import (
            retrieve_cellxgene_single_cell_tool as retrieval,
        )

        dataset_id = "5500c673-1610-40a0-86d9-64d987ae50e6"
        census = MagicMock()
        census["census_info"][
            "datasets"
        ].read.return_value.concat.return_value.to_pandas.return_value = pd.DataFrame(
            {"dataset_id": [dataset_id], "dataset_total_cell_count": [4]}
        )
        census["census_data"][
            "homo_sapiens"
        ].obs.read.return_value.concat.return_value.to_pandas.return_value = pd.DataFrame(
            {
                "soma_joinid": [0, 1, 2, 3],
                "dataset_id": [dataset_id] * 4,
                "cell_type": ["unknown", "A", "A", "B"],
            }
        )
        returned_obs = pd.DataFrame(
            {
                "dataset_id": [dataset_id] * 3,
                "cell_type": ["A", "A", "B"],
                "donor_id": ["d1", "d2", "d2"],
                "development_stage": ["fetal"] * 3,
                "cell_type_ontology_term_id": ["CL:0000000"] * 3,
            },
            index=["c1", "c2", "c3"],
        )
        reference = ad.AnnData(
            np.ones((3, 3), dtype=np.float32),
            obs=returned_obs,
            var=pd.DataFrame({"feature_name": ["A", "B", "C"]}, index=["A", "B", "C"]),
        )
        with (
            patch.object(retrieval.cellxgene_census, "open_soma") as open_soma,
            patch.object(
                retrieval.cellxgene_census, "get_anndata", return_value=reference
            ) as get_data,
        ):
            open_soma.return_value.__enter__.return_value = census
            result = retrieval.retrieve_cellxgene_reference_subset(
                [dataset_id],
                "reference.h5ad",
                "test-release",
                organism="Homo sapiens",
                development_stages=["fetal"],
            )
            self.assertEqual(result["status"], "success", result)
            call = get_data.call_args.kwargs
            self.assertEqual(call["obs_coords"].tolist(), [1, 2, 3])
            self.assertIn("donor_id", call["obs_column_names"])
            self.assertIn("development_stage", call["obs_column_names"])
            self.assertIn("cell_type_ontology_term_id", call["obs_column_names"])
        saved = ad.read_h5ad(self.project / "outputs" / "reference.h5ad")
        self.assertEqual(
            saved.uns["tissueagent_cellxgene_subset"][
                "n_placeholder_cells_excluded_before_sampling"
            ],
            1,
        )
        cached = retrieval.retrieve_cellxgene_reference_subset(
            [dataset_id],
            "reference.h5ad",
            "test-release",
            organism="Homo sapiens",
            development_stages=["fetal"],
        )
        self.assertEqual(cached["status"], "success", cached)
        self.assertTrue(cached["cache_hit"])
        provenance = json.loads(
            (self.project / "outputs" / "reference.provenance.json").read_text()
        )
        self.assertEqual(provenance["n_placeholder_cells_excluded_before_sampling"], 1)
        drift = retrieval.retrieve_cellxgene_reference_subset(
            [dataset_id],
            "reference.h5ad",
            "test-release",
            organism="Homo sapiens",
            development_stages=["adult"],
        )
        self.assertEqual(drift["status"], "error", drift)
        self.assertIn("development_stages", drift["message"])


if __name__ == "__main__":
    unittest.main()
