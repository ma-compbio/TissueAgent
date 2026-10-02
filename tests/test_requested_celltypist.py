"""Explicit CellTypist request binding, seed propagation and bounded graph integrity."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("OPENAI_API_KEY", "unit-test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import anndata as ad
import numpy as np
import pandas as pd
import config
from agents.cell_annotation_context import bind_cell_annotation_context
from agents.agent_registry.cell_annotater_agent.tools_impl import celltypist_annotation as backend
from agents.agent_registry.cell_annotater_agent.tools_impl import requested_celltypist as req
from agents.agent_registry.cell_annotater_agent.tools_impl.celltypist_bounded_graph import (
    overcluster,
)
from agents.manager_agent.tools import _cell_annotation_context_from_user_request


class RequestedCellTypistTests(unittest.TestCase):
    """Execution is fixed by user context and real input hashes, not generated arguments."""

    def setUp(self):
        """Prepare two small independent expression matrices in an isolated workspace."""
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        (self.project / "uploads").mkdir(parents=True)
        self.patches = [
            patch.object(config, "DATA_DIR", self.root),
            patch.object(config, "ACTIVE_PROJECT_DIR", self.project),
        ]
        for p in self.patches:
            p.start()
        self.query = self.project / "uploads/query.h5ad"
        self.reference = self.project / "uploads/reference.h5ad"
        for p, prefix in [(self.query, "q"), (self.reference, "r")]:
            a = ad.AnnData(
                np.ones((60, 4), dtype=np.float32),
                obs=pd.DataFrame(
                    {"cell.types": ["A"] * 30 + ["B"] * 30},
                    index=[f"{prefix}{i}" for i in range(60)],
                ),
                var=pd.DataFrame(index=["G1", "G2", "G3", "G4"]),
            )
            a.write_h5ad(p)
        self.spec = {
            "method": "celltypist",
            "spatial_anndata_path": "uploads/query.h5ad",
            "reference_anndata_path": "uploads/reference.h5ad",
            "cell_type_column": "cell.types",
            "output_path": "outputs/primary.h5ad",
            "random_state": 44,
            "majority_voting": True,
            "query_sha256": hashlib.sha256(self.query.read_bytes()).hexdigest(),
            "reference_sha256": hashlib.sha256(self.reference.read_bytes()).hexdigest(),
        }

    def tearDown(self):
        """Restore workspace and remove temporary artifacts."""
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_original_request_requires_explicit_method_and_complete_schema(self):
        """A mere mention or generated omission does not activate the special route."""
        self.assertIsNone(req.parse_execution_request("Please compare CellTypist."))
        with self.assertRaises(ValueError):
            req.parse_execution_request(req.MARKER + json.dumps(self.spec))
        prompt = (
            "species='Homo sapiens' primary_method='celltypist'\n"
            + req.MARKER
            + json.dumps(self.spec)
        )
        ctx = _cell_annotation_context_from_user_request(prompt)
        self.assertEqual(ctx["celltypist_execution_request"], self.spec)
        self.assertEqual(ctx["species"], "Homo sapiens")

    def test_unbound_tool_does_not_execute_and_bound_seed_is_forwarded(self):
        """Backend execution only uses fixed bound inputs, preserving seed 44."""
        with patch.object(
            backend, "celltypist_annotation_tool", return_value={"status": "success"}
        ) as run:
            with bind_cell_annotation_context(None):
                self.assertEqual(req.run_requested_celltypist_tool()["status"], "error")
            run.assert_not_called()
            with bind_cell_annotation_context({"celltypist_execution_request": self.spec}):
                self.assertEqual(req.run_requested_celltypist_tool()["status"], "success")
            kw = run.call_args.kwargs
            self.assertEqual(kw["random_state"], 44)
            self.assertTrue(kw["majority_voting"])
            self.assertEqual(kw["overclustering_strategy"], "bounded_v1")
            self.assertFalse(kw["execution_contract"]["automatic_method_selection"])

    def test_changed_reference_is_rejected_before_training(self):
        """An original request cannot authorize a later modified reference."""
        self.reference.write_bytes(b"changed")
        with patch.object(backend, "celltypist_annotation_tool") as run:
            with bind_cell_annotation_context({"celltypist_execution_request": self.spec}):
                self.assertEqual(req.run_requested_celltypist_tool()["status"], "error")
            run.assert_not_called()

    def test_training_receives_requested_random_state(self):
        """Classifier random_state must not remain the old fixed default zero."""
        model = SimpleNamespace(features=["G1"], cell_types=["A", "B"])
        module = SimpleNamespace(train=Mock(return_value=model))
        ref = ad.read_h5ad(self.reference)
        _, metadata = backend._train_reference_model(
            module,
            ref,
            reference_path=self.reference,
            cell_type_column="cell.types",
            n_jobs=2,
            random_state=43,
        )
        self.assertEqual(module.train.call_args.kwargs["random_state"], 43)
        self.assertEqual(metadata["random_state"], 43)

    def test_bounded_graph_preserves_expression_and_uses_requested_seed(self):
        """Numerical graph preparation changes no input and uses the explicit graph seed."""
        rng = np.random.default_rng(5)
        x = np.log1p(rng.poisson(4, (70, 12))).astype(np.float32)
        query = ad.AnnData(x.copy(), var=pd.DataFrame(index=[f"G{i}" for i in range(12)]))
        import scanpy as sc

        def leiden(graph, **kwargs):
            graph.obs[kwargs["key_added"]] = pd.Categorical(["0"] * 35 + ["1"] * 35)

        with (
            patch.object(sc.pp, "neighbors") as neighbors,
            patch.object(sc.tl, "leiden", side_effect=leiden) as cluster,
        ):
            labels, metadata = overcluster(query, 43, self.root)
        np.testing.assert_array_equal(query.X, x)
        self.assertEqual(len(labels), 70)
        self.assertEqual(metadata["random_state"], 43)
        self.assertEqual(neighbors.call_args.kwargs["random_state"], 43)
        self.assertEqual(cluster.call_args.kwargs["random_state"], 43)
        self.assertEqual(list(self.root.glob("celltypist-graph-*")), [])


if __name__ == "__main__":
    unittest.main()
