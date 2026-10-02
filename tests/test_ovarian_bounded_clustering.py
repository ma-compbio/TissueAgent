"""Validate cohort and full-expression preservation in the resource-limited rerun."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark/niche_annotation"))
from ovarian_bounded_clustering import bounded_utag, variable_features


class BoundedClusteringTests(unittest.TestCase):
    def data(self):
        return ad.AnnData(sparse.csr_matrix(np.arange(24).reshape(4, 6)),
            obs=pd.DataFrame({"cell_type": ["a", "b", "a", "c"]}, index=["c0", "c1", "c2", "c3"]),
            var=pd.DataFrame(index=[f"g{i}" for i in range(6)]),
            obsm={"spatial": np.arange(8).reshape(4, 2)})

    def test_discovery_is_reduced_but_annotation_preserves_all_input_evidence(self):
        original = self.data()
        def fake_utag(data, **kwargs):
            self.assertEqual(data.shape, (4, 2))
            self.assertFalse(kwargs["parallel"])
            data = data[[3, 1, 0, 2]].copy()
            data.X[:] = 0
            data.obs["UTAG Label_leiden_0.5"] = ["D", "B", "A", "C"]
            return data
        with patch("ovarian_bounded_clustering.variable_features", return_value=np.array([1, 4])), patch.dict(sys.modules, {"utag": SimpleNamespace(utag=fake_utag)}):
            result = bounded_utag(adata=original, slide_key=None, max_dist=20,
                normalization_mode="l1_norm", apply_clustering=True, clustering_method="leiden", resolutions=[.5])
        self.assertEqual(result.shape, original.shape)
        np.testing.assert_array_equal(result.X.toarray(), original.X.toarray())
        np.testing.assert_array_equal(result.obsm["spatial"], original.obsm["spatial"])
        pd.testing.assert_series_equal(result.obs.cell_type, original.obs.cell_type)
        self.assertEqual(result.obs["UTAG Label_leiden_0.5"].tolist(), ["A", "B", "C", "D"])
        self.assertNotIn("UTAG Label_leiden_0.5", original.obs)

    def test_changed_cohort_is_rejected(self):
        original = self.data()
        def fake_utag(data, **kwargs):
            return data[:3].copy()
        with patch.dict(sys.modules, {"utag": SimpleNamespace(utag=fake_utag)}), self.assertRaisesRegex(ValueError, "cohort"):
            bounded_utag(adata=original, slide_key=None, max_dist=20, normalization_mode="l1_norm",
                apply_clustering=True, clustering_method="leiden", resolutions=[.5])

    def test_feature_selection_is_deterministic_and_does_not_modify_counts(self):
        data = ad.AnnData(sparse.csr_matrix(np.random.default_rng(3).poisson(2, (80, 40)).astype(float)))
        before = data.X.copy()
        first, second = variable_features(data, 10), variable_features(data, 10)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(len(first), 10)
        self.assertEqual((before != data.X).nnz, 0)


if __name__ == "__main__":
    unittest.main()
