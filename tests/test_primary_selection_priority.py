"""Supervised-first primary annotation policy and authorization tests."""

from pathlib import Path
import os
import sys
import tempfile
import unittest

os.environ.setdefault("OPENAI_API_KEY", "unit-test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.agent_registry.cell_annotater_agent.tools_impl.selection_contract import (
    _primary_priority_violations,
    register_selection_contract,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.selection_preflight import (
    SELECTION_POLICY_VERSION,
    build_method_selection_policy,
)
from agents.manager_agent.tools import _cell_annotation_context_from_user_request


def assessment(
    prerequisites: str,
    evidence_tier: str,
    risk_tier: str,
) -> dict[str, object]:
    """Build the policy fields relevant to backend eligibility."""
    return {
        "prerequisites": prerequisites,
        "evidence_tier": evidence_tier,
        "risk_tier": risk_tier,
    }


class PrimarySelectionPriorityTests(unittest.TestCase):
    """Ensure priority and abstention are enforced below the prompt layer."""

    def test_harmony_precedes_celltypist_and_gptcelltype(self):
        """Harmony wins whenever its affirmative suitability gate passes."""
        policy = build_method_selection_policy(
            {
                "harmony": assessment("met", "conditional", "moderate"),
                "celltypist": assessment("met", "strong", "low"),
                "gptcelltype": assessment("met", "strong", "low"),
            }
        )
        self.assertEqual(policy["version"], SELECTION_POLICY_VERSION)
        self.assertEqual(policy["authorized_candidates"], ["harmony", "celltypist"])
        self.assertEqual(policy["default_candidates"], ["harmony"])
        self.assertEqual(policy["selection_basis"], "matched_reference_supervised_priority")

    def test_celltypist_is_used_when_harmony_is_unsuitable(self):
        """CellTypist is the automatic fallback after unsuitable Harmony."""
        policy = build_method_selection_policy(
            {
                "harmony": assessment("met", "adverse", "high"),
                "celltypist": assessment("met", "conditional", "moderate"),
                "gptcelltype": assessment("met", "strong", "low"),
            }
        )
        self.assertEqual(policy["authorized_candidates"], ["celltypist"])
        self.assertEqual(policy["selection_basis"], "pretrained_supervised_fallback")

    def test_default_policy_abstains_instead_of_selecting_gptcelltype(self):
        """Automatic policy never promotes marker-only GPTCellType."""
        policy = build_method_selection_policy(
            {
                "harmony": assessment("not_met", "adverse", "high"),
                "celltypist": assessment("not_met", "adverse", "high"),
                "gptcelltype": assessment("met", "strong", "low"),
            }
        )
        self.assertEqual(policy["status"], "abstain_required")
        self.assertTrue(policy["abstain_required"])
        self.assertEqual(policy["authorized_candidates"], [])

    def test_explicit_legacy_request_can_authorize_gptcelltype_last(self):
        """An explicit request retains the gated legacy escape hatch."""
        policy = build_method_selection_policy(
            {
                "harmony": assessment("not_met", "adverse", "high"),
                "celltypist": assessment("not_met", "adverse", "high"),
                "gptcelltype": assessment("met", "strong", "moderate"),
            },
            allow_gptcelltype_fallback=True,
        )
        self.assertEqual(policy["authorized_candidates"], ["gptcelltype"])
        self.assertEqual(policy["selection_basis"], "explicit_legacy_gptcelltype_request")

    def test_contract_authorizes_only_policy_candidates(self):
        """The execution contract preserves an empty abstention boundary."""
        with tempfile.TemporaryDirectory() as directory:
            query = Path(directory) / "query.h5ad"
            query.write_bytes(b"selection-contract-test")
            assessments = {
                "harmony": assessment("not_met", "adverse", "high"),
                "celltypist": assessment("not_met", "adverse", "high"),
                "gptcelltype": assessment("met", "strong", "low"),
            }
            policy = build_method_selection_policy(assessments)
            contract = register_selection_contract(
                query_path=query,
                reference_path=None,
                reference_cell_type_column="cell_type",
                context={"species": "human"},
                method_assessments=assessments,
                selection_policy=policy,
                celltypist={
                    "models": [],
                    "candidate_model_preflights": {},
                    "majority_voting_recommendation": {"recommended": False},
                },
            )
        self.assertEqual(contract["allowed_candidates"], [])

    def test_priority_validator_requires_harmony_to_be_unsuitable(self):
        """CellTypist cannot bypass a suitable authorized Harmony candidate."""
        blocked = _primary_priority_violations(
            "celltypist",
            ["harmony", "celltypist"],
            {"harmony": "moderate", "celltypist": "high", "gptcelltype": "low"},
        )
        allowed = _primary_priority_violations(
            "celltypist",
            ["harmony", "celltypist"],
            {"harmony": "low", "celltypist": "moderate", "gptcelltype": "low"},
        )
        self.assertTrue(blocked)
        self.assertEqual(allowed, [])

    def test_legacy_request_requires_unambiguous_primary_language(self):
        """A discussion of GPTCellType must not activate the legacy backend."""
        enabled = _cell_annotation_context_from_user_request(
            "Use GPTCellType as the primary backend for this annotation."
        )
        disabled = _cell_annotation_context_from_user_request(
            "GPTCellType can be ignored because the review stage is enabled."
        )
        self.assertTrue(enabled["allow_gptcelltype_fallback"])
        self.assertNotIn("allow_gptcelltype_fallback", disabled)

    def test_manager_does_not_reimpose_exact_stage_matching(self):
        """Manager verification must defer approximate-age suitability to the skill."""
        prompt = (
            Path(__file__).resolve().parents[1]
            / "src/agents/manager_agent/prompt.txt"
        ).read_text(encoding="utf-8")

        self.assertIn("literal metadata-string or exact-age", prompt)
        self.assertIn("reported compatible subset is acceptable", prompt)
        self.assertIn("only when the skill reports the reference as", prompt)

if __name__ == "__main__":
    unittest.main()
