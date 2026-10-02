"""Batch resumption, spatial screening, minority preservation and optional anchors."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_niche_artifact_recovery as fixtures
import anndata as ad
import numpy as np
import pandas as pd
from langchain_core.messages import AIMessage
import config
from agents.agent_registry.cell_annotater_agent.tools_impl import niche_batch as batch
from agents.agent_registry.cell_annotater_agent.tools_impl import niche_review as review


class FakeModel:
    model_name = "test-model"
    temperature = 0
    seed = 42
    reasoning_effort = "high"

    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def invoke(self, messages):
        self.calls.append(messages)
        if len(self.calls) == self.fail_at:
            raise ConnectionError("simulated interruption")
        payload = json.loads(messages[1].content)
        records = [
            {"niche_id": key, "label": "A", "justification": "Measured evidence"}
            for key in payload["niches"]
        ]
        return AIMessage(content=json.dumps({"annotations": records}))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "checkpoint.json"
        self.queries = {
            str(
                i
            ): f"Measured niche {i}\nOther clusters in this section (IDs are computational, not known anatomical regions):\nshared overview"
            for i in range(17)
        }

    def run_batch(self, model, **kwargs):
        return batch.label_niche_batches(
            self.queries, ["A", "B", "Unmatched"], "Unmatched", model, self.path, **kwargs
        )

    def test_batches_share_context_once_and_preserve_all_ids(self):
        model = FakeModel()
        result = self.run_batch(model)
        self.assertEqual(len(model.calls), 3)
        self.assertEqual(set(result), set(self.queries))
        self.assertEqual(model.calls[0][1].content.count("shared overview"), 1)

    def test_resume_never_repeats_completed_batches(self):
        model = FakeModel(fail_at=2)
        with self.assertRaises(ConnectionError):
            self.run_batch(model)
        self.assertEqual(len(json.loads(self.path.read_text())["results"]), 8)
        resumed = FakeModel()
        self.assertEqual(len(self.run_batch(resumed)), 17)
        self.assertEqual(len(resumed.calls), 2)
        self.assertNotIn('"0"', resumed.calls[0][1].content)
        finished = FakeModel()
        self.run_batch(finished)
        self.assertEqual(len(finished.calls), 0)

    def test_changed_evidence_and_model_settings_cannot_reuse_checkpoint(self):
        self.run_batch(FakeModel())
        self.queries["0"] = "changed measured evidence"
        with self.assertRaisesRegex(ValueError, "different evidence/settings"):
            self.run_batch(FakeModel())

    def test_missing_duplicate_and_unpermitted_annotations_are_rejected(self):
        for records in (
            [],
            [{"niche_id": "0", "label": "A", "justification": "x"}] * 8,
            [{"niche_id": str(i), "label": "invented", "justification": "x"} for i in range(8)],
        ):
            model = FakeModel()
            model.invoke = Mock(
                return_value=AIMessage(content=json.dumps({"annotations": records}))
            )
            with self.assertRaises(ValueError):
                self.run_batch(model)
            self.assertFalse(self.path.exists())


class ReviewTests(unittest.TestCase):
    setUp = fixtures.NicheArtifactTests.setUp
    annotate = fixtures.NicheArtifactTests.annotate
    completed = fixtures.NicheArtifactTests.completed
    sha = fixtures.NicheArtifactTests.sha

    def test_insufficient_gene_support_cannot_change_a_label(self):
        group = {"group_id": "g", "primary_label": "Region A", "measured_gene_evidence": [{"gene": "gene0"}]}
        metadata = {"parameters": {"allowed_labels": ["Region A", "Region B", "Unmatched"],
                                  "unmatched_label": "Unmatched"}, "dataset_context": {}}
        model = Mock()
        model.invoke.return_value = AIMessage(content=json.dumps({"decisions": [{
            "group_id": "g", "action": "assign", "label": "Region B",
            "supporting_genes": ["gene0"], "spatial_reason": "proposed contrast", "justification": "claim"}]}))
        decisions = review._decisions([group], metadata, model, self.root / "weak.json", 8, "test")
        self.assertEqual(decisions["g"]["label"], "Region A")
        self.assertEqual(decisions["g"]["action"], "retain")

    def test_hallucinated_review_gene_is_rejected(self):
        group = {"group_id": "g", "primary_label": "Region A", "measured_gene_evidence": [{"gene": "gene0"}]}
        metadata = {"parameters": {"allowed_labels": ["Region A", "Region B", "Unmatched"],
                                  "unmatched_label": "Unmatched"}, "dataset_context": {}}
        model = Mock()
        model.invoke.return_value = AIMessage(content=json.dumps({"decisions": [{
            "group_id": "g", "action": "assign", "label": "Region B",
            "supporting_genes": ["invented", "gene0"], "spatial_reason": "claim", "justification": "claim"}]}))
        with self.assertRaisesRegex(ValueError, "absent from the measured evidence"):
            review._decisions([group], metadata, model, self.root / "bad.json", 8, "test")
        self.assertFalse((self.root / "bad.json").exists())

    def test_spatial_screening_does_not_split_by_cell_type_or_flag_mixture_alone(self):
        n = 160
        data = ad.AnnData(
            np.ones((n, 6)),
            obs=pd.DataFrame(
                {
                    "cell_type": ["A", "B"] * 80,
                    "cluster": ["0"] * n,
                    "tissue_niche": ["Region A"] * n,
                },
                index=[str(i) for i in range(n)],
            ),
            var=pd.DataFrame(index=[f"g{i}" for i in range(6)]),
        )
        data.obsm["spatial"] = np.column_stack((np.arange(n), np.zeros(n)))
        metadata = {
            "parameters": {
                "niche_key": "cluster",
                "annotation_col": "tissue_niche",
                "celltype_key_resolved": "cell_type",
                "spatial_key": "spatial",
                "slide_key_resolved": None,
                "utag_max_dist": 10,
                "unmatched_label": "Unmatched",
            }
        }
        groups, membership = review._screen(data, metadata)
        self.assertTrue(all(not g["screening_reasons"] for g in groups))
        self.assertTrue(all(len(g["celltype_fractions"]) == 2 for g in groups))
        data.obs["cell_type"] = ["A"] * 80 + ["B"] * 80
        data.X[:80, :3] += 3
        data.X[80:, 3:] += 3
        changed, same_partition = review._screen(data, metadata)
        for key in membership:
            np.testing.assert_array_equal(membership[key], same_partition[key])
        self.assertTrue(
            any(
                "spatially_segregated_composition_and_expression" in g["screening_reasons"]
                for g in changed
            )
        )

    def test_no_flag_review_preserves_every_prediction_and_primary_binary(self):
        result = self.completed()
        before = self.sha(result["annotated_object_h5ad"])
        model = Mock()
        with patch.object(config, "DefaultModelCtor", return_value=model):
            reviewed = review.review_tissue_niches_tool(
                result["annotated_object_h5ad"], output_path="reviewed.h5ad"
            )
        self.assertEqual(reviewed["status"], "success", reviewed)
        self.assertEqual(reviewed["n_cells_changed"], 0)
        model.invoke.assert_not_called()
        self.assertEqual(self.sha(result["annotated_object_h5ad"]), before)

    def test_anchor_disagreement_never_directly_changes_predictions(self):
        result = self.completed()

        def invoke(messages):
            payload = json.loads(messages[1].content)
            if "cell_types" in payload:
                return AIMessage(content=json.dumps({"mapping": {"type A": "Region B"}}))
            return AIMessage(
                content=json.dumps(
                    {
                        "decisions": [
                            {
                                "group_id": g["group_id"],
                                "action": "retain",
                                "label": g["primary_label"],
                                "supporting_genes": [],
                                "justification": "Anchor alone is insufficient",
                            }
                            for g in payload["groups"]
                        ]
                    }
                )
            )

        model = Mock()
        model.invoke.side_effect = invoke
        with patch.object(config, "DefaultModelCtor", return_value=model):
            reviewed = review.review_tissue_niches_tool(
                result["annotated_object_h5ad"],
                output_path="anchor_reviewed.h5ad",
                use_anchor_evidence=True,
            )
        self.assertEqual(reviewed["status"], "success", reviewed)
        self.assertGreater(reviewed["n_groups_reviewed"], 0)
        self.assertEqual(reviewed["n_cells_changed"], 0)

    def test_budget_deferred_and_unselected_cells_are_preserved(self):
        result = self.completed()
        groups = [
            {
                "group_id": str(i),
                "parent_cluster": "0" if i < 2 else "1",
                "primary_label": "Region A" if i < 2 else "Region B",
                "priority": 3 - i,
                "screening_reasons": ["test_conflict"] if i < 2 else [],
                "measured_gene_evidence": [{"gene": "gene0"}, {"gene": "gene1"}],
            }
            for i in range(3)
        ]
        members = {"0": np.arange(6), "1": np.arange(6, 12), "2": np.arange(12, 24)}
        model = Mock()
        model.invoke.return_value = AIMessage(
            content=json.dumps(
                {
                    "decisions": [
                        {
                            "group_id": "0",
                            "action": "assign",
                            "label": "Region B",
                            "supporting_genes": ["gene0", "gene1"],
                            "spatial_reason": "Local measured contrast supports this region",
                            "justification": "supported change",
                        }
                    ]
                }
            )
        )
        with (
            patch.object(config, "DefaultModelCtor", return_value=model),
            patch.object(review, "_screen", return_value=(groups, members)),
        ):
            reviewed = review.review_tissue_niches_tool(
                result["annotated_object_h5ad"],
                output_path="bounded_reviewed.h5ad",
                max_review_groups=1,
            )
        self.assertEqual(reviewed["status"], "success", reviewed)
        self.assertEqual(reviewed["n_groups_deferred"], 1)
        self.assertEqual(reviewed["review_status"], "complete_with_deferrals")
        self.assertEqual(reviewed["n_cells_changed"], 6)
        data = ad.read_h5ad(self.root / reviewed["annotated_object_h5ad"])
        self.assertEqual(
            data.obs.tissue_niche.astype(str).tolist(),
            ["Region B"] * 6 + ["Region A"] * 6 + ["Region B"] * 12,
        )
        again = review.review_tissue_niches_tool(
            reviewed["annotated_object_h5ad"], output_path="again.h5ad"
        )
        self.assertEqual(again["status"], "error")


if __name__ == "__main__":
    unittest.main()
