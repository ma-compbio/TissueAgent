"""Niche path and audit-recovery regressions using real H5ADs and no network."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "unit-test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import anndata as ad
import numpy as np
import pandas as pd
import config
from agents.agent_registry.cell_annotater_agent.tools_impl import niche_annotation as niche
from agents.agent_registry.cell_annotater_agent.tools_impl import niche_artifacts as artifacts
from agents.tissue_niche_context import bind_tissue_niche_context
from graph.niche_review import guard_niche_review_verdict
from server.plan_store import PlanDocument, PlanStep


class NicheArtifactTests(unittest.TestCase):
    """Exercise the real artifact contract across candidate, recovery and delivery."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        (self.project / "uploads").mkdir(parents=True)
        (self.project / "outputs").mkdir()
        self.enterContext(patch.object(config, "DATA_DIR", self.root))
        self.enterContext(patch.object(config, "ACTIVE_PROJECT_DIR", self.project))
        self.input = self.project / "uploads/query.h5ad"
        obs = pd.DataFrame(
            {"cell_type": ["type A"] * 12 + ["type B"] * 12, "clusters": ["0"] * 12 + ["1"] * 12},
            index=[f"cell{i}" for i in range(24)],
        )
        rng = np.random.default_rng(42)
        data = ad.AnnData(
            rng.uniform(0.1, 2, size=(24, 6)).astype(np.float32),
            obs=obs,
            var=pd.DataFrame(index=[f"gene{i}" for i in range(6)]),
        )
        data.obsm["spatial"] = np.column_stack((np.arange(24), np.zeros(24))).astype(float)
        data.write_h5ad(self.input)
        self.context = {
            "input_path": "project/uploads/query.h5ad",
            "output_path": "project/outputs/final.h5ad",
            "celltype_key": "cell_type",
            "spatial_key": "spatial",
            "annotation_col": "tissue_niche",
            "allowed_labels": ["Region A", "Region B"],
        }
        self.enterContext(bind_tissue_niche_context(self.context))
        self.llm = self.enterContext(
            patch.object(
                niche,
                "_label_niches_with_llm",
                return_value={
                    "0": {
                        "label": "Region A",
                        "justification": "Measured first regional population",
                    },
                    "1": {
                        "label": "Region B",
                        "justification": "Measured second regional population",
                    },
                },
            )
        )
        self.utag = self.enterContext(
            patch.object(
                niche,
                "_run_utag",
                side_effect=AssertionError(
                    "Existing-cluster annotation and recovery must not recompute UTAG"
                ),
            )
        )

    def annotate(self, **kwargs):
        arguments = {
            "spatial_anndata_path": "project/uploads/query.h5ad",
            "output_dir": "project/outputs/audit",
            "slide_key": None,
            "niche_key": "clusters",
            "utag_apply_clustering": False,
            "utag_max_dist": 2.0,
            "parameter_rationale": "Measured local scale",
            "output_path": "project/outputs/candidate.h5ad",
        }
        arguments.update(kwargs)
        return niche.niche_annotation_tool(**arguments)

    def completed(self, **kwargs):
        result = self.annotate(**kwargs)
        self.assertEqual(result["status"], "success", result)
        return result

    def sha(self, relative):
        return hashlib.sha256((self.root / relative).read_bytes()).hexdigest()

    def test_candidate_path_is_honored_and_canonical_audits_are_real(self):
        original_hash = self.sha("project/uploads/query.h5ad")
        result = self.completed()
        self.assertEqual(result["annotated_object_h5ad"], "project/outputs/candidate.h5ad")
        self.assertFalse((self.project / "outputs/final.h5ad").exists())
        for key in (
            "niche_evidence_tsv",
            "annotation_parameters_json",
            "validation_summary_tsv",
            "run_meta_json",
        ):
            self.assertTrue((self.root / result[key]).is_file(), key)
        meta = json.loads((self.root / result["run_meta_json"]).read_text())
        self.assertEqual(meta["parameters"]["utag_max_dist"], 2.0)
        self.assertEqual(meta["review_status"], "not_verified")
        self.assertEqual(self.sha("project/uploads/query.h5ad"), original_hash)
        self.llm.assert_called_once()
        self.utag.assert_not_called()

    def test_omitted_candidate_path_defaults_to_bound_final(self):
        result = self.completed(output_path=None)
        self.assertEqual(result["annotated_object_h5ad"], "project/outputs/final.h5ad")

    def test_preview_then_label_keeps_candidate_without_reclustering(self):
        preview = self.annotate(preview_only=True)
        self.assertEqual(preview["status"], "ready_for_labeling", preview)
        self.llm.assert_not_called()
        result = self.completed(**preview["labeling_arguments"])
        self.assertEqual(result["radius_used"], 2.0)
        self.llm.assert_called_once()
        self.utag.assert_not_called()

    def test_missing_audits_recover_with_exact_paths_and_no_scientific_calls(self):
        result = self.completed()
        before = self.sha(result["annotated_object_h5ad"])
        for p in (self.project / "outputs/audit").iterdir():
            p.unlink()
        self.llm.reset_mock()
        with patch.object(
            niche, "build_niche_llm_queries", side_effect=AssertionError("No new prompts")
        ):
            restored = artifacts.recover_niche_annotation_artifacts_tool(
                result["annotated_object_h5ad"],
                "outputs/audit",
                evidence_path="outputs/audit/candidate_niche_evidence.tsv",
                parameters_path="outputs/audit/exact_parameters.json",
                validation_path="outputs/audit/exact_validation.tsv",
                metadata_path="outputs/audit/exact_run_meta.json",
            )
        self.assertEqual(restored["status"], "success", restored)
        self.assertEqual(restored["review_status"], "not_verified")
        self.assertEqual(self.sha(result["annotated_object_h5ad"]), before)
        self.assertTrue((self.project / "outputs/audit/candidate_niche_evidence.tsv").is_file())
        self.llm.assert_not_called()
        self.utag.assert_not_called()

    def test_delivery_is_a_byte_identical_copy_and_does_not_overwrite_other_result(self):
        result = self.completed()
        restored = artifacts.recover_niche_annotation_artifacts_tool(
            result["annotated_object_h5ad"], "outputs/final_audit", "outputs/final.h5ad"
        )
        self.assertEqual(restored["status"], "success", restored)
        self.assertEqual(
            self.sha(result["annotated_object_h5ad"]), self.sha(restored["annotated_object_h5ad"])
        )
        (self.project / "outputs/other.h5ad").write_bytes(b"preserve existing output")
        bad = artifacts.recover_niche_annotation_artifacts_tool(
            result["annotated_object_h5ad"], "outputs/other_audit", "outputs/other.h5ad"
        )
        self.assertEqual(bad["status"], "error")
        self.assertEqual(
            (self.project / "outputs/other.h5ad").read_bytes(), b"preserve existing output"
        )

    def test_audit_write_failure_preserves_recoverable_annotation(self):
        with patch.object(artifacts, "_write_text", side_effect=OSError("audit storage failure")):
            result = self.annotate()
        self.assertEqual(result["status"], "error", result)
        self.assertEqual(result["annotation_status"], "complete")
        before = self.sha(result["annotated_object_h5ad"])
        self.llm.reset_mock()
        restored = artifacts.recover_niche_annotation_artifacts_tool(
            result["annotated_object_h5ad"], "outputs/audit"
        )
        self.assertEqual(restored["status"], "success", restored)
        self.assertEqual(before, self.sha(result["annotated_object_h5ad"]))
        self.llm.assert_not_called()

    def test_recovery_rejects_changed_labels_cells_and_cell_types_before_writing(self):
        result = self.completed()
        path = self.root / result["annotated_object_h5ad"]
        original = ad.read_h5ad(path)
        for corruption in ("labels", "cells", "cell_types"):
            with self.subTest(corruption=corruption):
                data = original.copy()
                if corruption == "labels":
                    data.obs.loc["cell0", "tissue_niche"] = "Region B"
                elif corruption == "cells":
                    data = data[::-1].copy()
                else:
                    data.obs.loc["cell0", "cell_type"] = "type B"
                data.write_h5ad(path)
                bad = artifacts.recover_niche_annotation_artifacts_tool(
                    result["annotated_object_h5ad"], "outputs/rejected"
                )
                self.assertEqual(bad["status"], "error", bad)
                self.assertFalse((self.project / "outputs/rejected").exists())

    def test_recovery_rejects_collisions_and_wrong_task_vocabulary(self):
        result = self.completed()
        before = self.sha(result["annotated_object_h5ad"])
        bad = artifacts.recover_niche_annotation_artifacts_tool(
            result["annotated_object_h5ad"],
            "outputs/audit",
            metadata_path=result["annotated_object_h5ad"],
        )
        self.assertEqual(bad["status"], "error")
        with bind_tissue_niche_context({**self.context, "allowed_labels": ["Wrong region"]}):
            bad = artifacts.recover_niche_annotation_artifacts_tool(
                result["annotated_object_h5ad"], "outputs/wrong_task"
            )
        self.assertEqual(bad["status"], "error")
        self.assertEqual(self.sha(result["annotated_object_h5ad"]), before)

    def test_original_input_cannot_be_an_annotation_output(self):
        result = self.annotate(output_path="project/uploads/query.h5ad")
        self.assertEqual(result["status"], "error", result)
        self.llm.assert_not_called()


