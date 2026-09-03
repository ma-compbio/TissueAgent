"""The optimizer's edit surface is knowledge/*.md only — enforced in code.

A guardrail bug here would let the optimizer edit src/ or the frozen skill
scripts (which also generate the benchmark's reference outputs), so every
rejection path gets its own test.
"""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
REPO = SRC.parent
for _p in (str(SRC), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from optimizer.guardrails import (  # noqa: E402
    MAX_EDIT_CHARS,
    GuardrailError,
    check_edit_size,
    resolve_editable,
    validate_knowledge,
)


@pytest.fixture()
def knowledge_tree(tmp_path):
    skills = tmp_path / "skills"
    plans = tmp_path / "plans"
    skill_dir = skills / "ccc-foo"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "references").mkdir()
    plans.mkdir()

    (skill_dir / "SKILL.md").write_text(
        "---\nname: ccc-foo\ndescription: a skill\napplies_to: [coding_agent]\n---\nBody.\n"
    )
    (skill_dir / "scripts" / "run_foo.py").write_text("print('frozen')\n")
    (skill_dir / "references" / "notes.md").write_text("---\nname: notes\n---\nRef.\n")
    (skills / "flat-skill.md").write_text(
        "---\nname: flat-skill\ndescription: flat\napplies_to: []\n---\nBody.\n"
    )
    (plans / "plan_a.md").write_text(
        "---\nname: plan_a\nstatus: enabled\ndescription: a plan\n---\n## Steps\n"
    )
    return skills, plans


class TestResolveEditable:
    def test_accepts_folder_skill_md(self, knowledge_tree):
        skills, plans = knowledge_tree
        p = resolve_editable(str(skills / "ccc-foo" / "SKILL.md"), roots=(skills, plans))
        assert p.name == "SKILL.md"

    def test_accepts_flat_skill_and_plan(self, knowledge_tree):
        skills, plans = knowledge_tree
        assert resolve_editable(str(skills / "flat-skill.md"), roots=(skills, plans))
        assert resolve_editable(str(plans / "plan_a.md"), roots=(skills, plans))

    def test_rejects_outside_roots(self, knowledge_tree, tmp_path):
        skills, plans = knowledge_tree
        outside = tmp_path / "src_file.md"
        outside.write_text("x")
        with pytest.raises(GuardrailError, match="outside the editable roots"):
            resolve_editable(str(outside), roots=(skills, plans))

    def test_rejects_scripts_even_md(self, knowledge_tree):
        skills, plans = knowledge_tree
        md_in_scripts = skills / "ccc-foo" / "scripts" / "doc.md"
        md_in_scripts.write_text("x")
        with pytest.raises(GuardrailError, match="frozen asset directory"):
            resolve_editable(str(md_in_scripts), roots=(skills, plans))

    def test_rejects_references_dir(self, knowledge_tree):
        skills, plans = knowledge_tree
        with pytest.raises(GuardrailError, match="frozen asset directory"):
            resolve_editable(
                str(skills / "ccc-foo" / "references" / "notes.md"), roots=(skills, plans)
            )

    def test_rejects_non_md(self, knowledge_tree):
        skills, plans = knowledge_tree
        with pytest.raises(GuardrailError, match="not a Markdown file"):
            resolve_editable(str(skills / "ccc-foo" / "scripts" / "run_foo.py"), roots=(skills, plans))

    def test_rejects_traversal(self, knowledge_tree, tmp_path):
        skills, plans = knowledge_tree
        outside = tmp_path / "evil.md"
        outside.write_text("x")
        sneaky = str(skills / "ccc-foo" / ".." / ".." / "evil.md")
        with pytest.raises(GuardrailError, match="outside the editable roots"):
            resolve_editable(sneaky, roots=(skills, plans))

    def test_rejects_symlink_escape(self, knowledge_tree, tmp_path):
        skills, plans = knowledge_tree
        target = tmp_path / "outside_target.md"
        target.write_text("x")
        link = skills / "sneaky.md"
        link.symlink_to(target)
        with pytest.raises(GuardrailError, match="outside the editable roots"):
            resolve_editable(str(link), roots=(skills, plans))

    def test_rejects_missing_file(self, knowledge_tree):
        skills, plans = knowledge_tree
        with pytest.raises(GuardrailError, match="does not exist"):
            resolve_editable(str(plans / "no_such.md"), roots=(skills, plans))


class TestEditSize:
    def test_within_cap_ok(self):
        check_edit_size("a" * 100, "b" * 100)

    def test_over_cap_rejected(self):
        with pytest.raises(GuardrailError, match="cap"):
            check_edit_size("a" * MAX_EDIT_CHARS, "b")


class TestValidateKnowledge:
    def test_clean_tree_passes(self, knowledge_tree):
        skills, plans = knowledge_tree
        assert validate_knowledge(skills_dir=skills, plans_dir=plans) == []

    def test_broken_frontmatter_flagged(self, knowledge_tree):
        skills, plans = knowledge_tree
        (plans / "plan_a.md").write_text("name: plan_a\nno frontmatter fences here\n")
        errors = validate_knowledge(skills_dir=skills, plans_dir=plans)
        assert any("plan_a.md" in e and "frontmatter" in e for e in errors)

    def test_invalid_yaml_flagged(self, knowledge_tree):
        skills, plans = knowledge_tree
        (skills / "flat-skill.md").write_text("---\nname: [unclosed\n---\nBody.\n")
        errors = validate_knowledge(skills_dir=skills, plans_dir=plans)
        assert any("flat-skill.md" in e for e in errors)

    def test_duplicate_enabled_plan_names_flagged(self, knowledge_tree):
        skills, plans = knowledge_tree
        (plans / "plan_b.md").write_text(
            "---\nname: plan_a\nstatus: enabled\ndescription: dup\n---\n"
        )
        errors = validate_knowledge(skills_dir=skills, plans_dir=plans)
        assert any("plan_a" in e and "multiple files" in e for e in errors)

    def test_disabled_duplicate_is_fine(self, knowledge_tree):
        skills, plans = knowledge_tree
        (plans / "plan_b.md").write_text(
            "---\nname: plan_a\nstatus: disabled\ndescription: dup\n---\n"
        )
        assert validate_knowledge(skills_dir=skills, plans_dir=plans) == []

    def test_real_repo_knowledge_is_clean(self):
        # The actual registry must validate — otherwise every optimizer edit
        # would be rejected by pre-existing noise.
        assert validate_knowledge() == []
