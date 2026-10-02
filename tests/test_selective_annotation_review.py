"""Scientific boundaries and resumability for opt-in selective review; no network."""

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_annotation_review as fixtures
import anndata as ad
import numpy as np
from agents.agent_registry.cell_annotater_agent.tools_impl import selective_annotation_review as s
from agents.agent_registry.cell_annotater_agent.tools_impl import annotation_review as base


class SelectiveReviewTests(unittest.TestCase):
    """Use real measured synthetic evidence and native output validation."""

    setUp = fixtures.ReviewTests.setUp
    tearDown = fixtures.ReviewTests.tearDown
    inspect = fixtures.ReviewTests.inspect

    def screening(self, records):
        """Create one synthetic measured-conflict request per eligible group."""
        result = {}
        for c in records:
            chosen = []
            for g in c["groups"]:
                if g["change_eligible"]:
                    chosen.append(
                        {
                            "group_id": g["group_id"],
                            "issue": "marker_contradiction",
                            "support_markers": [m["gene"] for m in g["markers"][:2]],
                            "reason": "Test measured contradiction.",
                        }
                    )
            result[c["cluster_id"]] = {
                "reason": "Inspected measured markers.",
                "review_groups": chosen,
            }
        return result

    def fake_ask(self, model, system, payload, audit, validate):
        """Return validated synthetic decisions and assert annotation data boundaries."""
        self.assertNotIn("NEVER_SEND_SECRET", json.dumps(payload))
        if "clusters" in payload:
            result = self.screening(payload["clusters"])
        else:
            result = {
                g["group_id"]: {
                    "action": "keep",
                    "label": g["primary_label"],
                    "cell_type_ontology_id": g["primary_cell_type_ontology_id"],
                    "cell_state": None,
                    "support_markers": [],
                    "reason": "Primary supported.",
                }
                for g in payload["groups"]
            }
        validate(result)
        audit.append({"payload": payload, "attempts": [{"validated_result": result}]})
        return result

    def test_screen_rejects_foreign_group_and_unmeasured_evidence(self):
        """Reject out-of-scope group IDs and invented marker evidence."""
        _, evidence = self.inspect()
        records = s.build_screen_records(evidence["clusters"], evidence["groups"])
        result = self.screening(records)
        s.validate_screen(result, records)
        bad = copy.deepcopy(result)
        next(v for v in bad.values() if v["review_groups"])["review_groups"][0]["group_id"] = "fake"
        with self.assertRaises(ValueError):
            s.validate_screen(bad, records)
        bad = copy.deepcopy(result)
        next(v for v in bad.values() if v["review_groups"])["review_groups"][0][
            "support_markers"
        ] = ["INVENTED", "GENE0"]
        with self.assertRaises(ValueError):
            s.validate_screen(bad, records)

    def test_subgroup_selection_does_not_expand_entire_cluster(self):
        """A single selected subgroup must not pull in its cluster peers."""
        _, evidence = self.inspect()
        records = s.build_screen_records(evidence["clusters"], evidence["groups"])
        result = self.screening(records)
        keep_gid = result["0"]["review_groups"][0]["group_id"]
        result["0"]["review_groups"] = result["0"]["review_groups"][:1]
        result["1"]["review_groups"] = []
        s.validate_screen(result, records)
        selected, deferred, _ = s.select_groups(evidence["groups"], result, 48)
        self.assertEqual([g["group_id"] for g in selected], [keep_gid])
        self.assertEqual(deferred, [])

    def test_minority_selection_requires_within_cluster_markers(self):
        """Require measured within-cluster support for minority expansion."""
        _, evidence = self.inspect()
        records = s.build_screen_records(evidence["clusters"], evidence["groups"])
        result = {c["cluster_id"]: {"reason": "Checked", "review_groups": []} for c in records}
        g = next(g for g in evidence["groups"] if g["distinct_minority"])
        request = {
            "group_id": g["group_id"],
            "issue": "supported_minority",
            "support_markers": [m["gene"] for m in g["within_cluster_markers"][:2]],
            "reason": "Distinct measured population requires checking.",
        }
        result[g["cluster_id"]]["review_groups"].append(request)
        s.validate_screen(result, records)
        request["support_markers"] = request["support_markers"][:1]
        with self.assertRaises(ValueError):
            s.validate_screen(result, records)

    def test_budget_preserves_every_cell_and_reports_deferrals(self):
        """Budget limits must retain every original cell and label with honest status."""
        inspection, evidence = self.inspect()
        before = base.file_sha256(self.path)
        with (
            patch.object(s, "_ask_json", side_effect=self.fake_ask),
            patch.object(s, "model_ctor_for_role"),
        ):
            result = s.refine_cell_annotations_selective_tool(
                inspection["evidence_path"], inspection["evidence_sha256"], "review/final.h5ad", 1
            )
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(result["n_groups_reviewed"], 1)
        self.assertGreater(result["n_groups_deferred"], 0)
        self.assertFalse(result["detailed_review_complete"])
        final = ad.read_h5ad(self.root / result["annotated_object_h5ad"])
        self.assertEqual(final.obs_names.tolist(), self.data.obs_names.tolist())
        np.testing.assert_array_equal(final.X, self.data.X)
        self.assertEqual(final.obs[base.PRIMARY].tolist(), self.data.obs[base.PRIMARY].tolist())
        self.assertIn("deferred_budget", final.obs.cell_annotation_review_status.tolist())
        self.assertEqual(before, base.file_sha256(self.path))
        audit = json.loads((self.root / result["review_json"]).read_text())
        self.assertEqual(audit["version"], s.REVIEW_VERSION)
        self.assertEqual(len(audit["deferred_group_ids"]), result["n_groups_deferred"])

    def test_checkpoint_reuses_screening_and_rejects_changed_budget(self):
        """Resume accepted work only under the same frozen budget."""
        inspection, _ = self.inspect()
        calls = []

        def fail_refinement(model, system, payload, audit, validate):
            calls.append(payload)
            if "groups" in payload:
                raise ValueError("Simulated transport interruption")
            return self.fake_ask(model, system, payload, audit, validate)

        with (
            patch.object(s, "_ask_json", side_effect=fail_refinement),
            patch.object(s, "model_ctor_for_role"),
        ):
            result = s.refine_cell_annotations_selective_tool(
                inspection["evidence_path"], inspection["evidence_sha256"], "review/final.h5ad", 1
            )
        self.assertEqual(result["status"], "error")
        changed = s.refine_cell_annotations_selective_tool(
            inspection["evidence_path"], inspection["evidence_sha256"], "review/final.h5ad", 2
        )
        self.assertEqual(changed["status"], "error")
        resumed = []

        def resume(*args):
            resumed.append(args[2])
            return self.fake_ask(*args)

        with (
            patch.object(s, "_ask_json", side_effect=resume),
            patch.object(s, "model_ctor_for_role"),
        ):
            result = s.refine_cell_annotations_selective_tool(
                inspection["evidence_path"], inspection["evidence_sha256"], "review/final.h5ad", 1
            )
        self.assertEqual(result["status"], "success", result)
        self.assertTrue(all("groups" in payload for payload in resumed))


