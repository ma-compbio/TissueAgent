"""Smoke tests for ``server.plan_store`` covering Milestone 2 additions.

Run from the repo root::

    cd src && python ../tests/test_plan_store.py

These are deliberately self-contained — no pytest dependency — so the
tests can be executed before the project commits to a test framework.
"""

import sys
import tempfile
from pathlib import Path


SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from server.plan_store import (  # noqa: E402
    PlanStore,
    PlanDocument,
    PlanStep,
    PlanProvenance,
    PlanEditError,
    _parse_markdown,
)


def test_round_trip_idempotent() -> None:
    """Write -> read -> write yields identical markdown."""
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(plan_dir=Path(tmp))
        doc = PlanDocument(
            status="draft",
            user_request="Annotate cells",
            steps=[
                PlanStep(id=1, title="Locate reference",
                         description="Find h5ad", reasoning="Atlas needed",
                         expected_artifacts=["ref.h5ad"]),
                PlanStep(id=2, title="Run transfer",
                         description="Harmony", reasoning="Label transfer",
                         expected_artifacts=["out.h5ad"]),
            ],
        )
        md1 = store.write(doc)
        doc2 = store.read()
        md2 = store.write(doc2)
        assert md1 == md2, "round-trip not idempotent"
        print("OK: round_trip_idempotent")


def test_user_edit_rename_and_reorder() -> None:
    """User can rename a title; metadata is stamped to "user"."""
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(plan_dir=Path(tmp))
        store.write(PlanDocument(
            status="awaiting_plan_review",
            user_request="x",
            steps=[
                PlanStep(id=1, title="Original A", description="a"),
                PlanStep(id=2, title="Original B", description="b"),
            ],
        ))

        edited = """# Plan

```yaml
status: awaiting_plan_review
user_request: x
```

## Step 1 — Renamed A

```yaml
status: pending
assigned_agent: null
assigned_rationale: null
expected_artifacts: []
actual_outputs: []
```

**Description:** updated description

**Reasoning:** updated reasoning
"""
        doc = store.apply_user_edit(edited)
        assert len(doc.steps) == 1
        assert doc.steps[0].title == "Renamed A"
        assert doc.steps[0].description == "updated description"
        assert doc.last_edited_by == "user"
        assert doc.last_edited_at is not None
        on_disk = _parse_markdown(store.read_markdown())
        assert on_disk.last_edited_by == "user"
        print("OK: user_edit_rename_and_reorder")


def test_malformed_user_edit_rejected_and_does_not_corrupt() -> None:
    """Empty / step-less markdown is rejected; existing file is untouched."""
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(plan_dir=Path(tmp))
        original = PlanDocument(
            status="draft", user_request="keep me",
            steps=[PlanStep(id=1, title="Stay", description="d")],
        )
        store.write(original)
        before = store.read_markdown()

        for bad in ["", "   ", "no steps here, just prose"]:
            try:
                store.apply_user_edit(bad)
            except PlanEditError:
                pass
            else:
                raise AssertionError(f"expected PlanEditError for {bad!r}")

        after = store.read_markdown()
        assert before == after, "file was corrupted by a rejected edit"
        print("OK: malformed_user_edit_rejected_and_does_not_corrupt")


def test_new_metadata_round_trips() -> None:
    """last_edited_by / last_edited_at survive write -> read."""
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(plan_dir=Path(tmp))
        doc = PlanDocument(
            status="recruited", user_request="r",
            steps=[PlanStep(id=1, title="T", description="d")],
            last_edited_by="recruiter",
            last_edited_at="2026-05-23T15:00:00+00:00",
        )
        store.write(doc)
        loaded = store.read()
        assert loaded.last_edited_by == "recruiter"
        assert loaded.last_edited_at == "2026-05-23T15:00:00+00:00"
        print("OK: new_metadata_round_trips")


def test_old_plan_without_metadata_loads_clean() -> None:
    """Plans written before this milestone have no last_edited_* fields."""
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(plan_dir=Path(tmp))
        legacy = """# Plan

```yaml
status: draft
user_request: legacy
```

## Step 1 — old

```yaml
status: pending
assigned_agent: null
assigned_rationale: null
expected_artifacts: []
actual_outputs: []
```

**Description:** d
"""
        store.path.write_text(legacy)
        doc = store.read()
        assert doc.last_edited_by is None
        assert doc.last_edited_at is None
        assert doc.steps[0].title == "old"
        print("OK: old_plan_without_metadata_loads_clean")


def test_provenance_round_trip() -> None:
    """New-style provenance (template_names + decision) survives write -> read."""
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(plan_dir=Path(tmp))
        doc = PlanDocument(
            status="draft",
            user_request="Test provenance",
            steps=[PlanStep(id=1, title="Step", description="d")],
            provenance=PlanProvenance(
                template_names=["lr_analysis", "spatial_scatter"],
                decision="ADAPT",
            ),
        )
        store.write(doc)
        loaded = store.read()
        assert loaded.provenance is not None
        assert loaded.provenance.template_names == ["lr_analysis", "spatial_scatter"]
        assert loaded.provenance.decision == "ADAPT"
        print("OK: provenance_round_trip")


def test_denovo_provenance_round_trip() -> None:
    """Denovo provenance (empty template_names) survives write -> read."""
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(plan_dir=Path(tmp))
        doc = PlanDocument(
            status="draft",
            user_request="r",
            steps=[PlanStep(id=1, title="T", description="d")],
            provenance=PlanProvenance(template_names=[], decision=None),
        )
        store.write(doc)
        loaded = store.read()
        # Empty provenance should not serialize any provenance block
        assert loaded.provenance is None or loaded.provenance.template_names == []
        print("OK: denovo_provenance_round_trip")


if __name__ == "__main__":
    test_round_trip_idempotent()
    test_user_edit_rename_and_reorder()
    test_malformed_user_edit_rejected_and_does_not_corrupt()
    test_new_metadata_round_trips()
    test_old_plan_without_metadata_loads_clean()
    test_provenance_round_trip()
    test_denovo_provenance_round_trip()
    print("\nAll plan_store tests PASS")
