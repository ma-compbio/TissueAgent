"""Developmental-stage suitability tests for Harmony reference selection."""

from contextlib import contextmanager
from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "unit-test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.agent_registry.cell_annotater_agent.tools_impl import method_selection
from agents.agent_registry.cell_annotater_agent.tools_impl.method_selection import (
    _apply_developmental_stage_compatibility,
    _developmental_stage_compatibility,
)


class DevelopmentalStageCompatibilityTests(unittest.TestCase):
    """Ensure exact chronological age is preferred but not required."""

    def test_mixed_mouse_reference_keeps_nearest_stage_eligible(self):
        """Prefer a 4-week subset for a 7-week mouse without rejecting mixed ages."""
        compatibility = _developmental_stage_compatibility(
            "adult (approximately 7 weeks)",
            ["4-week-old stage", "20-month-old stage and over"],
            "Mus musculus",
        )

        self.assertEqual(compatibility["status"], "compatible_subset_available")
        self.assertEqual(compatibility["preferred_reference_values"], ["4-week-old stage"])
        self.assertEqual(
            compatibility["nonpreferred_reference_values"],
            ["20-month-old stage and over"],
        )
        self.assertFalse(compatibility["hard_conflict"])

    def test_same_broad_life_stage_does_not_require_exact_age(self):
        """Accept a broad adult label when the query supplies a specific adult age."""
        compatibility = _developmental_stage_compatibility(
            "adult (approximately 7 weeks)",
            ["adult stage"],
            "mouse",
        )

        self.assertEqual(compatibility["status"], "broad_match")
        self.assertFalse(compatibility["hard_conflict"])

    def test_prenatal_only_reference_is_hard_conflict_for_adult_query(self):
        """Reject a reference whose resolved stages are all prenatal for an adult query."""
        compatibility = _developmental_stage_compatibility(
            "adult stage",
            ["embryonic stage", "fetal stage"],
            "human",
        )

        self.assertEqual(compatibility["status"], "incompatible")
        self.assertTrue(compatibility["hard_conflict"])

    def test_distant_age_alone_is_warning_not_hard_failure(self):
        """Treat a distant adult or aged reference as a warning rather than a rejection."""
        compatibility = _developmental_stage_compatibility(
            "adult (approximately 7 weeks)",
            ["20-month-old stage and over"],
            "Mus musculus",
        )

        self.assertEqual(compatibility["status"], "distant_age_warning")
        self.assertFalse(compatibility["hard_conflict"])

    def test_compatible_subset_does_not_downgrade_harmony(self):
        """Keep the existing technical assessment when a compatible subset exists."""
        compatibility = _developmental_stage_compatibility(
            "adult (approximately 7 weeks)",
            ["4-week-old stage", "20-month-old stage and over"],
            "Mus musculus",
        )
        assessment = _apply_developmental_stage_compatibility(
            {
                "evidence_tier": "conditional",
                "risk_tier": "moderate",
                "supporting_codes": [],
                "adverse_codes": [],
                "unresolved_codes": [],
            },
            compatibility,
        )

        self.assertEqual(assessment["evidence_tier"], "conditional")
        self.assertEqual(assessment["risk_tier"], "moderate")
        self.assertIn(
            "reference_developmental_stage_compatible_subset_available",
            assessment["supporting_codes"],
        )
        self.assertIn(
            "reference_developmental_stage_subset_recommended",
            assessment["unresolved_codes"],
        )

    def test_hard_conflict_downgrades_harmony(self):
        """Convert a true developmental-stage conflict into high-risk evidence."""
        compatibility = _developmental_stage_compatibility(
            "adult stage", ["embryonic stage"], "human"
        )
        assessment = _apply_developmental_stage_compatibility(
            {
                "evidence_tier": "conditional",
                "risk_tier": "moderate",
                "supporting_codes": [],
                "adverse_codes": [],
                "unresolved_codes": [],
            },
            compatibility,
        )

        self.assertEqual(assessment["evidence_tier"], "adverse")
        self.assertEqual(assessment["risk_tier"], "high")
        self.assertIn("reference_developmental_stage_conflict", assessment["adverse_codes"])

    def test_method_policy_keeps_mixed_reference_authorized(self):
        """Propagate a compatible stage subset into the final method policy."""
        with self._assessment_patches():
            assessments, policy = method_selection._method_selection_policy(
                self._reference(["4-week-old stage", "20-month-old stage and over"]),
                {},
                {},
                {},
                {
                    "species": "Mus musculus",
                    "developmental_stage": "adult (approximately 7 weeks)",
                },
            )

        self.assertEqual(policy["default_candidates"], ["harmony"])
        self.assertIn("harmony", policy["authorized_candidates"])
        self.assertEqual(
            assessments["harmony"]["evidence_annotations"]["developmental_stage_compatibility"][
                "status"
            ],
            "compatible_subset_available",
        )

    def test_method_policy_rejects_true_stage_conflict(self):
        """Remove Harmony authorization when all reference stages conflict."""
        with self._assessment_patches():
            assessments, policy = method_selection._method_selection_policy(
                self._reference(["embryonic stage"]),
                {},
                {},
                {},
                {"species": "human", "developmental_stage": "adult stage"},
            )

        self.assertEqual(policy["default_candidates"], ["celltypist"])
        self.assertNotIn("harmony", policy["authorized_candidates"])
        self.assertIn(
            "reference_developmental_stage_conflict",
            assessments["harmony"]["adverse_codes"],
        )

    @staticmethod
    def _reference(stages):
        """Build the reference fields consumed by method selection."""
        return {
            "provided": True,
            "query_panel_preflight": {},
            "coverage": {
                "metadata_coverage": {
                    "diseases": {"values": []},
                    "developmental_stages": {"values": stages},
                }
            },
        }

    @staticmethod
    @contextmanager
    def _assessment_patches():
        """Patch unrelated preflights with deterministic categorical evidence."""

        def assessment(prerequisites, evidence_tier, risk_tier):
            return {
                "prerequisites": prerequisites,
                "evidence_tier": evidence_tier,
                "risk_tier": risk_tier,
                "supporting_codes": [],
                "adverse_codes": [],
                "unresolved_codes": [],
                "evidence_annotations": {},
            }

        with (
            patch.object(
                method_selection,
                "assess_harmony_selection_evidence",
                return_value=assessment("met", "conditional", "moderate"),
            ),
            patch.object(
                method_selection,
                "assess_celltypist_selection_evidence",
                return_value=assessment("met", "conditional", "moderate"),
            ),
            patch.object(
                method_selection,
                "assess_gptcelltype_selection_evidence",
                return_value=assessment("not_met", "adverse", "high"),
            ),
        ):
            yield


if __name__ == "__main__":
    unittest.main()
