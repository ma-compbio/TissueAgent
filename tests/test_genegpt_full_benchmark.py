"""Regression tests for the full paired GeneGPT benchmark harness."""

from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "benchmark"))

import run_genegpt_full_benchmark as full  # noqa: E402
import run_genegpt_paired_pilot as pilot  # noqa: E402


def test_full_corpus_counts() -> None:
    """The full corpus includes every GeneTuring and GeneHop question."""
    records = full._load_questions()

    assert len(records) == 600
    assert sum(record["scoreable"] for record in records) == 500
    assert Counter(record["suite"] for record in records) == {
        "GeneTuring": 450,
        "GeneHop": 150,
    }
    assert set(Counter(record["task"] for record in records).values()) == {50}


def test_geneturing_only_counts() -> None:
    """The GeneTuring-only selection contains nine fully scoreable tasks."""
    records = full._load_questions("GeneTuring")

    assert len(records) == 450
    assert all(record["scoreable"] for record in records)
    assert Counter(record["suite"] for record in records) == {"GeneTuring": 450}
    assert set(Counter(record["task"] for record in records).values()) == {50}


def test_completed_pilot_pairs_seed_full_run() -> None:
    """Matching pilot pairs are reused without changing their scored summary."""
    records = copy.deepcopy(full._load_questions())

    seeded = full._seed_pilot(records, full._PILOT_RECORDS)
    summary = full._summarize(records)

    assert seeded == 10
    assert summary["n_paired"] == 10
    assert summary["n_scoreable_paired"] == 10
    assert summary["direct_accuracy"] == 0.65
    assert summary["tissueagent_accuracy"] == 0.85
    assert summary["normalised_answer_agreement"] == 0.8


def test_tissueagent_timeout_is_retryable(tmp_path: Path, monkeypatch) -> None:
    """A timed-out child is recorded as an error instead of stopping the batch."""
    (tmp_path / "logs").mkdir()

    def raise_timeout(*args, **kwargs):
        raise pilot.subprocess.TimeoutExpired(args[0], timeout=1)

    monkeypatch.setattr(pilot.subprocess, "run", raise_timeout)

    result = pilot._run_tissueagent(1, "test question", tmp_path, timeout=1)

    assert result["status"] == "error"
    assert result["error_type"] == "TimeoutExpired"
    assert (tmp_path / "logs/01_tissueagent.stdout").is_file()
    assert (tmp_path / "logs/01_tissueagent.stderr").is_file()
