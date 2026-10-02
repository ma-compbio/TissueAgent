"""Regression checks for ARI/MCC on the actual cell-annotation scoring path."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
import warnings

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from benchmark.cell_type_annotation.evaluation import evaluate_predictions  # noqa: E402


class AgreementMetricTests(unittest.TestCase):
    """Exercise semantic identity, exclusions, and retained missing predictions."""

    def score(self, predictions):
        """Score four biological cells and one explicitly excluded truth cell."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth = pd.DataFrame(
                {"major_celltype": ["A", "A", "B", "B", "Unassigned"]},
                index=pd.Index(["c1", "c2", "c3", "c4", "c5"], name="cell_id"),
            )
            truth.to_csv(root / "truth.tsv", sep="\t")
            labels = ["A", "B", "Unassigned"]
            (root / "mapping.json").write_text(
                json.dumps(
                    {
                        "target_labels": labels,
                        "ground_truth_mapping": {label: label for label in labels},
                    }
                )
            )
            predicted = pd.DataFrame.from_dict(
                predictions, orient="index", columns=["raw_prediction"]
            )
            predicted.index.name = "cell_id"
            predicted.to_csv(root / "predictions.tsv", sep="\t")
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
                metrics = evaluate_predictions(
                    {
                        "run_dir": str(root),
                        "ground_truth_tsv": str(root / "truth.tsv"),
                        "ground_truth_column": "major_celltype",
                        "label_mapping_json": str(root / "mapping.json"),
                    },
                    {"test": root / "predictions.tsv"},
                    exclude_ground_truth_raw_labels=["Unassigned"],
                )
            saved = json.loads((root / "metrics.json").read_text())
            for metric in ["ari", "mcc"]:
                self.assertIn(metric, saved["metric_definitions"])
                self.assertEqual(saved["methods"][0][metric], metrics.loc["test", metric])
            self.assertEqual(metrics.loc["test", "n_truth_cells"], 4)
            self.assertEqual(metrics.loc["test", "n_excluded_truth_cells"], 1)
            return metrics.loc["test"]

    def test_perfect_labels(self):
        """Both metrics equal one for correctly named, identical partitions."""
        result = self.score(
            dict(zip(["c1", "c2", "c3", "c4", "c5"], ["A", "A", "B", "B", "A"], strict=True))
        )
        self.assertEqual(result["ari"], 1)
        self.assertEqual(result["mcc"], 1)

    def test_swapped_names_preserve_ari_but_reverse_mcc(self):
        """A name permutation must not be silently corrected for MCC."""
        result = self.score(
            dict(zip(["c1", "c2", "c3", "c4", "c5"], ["B", "B", "A", "A", "A"], strict=True))
        )
        self.assertEqual(result["accuracy"], 0)
        self.assertEqual(result["ari"], 1)
        self.assertEqual(result["mcc"], -1)

    def test_missing_and_unassigned_predictions_are_retained(self):
        """An absent prediction and explicit Unassigned both remain in scoring."""
        result = self.score({"c1": "A", "c2": "Unassigned", "c3": "B", "c5": "A"})
        self.assertEqual(result["n_unassigned"], 2)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertAlmostEqual(result["ari"], -2 / 7)
        self.assertAlmostEqual(result["mcc"], 1 / (5**0.5))

    def test_constant_unassigned_prediction(self):
        """The degenerate classifier follows sklearn's zero-MCC convention."""
        result = self.score({f"c{i}": "Unassigned" for i in range(1, 6)})
        self.assertEqual(result["ari"], 0)
        self.assertEqual(result["mcc"], 0)


if __name__ == "__main__":
    unittest.main()