class CellTypistStagePreservationTests(unittest.TestCase):
    """Saving raw/voted labels must not change classifier or voting behavior."""

    def test_details_preserve_raw_votes_and_confidence_without_changing_predictions(self):
        """Preserve raw versus voted disagreement without altering inference."""
        from types import SimpleNamespace
        from agents.agent_registry.cell_annotater_agent.tools_impl.celltypist_annotation import (
            _run_celltypist_inference,
        )
        import pandas as pd

        model = SimpleNamespace(
            features=np.array(["A", "B"]),
            cell_types=np.array(["type A", "type B"]),
            classifier=SimpleNamespace(coef_=np.array([[1.0, -1.0]]), intercept_=np.array([0.0])),
            scaler=SimpleNamespace(scale_=np.ones(2), mean_=np.zeros(2), with_mean=True),
        )
        query = ad.AnnData(
            np.array([[5.0, 0.0], [4.0, 0.0], [0.0, 5.0]]), var=pd.DataFrame(index=["A", "B"])
        )
        kwargs = dict(
            mode="best match",
            p_thres=0.5,
            majority_voting=True,
            over_clustering=np.array(["0", "0", "0"]),
        )
        original = _run_celltypist_inference(model, query, **kwargs)
        details = {}
        preserved = _run_celltypist_inference(model, query, **kwargs, prediction_details=details)
        np.testing.assert_array_equal(original[0], preserved[0])
        np.testing.assert_array_equal(original[1], preserved[1])
        self.assertEqual(details["raw_labels"].tolist(), ["type B", "type B", "type A"])
        self.assertEqual(details["majority_labels"].tolist(), ["type B"] * 3)
        self.assertGreater(details["raw_confidence"][2], preserved[1][2])


if __name__ == "__main__":
    unittest.main()