class NicheReviewGuardTests(unittest.TestCase):
    """A planned niche review cannot be replaced by an existing prediction file."""

    def plan(self, status="pending", skills=None):
        return PlanDocument(
            steps=[
                PlanStep(
                    id=1, title="Annotate", status="done", assigned_agent="cell_annotator_agent"
                ),
                PlanStep(
                    id=2,
                    title="Review ambiguous spatial regions",
                    status=status,
                    assigned_agent="coding_agent",
                    skills=skills or ["tissue-niche-annotation"],
                ),
            ]
        )

    def test_pending_failed_and_running_reviews_replan(self):
        for status in ("pending", "failed", "running"):
            result = guard_niche_review_verdict("ROUTE: REPORT\nH5AD exists", self.plan(status))
            self.assertTrue(result.startswith("ROUTE: REPLAN"), result)
            self.assertIn("Preserve the existing", result)

    def test_specialist_assigned_review_is_also_required(self):
        # The observed heart section 002 failure assigned review to the annotation specialist.
        plan = self.plan()
        plan.steps[1].assigned_agent = "cell_annotator_agent"
        result = guard_niche_review_verdict("ROUTE: REPORT\nFinal H5AD exists", plan)
        self.assertTrue(result.startswith("ROUTE: REPLAN"), result)

    def test_completed_optional_and_unrelated_reviews_do_not_force_work(self):
        content = "ROUTE: REPORT\nComplete"
        for plan in (self.plan("done"), PlanDocument(), self.plan(skills=["unrelated-skill"])):
            self.assertEqual(guard_niche_review_verdict(content, plan), content)
        replan = "ROUTE: REPLAN\nExisting blocker"
        self.assertEqual(guard_niche_review_verdict(replan, self.plan()), replan)


if __name__ == "__main__":
    unittest.main()
